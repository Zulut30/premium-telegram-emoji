"""
Генерирует site/index.html с превью всех premium emoji из каталога.

Использование:
    BOT_TOKEN=xxx python generate_site.py

Скачивает thumbnail каждого стикера через Telegram Bot API,
сохраняет в site/images/, генерирует статический HTML.
"""

from __future__ import annotations

import argparse
import json
import shutil
import os
import re
import sys
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from config import load_environment
from emoji_catalog import parse_catalog as load_catalog, catalog_data as make_catalog_data, safe_pack_url

REPO_DIR     = Path(__file__).parent
CATALOG_FILE = REPO_DIR / "references" / "emoji-catalog.md"
SITE_DIR     = REPO_DIR / "site"
IMG_DIR      = SITE_DIR / "images"
METADATA_FILE = REPO_DIR / "data" / "emoji-packs.json"
COMPOSITIONS_FILE = REPO_DIR / "data" / "emoji-compositions.json"
PREVIEW_DIR = REPO_DIR / "assets" / "previews"

load_environment(REPO_DIR)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API       = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ---------------------------------------------------------------------------
# Parse catalog
# ---------------------------------------------------------------------------

def parse_catalog() -> list[dict]:
    return load_catalog(CATALOG_FILE, METADATA_FILE)


# ---------------------------------------------------------------------------
# Telegram API helpers
# ---------------------------------------------------------------------------

def tg_get(method: str, **params) -> dict:
    url = f"{API}/{method}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())


def tg_post_json(method: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"{API}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _download_one(sticker: dict) -> tuple[str, str] | None:
    """Download thumbnail for one sticker. Returns (emoji_id, relative_path) or None."""
    eid   = sticker.get("custom_emoji_id")
    thumb = sticker.get("thumbnail") or sticker.get("thumb")
    if not eid or not thumb:
        return None
    dest = IMG_DIR / f"{eid}.png"
    if dest.exists() and dest.stat().st_size:
        return eid, dest.relative_to(SITE_DIR).as_posix()
    for attempt in range(3):
        try:
            fdata = tg_get("getFile", file_id=thumb["file_id"])
            file_path = fdata["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            partial = dest.with_suffix('.part')
            with urllib.request.urlopen(file_url, timeout=30) as response, partial.open('wb') as output:
                shutil.copyfileobj(response, output)
            partial.replace(dest)
            return eid, dest.relative_to(SITE_DIR).as_posix()
        except Exception as error:
            if attempt == 2:
                print(f"    ✗ {eid}: {str(error).replace(BOT_TOKEN, '[redacted]')}")
    return None


def fetch_thumbnails(emoji_ids: list[str], workers: int = 20) -> dict[str, str]:
    """Returns {emoji_id: local_image_path} — downloads missing in parallel."""
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    result: dict[str, str] = {}
    to_fetch: list[str] = []

    for eid in emoji_ids:
        cached = IMG_DIR / f"{eid}.png"
        override = PREVIEW_DIR / f"{eid}.png"
        if override.exists():
            shutil.copy2(override, cached)
            result[eid] = cached.relative_to(SITE_DIR).as_posix()
        elif cached.exists() and cached.stat().st_size:
            result[eid] = cached.relative_to(SITE_DIR).as_posix()
        else:
            to_fetch.append(eid)

    if not to_fetch:
        return result

    print(f"  Fetching thumbnails for {len(to_fetch)} emoji (×{workers} parallel)…")

    # Resolve sticker metadata in batches of 200
    stickers: list[dict] = []
    for i in range(0, len(to_fetch), 200):
        batch = to_fetch[i : i + 200]
        try:
            data = tg_post_json("getCustomEmojiStickers", {"custom_emoji_ids": batch})
        except Exception as e:
            print(f"  Warning: getCustomEmojiStickers failed: {e}")
            continue
        if not data.get("ok"):
            print(f"  Warning: API error: {data.get('description')}")
            continue
        stickers.extend(data.get("result", []))

    # Download in parallel
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_download_one, s): s for s in stickers}
        done = 0
        for future in as_completed(futures):
            res = future.result()
            if res:
                eid, path = res
                result[eid] = path
                done += 1
                if done % 20 == 0 or done == len(stickers):
                    print(f"    {done}/{len(stickers)} downloaded")

    return result


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

WEB_DIR = REPO_DIR / "web"
GITHUB_URL = "https://github.com/Zulut30/premium-telegram-emoji"


def catalog_data(sections: list[dict], thumbnails: dict[str, str]) -> dict:
    return make_catalog_data(sections, thumbnails, COMPOSITIONS_FILE)


def build_html(sections: list[dict], thumbnails: dict[str, str]) -> str:
    data = catalog_data(sections, thumbnails)
    # Escape '<' so untrusted names/notes cannot close the JSON script element.
    serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    brand = next((item["image"] for item in data["items"] if item["key"] == "breaking"), "icons/bolt.svg")
    return (WEB_DIR.joinpath("catalog.html").read_text(encoding="utf-8")
            .replace("__CATALOG_CSS__", WEB_DIR.joinpath("catalog.css").read_text(encoding="utf-8"))
            .replace("__CATALOG_JS__", WEB_DIR.joinpath("catalog.js").read_text(encoding="utf-8"))
            .replace("__SELECTION_JS__", WEB_DIR.joinpath("selection.js").read_text(encoding="utf-8"))
            .replace("__GITHUB_URL__", GITHUB_URL)
            .replace("__BRAND_IMAGE__", brand)
            .replace("__CATALOG_DATA__", serialized))


def write_site(sections: list[dict], thumbnails: dict[str, str]) -> Path:
    SITE_DIR.mkdir(exist_ok=True)
    shutil.copytree(WEB_DIR / "icons", SITE_DIR / "icons", dirs_exist_ok=True)
    out = SITE_DIR / "index.html"
    out.write_text(build_html(sections, thumbnails), encoding="utf-8")
    data = catalog_data(sections, thumbnails)
    (SITE_DIR / 'emoji-index.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Telegram emoji catalog")
    parser.add_argument("--offline", action="store_true", help="Use existing thumbnails without Telegram API calls")
    args = parser.parse_args()
    if not args.offline and not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    print("Parsing catalog…")
    sections = parse_catalog()
    all_ids = list(dict.fromkeys(e["emoji_id"] for s in sections for e in s["emojis"] if not e.get('availability')))
    print(f"  Found {sum(len(s['emojis']) for s in sections)} records in {len(sections)} sections")

    print("Using cached thumbnails…" if args.offline else "Fetching thumbnails…")
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    for eid in all_ids:
        override = PREVIEW_DIR / f"{eid}.png"
        if override.exists():
            shutil.copy2(override, IMG_DIR / f"{eid}.png")
    thumbnails = ({eid: f"images/{eid}.png" for eid in all_ids if (IMG_DIR / f"{eid}.png").exists()}
                  if args.offline else fetch_thumbnails(all_ids))
    print(f"  Got {len(thumbnails)} thumbnails")

    print("Building HTML…")
    out = write_site(sections, thumbnails)
    print(f"  Saved → {out}")
    print("Done!")


if __name__ == "__main__":
    main()
