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

GITHUB_URL = "https://github.com/Zulut30/premium-telegram-emoji"

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Каталог premium Telegram emoji с ID, превью и готовым кодом для aiogram-ботов">
<title>Premium Telegram Emoji — каталог</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:        #08080f;
  --surface:   #11111c;
  --card:      #16162280;
  --border:    #ffffff12;
  --border-h:  #7c6cfc60;
  --accent:    #7c6cfc;
  --accent2:   #a78bfa;
  --glow:      #7c6cfc30;
  --text:      #e8e8f5;
  --muted:     #6060a0;
  --success:   #34d399;
  --radius:    14px;
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif;
  min-height: 100vh;
  line-height: 1.5;
}

/* ── Hero ── */
.hero {
  padding: 4rem 1.5rem 3rem;
  text-align: center;
  background: radial-gradient(ellipse 80% 60% at 50% -10%, #7c6cfc18 0%, transparent 70%);
  border-bottom: 1px solid var(--border);
}
.hero-nav {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 2rem;
  max-width: 1280px;
  margin-left: auto;
  margin-right: auto;
}
.github-btn {
  display: inline-flex;
  align-items: center;
  gap: .45rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-size: .82rem;
  font-weight: 500;
  padding: .4rem .85rem;
  text-decoration: none;
  transition: border-color .2s, background .2s;
}
.github-btn:hover { border-color: var(--accent2); background: #1e1e30; }
.github-btn svg { flex-shrink: 0; }

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: .4rem;
  background: var(--glow);
  border: 1px solid var(--border-h);
  border-radius: 100px;
  color: var(--accent2);
  font-size: .75rem;
  font-weight: 600;
  letter-spacing: .04em;
  padding: .3rem .8rem;
  margin-bottom: 1.2rem;
  text-transform: uppercase;
}
.hero h1 {
  font-size: clamp(1.8rem, 5vw, 3rem);
  font-weight: 800;
  letter-spacing: -.02em;
  margin-bottom: .75rem;
  line-height: 1.15;
}
.hero h1 .grad {
  background: linear-gradient(135deg, #a78bfa 0%, #7c6cfc 50%, #60a5fa 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero p {
  color: var(--muted);
  font-size: 1rem;
  max-width: 520px;
  margin: 0 auto 1.75rem;
}
.hero-stats {
  display: flex;
  gap: 1.5rem;
  justify-content: center;
  flex-wrap: wrap;
}
.hero-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.hero-stat strong { font-size: 1.4rem; font-weight: 700; color: var(--text); }
.hero-stat span   { font-size: .75rem; color: var(--muted); }

/* ── Sticky toolbar ── */
.toolbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: #08080fe8;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border);
  padding: .75rem 1.5rem;
}
.toolbar-inner {
  max-width: 1280px;
  margin: 0 auto;
  display: flex;
  gap: .75rem;
  align-items: center;
  flex-wrap: wrap;
}

.search-wrap {
  position: relative;
  flex: 1;
  min-width: 180px;
  max-width: 320px;
}
.search-wrap svg {
  position: absolute;
  left: .7rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
  pointer-events: none;
}
input[type=search] {
  width: 100%;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text);
  font-size: .875rem;
  padding: .5rem .75rem .5rem 2.1rem;
  outline: none;
  transition: border-color .2s;
  -webkit-appearance: none;
}
input[type=search]:focus { border-color: var(--accent); }
input[type=search]::placeholder { color: var(--muted); }

