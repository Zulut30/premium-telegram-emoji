---
name: telegram-premium-emoji
description: >
  Select verified Telegram custom emoji by meaning, preserve a consistent visual
  style across a bot or application, and generate HTML with catalog IDs. Use when
  a Telegram project needs premium emoji or the user requests a palette from this
  catalog. Includes ordered multi-emoji compositions. Not for unrelated UI icons.
---

# Telegram emoji: meaning and a stable application style

Use the entire current catalog through `tools/select_emoji.py`; do not read
thousands of Markdown rows into context. Commands below run from the skill folder.
When running elsewhere, use the absolute script path and an application-specific
absolute `--profile` path. No API token or external model is needed for retrieval.

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

```sh
python tools/select_emoji.py styles
python tools/select_emoji.py search "напоминания" --style minimal --limit 8
python tools/select_emoji.py palette --style minimal --roles settings search notification success download --profile /absolute/application/emoji-style.json --save
```

Search returns shortlists with the actual name, exact string ID, preview URL,
source pack, style family, repainting/animation metadata, match evidence and HTML.
Full/partial describes matched intent coverage; it is not a probability that
the identification is correct. Inspect partial results and refine the request.
Missing roles are explicit: do not fill them with arbitrary symbols.

## Verify the visual choice and keep one coherent set

Inspect the real previews for the final candidates. Check silhouette, stroke
weight, filled versus outlined shapes, texture, color, animation and readability
at message size. For a multicolor image, adaptive=true alone does not establish
that the entire image is monochrome. Monochrome is separate evidence.

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

Default selection excludes uncertain/unavailable images, individual letters,
digits and composition fragments. --include-special is an inspection mode, not
permission to treat every entry as a reliable standalone icon. Do not infer the
picture from the fallback, guess an unknown brand, or invent a numeric ID.

## Whole compositions and typography

```sh
python tools/select_emoji.py compositions "ПОЛЕЗНОЕ" --pack nexus_base
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
python tools/select_emoji.py validate /absolute/application/emoji-style.json
```

Validation rejects invented/non-string IDs, incompatible packs, uncertain items,
wrong role evidence, incorrect fallbacks and broken composition order. Validate
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
