"""Portable distribution must work without bot code, packages or a specific cwd."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from tools.skill_package import AGENTS, MANIFEST, NAME, archive, destination, install, read_payload
from emoji_catalog import parse_catalog

ROOT = Path(__file__).resolve().parents[1]


class PortableSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = read_payload()

    def run_cli(self, script, *args, cwd):
        environment = {key: value for key, value in os.environ.items()
                       if key not in {'BOT_TOKEN', 'GITHUB_TOKEN', 'GH_TOKEN', 'PYTHONPATH'}}
        result = subprocess.run([sys.executable, '-I', str(script), *args], cwd=cwd,
                                env=environment, capture_output=True, encoding='utf-8', timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_payload_has_only_skill_resources_and_verified_hashes(self):
        manifest = json.loads(self.payload[MANIFEST])
        source_ids = {item['emoji_id'] for section in parse_catalog() for item in section['emojis']}
        self.assertEqual(manifest['emoji_count'], len(source_ids))
        self.assertEqual(set(manifest['files']), set(self.payload) - {MANIFEST})
        for path, content in self.payload.items():
            self.assertNotIn(path.split('/')[0], {'.env', '.git', '.runtime', '.venv', 'site', 'output'})
            self.assertNotIn(path, {'bot.py', 'config.py', 'generate_site.py', 'requirements.txt'})
            if path != MANIFEST:
                self.assertEqual(hashlib.sha256(content).hexdigest(), manifest['files'][path])

    def test_zip_has_one_named_root_and_reproducible_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = [Path(directory) / name for name in ['first.zip', 'second.zip']]
            archive(self.payload, first)
            archive(self.payload, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as bundle:
                self.assertEqual(set(bundle.namelist()), {f'{NAME}/{path}' for path in self.payload})
                bundle.extractall(Path(directory) / 'extracted')
            self.assertEqual(read_payload(Path(directory) / 'extracted' / NAME), self.payload)

    def test_standalone_zip_installs_and_selects_from_unicode_unrelated_cwd(self):
        with tempfile.TemporaryDirectory(prefix='emoji skill ') as directory:
            root = Path(directory)
            app = root / 'Приложение с пробелами'
            app.mkdir()
            bundle_path = root / 'bundle.zip'
            archive(self.payload, bundle_path)
            with zipfile.ZipFile(bundle_path) as bundle:
                bundle.extractall(root / 'extracted')
            source = root / 'extracted' / NAME
            custom = root / 'Agent Skills с пробелами'
            result = self.run_cli(source / 'install_skill.py', '--agent', 'claude', '--dest', str(custom), cwd=app)
            target = custom / NAME
            self.assertEqual(result['path'], str(target.resolve()))
            self.assertFalse((target / 'config.py').exists())
            script = target / 'scripts/select_emoji.py'
            choices = self.run_cli(script, 'search', 'колокольчик без звука', '--pack', 'sfsymbols', cwd=app)
            self.assertEqual(choices['decision'], 'matched')
            self.assertEqual(choices['candidates'][0]['id'], '6021440013214948027')
            self.assertIn('disabled', choices['candidates'][0]['features'])
            profile = app / 'emoji-style.json'
            selected = self.run_cli(script, 'palette', '--style', 'minimal', '--pack', 'sfsymbols',
                                    '--roles', 'notifications_on', 'notifications_muted',
                                    '--role-query', 'notifications_on=включить уведомления',
                                    '--role-query', 'notifications_muted=колокольчик без звука',
                                    '--profile', str(profile), '--save', cwd=app)
            self.assertNotEqual(selected['profile']['roles']['notifications_on']['id'],
                                selected['profile']['roles']['notifications_muted']['id'])
            self.assertTrue(self.run_cli(script, 'validate', str(profile), cwd=root)['valid'])
            preserved = profile.read_bytes()
            self.run_cli(target / 'install_skill.py', '--dest', str(custom), '--update', cwd=app)
            self.assertEqual(profile.read_bytes(), preserved)
            self.assertTrue(self.run_cli(script, 'validate', str(profile), cwd=root)['valid'])

    def test_agent_user_and_project_destinations_and_environment_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            for agent, (user, project) in AGENTS.items():
                with self.subTest(agent=agent):
                    self.assertEqual(destination(agent, home=home, environ={}), home / user / NAME)
                    self.assertEqual(destination(agent, scope='project', project=home), home / project / NAME)
            self.assertEqual(destination('codex-legacy', home=home, environ={'CODEX_HOME': str(home / 'codex runtime')}),
                             home / 'codex runtime/skills' / NAME)
            self.assertEqual(destination('opencode', home=home, environ={'XDG_CONFIG_HOME': str(home / 'config')}),
                             home / 'config/opencode/skills' / NAME)
            with self.assertRaises(ValueError):
                destination('cursor', scope='project')

    def test_update_preserves_local_files_and_requires_explicit_update(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / NAME
            install(self.payload, target)
            local = {'.env': b'LOCAL_CANARY=private\n', 'emoji-style.json': b'{"application":"kept"}',
                     'notes/personal.md': b'keep this local note'}
            for name, content in local.items():
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            with self.assertRaises(ValueError):
                install(self.payload, target)
            install(self.payload, target, update=True)
            for name, content in local.items():
                self.assertEqual((target / name).read_bytes(), content)

    def test_foreign_folder_and_invalid_package_paths_are_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / NAME
            target.mkdir()
            (target / 'SKILL.md').write_text('---\nname: unrelated-skill\n---\n', encoding='utf-8')
            before = (target / 'SKILL.md').read_bytes()
            with self.assertRaises(ValueError):
                install(self.payload, target, update=True)
            self.assertEqual((target / 'SKILL.md').read_bytes(), before)
            for relative in ['../outside', '/absolute', 'C:/outside', 'tools\\outside', '.']:
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    install({'SKILL.md': b'new', relative: b'invalid'}, Path(directory) / 'fresh')
            self.assertFalse((Path(directory) / 'fresh').exists())

    def test_modified_package_fails_integrity_check(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / NAME
            install(self.payload, target)
            (target / 'emoji_selection.py').write_text('modified', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'integrity'):
                read_payload(target)

    def test_manifest_cannot_add_credentials_or_unrelated_files_to_the_package(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / NAME
            install(self.payload, target)
            manifest = json.loads((target / MANIFEST).read_text(encoding='utf-8'))
            local = b'LOCAL_CANARY=private\n'
            (target / '.env').write_bytes(local)
            manifest['files']['.env'] = hashlib.sha256(local).hexdigest()
            (target / MANIFEST).write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'allowlist'):
                read_payload(target)

    def test_dry_run_writes_nothing_and_project_scope_uses_application(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'Another Project'
            project.mkdir()
            result = self.run_cli(ROOT / 'install_skill.py', '--agent', 'copilot', '--scope', 'project',
                                  '--project', str(project), '--dry-run', cwd=project)
            self.assertEqual(Path(result['path']), project.resolve() / '.github/skills' / NAME)
            self.assertTrue(result['dry_run'])
            self.assertEqual(list(project.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
