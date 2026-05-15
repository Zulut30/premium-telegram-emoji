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
  --bg:        #080a0f;
  --surface:   #10131d;
  --surface2:  #151a27;
  --card:      #151925cc;
  --border:    #ffffff14;
  --border-h:  #2dd4bf80;
  --accent:    #2dd4bf;
  --accent2:   #38bdf8;
  --amber:     #fbbf24;
  --coral:     #fb7185;
  --glow:      #2dd4bf24;
  --text:      #eef6ff;
  --muted:     #8a96ad;
  --soft:      #c8d2e3;
  --success:   #34d399;
  --radius:    16px;
}

body {
  background:
    linear-gradient(180deg, #0b1020 0%, #080a0f 42%, #080a0f 100%),
    repeating-linear-gradient(90deg, #ffffff05 0 1px, transparent 1px 84px);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif;
  min-height: 100vh;
  line-height: 1.5;
}

/* ── Hero ── */
.hero {
  padding: 3.6rem 1.5rem 3rem;
  text-align: center;
  background:
    linear-gradient(135deg, #2dd4bf18 0%, transparent 32%),
    linear-gradient(225deg, #fb718518 0%, transparent 36%);
  border-bottom: 1px solid var(--border);
}
.hero-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  max-width: 1280px;
  margin-left: auto;
  margin-right: auto;
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: .55rem;
  color: var(--soft);
  font-size: .86rem;
  font-weight: 700;
  letter-spacing: .01em;
}
.brand-mark {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #031018;
  box-shadow: 0 10px 30px #2dd4bf24;
}
.github-btn {
  display: inline-flex;
  align-items: center;
  gap: .45rem;
  background: #101723cc;
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text);
  font-size: .82rem;
  font-weight: 500;
  padding: .48rem .9rem;
  text-decoration: none;
  transition: border-color .2s, background .2s;
}
.github-btn:hover { border-color: var(--accent); background: #17202f; }
.github-btn svg { flex-shrink: 0; }

.hero h1 {
  font-size: clamp(2.05rem, 6vw, 4.25rem);
  font-weight: 800;
  letter-spacing: 0;
  margin: 0 auto .9rem;
  line-height: 1.05;
  max-width: 820px;
}
.hero h1 .grad {
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent2) 48%, var(--coral) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero p {
  color: var(--muted);
  font-size: 1.05rem;
  max-width: 680px;
  margin: 0 auto 2rem;
}
.hero p code {
  color: var(--soft);
  background: #ffffff0d;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: .92em;
  padding: .08rem .32rem;
}
.hero-stats {
  display: flex;
  gap: .75rem;
  justify-content: center;
  flex-wrap: wrap;
}
.hero-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 120px;
  padding: .85rem 1rem;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: #10172399;
}
.hero-stat strong { font-size: 1.4rem; font-weight: 700; color: var(--text); }
.hero-stat span   { font-size: .75rem; color: var(--muted); }

/* ── Sticky toolbar ── */
.toolbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: #080a0ff0;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border);
  padding: .85rem 1.5rem;
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
  background: #101723;
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text);
  font-size: .875rem;
  padding: .5rem .75rem .5rem 2.1rem;
  outline: none;
  transition: border-color .2s;
  -webkit-appearance: none;
}
input[type=search]:focus { border-color: var(--accent); box-shadow: 0 0 0 3px #2dd4bf18; }
input[type=search]::placeholder { color: var(--muted); }

.toolbar-select {
  appearance: none;
  background: #101723;
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--soft);
  cursor: pointer;
  font-size: .82rem;
  font-weight: 600;
  min-height: 36px;
  padding: .5rem 2rem .5rem .75rem;
  outline: none;
  background-image:
    linear-gradient(45deg, transparent 50%, var(--muted) 50%),
    linear-gradient(135deg, var(--muted) 50%, transparent 50%);
  background-position:
    calc(100% - 14px) 15px,
    calc(100% - 9px) 15px;
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
}
.toolbar-select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px #2dd4bf18; }

