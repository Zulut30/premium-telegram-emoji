import asyncio
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bot


CATALOG = '''# Catalog

## Section 1 — News
Pack: https://t.me/addemoji/NewsEmoji

| key suggestion | emoji_id | description | fallback |
|---|---|---|---|
| old | 111 | Old | 🚀 |

Keep this note.

---

## Section 9 — Игры

| key suggestion | emoji_id | description | fallback |
|---|---|---|---|
| game | 222 | Game | 🎮 |
'''
ENTRY = {'emoji_id': '333', 'description': 'Новая | ракета\n<запуск>', 'fallback': '🚀'}


class CatalogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ids = self.root / 'emoji-ids.txt'
        self.catalog = self.root / 'references' / 'emoji-catalog.md'
        self.catalog.parent.mkdir()
        self.catalog.write_text(CATALOG, encoding='utf-8')
        self.ids.write_text('111 - Old\n222 - Game\n', encoding='utf-8')
        self.paths = patch.multiple(bot, REPO_DIR=self.root, ID_FILE=self.ids, CATALOG_FILE=self.catalog)
        self.paths.start()

    def tearDown(self):
        self.paths.stop()
        self.temp.cleanup()

    def test_sections_and_keyboard_include_existing_custom_sections(self):
        self.assertEqual(bot.catalog_sections(), {'1': 'Section 1 — News', '9': 'Section 9 — Игры'})
        callbacks = [button.callback_data for row in bot.section_keyboard().inline_keyboard for button in row]
        self.assertEqual(callbacks, ['sec_1', 'sec_9', 'new_section'])

    def test_append_keeps_rows_in_table_and_preserves_following_note(self):
        bot.append_to_catalog([ENTRY], '1')
        text = self.catalog.read_text(encoding='utf-8')
        row = '| novaya | 333 | Новая &#124; ракета <запуск> | 🚀 |'
        self.assertIn('| old | 111 | Old | 🚀 |\n' + row + '\n\nKeep this note.', text)
        self.assertEqual(text.split('## Section 9')[1], CATALOG.split('## Section 9')[1])
        bot.append_to_id_file([ENTRY])
        self.assertIn('333 - Новая | ракета <запуск>', self.ids.read_text(encoding='utf-8'))

    async def test_new_section_saves_pending_emoji_and_escapes_reply(self):
        message = SimpleNamespace(text='  Новые   значки  ', answer=AsyncMock())
        state = SimpleNamespace(get_data=AsyncMock(return_value={'entries': [ENTRY]}), clear=AsyncMock())
        with patch.object(bot, 'git_commit_and_push', return_value='✅ Saved') as push:
            await bot.handle_section_name(message, state)
        self.assertEqual(bot.catalog_sections()['10'], 'Section 10 — Новые значки')
        section = self.catalog.read_text(encoding='utf-8').split('## Section 10')[1]
        self.assertIn('| novaya | 333 |', section)
        push.assert_called_once_with([ENTRY])
        state.clear.assert_awaited_once()
        self.assertIn('&lt;запуск&gt;', message.answer.call_args.args[0])

    def test_catalog_commit_and_push_to_isolated_local_remote(self):
        remote = self.root / 'remote.git'

        def git(*args):
            return subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)

        git('init', '--bare', str(remote))
        git('init', '-b', 'main')
        git('config', 'user.name', 'Test')
        git('config', 'user.email', 'test@example.invalid')
        git('remote', 'add', 'origin', str(remote))
        git('add', 'emoji-ids.txt', 'references/emoji-catalog.md')
        git('commit', '-m', 'Initial catalog')
        git('push', '-u', 'origin', 'main')
        unrelated = self.root / 'application.txt'
        unrelated.write_text('Unfinished application change', encoding='utf-8')
        git('add', 'application.txt')
        bot.append_to_catalog([ENTRY], '9')
        bot.append_to_id_file([ENTRY])
        with patch.dict(os.environ):
            os.environ.pop('GITHUB_TOKEN', None)
            result = bot.git_commit_and_push([ENTRY])
        self.assertEqual(result, '✅ Запушено в GitHub')
        pushed = git('--git-dir=' + str(remote), 'show', 'main:references/emoji-catalog.md').stdout.decode('utf-8')
        self.assertIn('| novaya | 333 |', pushed)
        self.assertEqual(git('diff', '--name-only', 'HEAD~1', 'HEAD').stdout.decode().splitlines(), ['emoji-ids.txt', 'references/emoji-catalog.md'])
        self.assertEqual(git('diff', '--cached', '--name-only').stdout.decode().splitlines(), ['application.txt'])

    async def test_slow_publication_keeps_event_loop_free_and_preserves_new_request(self):
        started, finish = threading.Event(), threading.Event()
        current = {'request': 'old'}
        async def clear():
            current['request'] = None
        state = SimpleNamespace(clear=AsyncMock(side_effect=clear))
        message = SimpleNamespace(answer=AsyncMock())
        def slow_publish(entries):
            started.set()
            if not finish.wait(5):
                raise AssertionError('Event loop was blocked')
            return '✅ Saved'
        with patch.object(bot, 'git_commit_and_push', side_effect=slow_publish):
            task = asyncio.create_task(bot.save_entries(message, state, [ENTRY], '1'))
            try:
                self.assertTrue(await asyncio.wait_for(asyncio.to_thread(started.wait, 2), timeout=3))
                self.assertFalse(task.done())
                current['request'] = 'new'
            finally:
                finish.set()
                await asyncio.wait_for(task, timeout=3)
        self.assertEqual(current['request'], 'new')
        state.clear.assert_awaited_once()
        self.assertIn('Добавлено', message.answer.call_args.args[0])

    async def test_write_failure_is_reported_without_publication(self):
        message = SimpleNamespace(answer=AsyncMock())
        state = SimpleNamespace(clear=AsyncMock())
        with patch.object(bot, 'save_and_publish', side_effect=OSError('Disk full')), self.assertLogs(level='ERROR'):
            await bot.save_entries(message, state, [ENTRY], '1')
        self.assertIn('Не удалось сохранить', message.answer.call_args.args[0])
        self.assertNotIn('333', self.ids.read_text(encoding='utf-8'))


class StartupAndParsingTests(unittest.TestCase):
    def test_env_is_loaded_before_token_is_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.env').write_text("# local config\nBOT_TOKEN='fake-token'\n", encoding='utf-8-sig')
            env = os.environ.copy()
            env.pop('BOT_TOKEN', None)
            program = ("import config,sys; from pathlib import Path; original=config.load_environment; "
                       "config.load_environment=lambda _: original(Path(sys.argv[1])); "
                       "import bot; assert bot.BOT_TOKEN == 'fake-token'")
            subprocess.run([sys.executable, '-c', program, str(root)], cwd=Path(bot.__file__).parent,
                           env=env, check=True, capture_output=True)

    def test_multiple_emoji_use_utf16_offsets(self):
        message = SimpleNamespace(text='🚀 Ракета\n🎮 Игра', entities=[
            SimpleNamespace(type='custom_emoji', custom_emoji_id='333', offset=0, length=2),
            SimpleNamespace(type='custom_emoji', custom_emoji_id='444', offset=10, length=2),
        ])
        self.assertEqual(bot.parse_emoji_entries(message), [
            {'emoji_id': '333', 'fallback': '🚀', 'description': 'Ракета'},
            {'emoji_id': '444', 'fallback': '🎮', 'description': 'Игра'},
        ])


if __name__ == '__main__':
    unittest.main()
