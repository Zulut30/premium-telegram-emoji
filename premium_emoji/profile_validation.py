"""Profile validation for verified Telegram emoji."""
from __future__ import annotations

import re
from .policy import POLICY
from .query import query_plan, plan_in_style
from .ranking import fits_constraints, rank


def merged_constraints(saved: dict, requested: dict | None) -> dict:
    result = dict(saved)
    for field, value in (requested or {}).items():
        if field not in POLICY['constraints'] or not isinstance(value, str) or value not in {'', 'any', *POLICY['constraints'][field]}:
            raise ValueError(f'Unknown constraint: {field}={value}')
        if value in {'', 'any'}:
            continue
        if field in result and result[field] not in {'any', value}:
            raise ValueError('Requested constraints conflict with the saved profile')
        result[field] = value
    return result


def validate_profile(data: dict, profile: dict) -> list[str]:
    errors = []
    if not isinstance(profile, dict) or not isinstance(profile.get('roles'), dict) or not isinstance(profile.get('secondary_packs', []), list):
        return ['Profile must be an object with roles and secondary_packs']
    if profile.get('schema_version') != 1:
        errors.append('Unsupported profile schema')
    by_id = {item['id']: item for item in data['items']}
    constraints = profile.get('constraints', {})
    if not isinstance(constraints, dict) or any(field not in POLICY['constraints'] or not isinstance(value, str) or value not in {'any', *POLICY['constraints'][field]}
                                               for field, value in constraints.items()):
        return errors + ['Invalid profile constraints']
    style = profile.get('style')
    allowed = [profile.get('primary_pack'), *profile.get('secondary_packs', [])]
    if not isinstance(style, str) or style not in POLICY['styles']:
        errors.append('Unknown profile style')
    if not profile.get('primary_pack'):
        errors.append('Missing primary pack')
    for pack in allowed:
        if not isinstance(pack, str) or not any(item['pack'] == pack and item['style_family'] == style for item in data['items']):
            errors.append('Unknown or incompatible profile pack')
    for role, saved in profile.get('roles', {}).items():
        if not isinstance(role, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', role):
            errors.append('Invalid role key')
            continue
        if not isinstance(saved, dict):
            errors.append(f'{role}: role must be an object')
            continue
        item = by_id.get(saved.get('id')) if isinstance(saved.get('id'), str) else None
        if not item:
            errors.append(f'{role}: ID is not a catalog string ID')
            continue
        if not item['selectable']:
            errors.append(f'{role}: unavailable, uncertain, or non-standalone emoji')
        if not fits_constraints(item, constraints):
            errors.append(f'{role}: saved emoji violates animation/color/repainting constraints')
        if item['style_family'] != style or item['pack'] not in allowed:
            errors.append(f'{role}: emoji violates the saved style or pack')
        if saved.get('html_fallback') != item['html_fallback']:
            errors.append(f'{role}: fallback differs from the catalog')
        if saved.get('pack') != item['pack']:
            errors.append(f'{role}: saved source pack differs from the catalog')
        if 'query' in saved:
            if not isinstance(saved['query'], str) or not saved['query'].strip():
                errors.append(f'{role}: invalid role query')
            else:
                plan = plan_in_style(saved['query'], style, constraints) if isinstance(style, str) and style in POLICY['styles'] else query_plan(saved['query'])
                evidence = rank(item, plan)
                if not evidence or not evidence['recommended']:
                    errors.append(f'{role}: saved emoji does not satisfy its role query or state')
        elif role not in item['intents']:
            errors.append(f'{role}: icon has no catalog evidence for this role')
    groups = {group['key']: group for group in data['compositions']}
    composition_roles = profile.get('composition_roles', {})
    if not isinstance(composition_roles, dict):
        return errors + ['composition_roles must be an object']
    for role, saved in composition_roles.items():
        group = groups.get(saved.get('key')) if isinstance(saved, dict) else None
        if not group or saved.get('emoji_ids') != group['emoji_ids']:
            errors.append(f'{role}: composition IDs/order/repetitions differ from catalog')
            continue
        if group['pack_name'] not in allowed or group['needs_review']:
            errors.append(f'{role}: composition violates the saved pack or is uncertain')
        if any(by_id[eid]['availability'] or by_id[eid]['needs_review'] or by_id[eid]['style_family'] != style for eid in group['emoji_ids']):
            errors.append(f'{role}: composition contains an unavailable, uncertain, or incompatible part')
        if any(not fits_constraints(by_id[eid], constraints) for eid in group['emoji_ids']):
            errors.append(f'{role}: composition violates animation/color/repainting constraints')
    return errors
