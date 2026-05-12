# Premium Emoji в Telegram-боте — практический гайд

Этот файл — про то, **как заставить вашего бота отправлять анимированные premium-эмодзи** в сообщения, в том числе в публикации канала. Гайд написан под задачу «новостной бот в канале», но всё применимо к любому use-case.

---

## 1. Что такое premium emoji и почему это не «обычные» эмодзи

В Telegram два разных типа эмодзи:

1. **Обычные unicode-эмодзи** — `⭐`, `🔥`, `📰` и т.п. Они работают везде, не требуют ничего.
2. **Premium custom emoji** — анимированные/стилизованные иконки из официальных Telegram-наборов. Каждый имеет уникальный `custom_emoji_id` (число вида `5877597667231534929`). Это **специальный тип Telegram entity**, не unicode.

С точки зрения Bot API custom emoji — это `MessageEntity` с `type="custom_emoji"`, который **накладывается на обычный unicode-символ-плейсхолдер** в тексте. Telegram-клиент при отображении заменяет этот символ на анимированную иконку.

---

## 2. Что нужно, чтобы бот мог отправлять premium emoji

| Требование | Зачем |
|---|---|
| **Telegram Premium у владельца бота** | Боты «наследуют» premium-возможности от своего владельца (того, кто создал бота через @BotFather). Без премиума у владельца бот не сможет отправлять custom emoji. |
| **Бот — администратор канала** | Чтобы публиковать сообщения. Стандартное требование, ничего особенного. |
| **Свежий Telegram-клиент у читателей** | Старые клиенты увидят unicode-плейсхолдер вместо иконки. Это допустимое деградирующее поведение. |
| **`parse_mode="HTML"` в сообщениях** | Удобный способ задать custom emoji. Альтернатива — вручную строить `MessageEntity`. |

⚠️ **Боту НЕ нужна отдельная Premium-подписка для самого бота.** Premium активируется на аккаунте владельца. Если владелец бота отказался от Premium — бот теряет возможность отправлять custom emoji.

---

## 3. Как узнать ID premium-эмодзи

Самый простой способ — через наш бот @chat_brainbot:

1. Откройте меню → **«Инструменты»** → **«🔮 ID Premium Emoji»**
2. Пришлите боту сообщение с любым premium-эмодзи (скопируйте из любого чата)
3. Бот вернёт `custom_emoji_id` и готовый HTML-код

Альтернативы:

- **Forward сообщения с эмодзи** в бота `@LeadConverterTGbot` или `@idstickerbot` (сторонние)
- **Через Bot API напрямую**: ваш бот получает `Message` с `entities`, у каждой entity типа `custom_emoji` есть поле `custom_emoji_id`

---

## 4. Как отправить сообщение с premium emoji

### Способ A: HTML-режим (рекомендуемый — самый простой)

```python
from aiogram import Bot

bot = Bot(token="YOUR_TOKEN")

# Любой символ внутри тега — fallback для не-премиум клиентов.
# Лучше использовать смысловой эмодзи, а не плейсхолдер.
TEXT = """🚨 <tg-emoji emoji-id="5877597667231534929">🔥</tg-emoji> <b>Срочная новость</b>

Текст новости здесь.

<tg-emoji emoji-id="5988023995125993550">🛠</tg-emoji> Подробности на сайте: https://example.com"""

await bot.send_message(
    chat_id="@your_news_channel",
    text=TEXT,
    parse_mode="HTML",
    disable_web_page_preview=False,
)
```

**Синтаксис тега:** `<tg-emoji emoji-id="ЦИФРОВОЙ_ID">UNICODE_FALLBACK</tg-emoji>`

- `emoji-id` — то самое число
- Внутри тега — **обычный unicode emoji** который покажется в старых клиентах или если custom emoji недоступен. Не пишите туда буквы — должен быть именно эмодзи.

### Способ B: Явный `MessageEntity` (для тех кто хочет полный контроль)

```python
from aiogram.types import MessageEntity

# Плейсхолдер-символ занимает 1 «emoji code unit» в тексте.
# offset/length считаются в UTF-16 code units, как требует Telegram API.
text = "🚨 🔥 Срочная новость"
entities = [
    MessageEntity(
        type="custom_emoji",
        offset=3,           # позиция плейсхолдера '🔥' в utf-16
        length=2,           # длина '🔥' в utf-16 = 2 (surrogate pair)
        custom_emoji_id="5877597667231534929",
    ),
]
await bot.send_message(
    chat_id="@your_news_channel",
    text=text,
    entities=entities,
)
```

Считать offset/length правильно сложнее, чем кажется — для эмодзи которые занимают 2 surrogate-пары (некоторые компаунд-эмодзи) длина будет другой. Лучше использовать HTML.

### Способ C: MarkdownV2 (НЕ рекомендую)

MarkdownV2 поддерживает custom emoji через синтаксис `![🔥](tg://emoji?id=5877597667231534929)`, но требует экранировать кучу спецсимволов в остальном тексте. Для большинства задач HTML удобнее.

---

## 5. Шаблон для новостного бота

Готовая функция-обёртка для вашего нового бота:

