"""Pure catalog loading for the site and portable skill; no environment or network access."""
from __future__ import annotations

import json
import re
import urllib.parse
from html import unescape as decode_html
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG_FILE = ROOT / 'references' / 'emoji-catalog.md'
METADATA_FILE = ROOT / 'data' / 'emoji-packs.json'
COMPOSITIONS_FILE = ROOT / 'data' / 'emoji-compositions.json'


def parse_catalog(catalog_file: Path = CATALOG_FILE, metadata_file: Path = METADATA_FILE) -> list[dict]:
    text = catalog_file.read_text(encoding="utf-8")
    reviewed = {}
    if metadata_file.exists():
        data = json.loads(metadata_file.read_text(encoding="utf-8"))
        reviewed = {
            item["emoji_id"]: {**item, "pack_name": pack["name"], "pack_url": pack["url"], "pack_style": pack.get("style", "")}
            for pack in data["packs"]
            for item in pack["items"]
        }
    sections: list[dict] = []
    current: dict | None = None

    for line in text.splitlines():
        m = re.match(r"^## (Section \d+ — .+)$", line)
        if m:
            current = {"title": m.group(1), "emojis": []}
            sections.append(current)
            continue

        if current and line.startswith("Pack: "):
            current["pack_url"] = line.removeprefix("Pack: ").strip()
            continue

        if (
            current
            and line.startswith("|")
            and not re.match(r"^\|\s*key(?: suggestion)?\s*\|", line)
            and not re.match(r"^\|[-| ]+$", line)
        ):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 4 and parts[1].isdigit():
                emoji = {
                    "key":         parts[0],
                    "emoji_id":    parts[1],
                    "description": parts[2],
                    "fallback":    parts[3],
                }
                metadata = reviewed.get(parts[1], {})
                for key in ["category", "subcategory", "tags", "pack_name", "pack_url", "monochrome", "needs_review", "notes", "original_fallback", "needs_repainting", "availability", "text", "composition_keys", "pack_style", "is_animated", "is_video", "role"]:
                    if key in metadata:
                        emoji[key] = metadata[key]
                current["emojis"].append(emoji)

    return sections


def safe_pack_url(value: str) -> str:
    parsed = urllib.parse.urlparse(str(value))
    return str(value) if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def catalog_data(sections: list[dict], thumbnails: dict[str, str], compositions_file: Path = COMPOSITIONS_FILE) -> dict:
    """Keep IDs as strings and combine repeated IDs without losing search aliases."""
    items: dict[str, dict] = {}
    groups = []
    for index, section in enumerate(sections, 1):
        match = re.search(r"Section (\d+)", section["title"])
        section_id = match.group(1) if match else str(index)
        title = section["title"].split(" — ", 1)[-1]
        name = {
            "Animated News Emoji": "Новости",
            "Static App Icons": "Приложения · статичные",
            "Animated App Icons": "Приложения · анимированные",
            "Minimalist B&W Icons": "Минимализм",
        }.get(title, title)
        member_ids = set()
        for emoji in section["emojis"]:
            eid = str(emoji["emoji_id"])
            member_ids.add(eid)
            description = decode_html(emoji["description"])
            key = decode_html(emoji["key"])
            pack = emoji.get("pack_name") or title
            search_parts = [description, key, eid, pack, name, title,
                            emoji.get("category", ""), emoji.get("subcategory", ""),
                            emoji.get("text", ""), *emoji.get("tags", [])]
            if eid in items:
                item = items[eid]
                if section_id not in item["sections"]:
                    item["sections"].append(section_id)
                item["aliases"].append({"name": description, "key": key})
                item["search"] += " " + " ".join(search_parts).lower()
                continue
            image = str(thumbnails.get(eid, "icons/bolt.svg")).replace("\\", "/")
            if emoji.get("availability"):
                image = "icons/bolt.svg"
            if not re.fullmatch(r"(?:images/[0-9]+\.png|icons/bolt\.svg)", image):
                image = "icons/bolt.svg"
            items[eid] = {
                "id": eid, "order": len(items), "name": description, "key": key,
                "fallback": decode_html(emoji["fallback"]),
                "original_fallback": emoji.get("original_fallback", ""),
                "pack": pack,
                "url": safe_pack_url(emoji.get("pack_url") or section.get("pack_url", "")),
                "image": image, "sections": [section_id], "aliases": [],
                "category": emoji.get("category", ""),
                "subcategory": emoji.get("subcategory", ""),
                "monochrome": bool(emoji.get("monochrome", False)),
                "color_known": "monochrome" in emoji,
                "needs_review": bool(emoji.get("needs_review", False)),
                "adaptive": bool(emoji.get("needs_repainting", False)),
                "repainting": emoji.get("needs_repainting"),
                "availability": emoji.get("availability", ""),
                "text": emoji.get("text", ""),
                "pack_style": emoji.get("pack_style", ""),
                "animated": emoji.get("is_animated"),
                "video": emoji.get("is_video"),
                "role": emoji.get("role", ""),
                "notes": emoji.get("notes", []),
                "search": " ".join(search_parts).lower(),
            }
        groups.append({"id": section_id, "name": name, "title": title,
                       "count": len(member_ids), "url": safe_pack_url(section.get("pack_url", ""))})
    compositions = []
    if compositions_file.exists():
        for composition in json.loads(compositions_file.read_text(encoding="utf-8"))["compositions"]:
            if all(eid in items for eid in composition["emoji_ids"]):
                compositions.append(composition)
    from emoji_selection import enrich_catalog
    return enrich_catalog({"items": list(items.values()), "sections": groups, "compositions": compositions,
                           "source_count": sum(len(section["emojis"]) for section in sections)})
