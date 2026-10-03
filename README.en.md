<div align="center">

![Telegram Premium Emoji — Meaning meets style](docs/assets/hero.svg)

# Telegram Premium Emoji

**Choose emoji by meaning. Keep a consistent style across your application.**

[![Portable skill](https://github.com/Zulut30/premium-telegram-emoji/actions/workflows/skill-package.yml/badge.svg)](https://github.com/Zulut30/premium-telegram-emoji/actions/workflows/skill-package.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Agent Skills](https://img.shields.io/badge/Agent_Skills-compatible-C4A6FF?style=flat-square)](https://agentskills.io/specification)

[Browse catalog](https://zulut30.github.io/premium-telegram-emoji/) · [Install](references/platforms.md) · [Download](https://github.com/Zulut30/premium-telegram-emoji/releases/latest) · [Русский](README.md)

</div>

## A catalog, an agent skill and a collection bot

A verified Telegram custom emoji catalog with **7,092 unique IDs, 68 sections,
13 style families**, and ordered multi-emoji compositions. The portable skill
helps an agent choose suitable symbols, inspect their previews and preserve
exact role bindings in an application's `emoji-style.json`.

- **Catalog:** previews, Russian/English search, pack/style filters, ratings, ID/HTML copying and profile export.
- **Skill:** action and state aware selection, one primary pack, strict animation/color/repainting constraints.
- **CLI:** offline JSON shortlists and profile validation; Python standard library only.
- **Bot:** collects Telegram emoji with descriptions and publishes catalog updates.

The skill follows the [Agent Skills format](https://agentskills.io/specification)
and supports Windows, macOS and Linux. Installation targets are provided for
Codex, Claude Code, Cursor, GitHub Copilot and OpenCode. Other capable agents can
load SKILL.md explicitly and use the same scripts.

## Install

Requires Git and Python 3.11+. No bot token, model API key or pip dependencies are
required for selection.

```bash
git clone https://github.com/Zulut30/premium-telegram-emoji.git
cd premium-telegram-emoji
python3 install_skill.py --agent codex
```

On Windows use `py -3 install_skill.py --agent codex`. Replace `codex` with
`claude`, `cursor`, `copilot`, `opencode` or `universal`. The installer prints
the destination. Open a new agent session after installation.

```bash
# Install for one application, so a team can share the skill
python3 install_skill.py --agent claude --scope project --project "/path/to/application"

# Refresh packaged files while preserving unrelated local files
git pull --ff-only
python3 install_skill.py --agent codex --update
```

Without Git, download and extract the release ZIP and run its `install_skill.py`.
The `.skill` asset is the same ZIP for hosts that accept that extension.
Every release includes SHA-256 checksums.

[Full installation guide](references/platforms.md): native directories, legacy
Codex, custom destinations, remote environments, manual loading and updates.

## Ask your agent

```text
Use telegram-premium-emoji to add settings, search, notifications and payment
icons to this Telegram application. Keep one minimal pack, inspect the previews,
save emoji-style.json in the application and apply the roles in the code.
```

Codex supports `$telegram-premium-emoji`; Claude Code uses
`/telegram-premium-emoji`; Cursor exposes it in the `/` menu. Subsequent requests
should refer to the existing application profile. Its ID bindings are retained
when the catalog grows or another agent works on the project.

## Selection and saved style

The selector distinguishes an action from its contextual object and preserves
negation and icon state. “Delete a file” needs a delete symbol; “mute
notifications” needs a muted bell. Named application roles can represent distinct
states. `--bind ROLE=ID` records the exact candidate approved after preview review.

Category-only matches, uncertain entries and incomplete compositions are not
promoted automatically. Missing roles are reported. Unknown metadata does not
satisfy a strict animation, color or repainting requirement. Full use requires
file/shell access and Python; preview inspection also requires network access and
an image/browser tool. CI tests the package and CLI on three operating systems;
it does not test every agent product or guarantee identical model choices.

```bash
python3 scripts/select_emoji.py search "mute notifications" --style minimal
python3 scripts/select_emoji.py search "notifications" --profile "/path/to/application/emoji-style.json"
python3 scripts/select_emoji.py palette --style minimal --roles settings search notification --profile "/path/to/application/emoji-style.json" --save
python3 scripts/select_emoji.py validate "/path/to/application/emoji-style.json"
```

Run these from the skill folder, or use the absolute script path from another
directory. The `tools/select_emoji.py` entrypoint remains compatible. Use returned
HTML with Telegram's HTML parse mode, and preview URLs as images on web surfaces.

## Explore and contribute

| Resource | Link |
| --- | --- |
| Public machine index | [emoji-index.json](https://zulut30.github.io/premium-telegram-emoji/emoji-index.json) |
| Exact catalog IDs | [emoji-catalog.md](references/emoji-catalog.md) |
| Pack metadata | [emoji-packs.json](data/emoji-packs.json) |
| Agent instructions | [SKILL.md](SKILL.md) |
| Selection details | [emoji-selection.md](references/emoji-selection.md) |
| Bot, imports and development | [Development guide](docs/development.md) |

Submit emoji with descriptions through the collection bot, or contribute a PR
with reviewed names and metadata. Pack imports include visual review before
publication. Catalog content and the bot are independent of the portable skill.
