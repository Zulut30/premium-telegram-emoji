# Разработка, бот и импорт

[← README](../README.md) · [Установка скилла](installation.md)

## Запуск бота

Бот принимает Telegram custom emoji с описанием, предлагает раздел каталога,
добавляет записи и выполняет commit/push. Для него нужны зависимости из
`requirements.txt`; для скилла они не нужны.

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Запиши BOT_TOKEN=токен_от_BotFather в локальный .env
.\Start-Bot.ps1
# Остановка:
.\Stop-Bot.ps1
```

Процесс работает в фоне, пока включён компьютер. Логи находятся в `.runtime/`.
На Windows резервный токен может храниться в `.runtime/bot-token.dpapi` под
защитой текущего пользователя. `.env`, резервный токен и логи исключены из Git.

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# Запиши BOT_TOKEN=токен_от_BotFather в локальный .env
.venv/bin/python bot.py
```

Этот пример запускает процесс в текущем терминале. Постоянный запуск на сервере
настраивается средствами выбранной платформы.

### Docker

Создай локальный `.env` с `BOT_TOKEN`. Для push используй авторизованный Git
или `GITHUB_TOKEN` для контейнера. Запусти `docker compose up -d` из репозитория.

| Переменная | Назначение |
| --- | --- |
| `BOT_TOKEN` | Доступ бота к Telegram и загрузка превью для сборки сайта |
| `GITHUB_TOKEN` | Авторизация Git из контейнера, если Git не настроен другим способом |

Для GitHub Actions `BOT_TOKEN` задаётся в repository secrets. Скилл не читает
ни окружение бота, ни защищённое локальное хранилище.

Команды бота: `/start`, `/sections`, `/cancel`. Для добавления отправь
`[premium emoji] Описание на русском`, затем выбери или создай раздел.

### Отправка custom emoji

```python
text = '<tg-emoji emoji-id="6021536113108196448">🔔</tg-emoji> Уведомления'
await bot.send_message(chat_id, text, parse_mode="HTML")
```

Внутри `<tg-emoji>` нужен действительный Unicode emoji. По
[Telegram Bot API](https://core.telegram.org/bots/api#html-style), Premium у
владельца разрешает такие сообщения бота напрямую в личных чатах, группах и
супергруппах; дополнительные имена, приобретённые на Fragment, дают более широкую
возможность использования. Права администратора канала сами по себе её не
предоставляют. Проверяй возможность отправки для фактического назначения.

<a id="import-packs"></a>

## Импорт паков

Проверенные названия и метаданные находятся в `data/emoji-packs.json`; словарь
семантического поиска — в `data/selection-policy.json`. Неоднозначные изображения
помечаются `needs_review`; недоступные файлы также отмечаются отдельно.

Для подготовки визуального анализа установи `requirements-inspection.txt`.
Инструменты `tools/inspect_packs.py` и `tools/inspect_animations.py` создают
материалы для просмотра. После реального просмотра сохраняй проверенные подписи
в `data/labels/` и отметки в `data/import-batches/*-review.json`.

```bash
python3 tools/review_pack_batch.py data/import-batches/2026-10-03.json
python3 tools/import_pack_batch.py data/import-batches/2026-10-03.json
```

Импорт сначала проверяется без записи; `--write-catalog` применяет его.
`tools/import_reviewed_packs.py --write-catalog` добавляет проверенные записи,
пропуская имеющиеся ID. История анализа: [pack-analysis.md](../references/pack-analysis.md).

## Сборка и проверки

```bash
python3 generate_site.py --offline
python3 -m unittest discover -s tests -v
python3 tools/skill_package.py --output dist
```

Для полного набора тестов бота нужны `requirements.txt`. Тесты подбора и
переносимости используют только стандартную библиотеку Python:

```bash
python3 -m unittest discover -s tests -p 'test_selection*.py' -v
python3 -m unittest discover -s tests -p 'test_skill*.py' -v
```

Офлайн-сборка сайта использует уже скачанные превью. Для их загрузки нужен
`BOT_TOKEN`; CI берёт его из секрета. Изменения общего загрузчика проверяются
также тестами сайта и составных изображений.

Интерфейс и согласованность ранжирования:

```bash
npm install --prefix .runtime/catalog-qa --no-audit --no-fund jsdom
node tests/catalog_dom.cjs
node tests/selection_parity.cjs
```

DOM-проверки дополняются просмотром в реальном браузере при изменениях интерфейса.
Файлы `web/` собираются в игнорируемую папку `site/`.

## Пакет и релиз скилла

`tools/skill_package.py` собирает ZIP с одной папкой `telegram-premium-emoji`,
копию с расширением `.skill` и `SHA256SUMS`. Внутренний `skill-manifest.json`
содержит версию каталога и хеши файлов. Пакет строится из явного списка;
бот, `.git`, `.env`, токены, логи и установленные зависимости не включаются.

Workflow `Portable skill` проверяет поиск, профили и реальную установку
распакованного пакета на Windows, macOS и Linux с Python 3.11. Он также запускает
подбор из сторонней папки с Unicode и пробелами в пути. Архивы доступны в
артефактах успешного workflow. Теги `skill-v*` публикуют эти архивы в GitHub Releases
после успешной матрицы проверок.

Пакет — снимок каталога на момент сборки. Для нового каталога установи обновление;
сам поиск не обращается к сети. Профили приложений проверяются обновлённым
валидатором, а закреплённые ID сохраняются.
