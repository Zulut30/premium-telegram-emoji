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

import asyncio
import html
import logging
import os
from config import load_environment
from premium_emoji.paths import DEFAULT_PATHS
from premium_emoji.catalog_store import CatalogStore, CATALOG_WRITE_LOCK, description_to_key, markdown_cell
from premium_emoji.telegram_entities import parse_emoji_entries, extract_utf16_char
from integrations.git_publish import publish_catalog

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

REPO_DIR = DEFAULT_PATHS.root


def load_env() -> None:
    load_environment(REPO_DIR)


load_env()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

ID_FILE = DEFAULT_PATHS.ids
CATALOG_FILE = DEFAULT_PATHS.catalog

def catalog_store() -> CatalogStore:
    return CatalogStore(CATALOG_FILE, ID_FILE)


def catalog_sections() -> dict[str, str]:
    return catalog_store().sections()

# ---------------------------------------------------------------------------
# FSM
# ---------------------------------------------------------------------------

class AddEmoji(StatesGroup):
    waiting_for_section = State()
    waiting_for_section_name = State()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def append_to_id_file(entries: list[dict]) -> None:
    catalog_store().append_ids(entries)


def append_to_catalog(entries: list[dict], section_num: str) -> None:
    catalog_store().append_catalog(entries, section_num)


def git_commit_and_push(entries: list[dict]) -> str:
    return publish_catalog(REPO_DIR, [ID_FILE, CATALOG_FILE], [item["description"] for item in entries])


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
    data = await state.get_data()
    await save_entries(message, state, data["entries"], None, section_name=name)


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


def save_and_publish(entries: list[dict], section_num: str | None, section_name: str = '') -> tuple[str, str]:
    # Serialize writes and publication, while keeping the Telegram event loop free.
    with CATALOG_WRITE_LOCK:
        section_num = catalog_store().save(entries, section_num, section_name=section_name)
        return section_num, git_commit_and_push(entries)


async def save_entries(message: Message, state: FSMContext, entries: list[dict], section_num: str | None,
                       *, section_name: str = '') -> None:
    # Release this accepted request's FSM state before IO. A newer message can
    # start its own request without a late clear erasing that new state.
    await state.clear()
    try:
        section_num, push_result = await asyncio.to_thread(save_and_publish, entries, section_num, section_name)
    except (OSError, ValueError):
        logging.exception("Catalog save failed")
        await message.answer("Не удалось сохранить эмодзи. Проверь запись каталога и подробности в логах перед повторной отправкой.")
        return
    lines = [f"<b>Добавлено в {html.escape(catalog_sections()[section_num])}:</b>"]
    for item in entries:
        key = description_to_key(item["description"])
        lines.append(f"• key: <code>{key}</code> | id: <code>{item['emoji_id']}</code> | {html.escape(item['description'])}")
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
    asyncio.run(main())
