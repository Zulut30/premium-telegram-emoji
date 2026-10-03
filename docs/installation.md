# Установка скилла

[← README](../README.md) · [English guide](../references/platforms.md)

В репозитории один скилл — `telegram-premium-emoji`. Он содержит инструкции
для агента, весь каталог и инструмент подбора. Устанавливать бота, aiogram,
локальную модель или API-ключ для работы скилла не нужно.

## Быстрый старт

Нужны Git и Python 3.11 или новее. Установка для одного агента занимает одну
команду после клонирования.

**Windows / PowerShell:**

```powershell
git clone https://github.com/Zulut30/premium-telegram-emoji.git
cd premium-telegram-emoji
py -3 install_skill.py --agent codex
```

**macOS / Linux:**

```bash
git clone https://github.com/Zulut30/premium-telegram-emoji.git
cd premium-telegram-emoji
python3 install_skill.py --agent codex
```

Если Python запускается командой `python`, используй её. Путь к интерпретатору
может быть абсолютным. Установщик напечатает, куда скопировал скилл. Открой
новую сессию агента, затем попроси применить `telegram-premium-emoji`.

## Выбор агента

| Агент | Аргумент | Для всех проектов пользователя | Внутри одного проекта |
| --- | --- | --- | --- |
| Codex | `--agent codex` | `~/.agents/skills/` | `.agents/skills/` |
| Claude Code | `--agent claude` | `~/.claude/skills/` | `.claude/skills/` |
| Cursor | `--agent cursor` | `~/.cursor/skills/` | `.cursor/skills/` |
| GitHub Copilot | `--agent copilot` | `~/.copilot/skills/` | `.github/skills/` |
| OpenCode | `--agent opencode` | `~/.config/opencode/skills/` | `.opencode/skills/` |
| Совместимый агент | `--agent universal` | `~/.agents/skills/` | `.agents/skills/` |

В каждой директории создаётся подпапка `telegram-premium-emoji`.
`~` — домашняя папка пользователя; на Windows обычно `C:\Users\Имя`.
OpenCode учитывает `XDG_CONFIG_HOME`. Для старой установки Codex используй
`--agent codex-legacy`: он учитывает `CODEX_HOME` и каталог `.codex/skills`.
Не дублируй один скилл в нескольких каталогах, которые читает твой агент.
Пути сверены с [официальными источниками](../references/platforms.md#official-discovery-documentation).

### Для команды или отдельного приложения

Укажи существующую папку приложения, в которую нужно установить скилл:

```powershell
py -3 install_skill.py --agent claude --scope project --project "C:\Projects\My Bot"
```

```bash
python3 install_skill.py --agent cursor --scope project --project "/home/me/projects/my-bot"
```

Проектную папку скилла можно добавить в Git приложения, чтобы команда использовала
одну версию. Для удалённого или облачного агента устанавливай скилл в его рабочую
среду или проект; локальная установка не переносится туда автоматически.

### Собственный каталог

```powershell
py -3 install_skill.py --dest "D:\My Agent\skills"
py -3 install_skill.py --agent codex --dry-run
```

`--dest` принимает **родительскую папку скиллов**. `--dry-run` показывает путь и
состав пакета без записи. Установщик не меняет настройки агента.

## Установка без Git

1. Скачай `telegram-premium-emoji.zip` из [последнего релиза](https://github.com/Zulut30/premium-telegram-emoji/releases/latest).
2. Распакуй архив. В нём одна папка `telegram-premium-emoji`.
3. Запусти `install_skill.py` из этой папки с нужным `--agent`, как в примерах выше.

Можно вручную положить **всю папку** в каталог из таблицы. Один `SKILL.md`
содержит инструкции; для поиска ему также нужны Python-файлы и данные.
Рядом с архивом публикуется `SHA256SUMS`. Архив `.skill` содержит те же ZIP-данные
для сред, принимающих это расширение; обычную установку проще делать из `.zip`.

## Как пользоваться

**Codex:**

```text
Используй $telegram-premium-emoji. Подбери эмодзи для настроек, поиска,
уведомлений и оплаты. Сохрани единый минималистичный стиль в emoji-style.json
этого приложения и примени выбранные роли в коде.
```

**Claude Code:** начни запрос с `/telegram-premium-emoji`.
**Cursor:** выбери скилл в меню `/`.
**Copilot / OpenCode:** попроси использовать скилл `telegram-premium-emoji`.

Для следующих изменений:

```text
Добавь экран подписки. Используй telegram-premium-emoji и существующий
emoji-style.json. Сохрани выбранные паки и уже закреплённые ID.
```

Агент определяет действие и состояние, получает кандидатов, проверяет превью,
затем сохраняет точные ID ролей. `notifications_on` и `notifications_muted`
можно закрепить отдельно. Подробности: [подбор и профиль](../references/emoji-selection.md).

### Агент без встроенной поддержки скиллов

Укажи абсолютный путь к установленному `SKILL.md` и попроси прочитать его и
следовать инструкциям. Дай агенту доступ к папке скилла и приложения. Он сможет
использовать тот же инструмент через собственный терминал. Полный процесс требует
Python и доступа к файлам; просмотр превью — сети и инструмента просмотра изображений.
В текстовом чате без исполнения кода установка папки сама по себе не добавляет
возможность выполнить подбор и проверку.

## Проверка и обновление

Проверь установленную копию из любой рабочей папки:

```powershell
py -3 "$env:USERPROFILE\.agents\skills\telegram-premium-emoji\scripts\select_emoji.py" search "колокольчик без звука" --style minimal
```

```bash
python3 "$HOME/.agents/skills/telegram-premium-emoji/scripts/select_emoji.py" search "mute notifications" --style minimal
```

Для другого агента подставь путь, который напечатал установщик.

```bash
git pull --ff-only
python3 install_skill.py --agent codex --update
```

На Windows используй `py -3`. Если устанавливал из ZIP, распакуй новый релиз
и запусти его установщик с `--update`. Заменяются файлы пакета; остальные
локальные файлы сохраняются. `emoji-style.json` храни в самом приложении.
После обновления проверь его командой `validate` из установленного скилла.

## Как устанавливать другие скиллы

У каждого скилла своя папка с `SKILL.md` и ресурсами. Её имя должно соответствовать
полю `name` в начале файла. Используй инструкции автора или импорт скилла в своём
агенте, затем открой новую сессию. Наш `install_skill.py` устанавливает только
`telegram-premium-emoji`; каталоги в таблице пригодны и для других совместимых
скиллов. Требования к Python, внешним инструментам и сети у них могут отличаться.
