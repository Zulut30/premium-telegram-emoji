"""Source-data checks used before tests, packaging and publication."""
from __future__ import annotations

import re

from .io import read_json
from .paths import DEFAULT_PATHS, ProjectPaths


def validate_documents(catalog: str, ids_text: str, metadata: dict, compositions: dict, policy: dict) -> list[str]:
    errors = []
    section_ids = re.findall(r'^## Section (\d+) — .+$', catalog, re.MULTILINE)
    if not section_ids or len(section_ids) != len(set(section_ids)):
        errors.append('emoji-catalog.md: sections must exist and have unique numbers')
    catalog_ids = set()
    for line_number, line in enumerate(catalog.splitlines(), 1):
        if not line.startswith('|') or re.match(r'^\|\s*key(?: suggestion)?\s*\||^\|[-| ]+$', line):
            continue
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        if len(cells) != 4 or not re.fullmatch(r'[0-9]+', cells[1]) or not cells[2]:
            errors.append(f'emoji-catalog.md:{line_number}: expected four cells and a string numeric ID with description')
        else:
            catalog_ids.add(cells[1])
    listed_ids = set(re.findall(r'^([0-9]+)\s+-\s+', ids_text, re.MULTILINE))
    for label, values in [('missing from emoji-ids.txt', catalog_ids - listed_ids),
                          ('missing from emoji-catalog.md', listed_ids - catalog_ids)]:
        if values:
            errors.append(f'Catalog IDs {label}: {", ".join(sorted(values)[:10])}')
    known_packs = set(re.findall(r'^## Section \d+ — (.+)$', catalog, re.MULTILINE))
    pack_members = {}
    for pack in metadata['packs']:
        name = pack['name']
        if name in pack_members:
            errors.append(f'emoji-packs.json: duplicate pack {name}')
        members = pack['items']
        if pack['count'] != len(members):
            errors.append(f'emoji-packs.json:{name}: count does not match items')
        known_packs.add(name)
        pack_members[name] = {}
        for item in members:
            eid = item['emoji_id']
            if not isinstance(eid, str) or not re.fullmatch(r'[0-9]+', eid):
                errors.append(f'emoji-packs.json:{name}: emoji_id must be a numeric string')
            elif eid not in catalog_ids:
                errors.append(f'emoji-packs.json:{name}: unknown catalog ID {eid}')
            index = item['pack_index']
            if index in pack_members[name]:
                errors.append(f'emoji-packs.json:{name}: duplicate pack_index {index}')
            pack_members[name][index] = eid
    keys = set()
    for group in compositions['compositions']:
        key = group['key']
        if key in keys:
            errors.append(f'emoji-compositions.json: duplicate key {key}')
        keys.add(key)
        members = group['emoji_ids']
        if not members or any(not isinstance(eid, str) or eid not in catalog_ids for eid in members):
            errors.append(f'emoji-compositions.json:{key}: unknown or non-string member ID')
        if 'pack_indices' in group:
            expected = [pack_members.get(group['pack_name'], {}).get(index) for index in group['pack_indices']]
            if expected != members:
                errors.append(f'emoji-compositions.json:{key}: IDs must follow pack_indices exactly, including repetitions')
    intents, features = policy['intents'], policy['features']
    for action in policy.get('actions', []):
        if action not in intents:
            errors.append(f'selection-policy.json: unknown action {action}')
    for feature in [*policy.get('default_excluded_features', []),
                    *[key for group in policy.get('feature_conflicts', []) for key in group]]:
        if feature not in features:
            errors.append(f'selection-policy.json: unknown feature {feature}')
    assigned = set()
    for style, rule in policy['styles'].items():
        for pack in rule['packs']:
            if pack not in known_packs:
                errors.append(f'selection-policy.json:{style}: unknown pack {pack}')
            if pack in assigned:
                errors.append(f'selection-policy.json:{style}: pack belongs to more than one style: {pack}')
            assigned.add(pack)
    def check_patterns(value, location='selection-policy.json'):
        if not isinstance(value, dict):
            return
        for key, child in value.items():
            path = f'{location}.{key}'
            if (key.endswith('pattern') or '.constraints.' in path) and isinstance(child, str):
                try:
                    re.compile(child)
                except re.error as error:
                    errors.append(f'{path}: invalid regular expression: {error}')
            else:
                check_patterns(child, path)
    check_patterns(policy)
    for feature, rule in features.items():
        if rule.get('implicit_intent') and rule['implicit_intent'] not in intents:
            errors.append(f'selection-policy.json:{feature}: unknown implicit_intent')
    return errors


def validate_sources(paths: ProjectPaths = DEFAULT_PATHS) -> list[str]:
    try:
        return validate_documents(paths.catalog.read_text(encoding='utf-8-sig'),
                                  paths.ids.read_text(encoding='utf-8-sig'), read_json(paths.metadata),
                                  read_json(paths.compositions), read_json(paths.policy))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        return [f'Source data could not be validated: {error}']
