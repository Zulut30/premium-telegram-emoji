"""Profiles for verified Telegram emoji."""
from __future__ import annotations

import re
from .policy import POLICY
from .query import normalized, plan_in_style
from .ranking import rank, candidate
from .profile_validation import merged_constraints, validate_profile
from .selection import search
from .rendering import emoji_html


def palette(data: dict, roles: list[str], *, style: str = '', pack: str = '', profile: dict | None = None,
            constraints: dict | None = None, role_queries: dict | None = None, bindings: dict | None = None) -> dict:
    existing = profile or {}
    role_queries = {} if role_queries is None else role_queries
    bindings = {} if bindings is None else bindings
    if profile is not None:
        errors = validate_profile(data, profile)
        if errors:
            raise ValueError('; '.join(errors))
        if (style and style != profile['style']) or (pack and pack != profile['primary_pack']):
            raise ValueError('Requested style/pack conflicts with the saved profile; use a different profile path to change it')
        style, pack = profile['style'], profile['primary_pack']
    requested = list(dict.fromkeys(roles))
    if not requested or any(not isinstance(role, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', role) for role in requested):
        raise ValueError('Palette role keys must be lowercase names such as notification or notifications_muted')
    if not isinstance(role_queries, dict) or not isinstance(bindings, dict) or (role_queries.keys() | bindings.keys()) - set(requested):
        raise ValueError('Role queries and bindings must refer to requested roles')
    queries, by_id = {}, {item['id']: item for item in data['items']}
    for role in requested:
        saved = existing.get('roles', {}).get(role, {})
        query = role_queries.get(role, saved.get('query', role if role in POLICY['intents'] else ''))
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f'{role}: provide --role-query for a custom role')
        if role in role_queries and saved.get('query') and normalized(query).split() != normalized(saved['query']).split():
            raise ValueError(f'{role}: role query conflicts with the saved profile; use a new role for a different state')
        if role in bindings:
            eid = bindings[role]
            if not isinstance(eid, str) or eid not in by_id:
                raise ValueError(f'{role}: binding must be a catalog string ID')
            if saved and saved['id'] != eid:
                raise ValueError(f'{role}: binding conflicts with the saved ID; use a new role or profile')
        queries[role] = query
    if profile is None and bindings:
        bound_packs = {by_id[eid]['pack'] for eid in bindings.values()}
        if len(bound_packs) != 1:
            raise ValueError('New profile bindings must use one primary pack')
        bound_pack = next(iter(bound_packs))
        if pack and pack != bound_pack:
            raise ValueError('Binding pack conflicts with the requested primary pack')
        pack = pack or bound_pack
        style = style or by_id[next(iter(bindings.values()))]['style_family']
    style = style or 'minimal'
    if style not in POLICY['styles']:
        raise ValueError(f'Unknown style: {style}')
    selected_constraints = merged_constraints(existing.get('constraints', {}), constraints)
    # Validate new restrictions against existing IDs before considering any write.
    if profile is not None:
        errors = validate_profile(data, {**profile, 'constraints': selected_constraints})
        if errors:
            raise ValueError('; '.join(errors))
    plans = {role: plan_in_style(query, style, selected_constraints) for role, query in queries.items()}
    for role, query in role_queries.items():
        saved = existing.get('roles', {}).get(role)
        if saved:
            checked = rank(by_id[saved['id']], plans[role])
            if not checked or not checked['recommended']:
                raise ValueError(f'{role}: role query conflicts with the saved emoji or state')
    packs = [pack] if pack else sorted({item['pack'] for item in data['items'] if item['style_family'] == style})
    allowed = [*packs, *existing.get('secondary_packs', [])]
    for role, eid in bindings.items():
        item = by_id[eid]
        if item['pack'] not in allowed or item['style_family'] != style:
            raise ValueError(f'{role}: binding violates the saved style or allowed packs')
        checked = rank(item, plans[role])
        if not checked or not checked['recommended']:
            raise ValueError(f'{role}: binding does not satisfy its role query, state or constraints')
    options = []
    for source in packs:
        selected, unresolved = {}, {}
        for role in requested:
            if role in existing.get('roles', {}):
                continue
            if role in bindings:
                selected[role] = candidate(rank(by_id[bindings[role]], plans[role]))
                continue
            allowed_sources = [source, *existing.get('secondary_packs', [])]
            decision = 'needs_clarification' if plans[role]['warnings'] else 'no_match'
            for allowed in allowed_sources:
                if plans[role]['warnings']:
                    break
                result = search(data, queries[role], style=style, pack=allowed, limit=12, constraints=selected_constraints)
                suitable = next((item for item in result['candidates'] if item['recommended']), None)
                if suitable:
                    selected[role] = suitable
                    break
                if result['decision'] == 'needs_review':
                    decision = 'needs_review'
            if role not in selected:
                unresolved[role] = {'query': queries[role], 'decision': decision}
        options.append((len(selected), sum(item['score'] for item in selected.values()), source, selected, unresolved))
    if not options:
        raise ValueError(f'No packs for style {style}')
    options.sort(key=lambda option: (-option[0], -option[1], option[2]))
    _, _, source, selected, unresolved = options[0]
    if pack and not any(item['pack'] == pack and item['style_family'] == style for item in data['items']):
        raise ValueError('Pack does not belong to the requested style')
    # Existing role IDs are authoritative; rankings may evolve as the catalog grows.
    saved = dict(existing.get('roles', {}))
    for role, item in selected.items():
        if role not in saved:
            saved[role] = {key: item[key] for key in ('id', 'key', 'name', 'pack', 'html_fallback')}
            if role in role_queries or role not in POLICY['intents']:
                saved[role]['query'] = queries[role]
    for role, query in role_queries.items():
        if role in saved and 'query' not in saved[role]:
            saved[role] = {**saved[role], 'query': query}
    result = {**existing, 'schema_version': 1, 'style': style, 'primary_pack': source,
              'secondary_packs': existing.get('secondary_packs', []), 'roles': saved,
              'catalog_version': data['catalog_version']}
    if selected_constraints:
        result['constraints'] = selected_constraints
    return {'profile': result, 'missing_roles': [role for role in requested if role not in saved],
            'unresolved_roles': unresolved,
            'html': {role: emoji_html(saved[role]) for role in requested if role in saved}}
