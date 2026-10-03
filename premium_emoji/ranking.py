"""Ranking for verified Telegram emoji."""
from __future__ import annotations

import re

from .policy import POLICY
from .query import matches, normalized
from .rendering import emoji_html


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
    games = set(item.get('games', []))
    requested_games = set(plan.get('games', []))
    if games & set(plan.get('excluded_games', [])):
        return None
    if requested_games and (plan.get('game_mode') == 'topic' or games) and not requested_games <= games:
        return None
    if plan['intents'] == ['game'] and not requested_games and games:
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
    if requested_games and requested_games <= games:
        score += 20
        for key in requested_games:
            preferred = POLICY['game_aliases'][key].get('preferred_source_pattern')
            if preferred and matches(preferred, item['name']):
                score += 12
    for key in direct:
        preferred = POLICY['intents'][key].get('preferred_source_pattern')
        if preferred and matches(preferred, item['name']):
            score += 12
    if plan['terms']:
        score += 8 * len(plan['terms'])
    # Names mentioning fewer other functions are more specific evidence for the requested role.
    score -= max(0, len(item['direct_intents']) - len(direct))
    score -= min(3, len(re.findall(r'[a-zа-я0-9]+', normalized(item['name']))) * .15)
    evidence = 'full' if len(direct) == len(plan['intents']) else 'partial' if direct else 'category_only'
    return {'item': item, 'score': score, 'matched_intents': matched, 'direct_intents': direct,
            'matched_context': context, 'match': evidence,
            'recommended': item['selectable'] and bool(plan['intents'] or plan['terms'] or requested_games) and evidence == 'full' and not plan['warnings']}


def candidate(result: dict) -> dict:
    item = result['item']
    return {**{key: item[key] for key in ('id', 'key', 'name', 'pack', 'style_family', 'html_fallback',
                                          'preview_url', 'selection_kind', 'selectable', 'adaptive', 'monochrome', 'animated', 'color_mode', 'repainting', 'features')},
            'games': item.get('games', []),
            'html': emoji_html(item), 'matched_intents': result['matched_intents'], 'direct_intents': result['direct_intents'],
            'matched_context': result['matched_context'], 'recommended': result['recommended'],
            'match': result['match'], 'score': result['score']}
