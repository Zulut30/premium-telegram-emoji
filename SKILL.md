---
name: telegram-premium-emoji
description: >
  Select verified Telegram custom emoji by meaning, preserve a consistent visual
  style across a bot or application, and generate HTML with catalog IDs. Use when
  a Telegram project needs premium emoji or the user requests a palette from this
  catalog. Includes ordered multi-emoji compositions. Not for unrelated UI icons.
metadata:
  runtime: "Python 3.11+ with file and shell access"
  platforms: "Windows, macOS, Linux; Agent Skills-compatible agents"
---

# Telegram emoji: meaning and a stable application style

Use the entire bundled catalog through `scripts/select_emoji.py`; do not read
thousands of Markdown rows into context. Resolve the skill folder from this
SKILL.md's location, rather than from the application's current directory.
Commands below run from that folder. Elsewhere, quote the absolute script path
and pass an application-specific absolute `--profile` path. Use the available
Python 3.11+ interpreter: `python`, `python3` or `py -3` on Windows. Keep one
interpreter for the workflow. The selector uses only Python's standard library,
does not read bot credentials, and runs offline; preview inspection needs network
access. It has no Codex-specific tools or model/API dependency.

Use the host agent's file, terminal and image/browser tools. If a host cannot
execute Python, use its capable runtime or request one; do not present unexecuted
selection or validation as completed. If previews cannot be inspected, report
that limit before treating a shortlist as visually approved. Installation paths,
manual loading for other agents, and updates are in
[the platform guide](references/platforms.md).

## Understand the role and reuse the application profile

Read the application's existing `emoji-style.json` and emoji helpers first. Infer
the brief from the current task: interface action, topic, tone, existing icon
family, animation, and whether the output is a bot message or another application
surface. Ask about style only if the user has not established it and it materially
changes the result. A neutral interface can start with `minimal`.

Translate the brief into concrete roles such as settings, notification, search,
success, payment, education. Use a function-specific symbol: an alert, an error
and a decoration serve different purposes. Do not choose an unrelated logo
because it has a similar color or a suitable Unicode fallback.
Identify the action separately from its object and state: "delete a file" needs
a delete symbol, while the file is context; "mute notifications" needs a crossed
bell. Preserve negations and constraints when searching. Split a request for
settings and notifications into two roles; one icon need not represent both.

```sh
python scripts/select_emoji.py styles
python scripts/select_emoji.py search "напоминания" --style minimal --limit 8
python scripts/select_emoji.py search "колокольчик без звука" --style minimal
python scripts/select_emoji.py search "уведомления" --animation static --color monochrome --repainting required
python scripts/select_emoji.py search "уведомления" --profile /absolute/application/emoji-style.json
python scripts/select_emoji.py palette --style minimal --roles settings search notification success download --profile /absolute/application/emoji-style.json --save
```

