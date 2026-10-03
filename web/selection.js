// Deterministic shortlist retrieval. The AI evaluates the brief and actual previews.
(() => {
  'use strict';
  const policy = JSON.parse(document.getElementById('catalog-data').textContent).selection_policy;
  const normalized = value => String(value).toLowerCase().replace(/ё/g, 'е').replace(/_/g, ' ');
  const rules = new Map();
  function spans(pattern, value) {
    if (!rules.has(pattern)) rules.set(pattern, new RegExp('(?:^|[^a-zа-я0-9])(' + normalized(pattern) + ')(?=$|[^a-z0-9]|(?:s|es|ing|ed)(?=$|[^a-z0-9]))', 'giu'));
    const regex = rules.get(pattern), text = normalized(value), result = [];
    regex.lastIndex = 0;
    for (const match of text.matchAll(regex)) {
      const start = match.index + match[0].length - match[1].length;
      let end = start + match[1].length;
      if (/[a-z]/.test(text[end - 1] || '') && /[a-z]/.test(text[end] || '')) {
        const suffix = text.slice(end).match(/^[a-z]+/)[0];
        if (!['s', 'es', 'ing', 'ed'].includes(suffix)) continue;
        end += suffix.length;
      }
      result.push([start, end]);
    }
    return result;
  }
  const matches = (pattern, value) => spans(pattern, value).length > 0;
  const concepts = value => Object.entries(policy.intents).filter(([key, rule]) => normalized(value).trim() === key || matches(rule.pattern, value)).map(([key]) => key);
  function plan(query, style = '', constraints = {}) {
    if (style && !policy.styles[style]) throw new Error(`Unknown style: ${style}`);
    let remaining = normalized(query);
    const required = [], excluded = [], excludedTerms = [], excludedStyles = [], found = {}, warnings = [];
    function consume(pattern) {
      const positions = spans(pattern, remaining);
      for (const [start, end] of positions.reverse()) remaining = remaining.slice(0, start) + ' '.repeat(end - start) + remaining.slice(end);
      return positions.length > 0;
    }
    for (const [field, choices] of Object.entries(policy.constraints)) {
      for (const [value, pattern] of Object.entries(choices)) {
        if (!consume('(?:не|без|not|no|without)\\s+(?:' + pattern + ')')) continue;
        const opposite = Object.keys(choices).find(key => key !== value);
        if (found[field] && found[field] !== opposite) warnings.push('conflicting_constraints');
        found[field] = opposite;
      }
    }
    for (const [field, choices] of Object.entries(policy.constraints)) {
      for (const [value, pattern] of Object.entries(choices)) {
        if (!consume(pattern)) continue;
        if (found[field] && found[field] !== value) warnings.push('conflicting_constraints');
        found[field] = value;
      }
    }
    for (const [key, rule] of Object.entries(policy.features)) {
      if (consume('(?:не|без|not|no|without)\\s+(?:' + rule.query_pattern + ')')) excluded.push(key);
    }
    for (const [key, rule] of Object.entries(policy.styles)) {
      if (consume('(?:не|без|not|no|without)\\s+(?:' + rule.pattern + ')[а-я]*')) excludedStyles.push(key);
    }
    for (const [key, rule] of Object.entries(policy.features)) {
      if (consume(rule.query_pattern)) required.push(key);
    }
    for (const [start, end] of spans('(?:не|без|not|no|without)\\s+[a-zа-я0-9]+', remaining).reverse()) {
      excludedTerms.push(remaining.slice(start, end).split(/\s+/).at(-1));
      remaining = remaining.slice(0, start) + ' '.repeat(end - start) + remaining.slice(end);
    }
    let inferred = Object.entries(policy.styles).filter(([, rule]) => matches(rule.pattern, remaining)).map(([key]) => key);
    const detected = concepts(remaining);
    if (detected.includes('shopping') && detected.includes('delete') && !matches(policy.intents.delete.action_pattern, remaining)) {
      detected.splice(detected.indexOf('delete'), 1);
    }
    const firstPosition = key => spans(policy.intents[key].pattern, remaining)[0]?.[0] ?? -1;
    const ordered = [...detected].sort((a, b) => firstPosition(a) - firstPosition(b));
    const compound = ordered.length > 1 && /(?:^|[^a-zа-я0-9])(?:и|или|and|or)(?=$|[^a-zа-я0-9])|,/iu.test(remaining);
    const actions = ordered.filter(key => policy.actions.includes(key));
    let intents, context;
    if (compound) {
      intents = detected; context = []; warnings.push('multiple_intents');
    } else {
      intents = (actions.length ? actions : ordered).slice(0, 1);
      context = detected.filter(key => !intents.includes(key));
    }
    if (!intents.length && required.length) intents = [...new Set(required.map(key => policy.features[key].implicit_intent).filter(Boolean))];
    const terms = (remaining.match(/[a-zа-я0-9]+/g) || []).filter(token =>
      !policy.stop_words.includes(token) && !concepts(token).length && !Object.values(policy.styles).some(rule => matches(rule.pattern, token)));
    if (!style && inferred.length > 1) {
      const specific = inferred.filter(key => key !== 'minimal');
      if (specific.length === 1) inferred = specific;
      else warnings.push('multiple_styles');
    }
    const selectedStyle = style || (inferred.length === 1 ? inferred[0] : '');
    if (excludedStyles.includes(selectedStyle)) warnings.push('conflicting_constraints');
    for (const [field, value] of Object.entries(constraints || {})) {
      if (['', 'any'].includes(value)) continue;
      if (!policy.constraints[field] || !policy.constraints[field][value]) throw new Error(`Unknown constraint: ${field}=${value}`);
      if (found[field] && found[field] !== value) warnings.push('conflicting_constraints');
      found[field] = value;
    }
    if (required.some(key => excluded.includes(key))) warnings.push('conflicting_constraints');
    if (policy.feature_conflicts.some(group => group.every(key => required.includes(key)))) warnings.push('conflicting_constraints');
    return {query, intents, context_intents: context, terms, style: selectedStyle, constraints: found, features: required,
      excluded_features: excluded, excluded_terms: excludedTerms, excluded_styles: excludedStyles, warnings: [...new Set(warnings)]};
  }
  function fitsConstraints(item, constraints) {
    return Object.entries(constraints).every(([field, value]) => {
      if (['', 'any'].includes(value)) return true;
      if (field === 'animation') return item.animated === (value === 'animated');
      if (field === 'color') return item.color_mode === value;
      if (field === 'repainting') return item.repainting === (value === 'required');
      return true;
    });
  }
  function rank(item, query, {pack = '', includeSpecial = false} = {}) {
    if (query.warnings.includes('conflicting_constraints')) return null;
    if (!includeSpecial && !item.selectable) return null;
    if (pack && item.pack !== pack) return null;
    if (query.style && item.style_family !== query.style) return null;
    if (query.excluded_styles.includes(item.style_family) || !fitsConstraints(item, query.constraints)) return null;
    if (!query.features.every(key => item.features.includes(key))) return null;
    const excluded = new Set(query.excluded_features);
    if (query.intents.length && !includeSpecial) {
      policy.default_excluded_features.filter(key => !query.features.includes(key)).forEach(key => excluded.add(key));
      if (query.intents.includes('lock') && !query.features.includes('open')) excluded.add('open');
    }
    if (item.features.some(key => excluded.has(key))) return null;
    const text = normalized(item.search);
    if (query.excluded_terms.some(term => text.includes(term))) return null;
    if (!query.terms.every(term => text.includes(term))) return null;
    const matched = query.intents.filter(key => item.intents.includes(key));
    if (query.intents.length && !matched.length) return null;
    const literal = query.query.trim() && text.includes(normalized(query.query).trim());
    const direct = matched.filter(key => item.direct_intents.includes(key));
    const context = query.context_intents.filter(key => item.direct_intents.includes(key));
    let score = matched.length * 20 + direct.length * 20 + (literal ? 12 : 0) + context.length * 4 + query.terms.length * 8;
    score -= Math.max(0, item.intents.length - matched.length);
    score -= Math.min(3, (normalized(item.name).match(/[a-zа-я0-9]+/g) || []).length * .15);
    const evidence = direct.length === query.intents.length ? 'full' : direct.length ? 'partial' : 'category_only';
    return {score, matched_intents: matched, direct_intents: direct, matched_context: context, match: evidence,
      recommended: item.selectable && !!(query.intents.length || query.terms.length) && evidence === 'full' && !query.warnings.length};
  }
  function decision(query, results) {
    if (query.warnings.length) return 'needs_clarification';
    if (!results.length) return 'no_match';
    if (!query.intents.length && !query.terms.length) return 'browse';
    return results[0].recommended ? 'matched' : 'needs_review';
  }
  window.EmojiSelection = Object.freeze({plan, rank, decision});
})();
