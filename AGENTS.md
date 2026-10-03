# Working on Premium Telegram Emoji

## Boundaries

- `premium_emoji/` is the standard-library core. It must not import `bot`,
  `config`, `aiogram`, `integrations` or third-party packages. It must not read
  credentials or call the network. Paths come from `ProjectPaths`, never the cwd.
- `integrations/` contains Telegram previews, static-site output and Git
  publication. `bot.py` and `generate_site.py` are runtime entrypoints.
- Keep `emoji_catalog.py`, `emoji_selection.py`, `scripts/select_emoji.py` and
  `tools/select_emoji.py` compatible. Installed skills use the same core files.
- Python and `web/selection.js` implement the same selection policy. When
  changing selection, update both and run the parity checks.

## Data and profiles

- Telegram IDs are strings. Preserve existing entries and aliases. Maintain
  matching ID sets in `emoji-ids.txt` and `references/emoji-catalog.md`.
- Reviewed labels and metadata live in `data/emoji-packs.json`; selection rules
  live in `data/selection-policy.json`. Do not infer reviewed labels from pack names.
- Preserve `needs_review`, availability markers, and unknown metadata. They
  must not pass strict selection constraints.
- Composition order and repeated IDs are significant. Never deduplicate members.
- Application profiles use schema version 1. Saved roles, queries, exact IDs,
  packs and constraints cannot change silently during selection or updates.

## Checks and delivery

Install `requirements.txt` and run `npm ci`, then use:

```sh
python scripts/project.py check --web
```

This gate validates source data, runs all Python tests (including an extracted
skill package), builds the offline site, checks DOM behavior and Python/JS parity.
CI runs this exact command on Linux, macOS and Windows before publication.
Use `python scripts/project.py validate-data` for a quick data-only check.
If adding a skill runtime file, update the explicit allowlist in
`tools/skill_package.py`. Keep bot adapters and configuration outside the package.

Use `CatalogStore.save()` for coordinated catalog writes. Serialize catalog
writes and Git publication with `CATALOG_WRITE_LOCK`; keep them off the async
Telegram event loop. Git commits must include only catalog paths.

Do not commit `.env`, `.runtime/`, `site/`, `dist/`, dependency folders, tokens,
logs or unrelated work. Preserve existing untracked user files. Read
[docs/architecture.md](docs/architecture.md) before changing module boundaries;
update it when the responsibilities change.
