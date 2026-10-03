import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from premium_emoji import io
from premium_emoji.catalog_store import CatalogStore
from premium_emoji.validation import validate_documents, validate_sources

ROOT = Path(__file__).resolve().parents[1]
CATALOG = '## Section 1 — Test\n| key | emoji_id | description | fallback |\n|---|---|---|---|\n| bell | 111 | Bell | 🔔 |\n'
ENTRY = {'emoji_id': '222', 'description': 'Muted bell', 'fallback': '🔕'}


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.catalog = self.root / 'catalog.md'
        self.ids = self.root / 'ids.txt'
        self.catalog.write_text(CATALOG, encoding='utf-8')
        self.ids.write_text('111 - Bell\n', encoding='utf-8')
        self.store = CatalogStore(self.catalog, self.ids)

    def tearDown(self):
        self.temp.cleanup()

    def test_second_replacement_failure_rolls_back_both_files_and_new_section(self):
        original = {path: path.read_bytes() for path in (self.catalog, self.ids)}
        replace = os.replace
        calls = 0
        def fail_second(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('Simulated disk failure')
            return replace(source, target)
        with patch.object(io.os, 'replace', side_effect=fail_second):
            with self.assertRaises(OSError):
                self.store.save([ENTRY], None, section_name='New section')
        self.assertEqual({path: path.read_bytes() for path in original}, original)
        self.assertEqual(set(self.root.iterdir()), {self.catalog, self.ids})

    def test_staging_failure_does_not_modify_either_file(self):
        before = {path: path.read_bytes() for path in (self.catalog, self.ids)}
        stage = io._stage
        calls = 0
        def fail_third(path, content):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError('Simulated full disk')
            return stage(path, content)
        with patch.object(io, '_stage', side_effect=fail_third), self.assertRaises(OSError):
            self.store.save([ENTRY], '1')
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertEqual(set(self.root.iterdir()), {self.catalog, self.ids})

    def test_rollback_failure_retains_original_for_manual_recovery(self):
        original = self.ids.read_bytes()
        replace = os.replace
        calls = 0
        def fail_write_and_rollback(source, target):
            nonlocal calls
            calls += 1
            if calls > 1:
                raise OSError('Filesystem unavailable')
            return replace(source, target)
        with patch.object(io.os, 'replace', side_effect=fail_write_and_rollback), self.assertRaisesRegex(OSError, 'manual recovery'):
            self.store.save([ENTRY], '1')
        backups = list(self.root.glob('*.tmp'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)

    def test_changed_source_is_preserved_and_stale_write_is_rejected(self):
        original = self.ids.read_bytes()
        self.ids.write_bytes(b'333 - External edit\n')
        with self.assertRaises(ValueError):
            io.replace_files({self.ids: b'222 - Stale edit'}, expected={self.ids: original})
        self.assertEqual(self.ids.read_bytes(), b'333 - External edit\n')
        self.assertFalse(list(self.root.glob('*.tmp')))

    def test_invalid_section_and_numeric_id_never_write(self):
        before = {path: path.read_bytes() for path in (self.catalog, self.ids)}
        for entries, section in [([ENTRY], '404'), ([{**ENTRY, 'emoji_id': 222}], '1')]:
            with self.subTest(section=section), self.assertRaises(ValueError):
                self.store.save(entries, section)
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_json_supports_bom_and_atomic_profile_replacement(self):
        profile = self.root / 'emoji-style.json'
        profile.write_text(json.dumps({'roles': {'bell': '111'}}), encoding='utf-8-sig')
        self.assertEqual(io.read_json(profile)['roles']['bell'], '111')
        io.atomic_write_json(profile, {'roles': {'bell': '222'}, 'name': 'Стиль'})
        self.assertEqual(io.read_json(profile)['roles']['bell'], '222')
        self.assertEqual(set(self.root.iterdir()), {self.catalog, self.ids, profile})


class SourceValidationTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {'packs': [{'name': 'Test', 'count': 1, 'items': [{'emoji_id': '111', 'pack_index': 1}]}]}
        self.groups = {'compositions': [{'key': 'repeat', 'pack_name': 'Test', 'pack_indices': [1, 1], 'emoji_ids': ['111', '111']}]}
        self.policy = {'styles': {'minimal': {'pattern': 'minimal', 'packs': ['Test']}},
                       'intents': {'sound': {'pattern': 'bell'}}, 'features': {}, 'actions': ['sound']}

    def validate(self, **changes):
        return validate_documents(changes.get('catalog', CATALOG), '111 - Bell',
                                  changes.get('metadata', self.metadata), changes.get('compositions', self.groups),
                                  changes.get('policy', self.policy))

    def test_real_sources_and_repeated_composition_members_are_valid(self):
        self.assertEqual(validate_sources(), [])
        self.assertEqual(self.validate(), [])

    def test_catalog_id_divergence_and_duplicate_sections_are_reported(self):
        errors = self.validate(catalog=CATALOG.replace('| 111 |', '| 222 |') + CATALOG)
        self.assertTrue(any('unique numbers' in error for error in errors))
        self.assertTrue(any('missing from emoji-ids.txt' in error for error in errors))

    def test_pack_counts_unknown_ids_and_numeric_ids_are_reported(self):
        for field, value, expected in [('count', 2, 'count'), ('emoji_id', '999', 'unknown'), ('emoji_id', 111, 'numeric string')]:
            metadata = deepcopy(self.metadata)
            if field == 'count':
                metadata['packs'][0][field] = value
            else:
                metadata['packs'][0]['items'][0][field] = value
            with self.subTest(field=field, value=value):
                self.assertTrue(any(expected in error for error in self.validate(metadata=metadata)))

    def test_composition_repetitions_cannot_be_deduplicated(self):
        groups = deepcopy(self.groups)
        groups['compositions'][0]['emoji_ids'] = ['111']
        self.assertTrue(any('exactly' in error for error in self.validate(compositions=groups)))

    def test_invalid_regex_and_unknown_policy_references_are_reported(self):
        policy = deepcopy(self.policy)
        policy['intents']['sound']['pattern'] = '['
        policy['styles']['minimal']['packs'] = ['Unknown']
        policy['actions'] = ['unknown']
        policy['intents']['sound']['query_overrides'] = ['unknown']
        errors = self.validate(policy=policy)
        self.assertTrue(any('invalid regular expression' in error for error in errors))
        self.assertTrue(any('unknown pack' in error for error in errors))
        self.assertTrue(any('unknown action' in error for error in errors))
        self.assertTrue(any('invalid overridden intent' in error for error in errors))


class DependencyBoundaryTests(unittest.TestCase):
    def test_core_does_not_import_adapters_or_bot_configuration(self):
        forbidden = {'aiogram', 'integrations', 'bot', 'config', 'dotenv'}
        for path in (ROOT / 'premium_emoji').glob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                modules = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                           else [node.module or ''] if isinstance(node, ast.ImportFrom) and not node.level else [])
                self.assertFalse(forbidden & {name.split('.')[0] for name in modules}, str(path))
                imported = {name.split('.')[0] for name in modules}
                self.assertFalse(imported - sys.stdlib_module_names - {'premium_emoji'}, str(path))

    def test_offline_import_and_search_need_no_sdk_credentials_or_network(self):
        program = '''import os,sys,urllib.request
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
before = dict(os.environ)
with patch.object(urllib.request, 'urlopen', side_effect=AssertionError('Network used')):
    import generate_site
    from premium_emoji.selection import search
    data = generate_site.catalog_data(generate_site.parse_catalog(), {})
    result = search(data, 'mute notifications', style='minimal', pack='sfsymbols')
    assert result['candidates'][0]['id'] == '6021440013214948027'
assert dict(os.environ) == before
assert not {'config', 'bot', 'aiogram'} & set(sys.modules)
'''
        with tempfile.TemporaryDirectory() as folder:
            subprocess.run([sys.executable, '-I', '-X', 'utf8', '-c', program, str(ROOT)], cwd=folder,
                           check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
