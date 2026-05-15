"""
Генерирует site/index.html с превью всех premium emoji из каталога.

Использование:
    BOT_TOKEN=xxx python generate_site.py

Скачивает thumbnail каждого стикера через Telegram Bot API,
сохраняет в site/images/, генерирует статический HTML.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_DIR     = Path(__file__).parent
CATALOG_FILE = REPO_DIR / "references" / "emoji-catalog.md"
SITE_DIR     = REPO_DIR / "site"
IMG_DIR      = SITE_DIR / "images"

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API       = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ---------------------------------------------------------------------------
# Parse catalog
# ---------------------------------------------------------------------------

def parse_catalog() -> list[dict]:
    text = CATALOG_FILE.read_text(encoding="utf-8")
    sections: list[dict] = []
    current: dict | None = None

    for line in text.splitlines():
        m = re.match(r"^## (Section \d+ — .+)$", line)
        if m:
            current = {"title": m.group(1), "emojis": []}
            sections.append(current)
            continue

        if (
            current
            and line.startswith("|")
            and not re.match(r"^\|\s*key", line)
            and not re.match(r"^\|[-| ]+$", line)
        ):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 4 and parts[1].isdigit():
                current["emojis"].append({
                    "key":         parts[0],
                    "emoji_id":    parts[1],
                    "description": parts[2],
                    "fallback":    parts[3],
                })

    return sections


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
    if dest.exists():
        return eid, str(dest.relative_to(SITE_DIR))
    try:
        fdata     = tg_get("getFile", file_id=thumb["file_id"])
        file_path = fdata["result"]["file_path"]
        file_url  = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        urllib.request.urlretrieve(file_url, dest)
        return eid, str(dest.relative_to(SITE_DIR))
    except Exception as e:
        print(f"    ✗ {eid}: {e}")
        return None


def fetch_thumbnails(emoji_ids: list[str], workers: int = 20) -> dict[str, str]:
    """Returns {emoji_id: local_image_path} — downloads missing in parallel."""
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    result: dict[str, str] = {}
    to_fetch: list[str] = []

    for eid in emoji_ids:
        cached = IMG_DIR / f"{eid}.png"
        if cached.exists():
            result[eid] = str(cached.relative_to(SITE_DIR))
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

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Premium Telegram Emoji Catalog</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:      #0f0f13;
    --card-bg: #1a1a24;
    --border:  #2a2a38;
    --accent:  #7c6cfc;
    --text:    #e2e2f0;
    --muted:   #7070a0;
    --success: #4caf50;
  }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    min-height: 100vh;
  }

  header {
    padding: 2rem 1.5rem 1rem;
    text-align: center;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    background: var(--bg);
    z-index: 100;
  }
  header h1 { font-size: 1.4rem; margin-bottom: .75rem; }
  header h1 span { color: var(--accent); }

  .controls {
    display: flex;
    gap: .6rem;
    flex-wrap: wrap;
    justify-content: center;
    align-items: center;
  }

  input[type=search] {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-size: .9rem;
    padding: .45rem .8rem;
    width: 260px;
    outline: none;
  }
  input[type=search]:focus { border-color: var(--accent); }

  .filter-btn {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--muted);
    cursor: pointer;
    font-size: .8rem;
    padding: .45rem .75rem;
    transition: all .15s;
  }
  .filter-btn.active, .filter-btn:hover {
    border-color: var(--accent);
    color: var(--text);
  }

  main { padding: 1.5rem; max-width: 1400px; margin: 0 auto; }

  .section-block { margin-bottom: 2.5rem; }
  .section-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--muted);
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: .5rem;
  }
  .section-title::after {
    content: "";
    flex: 1;
    height: 1px;
    background: var(--border);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: .75rem;
  }

  .card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem .75rem .75rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: .5rem;
    cursor: pointer;
    transition: border-color .15s, transform .1s;
    position: relative;
  }
  .card:hover { border-color: var(--accent); transform: translateY(-2px); }

  .card img, .card .fallback {
    width: 52px;
    height: 52px;
    object-fit: contain;
  }
  .card .fallback { font-size: 2.5rem; line-height: 52px; text-align: center; }

  .card .desc {
    font-size: .78rem;
    text-align: center;
    line-height: 1.3;
    color: var(--text);
    word-break: break-word;
  }
  .card .key {
    font-size: .7rem;
    color: var(--accent);
    font-family: monospace;
  }
  .card .id {
    font-size: .65rem;
    color: var(--muted);
    font-family: monospace;
    word-break: break-all;
    text-align: center;
  }

  .copied-tip {
    position: absolute;
    top: 6px; right: 8px;
    font-size: .65rem;
    color: var(--success);
    opacity: 0;
    transition: opacity .2s;
    pointer-events: none;
  }
  .card.copied .copied-tip { opacity: 1; }

  .empty { color: var(--muted); text-align: center; padding: 3rem; }

  footer {
    text-align: center;
    padding: 2rem;
    color: var(--muted);
    font-size: .8rem;
    border-top: 1px solid var(--border);
  }
</style>
</head>
<body>

<header>
  <h1>Premium <span>Telegram</span> Emoji</h1>
  <div class="controls">
    <input type="search" id="search" placeholder="Поиск по описанию…" oninput="filter()">
    <button class="filter-btn active" data-sec="all" onclick="setSection(this)">Все</button>
    {SECTION_BUTTONS}
  </div>
</header>

<main id="main">
  {SECTIONS_HTML}
</main>

<footer>
  {TOTAL} emoji · Нажми на карточку чтобы скопировать ID
</footer>

<script>
let activeSec = 'all';

function filter() {
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('.card').forEach(card => {
    const text = card.dataset.search;
    const sec  = card.dataset.sec;
    const matchQ   = !q || text.includes(q);
    const matchSec = activeSec === 'all' || sec === activeSec;
    card.style.display = (matchQ && matchSec) ? '' : 'none';
  });
  document.querySelectorAll('.section-block').forEach(block => {
    const visible = [...block.querySelectorAll('.card')].some(c => c.style.display !== 'none');
    block.style.display = visible ? '' : 'none';
  });
}

function setSection(btn) {
  activeSec = btn.dataset.sec;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  filter();
}

function copyId(card, id) {
  navigator.clipboard.writeText(id).then(() => {
    card.classList.add('copied');
    setTimeout(() => card.classList.remove('copied'), 1500);
  });
}
</script>
</body>
</html>
"""

