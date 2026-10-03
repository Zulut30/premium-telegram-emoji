"""Build the catalog site: python generate_site.py [--offline]."""
from __future__ import annotations

import argparse
import os
import sys

from premium_emoji.paths import DEFAULT_PATHS
from premium_emoji.catalog import parse_catalog as load_catalog, catalog_data as make_catalog_data, safe_pack_url
from integrations.site_builder import render_html, write_site as write_compiled_site, cached_thumbnails
from integrations.telegram_previews import TelegramPreviewClient

REPO_DIR = DEFAULT_PATHS.root
CATALOG_FILE = DEFAULT_PATHS.catalog
METADATA_FILE = DEFAULT_PATHS.metadata
COMPOSITIONS_FILE = DEFAULT_PATHS.compositions
SITE_DIR = DEFAULT_PATHS.site
IMG_DIR = SITE_DIR / 'images'
PREVIEW_DIR = DEFAULT_PATHS.previews
WEB_DIR = DEFAULT_PATHS.web


def parse_catalog() -> list[dict]:
    return load_catalog(CATALOG_FILE, METADATA_FILE)


def catalog_data(sections: list[dict], thumbnails: dict[str, str]) -> dict:
    return make_catalog_data(sections, thumbnails, COMPOSITIONS_FILE)


def build_html(sections: list[dict], thumbnails: dict[str, str]) -> str:
    return render_html(catalog_data(sections, thumbnails), WEB_DIR)


def write_site(sections: list[dict], thumbnails: dict[str, str]):
    return write_compiled_site(catalog_data(sections, thumbnails), WEB_DIR, SITE_DIR)


def fetch_thumbnails(emoji_ids: list[str], workers: int = 20) -> dict[str, str]:
    return TelegramPreviewClient(os.environ.get('BOT_TOKEN', ''), SITE_DIR, PREVIEW_DIR).fetch(emoji_ids, workers)


def main() -> None:
    parser = argparse.ArgumentParser(description='Build the Telegram emoji catalog')
    parser.add_argument('--offline', action='store_true', help='Use cached thumbnails without Telegram API calls')
    args = parser.parse_args()
    from premium_emoji.validation import validate_sources
    errors = validate_sources()
    if errors:
        parser.error('\n'.join(errors))
    if not args.offline:
        from config import load_environment
        load_environment(REPO_DIR)
        if not os.environ.get('BOT_TOKEN'):
            parser.error('BOT_TOKEN not set')
    print('Parsing catalog…')
    sections = parse_catalog()
    all_ids = list(dict.fromkeys(item['emoji_id'] for section in sections for item in section['emojis'] if not item.get('availability')))
    print(f"  Found {sum(len(section['emojis']) for section in sections)} records in {len(sections)} sections")
    print('Using cached thumbnails…' if args.offline else 'Fetching thumbnails…')
    thumbnails = (cached_thumbnails(all_ids, SITE_DIR, PREVIEW_DIR) if args.offline else fetch_thumbnails(all_ids))
    print(f'  Got {len(thumbnails)} thumbnails')
    out = write_site(sections, thumbnails)
    print(f'Saved → {out}')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
