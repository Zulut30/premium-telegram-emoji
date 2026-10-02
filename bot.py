"""
Бот для добавления premium emoji в каталог.

Формат сообщения:
  <premium_emoji> Описание на русском
  <premium_emoji> Описание 1
  <premium_emoji> Описание 2
  (несколько в одном сообщении тоже работает)

Бот распознаёт custom_emoji_id из entities, спрашивает секцию,
предлагает key и добавляет в оба файла + делает git commit + push.
"""

from __future__ import annotations

import base64
import html
import logging
import os
import re
import subprocess
from pathlib import Path
from config import load_environment

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_DIR = Path(__file__).resolve().parent


def load_env() -> None:
    load_environment(REPO_DIR)


load_env()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

ID_FILE      = REPO_DIR / "emoji-ids.txt"
CATALOG_FILE = REPO_DIR / "references" / "emoji-catalog.md"

def catalog_sections() -> dict[str, str]:
    return {
        match.group(1): match.group(0)[3:]
        for match in re.finditer(
            r"^## Section (\d+) — .+$",
            CATALOG_FILE.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    }

# ---------------------------------------------------------------------------
# FSM
# ---------------------------------------------------------------------------

class AddEmoji(StatesGroup):
    waiting_for_section = State()
    waiting_for_section_name = State()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_utf16_char(text: str, offset: int, length: int) -> str:
    """Extract substring using UTF-16 code unit offsets (Telegram API standard)."""
    encoded = text.encode("utf-16-le")
    start = offset * 2
    end   = (offset + length) * 2
    return encoded[start:end].decode("utf-16-le")


def parse_emoji_entries(message: Message) -> list[dict]:
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


def description_to_key(description: str) -> str:
    """Suggest a snake_case key from a Russian description."""
    # Very naive: take first meaningful word, transliterate roughly
    translit = {
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e",
        "ж":"zh","з":"z","и":"i","й":"j","к":"k","л":"l","м":"m",
        "н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u",
        "ф":"f","х":"h","ц":"ts","ч":"ch","ш":"sh","щ":"sch",
        "ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya",
    }
    word = description.split()[0].lower()
    key = "".join(translit.get(c, c) for c in word)
    key = re.sub(r"[^a-z0-9]", "_", key).strip("_")
    return key or "emoji"


def section_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=title.removeprefix("Section "), callback_data=f"sec_{number}"
        )
        for number, title in catalog_sections().items()
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="➕ Новая секция", callback_data="new_section")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def markdown_cell(value: str) -> str:
    return " ".join(value.split()).replace("|", "&#124;")


def append_to_id_file(entries: list[dict]) -> None:
    with open(ID_FILE, "a", encoding="utf-8") as f:
        for e in entries:
            f.write(f"\n{e['emoji_id']} - {' '.join(e['description'].split())}")


def append_to_catalog(entries: list[dict], section_num: str) -> None:
    section_header = f"## {catalog_sections()[section_num]}"
    text = CATALOG_FILE.read_text(encoding="utf-8")

    # Find the end of the target section (before the next ## or end of file)
    section_pos = text.find(section_header)
    if section_pos == -1:
        # Section not found — append at end
        with open(CATALOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n\n{section_header}\n\n")
            f.write("| key suggestion | emoji_id | description | fallback |\n")
            f.write("|---|---|---|---|\n")
            for e in entries:
                key = description_to_key(e["description"])
                f.write(f"| {key} | {e['emoji_id']} | {markdown_cell(e['description'])} | {markdown_cell(e['fallback'])} |\n")
        return

    # Find insertion point = just before the next section header or end
    next_section = text.find("\n## ", section_pos + len(section_header))
    section_end = next_section if next_section != -1 else len(text)
    # Keep new entries inside the existing table, before notes and separators.
    table_rows = list(re.finditer(r"^\|.*\|[ \t]*$", text[section_pos:section_end], re.MULTILINE))
    insert_at = section_pos + table_rows[-1].end() if table_rows else section_end

    new_rows = ""
    for e in entries:
        key = description_to_key(e["description"])
        new_rows += f"| {key} | {e['emoji_id']} | {markdown_cell(e['description'])} | {markdown_cell(e['fallback'])} |\n"

    updated = text[:insert_at].rstrip() + "\n" + new_rows.rstrip("\n") + text[insert_at:]
    if not updated.endswith("\n"):
        updated += "\n"
    CATALOG_FILE.write_text(updated, encoding="utf-8")


def git_commit_and_push(entries: list[dict]) -> str:
    descriptions = ", ".join(e["description"] for e in entries)
    try:
        subprocess.run(
            ["git", "add",
             str(ID_FILE.relative_to(REPO_DIR)),
             str(CATALOG_FILE.relative_to(REPO_DIR))],
            cwd=REPO_DIR, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"Add emoji: {descriptions}"],
            cwd=REPO_DIR, check=True, capture_output=True
        )

        # Pass optional authentication only in the child process environment.
        github_token = os.getenv("GITHUB_TOKEN", "")
        push_env = os.environ.copy()
        push_env["GIT_TERMINAL_PROMPT"] = "0"
        if github_token:
            credential = base64.b64encode(f"x-access-token:{github_token}".encode()).decode()
            config_index = int(push_env.get("GIT_CONFIG_COUNT", "0"))
            push_env["GIT_CONFIG_COUNT"] = str(config_index + 1)
            push_env[f"GIT_CONFIG_KEY_{config_index}"] = "http.https://github.com/.extraheader"
            push_env[f"GIT_CONFIG_VALUE_{config_index}"] = f"AUTHORIZATION: basic {credential}"

        result = subprocess.run(
            ["git", "push"],
            cwd=REPO_DIR, capture_output=True, text=True, env=push_env
        )

        if result.returncode == 0:
            return "✅ Запушено в GitHub"
        else:
            return "⚠️ Файлы сохранены локально, но push не удался. Проверь доступ к GitHub."
    except subprocess.CalledProcessError as exc:
        return "⚠️ Файлы сохранены локально, но Git не смог создать коммит. Проверь настройки Git."


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Отправь мне сообщение с premium emoji и описанием.\n\n"
        "<b>Формат:</b>\n"
        "<code>&lt;emoji&gt; Описание</code>\n\n"
        "Можно несколько в одном сообщении:\n"
        "<code>&lt;emoji1&gt; Первый\n&lt;emoji2&gt; Второй</code>",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("sections"))
