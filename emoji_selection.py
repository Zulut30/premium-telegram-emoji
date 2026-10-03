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
    required, excluded, excluded_terms, excluded_styles = [], [], [], []
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
    for key, rule in POLICY['styles'].items():
        if consume(r'(?:не|без|not|no|without)\s+(?:' + rule['pattern'] + ')[а-я]*'):
            excluded_styles.append(key)
    # Idioms such as "без звука" express a positive disabled-state request.
    for key, rule in POLICY['features'].items():
        if consume(rule['query_pattern']):
            required.append(key)
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
    if not intent_keys and required:
        intent_keys = list(dict.fromkeys(POLICY['features'][key]['implicit_intent'] for key in required
                                        if POLICY['features'][key].get('implicit_intent')))
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
            'style': selected_style, 'constraints': found_constraints, 'features': required,
            'excluded_features': excluded, 'excluded_terms': excluded_terms,
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
    score -= max(0, len(item['intents']) - len(matched))
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


def search(data: dict, query: str, *, style: str = '', pack: str = '', limit: int = 12,
           include_special: bool = False, constraints: dict | None = None) -> dict:
    plan = query_plan(query, style, constraints)
    results = [result for item in data['items']
               if (result := rank(item, plan, pack=pack, include_special=include_special))]
    results.sort(key=lambda result: (-result['score'], result['item']['order']))
    decision = ('needs_clarification' if plan['warnings'] else 'no_match' if not results else
                'browse' if not plan['intents'] and not plan['terms'] else
                'matched' if results[0]['recommended'] else 'needs_review')
    return {'query': plan, 'decision': decision, 'count': len(results),
            'candidates': [candidate(result) for result in results[:limit]]}


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
    if not isinstance(constraints, dict) or any(field not in POLICY['constraints'] or value not in {'any', *POLICY['constraints'][field]}
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
        if role not in item['intents']:
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
            constraints: dict | None = None) -> dict:
    existing = profile or {}
    if profile is not None:
        errors = validate_profile(data, profile)
        if errors:
            raise ValueError('; '.join(errors))
        if (style and style != profile['style']) or (pack and pack != profile['primary_pack']):
            raise ValueError('Requested style/pack conflicts with the saved profile; use a different profile path to change it')
        style, pack = profile['style'], profile['primary_pack']
    style = style or 'minimal'
    if style not in POLICY['styles']:
        raise ValueError(f'Unknown style: {style}')
    selected_constraints = dict(existing.get('constraints', {}))
    for field, value in (constraints or {}).items():
        if value and value != 'any':
            if field in selected_constraints and selected_constraints[field] not in {'any', value}:
                raise ValueError('Requested constraints conflict with the saved profile')
            selected_constraints[field] = value
    # Validate new restrictions against existing IDs before considering any write.
    if profile is not None:
        errors = validate_profile(data, {**profile, 'constraints': selected_constraints})
        if errors:
            raise ValueError('; '.join(errors))
    requested = list(dict.fromkeys(roles))
    if not requested or any(not re.fullmatch(r'[a-z][a-z0-9_]*', role) or role not in POLICY['intents'] for role in requested):
        raise ValueError('Palette roles must be known intent keys; use styles to list them')
    packs = [pack] if pack else sorted({item['pack'] for item in data['items'] if item['style_family'] == style})
    options = []
    for source in packs:
        selected = {}
        for role in requested:
            allowed_sources = [source, *existing.get('secondary_packs', [])]
            for allowed in allowed_sources:
                result = search(data, role, style=style, pack=allowed, limit=12, constraints=selected_constraints)
                suitable = next((item for item in result['candidates'] if item['recommended']), None)
                if suitable:
                    selected[role] = suitable
                    break
        options.append((len(selected), sum(item['score'] for item in selected.values()), source, selected))
    if not options:
        raise ValueError(f'No packs for style {style}')
    options.sort(key=lambda option: (-option[0], -option[1], option[2]))
    _, _, source, selected = options[0]
    if pack and not any(item['pack'] == pack and item['style_family'] == style for item in data['items']):
        raise ValueError('Pack does not belong to the requested style')
    # Existing role IDs are authoritative; rankings may evolve as the catalog grows.
    saved = dict(existing.get('roles', {}))
    for role, item in selected.items():
        if role not in saved:
            saved[role] = {key: item[key] for key in ('id', 'key', 'name', 'pack', 'html_fallback')}
    result = {**existing, 'schema_version': 1, 'style': style, 'primary_pack': source,
              'secondary_packs': existing.get('secondary_packs', []), 'roles': saved,
              'catalog_version': data['catalog_version']}
    if selected_constraints:
        result['constraints'] = selected_constraints
    return {'profile': result, 'missing_roles': [role for role in requested if role not in saved],
            'html': {role: emoji_html(saved[role]) for role in requested if role in saved}}
