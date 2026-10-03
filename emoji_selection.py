"""Verified candidates and stable project palettes; no model or API credentials needed."""
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POLICY = json.loads((ROOT / 'data/selection-policy.json').read_text(encoding='utf-8'))
SITE_URL = 'https://zulut30.github.io/premium-telegram-emoji/'


def normalized(value: str) -> str:
    return str(value).lower().replace('ё', 'е').replace('_', ' ')


def spans(pattern: str, value: str) -> list[tuple[int, int]]:
    """Russian stems can inflect; English matches cannot consume part of a brand word."""
    text = normalized(value)
    result = []
    ending = r'(?=$|[^a-z0-9]|(?:s|es|ing|ed)(?=$|[^a-z0-9]))'
    for match in re.finditer(r'(?:^|[^a-zа-я0-9])(' + normalized(pattern) + ')' + ending, text):
        start, end = match.span(1)
        if end and 'a' <= text[end - 1] <= 'z' and end < len(text) and 'a' <= text[end] <= 'z':
            suffix = re.match(r'[a-z]+', text[end:])[0]
            if suffix not in {'s', 'es', 'ing', 'ed'}:
                continue
            end += len(suffix)
        result.append((start, end))
    return result


def matches(pattern: str, value: str) -> bool:
    return bool(spans(pattern, value))


def concepts(value: str) -> list[str]:
    return [key for key, rule in POLICY['intents'].items()
            if normalized(value).strip() == key or matches(rule['pattern'], value)]


def query_plan(query: str, style: str = '', constraints: dict | None = None) -> dict:
    if style and style not in POLICY['styles']:
        raise ValueError(f'Unknown style: {style}')
    remaining = normalized(query)
    required, excluded, excluded_terms, excluded_styles, state_intents = [], [], [], [], []
    found_constraints, warnings = {}, []

    def consume(pattern: str) -> bool:
        nonlocal remaining
        found = spans(pattern, remaining)
        for start, end in reversed(found):
            remaining = remaining[:start] + ' ' * (end - start) + remaining[end:]
        return bool(found)

    for field, choices in POLICY['constraints'].items():
        for value, pattern in choices.items():
            if consume(r'(?:не|без|not|no|without)\s+(?:' + pattern + ')'):
                opposite = next(key for key in choices if key != value)
                if field in found_constraints and found_constraints[field] != opposite:
                    warnings.append('conflicting_constraints')
                found_constraints[field] = opposite
    for field, choices in POLICY['constraints'].items():
        for value, pattern in choices.items():
            if consume(pattern):
                if field in found_constraints and found_constraints[field] != value:
                    warnings.append('conflicting_constraints')
                found_constraints[field] = value
    for key, rule in POLICY['features'].items():
        negative = r'(?:не|без|not|no|without)\s+(?:' + rule['query_pattern'] + ')'
        if consume(negative):
            excluded.append(key)
            if rule.get('implicit_intent'):
                state_intents.append(rule['implicit_intent'])
        if rule.get('opposite_query_pattern') and consume(r'(?:не|без|not|no|without)\s+(?:' + rule['opposite_query_pattern'] + ')'):
            required.append(key)
            if rule.get('implicit_intent'):
                state_intents.append(rule['implicit_intent'])
    for key, rule in POLICY['styles'].items():
        if consume(r'(?:не|без|not|no|without)\s+(?:' + rule['pattern'] + ')[а-я]*'):
            excluded_styles.append(key)
    # Idioms such as "без звука" express a positive disabled-state request.
    for key, rule in POLICY['features'].items():
        if consume(rule['query_pattern']):
            required.append(key)
        if rule.get('opposite_query_pattern') and consume(rule['opposite_query_pattern']):
            excluded.append(key)
            if rule.get('implicit_intent'):
                state_intents.append(rule['implicit_intent'])
    # A negative brand/keyword is a filter, not positive search evidence.
    negative_terms = spans(r'(?:не|без|not|no|without)\s+[a-zа-я0-9]+', remaining)
    for start, end in reversed(negative_terms):
        excluded_terms.append(remaining[start:end].split()[-1])
        remaining = remaining[:start] + ' ' * (end - start) + remaining[end:]
    inferred = [key for key, rule in POLICY['styles'].items() if matches(rule['pattern'], remaining)]
    detected = concepts(remaining)
    if 'shopping' in detected and 'delete' in detected and not matches(POLICY['intents']['delete']['action_pattern'], remaining):
        detected.remove('delete')
    ordered = sorted(detected, key=lambda key: spans(POLICY['intents'][key]['pattern'], remaining)[0][0]
                     if spans(POLICY['intents'][key]['pattern'], remaining) else -1)
    compound = len(ordered) > 1 and bool(re.search(r'\b(?:и|или|and|or)\b|,', remaining))
    actions = [key for key in ordered if key in POLICY['actions']]
    if compound:
        intent_keys, context = detected, []
        warnings.append('multiple_intents')
    else:
        primary = (actions or ordered)[:1]
        intent_keys, context = primary, [key for key in detected if key not in primary]
    if not intent_keys:
        intent_keys = list(dict.fromkeys([*state_intents,
            *[POLICY['features'][key]['implicit_intent'] for key in required
              if POLICY['features'][key].get('implicit_intent')]]))
    tokens = re.findall(r'[a-zа-я0-9]+', remaining)
    terms = []
    for token in tokens:
        if token in POLICY['stop_words'] or concepts(token):
            continue
        if any(matches(rule['pattern'], token) for rule in POLICY['styles'].values()):
            continue
        terms.append(token)
    if not style and len(inferred) > 1:
        specific = [key for key in inferred if key != 'minimal']
        if len(specific) == 1:
            inferred = specific
        else:
            warnings.append('multiple_styles')
    selected_style = style or (inferred[0] if len(inferred) == 1 else '')
    if selected_style in excluded_styles:
        warnings.append('conflicting_constraints')
    for field, value in (constraints or {}).items():
        if value in {'', 'any'}:
            continue
        if field not in POLICY['constraints'] or value not in POLICY['constraints'][field]:
            raise ValueError(f'Unknown constraint: {field}={value}')
        if field in found_constraints and found_constraints[field] != value:
            warnings.append('conflicting_constraints')
        found_constraints[field] = value
    if any(key in excluded for key in required):
        warnings.append('conflicting_constraints')
    if any(all(key in required for key in group) for group in POLICY['feature_conflicts']):
        warnings.append('conflicting_constraints')
    return {'query': query, 'intents': intent_keys, 'context_intents': context, 'terms': terms,
            'style': selected_style, 'constraints': found_constraints, 'features': list(dict.fromkeys(required)),
            'excluded_features': list(dict.fromkeys(excluded)), 'excluded_terms': excluded_terms,
            'excluded_styles': excluded_styles, 'warnings': list(dict.fromkeys(warnings))}