```python
# news_channel_bot.py
import asyncio
import html as html_escape_module
from typing import Optional

from aiogram import Bot
from aiogram.types import LinkPreviewOptions


# Палитра эмодзи под темы новостей.
# IDs получены через @chat_brainbot → Инструменты → ID Premium Emoji.
EMOJI = {
    "news": "5877597667231534929",
    "tools": "5988023995125993550",
    "copy": "5877301185639091664",
    # ...добавляйте свои
}

# Не забудьте: fallback-символ должен быть unicode emoji, не буквой.
EMOJI_FALLBACK = {
    "news": "🔥",
    "tools": "🛠",
    "copy": "📋",
}


def emoji(key: str) -> str:
    """Собрать HTML-тег premium emoji по короткому имени."""
    eid = EMOJI.get(key)
    fb = EMOJI_FALLBACK.get(key, "⭐")
    if not eid:
        return fb  # graceful fallback на обычный unicode
    return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'


def safe(text: str) -> str:
    """HTML-эскейпинг user-input текста, чтобы '<' / '>' / '&' не ломали разметку."""
    return html_escape_module.escape(text, quote=False)


async def publish_news(
    bot: Bot,
    channel_id: str,
    title: str,
    body: str,
    url: Optional[str] = None,
) -> None:
    """Опубликовать новость в канал с premium emoji."""
    lines = [
        f"{emoji('news')} <b>{safe(title)}</b>",
        "",
        safe(body),
    ]
    if url:
        lines.extend(["", f"{emoji('tools')} Подробнее: {safe(url)}"])

    await bot.send_message(
        chat_id=channel_id,
        text="\n".join(lines),
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=False),
    )


async def main():
    bot = Bot(token="YOUR_BOT_TOKEN")
    try:
        await publish_news(
            bot=bot,
            channel_id="@your_news_channel",
            title="OpenAI выпустила GPT-6",
            body="Новая модель показала рекордные результаты на MMLU и HumanEval.",
            url="https://openai.com/blog/gpt-6",
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
```

**Что важно в этом шаблоне:**

1. **`EMOJI` и `EMOJI_FALLBACK`** разделены — это упрощает поддержку и читаемость кода.
2. **`safe()`** для всего пользовательского контента — title/body могут содержать `<`, `>` и `&`, которые сломают HTML-парсер Telegram.
3. **Graceful fallback** в `emoji()`: если ID не зарегистрирован — отдаём обычный unicode. Бот не падает.
4. **`LinkPreviewOptions`** — современный способ управлять превью ссылок (`disable_web_page_preview` устарело).

---

## 6. Типичные ошибки и как их избежать

| Симптом | Причина | Решение |
|---|---|---|
| `Bad Request: can't parse entities` | Внутри `<tg-emoji>` лежит буква вместо unicode-эмодзи, или эскейпинг сломан | Внутри тега — только эмодзи. Используйте `html.escape()` на user-input |
| Эмодзи отображается как обычный unicode у всех | У владельца бота нет Premium | Купите Premium для аккаунта-владельца |
| Эмодзи отображается только у части юзеров | Часть клиентов слишком старые | Это норма. Fallback-emoji внутри тега сделает текст осмысленным |
| `MessageEntityCustomEmojiInvalid` | ID несуществующий или удалён из набора | Перепроверьте ID. Сторонние боты иногда возвращают мусор |
| Эмодзи появляется, но «странного цвета» | Динамический эмодзи зависит от темы Telegram | Норма — Telegram сам подгоняет под тёмную/светлую тему |
| `Telegram server: TOPIC_CLOSED` или 400 при отправке в канал | Бот не админ или нет права постить | Проверьте `bot.get_chat_member(chat_id, bot.id)` — нужен статус `administrator` с `can_post_messages=True` |

---

## 7. Что НЕЛЬЗЯ через Bot API

- **Реакции premium emoji** на чужие сообщения — Bot API не поддерживает реакции вообще
- **Использовать premium emoji в `bot_name`/`description`** — Bot Profile API не парсит entities
- **Узнать набор (sticker set) из которого эмодзи** — публичный API не отдаёт эту информацию
- **Создать новый premium emoji** — это делается через @stickers/@emojistickers, ручной процесс, бот этим управлять не может

---

## 8. Где брать готовые ID

- **Через наш бот** @chat_brainbot — инструмент «ID Premium Emoji»
- **Из ваших же постов** — если вы вставляли эмодзи в чат-бот сообщения, можно найти ID через `message.entities`
- **Официальные наборы** — в @emojibank или @StickerEmojibot есть базы готовых ID, но эти ID не вечные (наборы могут удаляться)

⚠️ **Не хардкодьте больше 10-15 ID в коде.** Лучше держите в БД/JSON и обновляйте по мере надобности.

---

## 9. Минимальный чек-лист перед запуском новостного бота

- [ ] У владельца бота активна **Telegram Premium** подписка
- [ ] Бот добавлен в канал с правом **«Публиковать сообщения»** (`can_post_messages=True`)
- [ ] Собрана карта `EMOJI_ID → fallback` для всех нужных эмодзи (≤ 20 шт.)
- [ ] Все пользовательские данные пропускаются через `html.escape()`
- [ ] Отправка всегда с `parse_mode="HTML"`
- [ ] Логирование ошибок — `TelegramBadRequest` со стектрейсом, чтобы найти кривой entity
- [ ] Fallback-эмодзи внутри `<tg-emoji>` — реальный unicode, не буква

---

## 10. Полезные ссылки

- [Telegram Bot API — sendMessage](https://core.telegram.org/bots/api#sendmessage)
- [HTML formatting в Bot API](https://core.telegram.org/bots/api#html-style)
- [MessageEntity типа custom_emoji](https://core.telegram.org/bots/api#messageentity)
- [aiogram 3 — отправка сообщений](https://docs.aiogram.dev/en/latest/api/types/message.html)