async def cmd_sections(message: Message) -> None:
    await message.answer("\n".join(html.escape(title) for title in catalog_sections().values()))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Добавление отменено. Отправь новое сообщение с emoji и описанием.")


@router.callback_query(AddEmoji.waiting_for_section, F.data == "new_section")
async def handle_new_section(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddEmoji.waiting_for_section_name)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Напиши название новой секции. Для отмены: /cancel")
    await callback.answer()


@router.message(AddEmoji.waiting_for_section_name, F.text)
async def handle_section_name(message: Message, state: FSMContext) -> None:
    name = " ".join(message.text.split()).strip()
    if not name or len(name) > 80:
        await message.answer("Название должно содержать от 1 до 80 символов.")
        return
    sections = catalog_sections()
    section_num = str(max(map(int, sections), default=0) + 1)
    with CATALOG_FILE.open("a", encoding="utf-8") as catalog:
        catalog.write(f"\n\n## Section {section_num} — {name}\n\n")
        catalog.write("| key suggestion | emoji_id | description | fallback |\n|---|---|---|---|\n")
    data = await state.get_data()
    await save_entries(message, state, data["entries"], section_num)


@router.message(F.entities)
async def handle_message_with_entities(message: Message, state: FSMContext) -> None:
    entries = parse_emoji_entries(message)
    if not entries:
        await message.answer("Не нашёл premium emoji с описанием. Попробуй ещё раз.")
        return

    # Show what was found
    lines = ["<b>Нашёл:</b>"]
    for e in entries:
        lines.append(f"• <code>{e['emoji_id']}</code> — {html.escape(e['description'])} (fallback: {html.escape(e['fallback'])})")
    lines.append("\nВ какую секцию добавить?")

    await state.update_data(entries=entries)
    await state.set_state(AddEmoji.waiting_for_section)
    await message.answer("\n".join(lines), reply_markup=section_keyboard())


@router.callback_query(AddEmoji.waiting_for_section, F.data.startswith("sec_"))
async def handle_section_choice(callback: CallbackQuery, state: FSMContext) -> None:
    section_num = callback.data.split("_")[1]
    data = await state.get_data()
    entries = data["entries"]

    if section_num not in catalog_sections():
        await callback.answer("Секция больше не существует. Отправь emoji ещё раз.")
        return
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await save_entries(callback.message, state, entries, section_num)


async def save_entries(message: Message, state: FSMContext, entries: list[dict], section_num: str) -> None:

    # Update files
    append_to_id_file(entries)
    append_to_catalog(entries, section_num)
    push_result = git_commit_and_push(entries)
    await state.clear()

    # Summary
    lines = [f"<b>Добавлено в {html.escape(catalog_sections()[section_num])}:</b>"]
    for e in entries:
        key = description_to_key(e["description"])
        lines.append(f"• key: <code>{key}</code> | id: <code>{e['emoji_id']}</code> | {html.escape(e['description'])}")
    lines.append(f"\n{push_result}")

    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not BOT_TOKEN:
        raise RuntimeError("Нет BOT_TOKEN — задай переменную окружения или .env файл")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
