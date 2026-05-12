---
name: telegram-premium-emoji
description: >
  Adds premium Telegram custom emoji to bot messages and generates complete,
  ready-to-run bot code with verified emoji IDs. Use this skill whenever the
  user is building a Telegram bot and mentions emoji, styling, or "beautiful"
  messages — even if they just say "make it look nice". Also triggers for:
  custom_emoji_id questions, tg-emoji HTML tags, animated emoji in channels,
  aiogram / python-telegram-bot / telebot projects that need visual polish,
  or any request to style Telegram channel posts. Always invoke before writing
  Telegram bot code that involves emoji, icons, or message formatting.
---

# Telegram Premium Emoji Skill

Help the user pick the right premium emoji for their bot and generate complete,
working code they can drop straight into their project.

## Step 1 — Understand the bot

If the user hasn't described their bot yet, ask one conversational question:

> "Расскажи про бот: что он делает и какой стиль нужен?  
> Например: «новостной канал, серьёзный» или «крипто-алерты, динамичный»."

If they already explained the bot, skip the question and infer from context.

Also note which **library** they're using (aiogram 3, python-telegram-bot,
telebot, etc.) — the emoji HTML syntax is identical across all of them, but
the send_message call differs. Default to aiogram 3 if unspecified.

**Bot archetypes → emoji needs:**
| Type | Core emoji to include |
|---|---|
| News / media | breaking alert, fire, pin, mic, link, info, calendar |
| Crypto / finance | chart_up, chart_down, dollar/euro/ruble, percent, bell |
| Tools / utilities | settings, search, copy, link, info, bookmark, wrench |
| Entertainment | fire, star, like, heart, live-stream |
| Admin / moderation | ban, cross, checkmark, key, lock |
| Social / community | people, heart, like, hashtag, announcement |
| App-specific | icons from the platform the bot covers (Section 2 or 3) |

## Step 2 — Select emoji

Read `references/emoji-catalog.md` (all four sections) then choose **5–12 emoji**:

- Animated News pack (Section 1) for dynamic content and UI actions
- Static app icons (Section 2) only when the bot explicitly covers those apps
- Animated app icons (Section 3) for GitHub, Discord, Twitch, live stream, stars
- Minimalist B&W icons (Section 4) for clean utility UI

Always include at least one utility emoji (info, link, checkmark) alongside
theme-specific picks — these appear in almost every bot's messages.

For each selected emoji record:
- `key` — short snake_case label used in code
- `emoji_id` — the exact numeric string from the catalog
- `fallback` — a relevant unicode emoji character (not a letter or word!)

## Step 3 — Generate code

Produce a complete, runnable Python file with these components:

### 3a. Imports and compatibility

Always start with:
```python
from __future__ import annotations
```
This one line makes all type annotations forward-compatible with Python 3.9+,
avoiding runtime errors from `list[str] | None` and similar union syntax.

### 3b. EMOJI dict + helpers

```python
import html as _html
import os

# Format: "key": ("emoji_id", "unicode_fallback")
# IDs from <pack name> — https://t.me/addemoji/<pack>
EMOJI: dict[str, tuple[str, str]] = {
    "breaking": ("5456140674028019486", "🚨"),
    "fire":     ("5424972470023104089", "🔥"),
    # ... selected entries
}

def e(key: str) -> str:
    """Return <tg-emoji> tag, or unicode fallback if key unknown."""
    if key not in EMOJI:
        return key
    eid, fb = EMOJI[key]
    return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'

def safe(text: str) -> str:
    """HTML-escape any user-supplied text before embedding in messages."""
    return _html.escape(str(text), quote=False)
```

**Token and channel ID must come from environment variables**, not hardcoded:
```python
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")
```

### 3c. Message builder functions

Write 1–3 builders tailored to the bot type. Each must:
- Compose messages with `e("key")` calls embedded naturally in f-strings
- Wrap every dynamic value (user input, API data, titles, names) in `safe()`
- Set `parse_mode="HTML"` (or `ParseMode.HTML` for aiogram)
- Use `LinkPreviewOptions(is_disabled=True/False)` (not `disable_web_page_preview`)

### 3d. Minimal bot skeleton

A short runnable `main()` showing the builder in action — enough that the user
can paste their token and run it.

**For aiogram 3**, use `DefaultBotProperties(parse_mode=ParseMode.HTML)` on Bot
so you don't need to set parse_mode on every send call.

**For python-telegram-bot**, pass `parse_mode=ParseMode.HTML` on each
`send_message` / `send_photo` call.

**For telebot**, pass `parse_mode="HTML"` to `bot.send_message(...)`.

## Step 4 — Requirements checklist

After the code block, add this as a Python comment block:

```
# Чтобы premium emoji отображались:
# ✅ У владельца бота должна быть активна Telegram Premium подписка
# ✅ Бот добавлен в канал с правом «Публиковать сообщения» (can_post_messages=True)
# ✅ parse_mode="HTML" в каждом send_message
# ✅ Внутри <tg-emoji> — символ unicode-эмодзи, не буква
```

## Hard rules — never break these

**Fallback must be a unicode emoji character.** The character between `<tg-emoji>`
and `</tg-emoji>` is shown to users without Premium. A letter or word there will
cause `Bad Request: can't parse entities` from Telegram.

❌ `<tg-emoji emoji-id="123">fire</tg-emoji>` — letter, will error  
✅ `<tg-emoji emoji-id="123">🔥</tg-emoji>` — unicode emoji, correct

**Always use safe() on dynamic content.** A repo name containing `<`, a news
title with `&`, or a username with `>` will silently corrupt the HTML if not
escaped. The `safe()` wrapper prevents this.

**Never use MarkdownV2 for emoji-heavy messages.** The `<tg-emoji>` tag is
HTML-only. MarkdownV2 has a different syntax (`![🔥](tg://emoji?id=...)`) that
requires escaping dozens of other characters — not worth it.

**Use IDs only from the catalog.** Without the catalog, Claude will hallucinate
plausible-looking but wrong IDs that Telegram rejects with
`MessageEntityCustomEmojiInvalid`.

## References

- `references/emoji-catalog.md` — verified emoji IDs in four categories.
  Read all four sections before selecting emoji.
