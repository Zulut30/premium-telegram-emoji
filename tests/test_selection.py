import copy
import unittest

from emoji_selection import palette, safe_fallback, search, search_compositions, validate_profile
from generate_site import catalog_data, parse_catalog


class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = catalog_data(parse_catalog(), {})

    def test_reminder_synonym_and_natural_request_find_known_bell(self):
        for query in ['значок напоминания', 'какой эмодзи подойдет для кнопки уведомлений', 'notification']:
            with self.subTest(query=query):
                result = search(self.data, query, style='minimal', limit=3)
                self.assertIn('5909201569898827582', [item['id'] for item in result['candidates']])
                self.assertTrue(all(item['style_family'] == 'minimal' for item in result['candidates']))

    def test_pixel_and_neon_queries_preserve_distinct_art_styles(self):
        cases = [('пиксельное сердце', 'pixel', '5226925205812711655'),
                 ('неоновое сердце', 'neon', '5364201435858744869')]
        for query, style, expected in cases:
            with self.subTest(query=query):
                result = search(self.data, query)
                self.assertEqual(result['candidates'][0]['id'], expected)
                self.assertTrue(all(item['style_family'] == style for item in result['candidates']))

    def test_copy_does_not_match_copyright_and_link_does_not_match_linkedin(self):
        for query, bad_name in [('копирование', 'copyright'), ('ссылки', 'linkedin')]:
            result = search(self.data, query, limit=100)
            self.assertGreater(result['count'], 0)
            self.assertFalse(any(bad_name in item['name'].lower() for item in result['candidates']))

    def test_default_selection_excludes_uncertainty_letters_and_fragments(self):
        for query in ['', 'скачать', 'образование', 'emoji']:
            result = search(self.data, query, limit=100)
            self.assertTrue(all(item['selectable'] and item['selection_kind'] == 'emoji' for item in result['candidates']))
        self.assertEqual(search(self.data, '5296556942192317930', pack='nexus_base')['count'], 0)
        self.assertEqual(search(self.data, '5296556942192317930', pack='nexus_base', include_special=True)['count'], 1)
        self.assertEqual(search(self.data, 'qzxnonexistent999')['count'], 0)

    def test_palette_has_one_pack_and_does_not_replace_saved_roles_on_new_ranking(self):
        before = palette(self.data, ['settings', 'search', 'notification', 'success', 'download'])
        profile = before['profile']
        self.assertFalse(before['missing_roles'])
        self.assertEqual({item['pack'] for item in profile['roles'].values()}, {profile['primary_pack']})
        changed = copy.deepcopy(self.data)
        for item in changed['items']:
            item['order'] = -item['order']
        after = palette(changed, ['settings', 'search', 'info', 'calendar'], profile=profile)
        for role, saved in profile['roles'].items():
            self.assertEqual(after['profile']['roles'][role], saved)
        self.assertEqual(after['profile']['primary_pack'], profile['primary_pack'])
        self.assertFalse(validate_profile(changed, after['profile']))
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            palette(self.data, ['search'], style='neon', profile=profile)

    def test_missing_role_is_reported_without_mixing_packs(self):
        result = palette(self.data, ['notification', 'download'], style='pixel', pack='wi_pixelru')
        self.assertEqual(result['missing_roles'], ['notification', 'download'])
        self.assertFalse(result['profile']['roles'])

    def test_validation_rejects_numeric_and_foreign_ids_and_wrong_role(self):
        profile = palette(self.data, ['search'])['profile']
        for invalid in [1234567890123456789, '9999999999999999999']:
            broken = copy.deepcopy(profile)
            broken['roles']['search']['id'] = invalid
            self.assertTrue(validate_profile(self.data, broken))
        broken = copy.deepcopy(profile)
        broken['roles']['notification'] = broken['roles'].pop('search')
        self.assertTrue(validate_profile(self.data, broken))
        broken = copy.deepcopy(profile)
        broken['roles']['search']['id'] = '5364201435858744869'
        self.assertTrue(validate_profile(self.data, broken))

    def test_html_fallback_is_one_emoji_and_cannot_embed_text_or_markup(self):
        for value in ['notify', 'text🔔', '<🔔>', '🔔🔥', 'A', '7']:
            self.assertEqual(safe_fallback(value), '✨')
        for value in ['🔔', '⚙️', '🇷🇺', '1️⃣', '👩‍💻']:
            self.assertEqual(safe_fallback(value), value)
        self.assertEqual(safe_fallback('%'), '💯')

    def test_complete_assemblies_preserve_repetitions_and_reject_wrong_order(self):
        result = search_compositions(self.data, '', pack='nexus_base', limit=100)
        self.assertEqual(result['count'], 14)  # One assembly has an unavailable end piece.
        group = next(item for item in result['compositions'] if len(set(item['emoji_ids'])) < len(item['emoji_ids']))
        self.assertEqual(group['html'].count('<tg-emoji'), len(group['emoji_ids']))
        self.assertNotIn('</tg-emoji> <tg-emoji', group['html'])
        profile = {'schema_version': 1, 'style': 'composite', 'primary_pack': 'nexus_base',
                   'secondary_packs': [], 'roles': {}, 'composition_roles': {'divider': {
                       'key': group['key'], 'emoji_ids': group['emoji_ids']}}}
        self.assertFalse(validate_profile(self.data, profile))
        profile['composition_roles']['divider']['emoji_ids'] = list(dict.fromkeys(group['emoji_ids']))
        self.assertTrue(validate_profile(self.data, profile))


if __name__ == '__main__':
    unittest.main()