def safe_fallback(value: str) -> str:
    # Original sticker alternatives are preferred; letters and punctuation need a real emoji.
    base = r'[\U0001F000-\U0001F1E5\U0001F200-\U0001F3FA\U0001F400-\U0001FAFF\u2600-\u27BF\u2190-\u23FF\u2B00-\u2BFF\u00A9\u00AE\u203C\u2049\u2122\u2139\u25AA\u25AB\u25B6\u25C0\u25FB-\u25FE\u3030\u303D\u3297\u3299]'
    unit = base + r'(?:\uFE0F|[\U0001F3FB-\U0001F3FF])?'
    pattern = r'(?:[\U0001F1E6-\U0001F1FF]{2}|[0-9#*]\uFE0F?\u20E3|' + unit + r'(?:\u200D' + unit + r')*(?:[\U000E0020-\U000E007E]+\U000E007F)?)'
    if value and re.fullmatch(pattern, value):
        return value
    return '💯' if value == '%' else '✨'


def emoji_html(item: dict) -> str:
    return f'<tg-emoji emoji-id="{item["id"]}">{html.escape(item["html_fallback"])}</tg-emoji>'


def enrich_catalog(data: dict) -> dict:
    """Share the same source policy and item evidence with CLI and browser."""
    families = {pack: key for key, rule in POLICY['styles'].items() for pack in rule['packs']}
    for item in data['items']:
        # Pack prefixes describe provenance, not the meaning of every member.
        key_evidence = item['key']
        prefix = item['pack'].lower() + '_'
        if key_evidence.lower().startswith(prefix):
            key_evidence = key_evidence[len(prefix):]
        evidence = ' '.join([item['name'], key_evidence,
                             *[alias['name'] for alias in item.get('aliases', [])]])
        excluded_intents = {key for key, rule in POLICY['intents'].items()
                            if rule.get('source_exclude_pattern') and matches(rule['source_exclude_pattern'], evidence)}
        item['direct_intents'] = [key for key in concepts(evidence) if key not in excluded_intents]
        item['intents'] = list(dict.fromkeys([*item['direct_intents'],
                            *[key for key in concepts(item.get('subcategory', '')) if key not in excluded_intents]]))
        item['style_family'] = families.get(item['pack'], 'unclassified')
        role = item.get('role', '')
        if role == 'composition_part' or matches('часть|сегмент|фрагмент|половин', item['name']):
            kind = 'fragment'
        elif role in {'letter', 'digit'}:
            kind = role
        else:
            kind = 'emoji'
        item['selection_kind'] = kind
        item['selectable'] = not item.get('needs_review') and not item.get('availability') and kind == 'emoji'
        item['html_fallback'] = safe_fallback(item.get('original_fallback') or item['fallback'])
        item['preview_url'] = '' if item.get('availability') else SITE_URL + f'images/{item["id"]}.png'
        item['features'] = [key for key, rule in POLICY['features'].items() if matches(rule['pattern'], item['name'])]
        if matches('замок|lock', item['name']) and not {'open', 'disabled'} & set(item['features']) and 'closed' not in item['features']:
            item['features'].append('closed')
        item['color_mode'] = ('monochrome' if item['monochrome'] else 'color') if item.get('color_known') else 'unknown'
    data['selection_policy'] = POLICY
    material = [{key: item.get(key) for key in ('id', 'name', 'pack', 'style_family', 'intents', 'direct_intents', 'features', 'color_mode', 'repainting', 'animated', 'selection_kind', 'selectable')}
                for item in data['items']]
    data['catalog_version'] = hashlib.sha256(json.dumps({'items': material, 'policy': POLICY}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    return data


def rank(item: dict, plan: dict, *, pack: str = '', include_special: bool = False) -> dict | None:
    if 'conflicting_constraints' in plan['warnings']:
        return None
    if not include_special and not item['selectable']:
        return None
    if pack and item['pack'] != pack:
        return None
    if plan['style'] and item['style_family'] != plan['style']:
        return None
    if item['style_family'] in plan['excluded_styles'] or not fits_constraints(item, plan['constraints']):
        return None
    if not all(key in item['features'] for key in plan['features']):
        return None
    excluded = set(plan['excluded_features'])
    if plan['intents'] and not include_special:
        excluded.update(key for key in POLICY['default_excluded_features'] if key not in plan['features'])
        if 'lock' in plan['intents'] and 'open' not in plan['features']:
            excluded.add('open')
    if excluded & set(item['features']):
        return None
    text = normalized(item['search'])
    if any(term in text for term in plan['excluded_terms']):
        return None
    if not all(term in text for term in plan['terms']):
        return None
    matched = [key for key in plan['intents'] if key in item['intents']]
    if plan['intents'] and not matched:
        return None
    literal = normalized(plan['query']).strip() in text
    direct = [key for key in matched if key in item.get('direct_intents', item['intents'])]
    context = [key for key in plan['context_intents'] if key in item['direct_intents']]
    score = len(matched) * 20 + len(direct) * 20 + (12 if literal and plan['query'].strip() else 0)
    score += len(context) * 4
    if plan['terms']:
        score += 8 * len(plan['terms'])
    # Names mentioning fewer other functions are more specific evidence for the requested role.
    score -= max(0, len(item['direct_intents']) - len(direct))
    score -= min(3, len(re.findall(r'[a-zа-я0-9]+', normalized(item['name']))) * .15)
    evidence = 'full' if len(direct) == len(plan['intents']) else 'partial' if direct else 'category_only'
    return {'item': item, 'score': score, 'matched_intents': matched, 'direct_intents': direct,
            'matched_context': context, 'match': evidence,
            'recommended': item['selectable'] and bool(plan['intents'] or plan['terms']) and evidence == 'full' and not plan['warnings']}


def fits_constraints(item: dict, constraints: dict) -> bool:
    for field, value in constraints.items():
        if value in {'', 'any'}:
            continue
        if field == 'animation' and item['animated'] is not (value == 'animated'):
            return False
        if field == 'color' and item['color_mode'] != value:
            return False
        if field == 'repainting' and item.get('repainting') is not (value == 'required'):
            return False
    return True


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


def plan_in_style(query: str, style: str, constraints: dict) -> dict:
    plan = query_plan(query, style, constraints)
    inferred = query_plan(query)['style']
    if inferred and inferred != style and 'conflicting_constraints' not in plan['warnings']:
        plan['warnings'].append('conflicting_constraints')
    return plan


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
                'browse' if not plan['intents'] and not plan['terms'] else
                'matched' if results[0]['recommended'] else 'needs_review')
    candidates = [candidate(result) for result in results[:limit]]
    result = {'query': plan, 'decision': decision, 'count': len(results), 'candidates': candidates}
    if profile is not None:
        for item in candidates:
            item['saved_roles'] = saved_roles.get(item['id'], [])
        result['profile_context'] = {'style': style, 'allowed_packs': [pack] if pack else allowed,
            'constraints': constraints, 'catalog_changed': profile.get('catalog_version') != data['catalog_version']}
    return result


def candidate(result: dict) -> dict:
    item = result['item']
    return {**{key: item[key] for key in ('id', 'key', 'name', 'pack', 'style_family', 'html_fallback',
                                          'preview_url', 'selection_kind', 'selectable', 'adaptive', 'monochrome', 'animated', 'color_mode', 'repainting', 'features')},
            'html': emoji_html(item), 'matched_intents': result['matched_intents'], 'direct_intents': result['direct_intents'],
            'matched_context': result['matched_context'], 'recommended': result['recommended'],
            'match': result['match'], 'score': result['score']}


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
