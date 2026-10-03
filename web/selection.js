// Deterministic shortlist retrieval. The AI evaluates the brief and actual previews.
(() => {
  'use strict';
  const policy = JSON.parse(document.getElementById('catalog-data').textContent).selection_policy;
  const normalized = value => String(value).toLowerCase().replace(/ё/g, 'е').replace(/_/g, ' ');
  const rules = new Map();
  const matches = (pattern, value) => {
    if (!rules.has(pattern)) rules.set(pattern, new RegExp('(?:^|[^a-zа-я0-9])(?:' + normalized(pattern) + ')', 'iu'));
    return rules.get(pattern).test(normalized(value));
  };
  const concepts = value => Object.entries(policy.intents).filter(([key, rule]) => normalized(value).trim() === key || matches(rule.pattern, value)).map(([key]) => key);
  function plan(query, style = '') {
    const inferred = Object.entries(policy.styles).filter(([, rule]) => matches(rule.pattern, query)).map(([key]) => key);
    const terms = (normalized(query).match(/[a-zа-я0-9]+/g) || []).filter(token =>
      !policy.stop_words.includes(token) && !concepts(token).length && !Object.values(policy.styles).some(rule => matches(rule.pattern, token)));
    return {query, intents: concepts(query), terms, style: style || (inferred.length === 1 ? inferred[0] : '')};
  }
  function rank(item, query, {pack = '', includeSpecial = false} = {}) {
    if (!includeSpecial && !item.selectable) return null;
    if (pack && item.pack !== pack) return null;
    if (query.style && item.style_family !== query.style) return null;
    const text = normalized(item.search);
    if (!query.terms.every(term => text.includes(term))) return null;
    const matched = query.intents.filter(key => item.intents.includes(key));
    if (query.intents.length && !matched.length) return null;
    const literal = query.query.trim() && text.includes(normalized(query.query).trim());
    const direct = matched.filter(key => item.direct_intents.includes(key));
    let score = matched.length * 20 + direct.length * 10 + (literal ? 12 : 0) + query.terms.length * 8;
    score -= Math.max(0, item.intents.length - matched.length);
    score -= Math.min(3, (normalized(item.name).match(/[a-zа-я0-9]+/g) || []).length * .15);
    return {score, matched_intents: matched, direct_intents: direct, match: matched.length === query.intents.length ? 'full' : 'partial'};
  }
  window.EmojiSelection = Object.freeze({plan, rank});
})();
