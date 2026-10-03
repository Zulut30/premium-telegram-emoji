"""Query for verified Telegram emoji."""
from __future__ import annotations

import re
from .policy import POLICY


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


def concepts(value: str, *, source: bool = False) -> list[str]:
    return [key for key, rule in POLICY['intents'].items()
            if normalized(value).strip() == key or matches(rule.get('source_pattern', rule['pattern']) if source else rule['pattern'], value)]


def extract_games(value: str) -> tuple[str, list[str], list[str]]:
    """Protect whole game names from role/state parsing, including negations."""
    remaining, games, excluded = normalized(value), [], []
    for key, rule in POLICY.get('game_aliases', {}).items():
        for start, end in reversed(spans(rule['pattern'], remaining)):
            if end and 'а' <= remaining[end - 1] <= 'я':
                end += len(re.match(r'[а-я]*', remaining[end:])[0])
            negative = re.search(r'(?:^|[^a-zа-я0-9])((?:не|без|not|no|without)\s+)$', remaining[:start])
            if negative:
                excluded.append(key)
                start = negative.start(1)
            else:
                games.append(key)
            remaining = remaining[:start] + ' ' * (end - start) + remaining[end:]
    return remaining, list(dict.fromkeys(games)), list(dict.fromkeys(excluded))


def query_plan(query: str, style: str = '', constraints: dict | None = None) -> dict:
    if style and style not in POLICY['styles']:
        raise ValueError(f'Unknown style: {style}')
    remaining, games, excluded_games = extract_games(query)
    required, excluded, excluded_terms, excluded_styles, state_intents = [], [], [], [], []
    found_constraints, warnings = {}, []
    if len(games) > 1:
        warnings.append('multiple_games')
    if set(games) & set(excluded_games):
        warnings.append('conflicting_constraints')

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
    overridden = {target for key in detected for target in POLICY['intents'][key].get('query_overrides', [])}
    if games:
        overridden.add('game')
    detected = [key for key in detected if key not in overridden]
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
    # Whole role phrases are evidence, not extra literal requirements.
    terms_text = remaining
    positions = sorted({position for rule in POLICY['intents'].values() for position in spans(rule['pattern'], remaining)}, reverse=True)
    for start, end in positions:
        if end and 'а' <= remaining[end - 1] <= 'я':
            end += len(re.match(r'[а-я]*', remaining[end:])[0])
        terms_text = terms_text[:start] + ' ' * (end - start) + terms_text[end:]
    tokens = re.findall(r'[a-zа-я0-9]+', terms_text)
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
            'games': games, 'excluded_games': excluded_games,
            'game_mode': 'context' if intent_keys and intent_keys != ['game'] else 'topic',
            'style': selected_style, 'constraints': found_constraints, 'features': list(dict.fromkeys(required)),
            'excluded_features': list(dict.fromkeys(excluded)), 'excluded_terms': excluded_terms,
            'excluded_styles': excluded_styles, 'warnings': list(dict.fromkeys(warnings))}


def plan_in_style(query: str, style: str, constraints: dict) -> dict:
    plan = query_plan(query, style, constraints)
    inferred = query_plan(query)['style']
    if inferred and inferred != style and 'conflicting_constraints' not in plan['warnings']:
        plan['warnings'].append('conflicting_constraints')
    return plan
