import json
import re
import unittest

from generate_site import build_html, catalog_data


ID = "5456140674028019486"


def section(number, name="News", **overrides):
    emoji = {"emoji_id": ID, "description": "Срочная новость", "key": "breaking", "fallback": "🚨"}
    emoji.update(overrides)
    return {"title": f"Section {number} — {name}", "pack_url": "https://t.me/addemoji/NewsEmoji", "emojis": [emoji]}


class SiteDataTests(unittest.TestCase):
    def test_duplicate_ids_keep_memberships_and_search_aliases(self):
        data = catalog_data([section(1), section(2, "Other", key="alternate", description="Другое название")], {})
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertEqual(item["id"], ID)
        self.assertIsInstance(item["id"], str)
        self.assertEqual(item["sections"], ["1", "2"])
        self.assertIn("другое название", item["search"])
        self.assertIn("alternate", item["search"])
        self.assertEqual(item["aliases"], [{"name": "Другое название", "key": "alternate"}])
        self.assertEqual(data["source_count"], 2)

    def test_embedded_json_cannot_close_script_and_preserves_original_text(self):
        payload = '</script><script>alert("catalog")</script> & &#124;'
        result = build_html([section(1, description=payload, notes=[payload])], {ID: f"images/{ID}.png"})
        embedded = re.search(r'<script type="application/json" id="catalog-data">(.*?)</script>', result, re.S)[1]
        self.assertNotIn("<", embedded)
        item = json.loads(embedded)["items"][0]
        self.assertEqual(item["name"], payload.replace("&#124;", "|"))
        self.assertEqual(item["notes"], [payload])
        self.assertEqual(item["id"], ID)

    def test_portable_paths_and_executable_url_rejection(self):
        sample = section(1, pack_url="javascript:alert(1)")
        item = catalog_data([sample], {ID: f"images\\{ID}.png"})["items"][0]
        self.assertEqual(item["image"], f"images/{ID}.png")
        self.assertEqual(item["url"], "")
        for invalid_path in ["images/../secret", 'images/x" onerror="alert(1)', "https://example.com/emoji.png"]:
            with self.subTest(path=invalid_path):
                self.assertEqual(catalog_data([sample], {ID: invalid_path})["items"][0]["image"], "icons/bolt.svg")


if __name__ == "__main__":
    unittest.main()
