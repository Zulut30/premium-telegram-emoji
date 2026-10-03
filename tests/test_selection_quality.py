"""Regressions use real IDs and independently asserted states, not score snapshots."""
import copy
import json
import unittest
from pathlib import Path

from emoji_selection import concepts, palette, search, validate_profile
from generate_site import catalog_data, parse_catalog

CASES = json.loads(Path(__file__).with_name('selection_cases.json').read_text(encoding='utf-8'))


def assert_case(test, data, case, search_function=search):
    result = search_function(data, limit=12, **{key: value for key, value in case.items() if key != 'expect'})
    expected = case['expect']
    candidates = result['candidates']
    source = {item['id']: item for item in data['items']}
    ids = [item['id'] for item in candidates]
    if expected.get('empty'):
        test.assertEqual(result['count'], 0)
    else:
        test.assertGreater(result['count'], 0)
    if 'decision' in expected:
        test.assertEqual(result.get('decision'), expected['decision'])
    if 'top' in expected:
        test.assertEqual(ids[0], expected['top'])
    for eid in expected.get('includes', []):
        test.assertIn(eid, ids)
    for eid in expected.get('excludes', []):
        test.assertNotIn(eid, ids)
    if 'primary' in expected:
        test.assertEqual(result['query']['intents'], expected['primary'])
    if 'context' in expected:
        test.assertEqual(result['query'].get('context_intents'), expected['context'])
    for candidate in candidates:
        item = source[candidate['id']]
        for feature in expected.get('features', []):
            test.assertIn(feature, item['features'])
        for feature in expected.get('without_features', []):
            test.assertNotIn(feature, item['features'])
        for field, key in [('style', 'style_family'), ('animation', 'animated'), ('color', 'color_mode'), ('repainting', 'repainting')]:
            if field in expected:
                test.assertEqual(item[key], expected[field])
        if 'excluded_style' in expected:
            test.assertNotEqual(item['style_family'], expected['excluded_style'])
        if 'recommended' in expected:
            test.assertIs(candidate.get('recommended'), expected['recommended'])


class SelectionQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = catalog_data(parse_catalog(), {})

    def test_real_requests_and_opposite_states(self):
        for case in CASES:
            with self.subTest(query=case['query']):
                assert_case(self, self.data, case)

    def test_english_aliases_are_words_not_brand_prefixes(self):
        for word in ['copyright', 'LinkedIn', 'bookmark', 'homebrew', 'office', 'checkout', 'updated']:
            with self.subTest(word=word):
                found = concepts(word)
                self.assertFalse(set(found) & {'copy', 'link', 'education', 'home', 'success', 'calendar'})
        for word, role in [('reminders', 'notification'), ('information', 'info'), ('deletion', 'delete'), ('checkmark', 'success')]:
            self.assertIn(role, concepts(word))

    def test_pack_provenance_and_broad_categories_cannot_fill_a_role(self):
        result = search(self.data, 'образование', pack='Education2026', limit=100)
        weak = next(item for item in result['candidates'] if item['match'] == 'category_only')
        self.assertFalse(weak['recommended'])
        limited = copy.deepcopy(self.data)
        limited['items'] = [item for item in limited['items'] if item['id'] == weak['id']]
        self.assertEqual(search(limited, 'образование')['decision'], 'needs_review')
        profile = palette(limited, ['education'], style='illustrated', pack='Education2026')
        self.assertEqual(profile['missing_roles'], ['education'])
        self.assertFalse(profile['profile']['roles'])

    def test_saved_constraints_reuse_ids_and_reject_incompatible_changes(self):
        constraints = {'animation': 'static', 'color': 'monochrome', 'repainting': 'required'}
        before = palette(self.data, ['notification'], style='outline', pack='ref_x3_collab', constraints=constraints)
        profile = before['profile']
        self.assertFalse(before['missing_roles'])
        self.assertEqual(profile['constraints'], constraints)
        after = palette(self.data, ['notification', 'calendar'], profile=profile)
        self.assertEqual(after['profile']['roles']['notification'], profile['roles']['notification'])
        self.assertEqual(after['profile']['constraints'], constraints)
        self.assertFalse(validate_profile(self.data, after['profile']))
        snapshot = copy.deepcopy(profile)
        with self.assertRaisesRegex(ValueError, 'conflict'):
            palette(self.data, ['notification'], profile=profile, constraints={'animation': 'animated'})
        self.assertEqual(profile, snapshot)
        unknown = palette(self.data, ['notification'], style='minimal', pack='Minimalist B&W Icons')['profile']
        with self.assertRaisesRegex(ValueError, 'violates'):
            palette(self.data, ['search'], profile=unknown, constraints={'animation': 'static'})

    def test_only_declared_secondary_pack_can_supply_a_missing_role(self):
        primary = palette(self.data, ['notification'], style='minimal', pack='Minimalist B&W Icons')['profile']
        missing = palette(self.data, ['calendar'], profile=primary)
        self.assertEqual(missing['missing_roles'], ['calendar'])
        approved = {**primary, 'secondary_packs': ['sfsymbols']}
        added = palette(self.data, ['calendar'], profile=approved)
        self.assertFalse(added['missing_roles'])
        self.assertEqual(added['profile']['roles']['calendar']['pack'], 'sfsymbols')
        self.assertEqual(added['profile']['roles']['notification'], primary['roles']['notification'])
        self.assertFalse(validate_profile(self.data, added['profile']))

    def test_inspection_does_not_promote_fragments_to_recommendations(self):
        result = search(self.data, '5296556942192317930', include_special=True)
        self.assertEqual(result['count'], 1)
        self.assertFalse(result['candidates'][0]['recommended'])


if __name__ == '__main__':
    unittest.main()