.filters {
  display: flex;
  gap: .4rem;
  flex-wrap: wrap;
  align-items: center;
}
.filter-btn {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--muted);
  cursor: pointer;
  font-size: .78rem;
  font-weight: 500;
  padding: .38rem .7rem;
  transition: all .15s;
  white-space: nowrap;
}
.filter-btn .cnt {
  display: inline-block;
  background: #ffffff10;
  border-radius: 4px;
  font-size: .68rem;
  margin-left: .3rem;
  padding: 0 .3rem;
}
.filter-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.filter-btn.active .cnt { background: #ffffff25; }
.filter-btn:not(.active):hover { border-color: var(--border-h); color: var(--text); }

/* ── Main content ── */
main {
  padding: 2rem 1.5rem;
  max-width: 1280px;
  margin: 0 auto;
}

.section-block { margin-bottom: 3rem; }

.section-header {
  display: flex;
  align-items: center;
  gap: .75rem;
  margin-bottom: 1.25rem;
}
.section-name {
  font-size: .95rem;
  font-weight: 700;
  color: var(--text);
  white-space: nowrap;
}
.section-count {
  font-size: .75rem;
  color: var(--muted);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: .1rem .45rem;
}
.section-line {
  flex: 1;
  height: 1px;
  background: var(--border);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
  gap: .75rem;
}

/* ── Card ── */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.1rem .85rem .85rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: .45rem;
  cursor: pointer;
  position: relative;
  transition: border-color .2s, box-shadow .2s, transform .15s;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  overflow: hidden;
}
.card::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #ffffff06, transparent 60%);
  pointer-events: none;
}
.card:hover {
  border-color: var(--border-h);
  box-shadow: 0 0 0 1px var(--border-h), 0 8px 32px var(--glow);
  transform: translateY(-3px);
}
.card:active { transform: translateY(-1px); }

.card-img-wrap {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffffff08;
  border-radius: 12px;
  border: 1px solid var(--border);
}
.card img {
  width: 44px;
  height: 44px;
  object-fit: contain;
}
.card .fallback { font-size: 2rem; line-height: 1; }

.card-desc {
  font-size: .78rem;
  font-weight: 500;
  text-align: center;
  line-height: 1.3;
  color: var(--text);
  word-break: break-word;
}
.card-key {
  font-size: .68rem;
  color: var(--accent2);
  font-family: "SF Mono", "Fira Code", monospace;
  background: #7c6cfc15;
  border-radius: 5px;
  padding: .1rem .35rem;
}
.card-id {
  font-size: .62rem;
  color: var(--muted);
  font-family: "SF Mono", "Fira Code", monospace;
  word-break: break-all;
  text-align: center;
  line-height: 1.4;
}

.copy-hint {
  position: absolute;
  inset: 0;
  background: #7c6cfc22;
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: .8rem;
  font-weight: 600;
  color: var(--success);
  opacity: 0;
  transition: opacity .2s;
  pointer-events: none;
  backdrop-filter: blur(4px);
}
.card.copied .copy-hint { opacity: 1; }

/* ── Empty state ── */
.empty {
  text-align: center;
  padding: 5rem 2rem;
  color: var(--muted);
}
.empty p { margin-top: .5rem; font-size: .9rem; }

/* ── Footer ── */
footer {
  border-top: 1px solid var(--border);
  padding: 2rem 1.5rem;
  text-align: center;
  color: var(--muted);
  font-size: .82rem;
}
footer a { color: var(--accent2); text-decoration: none; }
footer a:hover { text-decoration: underline; }

/* ── Mobile ── */
@media (max-width: 600px) {
  .hero { padding: 2.5rem 1rem 2rem; }
  .hero-nav { margin-bottom: 1.25rem; }
  .hero-stats { gap: 1rem; }
  .toolbar { padding: .6rem 1rem; }
  .toolbar-inner { gap: .5rem; }
  .search-wrap { max-width: 100%; }
  .filters { gap: .35rem; }
  .filter-btn { font-size: .72rem; padding: .32rem .55rem; }
  main { padding: 1.25rem 1rem; }
  .grid { grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: .55rem; }
  .card { padding: .9rem .65rem .7rem; }
  .card-img-wrap { width: 48px; height: 48px; }
  .card img { width: 36px; height: 36px; }
}