Search returns shortlists with the actual name, exact string ID, preview URL,
source pack, style family, repainting/animation metadata, match evidence and HTML.
Read decision before selecting. matched permits evaluation of candidates marked
recommended; needs_review means the evidence is weak, needs_clarification means
the query has conflicting constraints or multiple roles/styles, and no_match
means no eligible candidate. browse is catalog exploration. Resolve a query from
the application context or search roles separately before asking the user.
full means direct name/key evidence for every primary intent; partial and
category_only are weaker matches. These labels are not probabilities. Do not
promote a category-only match to a role, or use a pack's name as proof of meaning.
Missing roles are explicit: do not fill them with arbitrary symbols.
For a gaming bot, distinguish the game topic from the interface action: a
Minecraft emblem names the game; a backpack opens inventory; a play symbol starts
the game. The selector supports gaming roles and common Russian/English game
aliases. A controller, dice and a play button are distinct roles. Use one pack
for interface roles and an explicitly reviewed topic pack for game emblems.
Read [gaming examples](references/emoji-selection.md#gaming-bots) for supported
roles, alias queries and a coherent bot palette. A matched shortlist still needs
preview review, especially when an abstract role maps to a conventional symbol.
Once a profile exists, pass --profile to searches too. It limits candidates to
the recorded packs, inherits constraints, and prioritizes compatible saved IDs.
saved_roles identifies those choices; catalog_changed reports source updates
without changing bindings. A request for a different style requires a deliberate
profile change, rather than choosing an out-of-style candidate from global search.

## Verify the visual choice and keep one coherent set

Inspect the real previews for the final candidates. Check silhouette, stroke
weight, filled versus outlined shapes, texture, color, animation and readability
at message size. For a multicolor image, adaptive=true alone does not establish
that the entire image is monochrome. Monochrome is separate evidence.
Use --animation, --color and --repainting for requirements established by the
brief. Unknown metadata does not satisfy a strict constraint. Name-derived state
filters narrow candidates; absence of a counter/broken feature does not prove
every visual detail. Check the actual image, especially for "without numbers".

Use one primary pack for ordinary interface roles. Style families narrow the
search; sharing a family does not prove that two artists' packs match. The palette
tool chooses the pack with the best requested-role coverage and keeps existing
role IDs on subsequent runs. Reuse those bindings throughout the application,
including future screens and messages. If a role is missing, first search the
primary pack with another precise description; explain an unresolved gap.

Add a secondary pack only when needed by the brief and its actual appearance
fits. Record its name in secondary_packs, and preserve a single role-to-ID
mapping in the profile. Brand marks may warrant a separate deliberate treatment;
do not silently replace interface symbols with colorful logos. A style change is
an intentional project decision, not a side effect of a newer catalog or ranking.
The palette can fill gaps from already recorded secondary_packs after trying the
primary pack. It stores animation/color/repainting requirements in constraints
and reuses them. Tightening a requirement that conflicts with saved IDs raises
an error without changing the profile; review the affected roles deliberately.

Use descriptive application role keys with --role-query ROLE=QUERY when one
concept has several states: notifications_on and notifications_muted need
different icons. The query is stored with the ID, inherited on later runs, and
checked by validate. After viewing candidates, --bind ROLE=ID saves the exact
reviewed choice instead of accepting the first ranked result. Bindings must fit
their query, state, saved packs and constraints. Reusing a role for a new state or
replacing its saved ID raises an error; introduce a distinct role when needed.
See the selection guide for named-role and binding examples. unresolved_roles
explains gaps; an ambiguous query does not create a role binding.

Default selection excludes uncertain/unavailable images, individual letters,
digits and composition fragments. --include-special is an inspection mode, not
permission to treat every entry as a reliable standalone icon. Do not infer the
picture from the fallback, guess an unknown brand, or invent a numeric ID.

## Whole compositions and typography

```sh
python scripts/select_emoji.py compositions "ПОЛЕЗНОЕ" --pack nexus_base
```

For a pill, keyboard, frame or separator, use the complete ordered assembly.
Preserve all emoji_ids, including repeated IDs, and concatenate tags without
spaces between the parts. Do not sort or deduplicate them. Record intentional
assemblies in composition_roles as {"role": {"key": "catalog_key",
"emoji_ids": ["id1", "id2"]}}. The validator checks their exact order and source.
Incomplete/unavailable assemblies are excluded from default composition search.
For letters or numbers, explicitly inspect the right font pack and preserve its
case/language; do not mix alphabets or artists in one word.

## Apply and validate

Keep the saved profile in the application, alongside the code that uses it.
Render through a shared role-based helper rather than scattering numeric IDs
through different builders. Escape dynamic message content. Copy the returned
html_fallback and HTML; use Telegram HTML parse mode for <tg-emoji>. Handle
environments where custom emoji cannot render with the recorded Unicode emoji.
For a web surface, use the preview URL as an image; <tg-emoji> is Telegram
message markup and does not render as a browser icon.

```sh
python scripts/select_emoji.py validate /absolute/application/emoji-style.json
```

Validation rejects invented/non-string IDs, incompatible packs, uncertain items,
wrong role evidence, incorrect fallbacks, broken composition order, and
animation/color/repainting restrictions for icons and composition parts. Validate
the actual generated application's use of the role mapping as well. Report
remaining gaps rather than claiming that every requested concept was found.

Current sending eligibility and fallback requirements are defined by the
[Telegram Bot API](https://core.telegram.org/bots/api#html-style). A valid emoji
must be inside each <tg-emoji> tag. Owner Premium permits direct private/group/
supergroup messages; bots with additional Fragment usernames have the broader
custom-emoji entitlement. Channel administrator rights alone do not establish
custom-emoji eligibility. Check the actual target when a send fails.

## Data and references

- [Selection guide](references/emoji-selection.md): profiles, examples and limits.
- data/selection-policy.json: maintained style families and bilingual role aliases.
- [Public machine index](https://zulut30.github.io/premium-telegram-emoji/emoji-index.json):
  the current complete catalog, verified metadata, policy and ordered compositions.
- [Pack analysis](references/pack-analysis.md): pack-specific descriptions and ambiguity notes.
- [Compositions](references/emoji-compositions.md): whole assemblies and component order.
- [Raw catalog](references/emoji-catalog.md): exact IDs and legacy aliases when needed.
