<div align="center">

# ✨ Premium Telegram Emoji

**Верифицированный каталог premium emoji + инструменты для разработчиков Telegram-ботов**

[![GitHub Pages](https://img.shields.io/badge/Catalog-GitHub%20Pages-7c6cfc?style=for-the-badge&logo=github)](https://zulut30.github.io/premium-telegram-emoji/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-009DFF?style=for-the-badge)](https://aiogram.dev)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

[🌐 Открыть каталог](https://zulut30.github.io/premium-telegram-emoji/) · [📦 Установить скилл](#-claude-code-skill) · [🤖 Запустить бота](#-telegram-бот)

</div>

---

## Что это?

Репозиторий решает одну конкретную боль разработчиков Telegram-ботов: **где взять правильные `custom_emoji_id`** и как не тратить час на поиск нужного эмодзи.

Здесь три инструмента, которые работают вместе:

| Инструмент | Что делает |
|---|---|
| 📋 **Каталог** | 275+ верифицированных ID premium emoji с превью, описанием и fallback |
| 🤖 **Бот** | Принимает emoji в Telegram → автоматически добавляет в каталог → пушит в GitHub |
| 🧠 **Claude Skill** | Спрашивает о стиле бота → выбирает подходящие emoji → генерирует готовый aiogram-код |

---

## 🌐 Онлайн-каталог

**[zulut30.github.io/premium-telegram-emoji](https://zulut30.github.io/premium-telegram-emoji/)**

- Превью каждого стикера прямо в браузере
- Поиск по названию и фильтр по секциям
- Нажми на карточку → ID скопирован в буфер
- Обновляется автоматически при каждом пуше в репозиторий

---

## 🧠 Claude Code Skill

Скилл для Claude Code, Cursor и других AI-редакторов. Генерирует полный рабочий код aiogram-бота с premium emoji под ваш стиль.

### Установка

```bash
# Клонируй репозиторий
git clone https://github.com/Zulut30/premium-telegram-emoji.git

# Установи скилл (скопируй в директорию скиллов Claude Code)
# macOS / Linux
cp -r premium-telegram-emoji ~/.claude/skills/telegram-premium-emoji

# Или распакуй .skill файл
unzip premium-telegram-emoji/telegram-premium-emoji.skill \
  -d ~/.claude/skills/telegram-premium-emoji
```

### Использование

Просто попроси Claude:

```
Добавь premium emoji в моего новостного бота
Хочу красивые иконки в боте для криптовалютных сигналов
Сделай бота с premium emoji в стиле минимализм
```

Claude спросит про стиль, выберет подходящие emoji из каталога и сгенерирует:

```python
from __future__ import annotations
import html
import os
from aiogram import Bot
from aiogram.types import LinkPreviewOptions

EMOJI = {
    "breaking": "5456140674028019486",   # 🚨 Срочная новость
    "chart_up": "5449683594425410231",   # 📈 Рост
    "warning":  "5447644880824181073",   # ⚠️ Предупреждение
}

def e(key: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{EMOJI[key]}">{fallback}</tg-emoji>'

async def send_news(bot: Bot, channel: str, title: str, body: str) -> None:
    text = f"{e('breaking', '🚨')} <b>{html.escape(title)}</b>\n\n{html.escape(body)}"
    await bot.send_message(channel, text, parse_mode="HTML")
```

---

## 🤖 Telegram Бот

Бот для пополнения каталога. Отправляешь ему сообщение с premium emoji и описанием — он сам добавляет всё в каталог и пушит в GitHub.

### Быстрый старт

```bash
git clone https://github.com/Zulut30/premium-telegram-emoji.git
cd premium-telegram-emoji

# Создай .env
echo "BOT_TOKEN=ваш_токен_от_BotFather" > .env
echo "GITHUB_TOKEN=ваш_github_pat" >> .env

# Запусти через Docker
docker compose up -d
```

### Как добавить emoji

1. Открой любой чат в Telegram, найди нужный premium emoji
2. Напиши боту: `[emoji] Описание на русском`
3. Выбери секцию (или создай новую кнопкой **➕ Новая секция**)
4. Готово — emoji появится в каталоге и на сайте

```
📩 Входящее сообщение:
🚀 Ракета / запуск

🤖 Ответ бота:
Нашёл:
• 5472169951538224541 — Ракета / запуск (fallback: 🚀)

В какую секцию добавить?
[1 — Новости] [2 — Иконки] [3 — Анимир.] [4 — Минимализм] [➕ Новая секция]
```

### Команды

| Команда | Описание |
|---|---|
| `/start` | Инструкция по использованию |
| `/sections` | Список всех секций каталога |

---

## 📋 Структура каталога

Каталог в [`references/emoji-catalog.md`](references/emoji-catalog.md) разделён по тематике:

| # | Секция | Emoji |
|---|---|---|
| 1 | 📰 Animated News Emoji | Срочные новости, статистика, соцсети |
| 2 | 📱 Static App Icons | GitHub, Docker, Figma, Notion и др. |
| 3 | 🎨 Animated App Icons | Анимированные версии логотипов |
| 4 | ⬛ Minimalist B&W Icons | Минималистичные монохромные иконки |
| 5+ | 🗂 Кастомные секции | Добавляются через бота |

Формат записи:

```markdown
| key          | emoji_id             | description          | fallback |
|---|---|---|---|
| breaking     | 5456140674028019486  | Срочная новость      | 🚨       |
| github       | 4999005636604723783  | GitHub (animated)    | 🐙       |
```

---

## 🏗 Архитектура

```
premium-telegram-emoji/
├── references/
│   └── emoji-catalog.md     # Основной каталог (275+ emoji)
├── SKILL.md                 # Claude Code Skill
├── bot.py                   # Telegram бот (aiogram 3)
├── generate_site.py         # Генератор статического сайта
├── site/                    # Собранный сайт (GitHub Pages)
│   └── images/              # Превью стикеров
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/
    └── deploy-site.yml      # Авто-деплой при пуше
```

**Поток данных:**

```
Telegram сообщение
      ↓
   bot.py                 → emoji-catalog.md
   (aiogram 3)            → emoji-ids.txt
      ↓                   → git commit + push
   GitHub
      ↓
   GitHub Actions         ← BOT_TOKEN (secret)
   generate_site.py
      ↓
   GitHub Pages
   (автообновление)
```

---

## ⚙️ Переменные окружения

| Переменная | Обязательная | Описание |
|---|---|---|
| `BOT_TOKEN` | ✅ | Токен бота от [@BotFather](https://t.me/botfather) |
| `GITHUB_TOKEN` | ☑️ | Personal Access Token для git push из контейнера |

GitHub Actions использует `BOT_TOKEN` как [repository secret](https://docs.github.com/en/actions/security-guides/encrypted-secrets) для генерации сайта.

---

## 🔧 Требования к боту

Чтобы бот мог отправлять premium emoji в канал:

- ✅ **Telegram Premium** у владельца аккаунта, создавшего бота
- ✅ Бот добавлен в канал как **администратор** с правом постить
- ✅ `parse_mode="HTML"` в каждом сообщении с emoji

> 💡 Боту **не нужна** отдельная Premium-подписка — достаточно Premium на аккаунте владельца.

---

## 📖 Как устроен custom emoji в Bot API

```python
# HTML-синтаксис (рекомендуется)
text = '<tg-emoji emoji-id="5456140674028019486">🚨</tg-emoji> Срочная новость'

# Внутри тега — unicode fallback для клиентов без Premium
# emoji-id  — число из каталога этого репозитория
```

Подробно о работе с `MessageEntity`, UTF-16 оффсетах и типичных ошибках — в [оригинальном гайде](references/).

---

## 🤝 Как добавить свои emoji

1. **Через бота** (рекомендуется) — отправь emoji + описание, выбери секцию
2. **Вручную** — отредактируй [`references/emoji-catalog.md`](references/emoji-catalog.md) и [`emoji-ids.txt`](emoji-ids.txt), сделай PR

---

<div align="center">

Сделано с ❤️ для разработчиков Telegram-ботов

</div>
