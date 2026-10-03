# Install and use the skill across agents

This is a self-contained [Agent Skill](https://agentskills.io/specification).
One package works on Windows, macOS and Linux. The host needs file and terminal
access with Python 3.11+; the selector has no pip dependencies, API key or bot
token requirement. Search and profile validation run offline against the bundled
catalog. Inspecting hosted previews requires network and an image/browser tool.

## Install from GitHub

```sh
git clone https://github.com/Zulut30/premium-telegram-emoji.git
cd premium-telegram-emoji
python3 install_skill.py --agent codex
```

On Windows, replace `python3` with `py -3` or the path to your Python 3.11+
interpreter. The installer prints the exact destination. Open a new agent session
after installation. Change `codex` to the host you use:

| `--agent` | Personal installation | Project installation |
| --- | --- | --- |
| `codex` | `~/.agents/skills/telegram-premium-emoji` | `.agents/skills/telegram-premium-emoji` |
| `claude` | `~/.claude/skills/telegram-premium-emoji` | `.claude/skills/telegram-premium-emoji` |
| `cursor` | `~/.cursor/skills/telegram-premium-emoji` | `.cursor/skills/telegram-premium-emoji` |
| `copilot` | `~/.copilot/skills/telegram-premium-emoji` | `.github/skills/telegram-premium-emoji` |
| `opencode` | `~/.config/opencode/skills/telegram-premium-emoji` | `.opencode/skills/telegram-premium-emoji` |
| `universal` | `~/.agents/skills/telegram-premium-emoji` | `.agents/skills/telegram-premium-emoji` |

`~` means the current user's home directory on every OS. OpenCode respects
`XDG_CONFIG_HOME` when set. `universal` is for hosts that discover `.agents/skills`;
other hosts can load the file explicitly. For older Codex environments, use
`--agent codex-legacy`: it honors `CODEX_HOME/skills` or `~/.codex/skills`.
An existing customized skills location can be selected with `--dest`.

```sh
python3 install_skill.py --agent claude
python3 install_skill.py --agent cursor --scope project --project /path/to/application
python3 install_skill.py --agent copilot --dry-run
python3 install_skill.py --dest /path/to/skills
```

`--dest` is the parent skills directory; the installer adds
`telegram-premium-emoji`. It copies an explicit list of runtime code, catalog
data and references. It does not copy the repository's bot, credentials, logs,
virtual environment or Git directory, and does not edit host configuration.

## Download a standalone package

Download `telegram-premium-emoji.zip` from the repository's
[releases](https://github.com/Zulut30/premium-telegram-emoji/releases/latest).
Extract it; the archive contains one `telegram-premium-emoji/` folder. Run
`install_skill.py` inside that folder with the same arguments, or place the whole
folder in a skill directory from the table. Copying only SKILL.md loses the
selector and catalog. `SHA256SUMS` accompanies the download.

`telegram-premium-emoji.skill` contains the same ZIP bytes for hosts that accept
that extension. For a host's web upload, use its documented skill import process;
a successful upload alone does not establish Python execution or preview access.

## Invoke the skill

Ask the host to use `telegram-premium-emoji` for a Telegram bot or mini app:

> Use telegram-premium-emoji to add settings, search and notifications to this
> Telegram application. Keep one minimal icon pack and save emoji-style.json in
> the application. Reuse its choices on future screens.

Codex supports `$telegram-premium-emoji`. Claude Code uses
`/telegram-premium-emoji`; in Cursor select the skill from the `/` menu.
In other hosts, a plain-language request can trigger a discovered skill.
Automatic discovery depends on the agent's version and enabled features.

For an agent without native skill discovery, give it the absolute path to the
installed SKILL.md, ask it to read and follow it, and grant access to that skill
directory and the target application. It can run the same CLI with its own file
and shell tools. An agent without those capabilities can consume the public
JSON index, but cannot perform the full executable selection workflow.

## Test the installed copy

Run from any directory, including an unrelated application:

```sh
python3 "/path/to/skills/telegram-premium-emoji/scripts/select_emoji.py" search "mute notifications" --style minimal
python3 "/path/to/skills/telegram-premium-emoji/scripts/select_emoji.py" search "notifications" --profile "/path/to/application/emoji-style.json"
python3 "/path/to/skills/telegram-premium-emoji/scripts/select_emoji.py" validate "/path/to/application/emoji-style.json"
```

The source repository's `tools/select_emoji.py` remains a compatible entrypoint.
The application profile is independent of the host: the same saved roles, pack,
states and exact string IDs can be reused by another agent or on another OS.
Paths are execution arguments rather than fields embedded in the profile.

## Update

For a Git checkout, pull the new version and refresh the chosen destination:

```sh
git pull --ff-only
python3 install_skill.py --agent codex --update
```

For a ZIP installation, download and extract the new release, then run its
installer with `--update`. Updates replace packaged files while preserving
unrelated local files. Keep application profiles in the application; catalog
updates do not change their bindings. Run `validate` against the refreshed catalog
before reusing a profile. Search does not silently download a new catalog.

## Official discovery documentation

Paths checked on 2026-10-03:
[Codex](https://learn.chatgpt.com/docs/build-skills),
[Claude Code](https://code.claude.com/docs/en/skills),
[Cursor](https://cursor.com/docs/skills),
[GitHub Copilot](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills),
[OpenCode](https://opencode.ai/docs/skills/).
The CI matrix exercises the package and CLI on three operating systems; it does
not run all of these agent products or guarantee identical model decisions.
