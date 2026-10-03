"""Static site rendering and output, without Telegram or environment access."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from premium_emoji.io import replace_files

GITHUB_URL = 'https://github.com/Zulut30/premium-telegram-emoji'


def render_html(data: dict, web_dir: Path) -> str:
    serialized = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    brand = next((item['image'] for item in data['items'] if item['key'] == 'breaking'), 'icons/bolt.svg')
    return (web_dir.joinpath('catalog.html').read_text(encoding='utf-8')
            .replace('__CATALOG_CSS__', web_dir.joinpath('catalog.css').read_text(encoding='utf-8'))
            .replace('__CATALOG_JS__', web_dir.joinpath('catalog.js').read_text(encoding='utf-8'))
            .replace('__SELECTION_JS__', web_dir.joinpath('selection.js').read_text(encoding='utf-8'))
            .replace('__GITHUB_URL__', GITHUB_URL)
            .replace('__BRAND_IMAGE__', brand)
            .replace('__CATALOG_DATA__', serialized))


def write_site(data: dict, web_dir: Path, site_dir: Path) -> Path:
    site_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(web_dir / 'icons', site_dir / 'icons', dirs_exist_ok=True)
    index = site_dir / 'index.html'
    replace_files({index: render_html(data, web_dir).encode('utf-8'),
                   site_dir / 'emoji-index.json': json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')})
    return index


def cached_thumbnails(emoji_ids: list[str], site_dir: Path, preview_dir: Path) -> dict[str, str]:
    image_dir = site_dir / 'images'
    image_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    for eid in emoji_ids:
        cached = image_dir / f'{eid}.png'
        override = preview_dir / f'{eid}.png'
        if override.is_file():
            shutil.copy2(override, cached)
        if cached.is_file() and cached.stat().st_size:
            result[eid] = f'images/{eid}.png'
    return result