@media (max-width: 380px) {
  .grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
</head>
<body>

<!-- Hero -->
<section class="hero">
  <nav class="hero-nav">
    <a class="github-btn" href="{GITHUB_URL}" target="_blank" rel="noopener">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
      </svg>
      GitHub
    </a>
  </nav>
  <div class="hero-badge">✦ Telegram Premium</div>
  <h1>Каталог <span class="grad">Premium Emoji</span></h1>
  <p>Верифицированные ID premium-стикеров для Telegram-ботов. Готовый код для aiogram 3 — просто скопируй ID и используй.</p>
  <div class="hero-stats">
    <div class="hero-stat"><strong>{TOTAL}</strong><span>emoji</span></div>
    <div class="hero-stat"><strong>{SECTIONS_COUNT}</strong><span>секций</span></div>
    <div class="hero-stat"><strong>aiogram 3</strong><span>совместимость</span></div>
  </div>
</section>

<!-- Toolbar -->
<div class="toolbar">
  <div class="toolbar-inner">
    <div class="search-wrap">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
      </svg>
      <input type="search" id="search" placeholder="Поиск…" oninput="filter()" autocomplete="off">
    </div>
    <div class="filters" id="filters">
      <button class="filter-btn active" data-sec="all" onclick="setSection(this)">
        Все <span class="cnt">{TOTAL}</span>
      </button>
      {SECTION_BUTTONS}
    </div>
  </div>
</div>

<!-- Catalog -->
<main id="main">
  {SECTIONS_HTML}
  <div class="empty" id="empty" style="display:none">
    <div style="font-size:2rem">🔍</div>
    <p>Ничего не найдено</p>
  </div>
</main>

<footer>
  {TOTAL} emoji · Нажми на карточку чтобы скопировать ID ·
  <a href="{GITHUB_URL}" target="_blank">GitHub</a>
</footer>

<script>
let activeSec = 'all';

function filter() {
  const q = document.getElementById('search').value.toLowerCase().trim();
  let total = 0;
  document.querySelectorAll('.card').forEach(card => {
    const matchQ   = !q || card.dataset.search.includes(q);
    const matchSec = activeSec === 'all' || card.dataset.sec === activeSec;
    const show = matchQ && matchSec;
    card.style.display = show ? '' : 'none';
    if (show) total++;
  });
  document.querySelectorAll('.section-block').forEach(block => {
    const vis = [...block.querySelectorAll('.card')].some(c => c.style.display !== 'none');
    block.style.display = vis ? '' : 'none';
  });
  document.getElementById('empty').style.display = total ? 'none' : '';
}

function setSection(btn) {
  activeSec = btn.dataset.sec;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  filter();
  window.scrollTo({ top: document.querySelector('.toolbar').offsetTop - 1, behavior: 'smooth' });
}

function copyId(card, id) {
  navigator.clipboard.writeText(id).then(() => {
    card.classList.add('copied');
    setTimeout(() => card.classList.remove('copied'), 1200);
  });
}
</script>
</body>
</html>
"""

CARD_TMPL = """\
<div class="card" data-search="{SEARCH}" data-sec="{SEC_ID}" onclick="copyId(this, '{EMOJI_ID}')">
  <div class="copy-hint">✓ скопировано</div>
  <div class="card-img-wrap">{IMG_TAG}</div>
  <div class="card-desc">{DESC}</div>
  <div class="card-key">{KEY}</div>
  <div class="card-id">{EMOJI_ID}</div>
</div>
"""


def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_html(sections: list[dict], thumbnails: dict[str, str]) -> str:
    sec_buttons  = ""
    sections_html = ""
    total = 0

    for sec in sections:
        sec_id    = re.search(r"Section (\d+)", sec["title"]).group(1)
        sec_short = sec["title"].split(" — ", 1)[1] if " — " in sec["title"] else sec["title"]
        count     = len(sec["emojis"])
        sec_buttons += (
            f'<button class="filter-btn" data-sec="{sec_id}" onclick="setSection(this)">'
            f'{escape(sec_short)} <span class="cnt">{count}</span></button>\n      '
        )

        cards = ""
        for e in sec["emojis"]:
            eid      = e["emoji_id"]
            img_path = thumbnails.get(eid)
            img_tag  = (
                f'<img src="{img_path}" alt="{escape(e["fallback"])}" loading="lazy">'
                if img_path else
                f'<span class="fallback">{e["fallback"]}</span>'
            )
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

        sections_html += (
            f'<div class="section-block" data-sec="{sec_id}">'
            f'<div class="section-header">'
            f'<span class="section-name">{escape(sec["title"])}</span>'
            f'<span class="section-count">{count}</span>'
            f'<div class="section-line"></div>'
            f'</div>'
            f'<div class="grid">{cards}</div>'
            f'</div>\n'
        )

    return (HTML_TEMPLATE
            .replace("{GITHUB_URL}",      GITHUB_URL)
            .replace("{SECTION_BUTTONS}", sec_buttons.strip())
            .replace("{SECTIONS_HTML}",   sections_html)
            .replace("{TOTAL}",           str(total))
            .replace("{SECTIONS_COUNT}",  str(len(sections))))


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
