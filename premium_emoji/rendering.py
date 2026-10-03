"""Rendering for verified Telegram emoji."""
from __future__ import annotations

import html
import re


def safe_fallback(value: str) -> str:
    # Original sticker alternatives are preferred; letters and punctuation need a real emoji.
    base = r'[\U0001F000-\U0001F1E5\U0001F200-\U0001F3FA\U0001F400-\U0001FAFF\u2600-\u27BF\u2190-\u23FF\u2B00-\u2BFF\u00A9\u00AE\u203C\u2049\u2122\u2139\u25AA\u25AB\u25B6\u25C0\u25FB-\u25FE\u3030\u303D\u3297\u3299]'
    unit = base + r'(?:\uFE0F|[\U0001F3FB-\U0001F3FF])?'
    pattern = r'(?:[\U0001F1E6-\U0001F1FF]{2}|[0-9#*]\uFE0F?\u20E3|' + unit + r'(?:\u200D' + unit + r')*(?:[\U000E0020-\U000E007E]+\U000E007F)?)'
    if value and re.fullmatch(pattern, value):
        return value
    return '💯' if value == '%' else '✨'


def emoji_html(item: dict) -> str:
    return f'<tg-emoji emoji-id="{item["id"]}">{html.escape(item["html_fallback"])}</tg-emoji>'
