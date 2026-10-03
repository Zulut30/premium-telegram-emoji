"""Pure UTF-16 Telegram entity parsing; no SDK, token or network access."""
from __future__ import annotations
from typing import Protocol

class EmojiEntity(Protocol):
    type: str
    custom_emoji_id: str | None
    offset: int
    length: int

class MessageLike(Protocol):
    text: str | None
    entities: list[EmojiEntity] | None


def extract_utf16_char(text: str, offset: int, length: int) -> str:
    """Extract substring using UTF-16 code unit offsets (Telegram API standard)."""
    encoded = text.encode("utf-16-le")
    start = offset * 2
    end   = (offset + length) * 2
    return encoded[start:end].decode("utf-16-le")



def parse_emoji_entries(message: MessageLike) -> list[dict]:
    """
    Extract all custom emoji from a message.

    Returns list of:
        {"emoji_id": str, "fallback": str, "description": str}
    """
    if not message.text or not message.entities:
        return []

    # Collect all custom emoji entities sorted by position
    custom = [
        e for e in message.entities
        if e.type == "custom_emoji" and e.custom_emoji_id
    ]
    if not custom:
        return []

    custom.sort(key=lambda e: e.offset)

    # Build a list of (start_utf16, end_utf16, emoji_id, fallback_char)
    # then figure out the description = text between this emoji and the next (or end)
    text = message.text
    encoded = text.encode("utf-16-le")

    def utf16_to_str_pos(utf16_offset: int) -> int:
        """Convert UTF-16 code unit offset to Python str index."""
        segment = encoded[: utf16_offset * 2].decode("utf-16-le")
        return len(segment)

    entries = []
    for i, entity in enumerate(custom):
        fallback = extract_utf16_char(text, entity.offset, entity.length)

        # Description = text after this emoji up to the next emoji (or end of text)
        after_start_utf16 = entity.offset + entity.length
        if i + 1 < len(custom):
            after_end_utf16 = custom[i + 1].offset
        else:
            after_end_utf16 = len(text.encode("utf-16-le")) // 2

        start_idx = utf16_to_str_pos(after_start_utf16)
        end_idx   = utf16_to_str_pos(after_end_utf16)

        description = text[start_idx:end_idx].strip().strip("-–—").strip()

        if description:
            entries.append({
                "emoji_id":   entity.custom_emoji_id,
                "fallback":   fallback,
                "description": description,
            })

    return entries
