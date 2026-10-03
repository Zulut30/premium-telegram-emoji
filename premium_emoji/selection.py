"""Selection for verified Telegram emoji."""
from __future__ import annotations

from .query import query_plan, plan_in_style, concepts
from .ranking import rank, candidate
from .profile_validation import merged_constraints, validate_profile
from .rendering import emoji_html


def search(data: dict, query: str, *, style: str = '', pack: str = '', limit: int = 12,
           include_special: bool = False, constraints: dict | None = None, profile: dict | None = None) -> dict:
    allowed, saved_roles = [], {}
    if profile is not None:
        errors = validate_profile(data, profile)
        if errors:
            raise ValueError('; '.join(errors))
        if style and style != profile['style']:
            raise ValueError('Requested style conflicts with the saved profile')
        allowed = list(dict.fromkeys([profile['primary_pack'], *profile.get('secondary_packs', [])]))
        if pack and pack not in allowed:
            raise ValueError('Requested pack is not allowed by the saved profile')
        style = profile['style']
        constraints = merged_constraints(profile.get('constraints', {}), constraints)
        for role, saved in profile['roles'].items():
            saved_roles.setdefault(saved['id'], []).append(role)
        plan = plan_in_style(query, style, constraints)
    else:
        plan = query_plan(query, style, constraints)
    results = [result for item in data['items']
               if (not allowed or item['pack'] in allowed)
               if (result := rank(item, plan, pack=pack, include_special=include_special))]
    if profile is not None:
        # Reuse a compatible reviewed choice before offering a new icon. Strong
        # evidence still outranks a broad category in any allowed source.
        results.sort(key=lambda result: (not result['recommended'], result['item']['id'] not in saved_roles,
                     allowed.index(result['item']['pack']), -result['score'], result['item']['order']))
    else:
        results.sort(key=lambda result: (-result['score'], result['item']['order']))
    decision = ('needs_clarification' if plan['warnings'] else 'no_match' if not results else
                'browse' if not plan['intents'] and not plan['terms'] and not plan.get('games') else
                'matched' if results[0]['recommended'] else 'needs_review')
    candidates = [candidate(result) for result in results[:limit]]
    result = {'query': plan, 'decision': decision, 'count': len(results), 'candidates': candidates}
    if profile is not None:
        for item in candidates:
            item['saved_roles'] = saved_roles.get(item['id'], [])
        result['profile_context'] = {'style': style, 'allowed_packs': [pack] if pack else allowed,
            'constraints': constraints, 'catalog_changed': profile.get('catalog_version') != data['catalog_version']}
    return result


def search_compositions(data: dict, query: str, *, pack: str = '', limit: int = 12) -> dict:
    plan = query_plan(query)
    by_id = {item['id']: item for item in data['items']}
    results = []
    for group in data['compositions']:
        if (pack and group['pack_name'] != pack) or group.get('needs_review'):
            continue
        members = [by_id[eid] for eid in group['emoji_ids']]
        if any(item['availability'] or item['needs_review'] for item in members):
            continue
        name = group['name_ru']
        synthetic = {**members[0], 'name': name, 'pack': group['pack_name'], 'selectable': True,
                     'search': name + ' ' + group['pack_name'], 'intents': concepts(name), 'direct_intents': concepts(name)}
        match = rank(synthetic, plan, pack=pack)
        if match:
            results.append({'key': group['key'], 'name': name, 'pack': group['pack_name'],
                            'emoji_ids': group['emoji_ids'], 'html': ''.join(emoji_html(item) for item in members),
                            'score': match['score'], 'notes': group['notes']})
    results.sort(key=lambda group: -group['score'])
    return {'query': plan, 'count': len(results), 'compositions': results[:limit]}