CARD_TMPL = """\
<div class="card" data-search="{SEARCH}" data-sec="{SEC_ID}"
     onclick="copyId(this, '{EMOJI_ID}')">
  <span class="copied-tip">скопировано!</span>
  {IMG_TAG}
  <div class="desc">{DESC}</div>
  <div class="key">{KEY}</div>
  <div class="id">{EMOJI_ID}</div>
</div>
"""


def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_html(sections: list[dict], thumbnails: dict[str, str]) -> str:
    sec_buttons = ""
    sections_html = ""
    total = 0

    for sec in sections:
        sec_id  = re.search(r"Section (\d+)", sec["title"]).group(1)
        sec_short = sec["title"].split(" — ", 1)[1] if " — " in sec["title"] else sec["title"]
        sec_buttons += f'<button class="filter-btn" data-sec="{sec_id}" onclick="setSection(this)">{escape(sec_short)}</button>\n    '

        cards = ""
        for e in sec["emojis"]:
            eid  = e["emoji_id"]
            img_path = thumbnails.get(eid)
            if img_path:
                img_tag = f'<img src="{img_path}" alt="{escape(e["fallback"])}" loading="lazy">'
            else:
                img_tag = f'<div class="fallback">{e["fallback"]}</div>'

            search = f"{e['description'].lower()} {e['key'].lower()}"
            cards += CARD_TMPL.format(
                SEARCH   = escape(search),
                SEC_ID   = sec_id,
                EMOJI_ID = eid,
                IMG_TAG  = img_tag,
                DESC     = escape(e["description"]),
                KEY      = escape(e["key"]),
            )
            total += 1

        sections_html += f"""
<div class="section-block" data-sec="{sec_id}">
  <div class="section-title">{escape(sec["title"])}</div>
  <div class="grid">{cards}</div>
</div>
"""

    return (HTML_TEMPLATE
            .replace("{SECTION_BUTTONS}", sec_buttons.strip())
            .replace("{SECTIONS_HTML}",  sections_html)
            .replace("{TOTAL}",          str(total)))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    print("Parsing catalog…")
    sections = parse_catalog()
    all_ids  = [e["emoji_id"] for s in sections for e in s["emojis"]]
    print(f"  Found {len(all_ids)} emoji in {len(sections)} sections")

    print("Fetching thumbnails…")
    thumbnails = fetch_thumbnails(all_ids)
    print(f"  Got {len(thumbnails)} thumbnails")

    print("Building HTML…")
    SITE_DIR.mkdir(exist_ok=True)
    html = build_html(sections, thumbnails)
    out  = SITE_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"  Saved → {out}")
    print("Done!")


if __name__ == "__main__":
    main()
