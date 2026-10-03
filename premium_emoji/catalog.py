"""Pure catalog loading for the site and portable skill; no environment or network access."""
from __future__ import annotations

import json
import re
import urllib.parse
from html import unescape as decode_html
from pathlib import Path

from .paths import DEFAULT_PATHS
from .policy import POLICY, SITE_URL
from .query import concepts, matches, extract_games
from .rendering import safe_fallback
import hashlib

ROOT = DEFAULT_PATHS.root
CATALOG_FILE = DEFAULT_PATHS.catalog
METADATA_FILE = DEFAULT_PATHS.metadata
COMPOSITIONS_FILE = DEFAULT_PATHS.compositions


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
    return enrich_catalog({"items": list(items.values()), "sections": groups, "compositions": compositions,
                           "source_count": sum(len(section["emojis"]) for section in sections)})


def enrich_catalog(data: dict) -> dict:
    """Share the same source policy and item evidence with CLI and browser."""
    families = {pack: key for key, rule in POLICY['styles'].items() for pack in rule['packs']}
    for item in data['items']:
        # Pack prefixes describe provenance, not the meaning of every member.
        key_evidence = item['key']
        prefix = item['pack'].lower() + '_'
        if key_evidence.lower().startswith(prefix):
            key_evidence = key_evidence[len(prefix):]
        evidence = ' '.join([item['name'], key_evidence,
                             *[alias['name'] for alias in item.get('aliases', [])]])
        excluded_intents = {key for key, rule in POLICY['intents'].items()
                            if rule.get('source_exclude_pattern') and matches(rule['source_exclude_pattern'], evidence)}
        direct = set(concepts(evidence, source=True))
        direct.update(key for key, rule in POLICY['intents'].items()
                      if rule.get('source_pattern') and matches(rule['source_pattern'], item['name']))
        item['direct_intents'] = [key for key in POLICY['intents'] if key in direct and key not in excluded_intents]
        item['intents'] = list(dict.fromkeys([*item['direct_intents'],
                            *[key for key in concepts(item.get('subcategory', ''), source=True) if key not in excluded_intents]]))
        item['games'] = [key for key, rule in POLICY.get('game_aliases', {}).items() if matches(rule['source_pattern'], evidence)]
        item['style_family'] = families.get(item['pack'], 'unclassified')
        role = item.get('role', '')
        if role == 'composition_part' or matches('часть|сегмент|фрагмент|половин', item['name']):
            kind = 'fragment'
        elif role in {'letter', 'digit'}:
            kind = role
        else:
            kind = 'emoji'
        item['selection_kind'] = kind
        item['selectable'] = not item.get('needs_review') and not item.get('availability') and kind == 'emoji'
        item['html_fallback'] = safe_fallback(item.get('original_fallback') or item['fallback'])
        item['preview_url'] = '' if item.get('availability') else SITE_URL + f'images/{item["id"]}.png'
        feature_evidence = extract_games(item['name'])[0]
        item['features'] = [key for key, rule in POLICY['features'].items() if matches(rule['pattern'], feature_evidence)]
        if matches('замок|lock', item['name']) and not {'open', 'disabled'} & set(item['features']) and 'closed' not in item['features']:
            item['features'].append('closed')
        item['color_mode'] = ('monochrome' if item['monochrome'] else 'color') if item.get('color_known') else 'unknown'
    data['selection_policy'] = POLICY
    material = [{key: item.get(key) for key in ('id', 'name', 'pack', 'style_family', 'intents', 'direct_intents', 'games', 'features', 'color_mode', 'repainting', 'animated', 'selection_kind', 'selectable')}
                for item in data['items']]
    data['catalog_version'] = hashlib.sha256(json.dumps({'items': material, 'policy': POLICY}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    return data