.filters {
  display: flex;
  gap: .4rem;
  flex-wrap: wrap;
  align-items: center;
}
.filter-btn {
  background: #101723;
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
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  border-color: var(--accent);
  color: #031018;
}
.filter-btn.active .cnt { background: #ffffff25; }
.filter-btn:not(.active):hover { border-color: var(--border-h); color: var(--text); }

/* ── Main content ── */
main {
  padding: 2.25rem 1.5rem;
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
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: .9rem;
}

/* ── Card ── */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem .9rem .85rem;
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
  background: linear-gradient(135deg, #ffffff08, transparent 58%);
  pointer-events: none;
}
.card:hover {
  border-color: var(--border-h);
  box-shadow: 0 0 0 1px var(--border-h), 0 14px 42px var(--glow);
  transform: translateY(-3px);
}
.card[data-rating]:not([data-rating="0"]) {
  border-color: #fbbf2440;
}
.card:active { transform: translateY(-1px); }

.card-img-wrap {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffffff08;
  border-radius: 16px;
  border: 1px solid var(--border);
}
.card img {
  width: 50px;
  height: 50px;
  object-fit: contain;
}
.card .fallback { font-size: 2rem; line-height: 1; }

.card-desc {
  min-height: 2.15rem;
  font-size: .8rem;
  font-weight: 500;
  text-align: center;
  line-height: 1.3;
  color: var(--text);
  word-break: break-word;
}
.card-key {
  font-size: .68rem;
  color: var(--accent);
  font-family: "SF Mono", "Fira Code", monospace;
  background: #2dd4bf14;
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

.rating {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: .1rem;
  min-height: 30px;
  margin-top: .12rem;
  position: relative;
  z-index: 1;
}
.star {
  appearance: none;
  border: 0;
  background: transparent;
  color: #3b4354;
  cursor: pointer;
  font-size: 1.06rem;
  line-height: 1;
  padding: .18rem;
  transition: color .15s, transform .15s, text-shadow .15s;
}
.star:hover,
.star.active {
  color: var(--amber);
  text-shadow: 0 0 16px #fbbf2440;
}
.star:hover { transform: translateY(-1px) scale(1.08); }
.rating-label {
  color: var(--muted);
  font-size: .66rem;
  line-height: 1;
  min-height: .8rem;
  text-align: center;
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
  .hero { padding: 2rem 1rem 1.8rem; text-align: left; }
  .hero-nav { margin-bottom: 1.25rem; }
  .github-btn span { display: none; }
  .hero h1 { font-size: 2.25rem; }
  .hero p { font-size: .95rem; margin-bottom: 1.25rem; }
  .hero-stats { justify-content: stretch; gap: .5rem; }
  .hero-stat { flex: 1 1 calc(50% - .5rem); min-width: 110px; padding: .7rem .75rem; align-items: flex-start; }
  .toolbar { padding: .6rem 1rem; }
  .toolbar-inner { gap: .5rem; }
  .search-wrap { max-width: 100%; min-width: 100%; }
  .toolbar-select { flex: 1; min-width: 150px; }
  .filters { gap: .35rem; }
  .filter-btn { font-size: .72rem; padding: .32rem .55rem; }
  main { padding: 1.25rem 1rem; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .65rem; }
  .card { padding: .9rem .65rem .7rem; }
  .card-img-wrap { width: 54px; height: 54px; }
  .card img { width: 42px; height: 42px; }
  .star { font-size: 1rem; padding: .16rem; }
  .section-header { align-items: flex-start; }
  .section-name { white-space: normal; line-height: 1.25; }
}

@media (max-width: 380px) {
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .card-id { font-size: .58rem; }
}
</style>
</head>
<body>

<!-- Hero -->
<section class="hero">
  <nav class="hero-nav">
    <div class="brand">
      <span class="brand-mark">✦</span>
      <span>premium-telegram-emoji</span>
    </div>
    <a class="github-btn" href="{GITHUB_URL}" target="_blank" rel="noopener">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
      </svg>
      <span>GitHub</span>
    </a>
  </nav>
  <h1>Каталог <span class="grad">Premium Emoji</span> для Telegram-ботов</h1>
  <p>Верифицированные ID, реальные превью из Telegram, локальные оценки и готовый путь до кода: выбери emoji, скопируй ID и вставь в <code>&lt;tg-emoji&gt;</code>.</p>
  <div class="hero-stats">
    <div class="hero-stat"><strong>{TOTAL}</strong><span>emoji</span></div>
    <div class="hero-stat"><strong>{SECTIONS_COUNT}</strong><span>секций</span></div>
    <div class="hero-stat"><strong>★</strong><span>твои оценки</span></div>
    <div class="hero-stat"><strong>aiogram 3</strong><span>и HTML parse_mode</span></div>
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
    <select class="toolbar-select" id="sort" onchange="sortCards()">
      <option value="catalog">Порядок каталога</option>
      <option value="rating">Сначала лучшие</option>
      <option value="unrated">Неоценённые</option>
    </select>
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
  {TOTAL} emoji · Клик по карточке копирует ID · Оценки сохраняются только в твоём браузере ·
  <a href="{GITHUB_URL}" target="_blank">GitHub</a>
</footer>

<script>
let activeSec = 'all';
const RATING_KEY = 'premiumEmojiRatings:v1';
let ratings = {};

try {
  ratings = JSON.parse(localStorage.getItem(RATING_KEY) || '{}');
} catch (_) {
  ratings = {};
}

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

function setRating(event, id, value) {
  event.stopPropagation();
  if (ratings[id] === value) {
    delete ratings[id];
  } else {
    ratings[id] = value;
  }
  localStorage.setItem(RATING_KEY, JSON.stringify(ratings));
  paintRatings();
  sortCards(false);
}

function paintRatings() {
  document.querySelectorAll('.card').forEach(card => {
    const id = card.dataset.id;
    const rating = Number(ratings[id] || 0);
    card.dataset.rating = String(rating);
    card.querySelectorAll('.star').forEach(star => {
      const value = Number(star.dataset.value);
      star.classList.toggle('active', value <= rating);
      star.setAttribute('aria-pressed', value <= rating ? 'true' : 'false');
    });
    const label = card.querySelector('.rating-label');
    if (label) {
      label.textContent = rating ? `${rating}/5` : 'оценить';
    }
  });
}

function sortCards(shouldFilter = true) {
  const mode = document.getElementById('sort').value;
  document.querySelectorAll('.grid').forEach(grid => {
    const cards = [...grid.querySelectorAll('.card')];
    cards.sort((a, b) => {
      const ar = Number(ratings[a.dataset.id] || 0);
      const br = Number(ratings[b.dataset.id] || 0);
      const ao = Number(a.dataset.order);
      const bo = Number(b.dataset.order);

      if (mode === 'rating') {
        return (br - ar) || (ao - bo);
      }
      if (mode === 'unrated') {
        return ((ar ? 1 : 0) - (br ? 1 : 0)) || (ao - bo);
      }
      return ao - bo;
    });
    cards.forEach(card => grid.appendChild(card));
  });
  if (shouldFilter) filter();
}

paintRatings();
</script>
</body>
</html>
"""

CARD_TMPL = """\
<div class="card" data-id="{EMOJI_ID}" data-order="{ORDER}" data-rating="0" data-search="{SEARCH}" data-sec="{SEC_ID}" onclick="copyId(this, '{EMOJI_ID}')">
  <div class="copy-hint">✓ скопировано</div>
  <div class="card-img-wrap">{IMG_TAG}</div>
  <div class="card-desc">{DESC}</div>
  <div class="card-key">{KEY}</div>
  <div class="card-id">{EMOJI_ID}</div>
  <div class="rating" aria-label="Оценка emoji">
    <button class="star" type="button" data-value="1" onclick="setRating(event, '{EMOJI_ID}', 1)" aria-label="Оценить на 1">★</button>
    <button class="star" type="button" data-value="2" onclick="setRating(event, '{EMOJI_ID}', 2)" aria-label="Оценить на 2">★</button>
    <button class="star" type="button" data-value="3" onclick="setRating(event, '{EMOJI_ID}', 3)" aria-label="Оценить на 3">★</button>
    <button class="star" type="button" data-value="4" onclick="setRating(event, '{EMOJI_ID}', 4)" aria-label="Оценить на 4">★</button>
    <button class="star" type="button" data-value="5" onclick="setRating(event, '{EMOJI_ID}', 5)" aria-label="Оценить на 5">★</button>
  </div>
  <div class="rating-label">оценить</div>
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
            search = f"{e['description'].lower()} {e['key'].lower()} {eid}"
            cards += CARD_TMPL.format(
                SEARCH   = escape(search),
                SEC_ID   = sec_id,
                ORDER    = total,
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
