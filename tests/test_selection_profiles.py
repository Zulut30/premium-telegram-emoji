"""A project can reuse reviewed IDs for named roles and distinct icon states."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from emoji_selection import palette, search, validate_profile
from generate_site import catalog_data, parse_catalog

ROOT = Path(__file__).resolve().parents[1]
STATE_QUERIES = {'notifications_on': 'включить уведомления', 'notifications_muted': 'колокольчик без звука',
                 'access_open': 'открытый замок', 'access_locked': 'закрытый замок'}
STATE_IDS = {'notifications_on': '6021536113108196448', 'notifications_muted': '6021440013214948027',
             'access_open': '6019251723082668416', 'access_locked': '6019568309417023812'}


class ProjectProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = catalog_data(parse_catalog(), {})

    def states(self):
        return palette(self.data, list(STATE_QUERIES), style='minimal', pack='sfsymbols',
                       constraints={'color': 'monochrome'}, role_queries=STATE_QUERIES)['profile']

    def test_distinct_states_keep_their_queries_ids_and_primary_pack(self):
        profile = self.states()
        self.assertFalse(validate_profile(self.data, profile))
        for role, eid in STATE_IDS.items():
            self.assertEqual(profile['roles'][role]['id'], eid)
            self.assertEqual(profile['roles'][role]['query'], STATE_QUERIES[role])
            self.assertEqual(profile['roles'][role]['pack'], 'sfsymbols')
        expanded = palette(self.data, [*STATE_QUERIES, 'search'], profile=profile)
        self.assertFalse(expanded['missing_roles'])
        for role, saved in profile['roles'].items():
            self.assertEqual(expanded['profile']['roles'][role], saved)
        self.assertFalse(validate_profile(self.data, expanded['profile']))

    def test_swapping_normal_and_muted_ids_fails_state_validation(self):
        profile = self.states()
        normal = copy.deepcopy(profile['roles']['notifications_on'])
        profile['roles']['notifications_muted'] = {**normal, 'query': STATE_QUERIES['notifications_muted']}
        self.assertTrue(any('state' in error for error in validate_profile(self.data, profile)))

    def test_manual_binding_reuses_a_reviewed_option_instead_of_top_rank(self):
        reviewed = '6025951481222403788'  # Edit symbol in a circle, not the top plain pencil.
        default = search(self.data, 'edit', pack='sfsymbols')['candidates'][0]['id']
        self.assertNotEqual(default, reviewed)
        before = palette(self.data, ['editor_button'], role_queries={'editor_button': 'edit'},
                         bindings={'editor_button': reviewed})['profile']
        self.assertEqual(before['primary_pack'], 'sfsymbols')
        self.assertEqual(before['roles']['editor_button']['id'], reviewed)
        changed = copy.deepcopy(self.data)
        for item in changed['items']:
            item['order'] = -item['order']
        after = palette(changed, ['editor_button', 'search'], profile=before)
        self.assertEqual(after['profile']['roles']['editor_button'], before['roles']['editor_button'])
        lookup = search(changed, 'edit', profile=before, limit=1)
        self.assertEqual(lookup['candidates'][0]['id'], reviewed)
        self.assertEqual(lookup['candidates'][0]['saved_roles'], ['editor_button'])

    def test_profile_search_inherits_constraints_and_never_leaks_other_packs(self):
        profile = self.states()
        for query, eid, role in [('уведомления', STATE_IDS['notifications_on'], 'notifications_on'),
                                 ('отключить уведомления', STATE_IDS['notifications_muted'], 'notifications_muted')]:
            result = search(self.data, query, profile=profile)
            self.assertEqual(result['candidates'][0]['id'], eid)
            self.assertEqual(result['candidates'][0]['saved_roles'], [role])
            self.assertTrue(all(item['pack'] == 'sfsymbols' and item['color_mode'] == 'monochrome' for item in result['candidates']))
        self.assertEqual(search(self.data, 'неоновое сердце', profile=profile)['decision'], 'needs_clarification')
        with self.assertRaisesRegex(ValueError, 'style conflicts'):
            search(self.data, 'сердце', profile=profile, style='neon')
        with self.assertRaisesRegex(ValueError, 'not allowed'):
            search(self.data, 'уведомления', profile=profile, pack='CuteEmoji')
        with self.assertRaisesRegex(ValueError, 'constraints conflict'):
            search(self.data, 'уведомления', profile=profile, constraints={'color': 'color'})

    def test_reviewed_secondary_binding_is_reused_before_a_new_primary_candidate(self):
        profile = palette(self.data, ['notification'], style='minimal', pack='Minimalist B&W Icons')['profile']
        profile['secondary_packs'] = ['sfsymbols']
        expanded = palette(self.data, ['editor_button'], profile=profile,
                           role_queries={'editor_button': 'редактирование'}, bindings={'editor_button': '6025951481222403788'})
        self.assertEqual(expanded['profile']['primary_pack'], 'Minimalist B&W Icons')
        self.assertEqual(search(self.data, 'редактирование', profile=expanded['profile'])['candidates'][0]['id'], '6025951481222403788')
        self.assertFalse(validate_profile(self.data, expanded['profile']))

    def test_invalid_bindings_and_ambiguous_role_definitions_are_not_saved(self):
        for bindings, roles, queries in [({'edit': '9999999999999999999'}, ['edit'], {}),
                                       ({'edit': STATE_IDS['notifications_muted']}, ['edit'], {}),
                                       ({'notifications_on': STATE_IDS['notifications_muted']}, ['notifications_on'],
                                        {'notifications_on': STATE_QUERIES['notifications_on']})]:
            with self.subTest(bindings=bindings), self.assertRaises(ValueError):
                palette(self.data, roles, style='minimal', pack='sfsymbols', bindings=bindings, role_queries=queries)
        missing = palette(self.data, ['combined'], style='minimal', pack='sfsymbols', role_queries={'combined': 'настройки и уведомления'})
        self.assertEqual(missing['missing_roles'], ['combined'])
        self.assertEqual(missing['unresolved_roles']['combined']['decision'], 'needs_clarification')
        self.assertFalse(missing['profile']['roles'])

    def test_existing_state_definition_and_id_cannot_change_silently(self):
        profile = self.states()
        before = copy.deepcopy(profile)
        for kwargs in [{'bindings': {'notifications_muted': STATE_IDS['notifications_on']}},
                       {'role_queries': {'notifications_muted': 'включить уведомления'}}]:
            with self.assertRaisesRegex(ValueError, 'conflicts'):
                palette(self.data, ['notifications_muted'], profile=profile, **kwargs)
            self.assertEqual(profile, before)

    def test_cli_persists_queries_and_rejects_changes_without_touching_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'emoji-style.json'
            def cli(*args):
                return subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'tools/select_emoji.py'), *args],
                                      cwd=folder, capture_output=True, text=True, encoding='utf-8')
            first = cli('palette', '--roles', 'notifications_on', 'notifications_muted', '--pack', 'sfsymbols',
                        '--role-query', 'notifications_on=включить уведомления', '--role-query', 'notifications_muted=колокольчик без звука',
                        '--bind', 'notifications_muted=' + STATE_IDS['notifications_muted'], '--profile', str(path), '--save')
            self.assertEqual(first.returncode, 0, first.stderr)
            original = path.read_bytes()
            lookup = cli('search', 'отключить уведомления', '--profile', str(path), '--limit', '1')
            self.assertEqual(lookup.returncode, 0, lookup.stderr)
            self.assertEqual(json.loads(lookup.stdout)['candidates'][0]['id'], STATE_IDS['notifications_muted'])
            self.assertEqual(path.read_bytes(), original)
            rejected = cli('palette', '--roles', 'notifications_muted', '--bind', 'notifications_muted=' + STATE_IDS['notifications_on'],
                           '--profile', str(path), '--save')
            self.assertEqual(rejected.returncode, 2)
            self.assertEqual(path.read_bytes(), original)
            checked = cli('validate', str(path))
            self.assertEqual(checked.returncode, 0, checked.stderr)


if __name__ == '__main__':
    unittest.main()
