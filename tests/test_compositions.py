import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import generate_site as site


class CompositionTests(unittest.TestCase):
    def test_catalog_keeps_real_key_prefix_row(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / 'catalog.md'
            catalog.write_text('## Section 1 — Test\n| key suggestion | emoji_id | description | fallback |\n|---|---|---|---|\n| key_bw | 6005570495603282482 | Ключ | 🔑 |\n', encoding='utf-8')
            with patch.object(site, 'CATALOG_FILE', catalog), patch.object(site, 'METADATA_FILE', Path(directory) / 'absent.json'):
                result = site.parse_catalog()
            self.assertEqual(result[0]['emojis'][0]['key'], 'key_bw')

    def test_order_and_repeated_ids_survive_site_generation(self):
        ids = ['6005570495603282482', '6005570495603282483']
        section = {'title': 'Section 1 — Chain', 'emojis': [
            {'emoji_id': eid, 'key': f'part_{i}', 'description': f'Часть {i}', 'fallback': '✨'}
            for i, eid in enumerate(ids)]}
        group = {'key': 'chain', 'emoji_ids': [ids[0], ids[0], ids[1]]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'compositions.json'
            path.write_text(json.dumps({'compositions': [group, {'key': 'missing', 'emoji_ids': ['999']}]}), encoding='utf-8')
            with patch.object(site, 'COMPOSITIONS_FILE', path):
                data = site.catalog_data([section], {})
        self.assertEqual(data['compositions'], [group])
        self.assertEqual(data['compositions'][0]['emoji_ids'], [ids[0], ids[0], ids[1]])

    def test_transparent_image_uses_visible_unavailable_indicator(self):
        eid = '6005570495603282482'
        section = {'title': 'Section 1 — Empty', 'emojis': [{'emoji_id': eid, 'key': 'empty', 'description': 'Прозрачный элемент', 'fallback': '✨', 'availability': 'transparent_placeholder', 'needs_review': True, 'needs_repainting': True}]}
        item = site.catalog_data([section], {eid: f'images/{eid}.png'})['items'][0]
        self.assertEqual(item['image'], 'icons/bolt.svg')
        self.assertTrue(item['adaptive'])
        self.assertEqual(item['availability'], 'transparent_placeholder')


if __name__ == '__main__':
    unittest.main()
