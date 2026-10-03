(() => {
  'use strict';
  const catalog = JSON.parse(document.getElementById('catalog-data').textContent);
  const items = catalog.items;
  const byId = new Map(items.map(item => [item.id, item]));
  const sections = catalog.sections;
  const compositions = catalog.compositions || [];
  const compositionsByKey = new Map(compositions.map(group => [group.key, group]));
  const RATING_KEY = 'premiumEmojiRatings:v1';
  const STYLE_KEY = 'premiumEmojiStyle:v1';
  const PAGE_SIZE = 30;
  const mobile = window.matchMedia('(max-width: 860px)');
  const $ = id => document.getElementById(id);
  const format = value => new Intl.NumberFormat('ru-RU').format(value);
  const escape = value => String(value).replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
  const icon = (name, classes = '') => `<img class="icon ${classes}" src="icons/${name}.svg" alt="" aria-hidden="true">`;
  let ratings = loadRatings();
  let savedStyle = loadStyle();
  let view = 'all';
  let page = 0;
  let selectedId = items[0]?.id || null;
  let currentPage = [];
  let lastRow = null;
  let toastTimer;

  function loadRatings() {
    const result = Object.create(null);
    try {
      const stored = JSON.parse(localStorage.getItem(RATING_KEY) || '{}');
      if (stored && typeof stored === 'object' && !Array.isArray(stored)) {
        for (const [id, value] of Object.entries(stored)) {
          if (/^\d+$/.test(id) && Number.isInteger(value) && value >= 1 && value <= 5) result[id] = value;
        }
      }
    } catch (_) { /* Ratings are optional; browsing stays available. */ }
    return result;
  }

  function image(item, extra = '') {
    const classes = `${item.image.startsWith('icons/') ? 'icon ' : item.monochrome ? 'monochrome ' : ''}${extra}`;
    return `<img class="${classes}" src="${escape(item.image)}" alt="" loading="lazy" width="40" height="40" data-emoji-image="${escape(item.id)}">`;
  }

  function loadStyle() {
    try {
      const saved = JSON.parse(localStorage.getItem(STYLE_KEY) || '{}');
      if (saved && (saved.style === 'all' || Object.hasOwn(catalog.selection_policy.styles, saved.style))) {
        return {style: saved.style, pack: sections.some(section => section.id === saved.pack) ? saved.pack : 'all'};
      }
    } catch (_) { /* The catalog works without browser storage. */ }
    return {style: 'all', pack: 'all'};
  }

  function saveStyle() {
    savedStyle = {style: $('style-filter').value, pack: $('pack-filter').value};
    try { localStorage.setItem(STYLE_KEY, JSON.stringify(savedStyle)); }
    catch (_) { notify('Стиль выбран; браузер не разрешает сохранить его после закрытия страницы.'); }
  }

  function styleProfile() {
    const item = byId.get(selectedId);
    if (!item || !Object.hasOwn(catalog.selection_policy.styles, item.style_family)) return null;
    return {schema_version: 1, style: item.style_family, primary_pack: item.pack,
      secondary_packs: [], roles: {}, catalog_version: catalog.catalog_version};
  }

  // Telegram requires one emoji, rather than a word or currency sign, inside tg-emoji.
  function fallbackForHTML(item) {
    const text = item.original_fallback || item.fallback || '';
    const pattern = /^(?:\p{Regional_Indicator}{2}|[0-9#*]\uFE0F?\u20E3|[\p{Extended_Pictographic}\p{Emoji_Presentation}](?:\uFE0F|\p{Emoji_Modifier})?(?:\u200D[\p{Extended_Pictographic}\p{Emoji_Presentation}](?:\uFE0F|\p{Emoji_Modifier})?)*)$/u;
    if (pattern.test(text)) return text;
    if (text === '%') return '💯';
    return '✨';
  }

  function htmlFor(item) {
    return `<tg-emoji emoji-id="${item.id}">${escape(fallbackForHTML(item))}</tg-emoji>`;
  }

  function compositionCard(group) {
    const preview = group.emoji_ids.map(id => {
      const item = byId.get(id);
      return item.availability ? '<span class="empty-emoji" title="Изображение недоступно">?</span>' : image(item);
    }).join('');
    return `<article class="composition-card"><h4>${escape(group.name_ru)}</h4>
      <div class="composition-strip" aria-label="${escape(group.name_ru)}">${preview}</div>
      ${group.needs_review ? '<p class="composition-warning">Есть часть без доступного изображения.</p>' : ''}
      <div class="composition-actions">
        <button type="button" class="secondary-button" data-composition="${escape(group.key)}" data-copy-kind="html">Копировать HTML</button>
        <button type="button" class="text-button" data-composition="${escape(group.key)}" data-copy-kind="ids">ID по порядку</button>
      </div><pre class="composition-code" hidden></pre></article>`;
  }

  function renderCompositionPanel() {
    const section = sections.find(group => group.id === $('pack-filter').value);
    const candidates = view === 'packs' || !section ? [] : compositions.filter(group => group.emoji_ids.some(id => byId.get(id)?.sections.includes(section.id)));
    $('composition-panel').hidden = !candidates.length;
    $('composition-summary').textContent = `Примеры сборки · ${candidates.length}`;
    $('composition-list').innerHTML = candidates.map(compositionCard).join('');
  }

  function matchingItems() {
    const query = $('search').value.trim();
    const plan = window.EmojiSelection.plan(query, $('style-filter').value === 'all' ? '' : $('style-filter').value);
    const scores = new Map();
    const pack = $('pack-filter').value;
    const result = items.filter(item => {
      if (pack !== 'all' && !item.sections.includes(pack)) return false;
      if (view === 'ratings' && !ratings[item.id]) return false;
      if (view === 'news' && !item.sections.includes('1')) return false;
      if (view === 'apps' && !item.sections.some(id => ['2', '3', '7', '8'].includes(id))) return false;
      const result = window.EmojiSelection.rank(item, plan, {includeSpecial: !plan.intents.length || query === item.id});
      if (!result) return false;
      scores.set(item.id, result.score);
      return true;
    });
    const mode = $('sort').value;
    result.sort((a, b) => {
      if (mode === 'rating') return ((ratings[b.id] || 0) - (ratings[a.id] || 0)) || (a.order - b.order);
      if (mode === 'unrated') return (Number(Boolean(ratings[a.id])) - Number(Boolean(ratings[b.id]))) || (a.order - b.order);
      if (mode === 'name') return a.name.localeCompare(b.name, 'ru') || (a.order - b.order);
      return (query ? scores.get(b.id) - scores.get(a.id) : 0) || a.order - b.order;
    });
    if (plan.warnings.includes('conflicting_constraints')) {
      $('style-status').textContent = 'Ограничения противоречат друг другу. Уточните запрос.';
    } else if (plan.warnings.includes('multiple_intents')) {
      $('style-status').textContent = 'Несколько назначений: ищите каждый значок отдельно.';
    } else if (plan.warnings.includes('multiple_styles')) {
      $('style-status').textContent = 'Укажите один стиль, чтобы получить согласованный набор.';
    } else if (plan.intents.length && result.length && !result.some(item =>
      window.EmojiSelection.rank(item, plan)?.recommended)) {
      $('style-status').textContent = 'Есть лишь совпадения по категории. Уточните назначение и проверьте изображение.';
    }
    return result;
  }

  function updateNavigation() {
    document.querySelectorAll('[data-view]').forEach(button => {
      const active = button.dataset.view === view;
      button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    $('page-title').textContent = {all: 'Каталог эмодзи', packs: 'Паки эмодзи', ratings: 'Мои оценки', news: 'Новости', apps: 'Приложения'}[view];
    $('catalog-summary').textContent = view === 'packs' ? `${format(sections.length)} паков` : `${format(items.length)} эмодзи в ${sections.length} разделах`;
    $('search').placeholder = view === 'packs' ? 'Найти пак по названию' : 'Найти по названию, игре или ID';
    $('search').setAttribute('aria-label', view === 'packs' ? 'Поиск паков по названию' : 'Поиск по названию, игре или ID');
    $('clear-search').hidden = !$('search').value;
    $('pack-filter').hidden = view === 'packs';
    $('sort').hidden = view === 'packs';
    $('style-filter').hidden = view === 'packs';
    document.querySelector('.style-tools').hidden = view === 'packs';
    const style = $('style-filter').value;
    const label = catalog.selection_policy.styles[style]?.label;
    $('style-status').textContent = label ? `${label} · выбор сохраняется в этом браузере` : 'Поиск по назначению: например, «уведомления» или «скачать»';
  }

  function render() {
    updateNavigation();
    renderCompositionPanel();
    if (view === 'packs') {
      renderPacks();
      return;
    }
    $('pack-list').hidden = true;
    const results = matchingItems();
    const pageCount = Math.max(1, Math.ceil(results.length / PAGE_SIZE));
    page = Math.min(page, pageCount - 1);
    currentPage = results.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
    if (!currentPage.some(item => item.id === selectedId)) selectedId = currentPage[0]?.id || null;
    $('results-count').textContent = `Найдено: ${format(results.length)} эмодзи`;
    $('table-shell').hidden = !results.length;
    $('empty-state').hidden = !!results.length;
    $('pagination').hidden = !results.length;
    $('empty-title').textContent = view === 'ratings' && !items.some(item => ratings[item.id]) ? 'Пока нет оценок' : 'Ничего не найдено';
    $('empty-description').textContent = view === 'ratings' && !items.some(item => ratings[item.id]) ? 'Выберите эмодзи в каталоге и поставьте ему личную оценку.' : 'Попробуйте другой запрос или сбросьте фильтры.';
    $('emoji-list').innerHTML = currentPage.map(item => {
      const rating = ratings[item.id] || 0;
      const selected = selectedId === item.id;
      return `<button type="button" class="emoji-row${selected ? ' selected' : ''}" data-id="${item.id}" aria-pressed="${selected}" aria-label="${escape(item.name)}, ${escape(item.pack)}, ${rating ? `моя оценка ${rating} из 5` : 'без оценки'}">
        <span class="row-preview">${image(item)}</span>
        <span class="row-name"><span class="row-title" title="${escape(item.name)}">${escape(item.name)}</span><span class="row-pack">${escape(item.pack)}</span></span>
        <span class="row-key" title="${escape(item.key)}">${escape(item.key)}</span>
        <span class="row-rating${rating ? '' : ' unrated'}">${icon(rating ? 'star-filled' : 'star', rating ? 'gold' : '')}<span>${rating || '—'}</span></span>
      </button>`;
    }).join('');
    $('page-range').textContent = results.length ? `${format(page * PAGE_SIZE + 1)}–${format(Math.min((page + 1) * PAGE_SIZE, results.length))} из ${format(results.length)}` : '';
    $('page-number').textContent = `${page + 1} из ${pageCount}`;
    $('previous-page').disabled = page === 0;
    $('next-page').disabled = page >= pageCount - 1;
    renderDetail();
  }

  function renderPacks() {
    const query = $('search').value.toLocaleLowerCase('ru').trim();
    const visible = sections.filter(section => `${section.name} ${section.title}`.toLocaleLowerCase('ru').includes(query));
    $('table-shell').hidden = true;
    $('pagination').hidden = true;
    $('pack-list').hidden = !visible.length;
    $('empty-state').hidden = !!visible.length;
    $('empty-title').textContent = 'Пак не найден';
    $('empty-description').textContent = 'Попробуйте другое название или очистите поиск.';
    $('results-count').textContent = `Найдено: ${visible.length} паков`;
    $('pack-list').innerHTML = visible.map(section => {
      const preview = items.filter(item => item.sections.includes(section.id)).slice(0, 3);
      return `<button class="pack-card" type="button" data-pack="${section.id}"><span class="pack-previews">${preview.map(item => image(item)).join('')}</span><h2>${escape(section.name)}</h2><p>${format(section.count)} эмодзи · Смотреть пак</p></button>`;
    }).join('');
    $('detail-content').hidden = true;
    $('detail-empty').hidden = false;
    $('detail-empty').textContent = 'Выберите пак, чтобы посмотреть его эмодзи.';
  }

  function renderDetail() {
    $('export-style').disabled = !styleProfile();
    const item = byId.get(selectedId);
    $('detail-content').hidden = !item;
    $('detail-empty').hidden = !!item;
    $('detail-empty').textContent = 'Выберите эмодзи в списке, чтобы увидеть его ID и HTML.';
    if (!item) return;
    $('detail-preview').innerHTML = image(item);
    $('detail-title').textContent = item.name;
    $('detail-key').textContent = item.key;
    $('detail-pack').textContent = item.pack;
    $('emoji-id').value = item.id;
    $('emoji-html').textContent = htmlFor(item);
    $('open-pack').hidden = !item.url;
    $('pack-hint').textContent = item.url ? 'Открыть этот пак в Telegram' : 'Ссылка на исходный пак не указана';
    if (item.url) $('open-pack').href = item.url;
    else $('open-pack').removeAttribute('href');
    $('review-note').hidden = !item.needs_review;
    $('review-note').textContent = item.needs_review ? `Требует уточнения${item.notes.length ? ': ' + item.notes.join(' ') : ''}` : '';
    $('adaptive-note').hidden = !item.adaptive;
    const groups = compositions.filter(group => group.emoji_ids.includes(item.id));
    $('composition-detail').hidden = !groups.length;
    $('detail-compositions').innerHTML = groups.map(compositionCard).join('');
    $('detail-category').hidden = !item.category && !item.subcategory;
    $('detail-category').textContent = [item.category, item.subcategory].filter(Boolean).join(' · ');
    $('choose-pack-style').hidden = !Object.hasOwn(catalog.selection_policy.styles, item.style_family);
    $('export-style').disabled = !styleProfile();
    paintRating();
  }

  function paintRating() {
    const value = ratings[selectedId] || 0;
    $('rating-value').textContent = value ? `${value}/5` : 'Без оценки';
    document.querySelectorAll('.rating-button').forEach(button => {
      const level = Number(button.dataset.rating);
      button.setAttribute('aria-pressed', String(level === value));
      button.innerHTML = icon(level <= value ? 'star-filled' : 'star', level <= value ? 'gold' : '');
    });
    $('reset-rating').disabled = !value;
  }

  function selectItem(id, row, open = true) {
    if (!byId.has(id)) return;
    selectedId = id;
    document.querySelectorAll('.emoji-row').forEach(button => {
      const selected = button.dataset.id === id;
      button.classList.toggle('selected', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
    renderDetail();
    if (mobile.matches && open) {
      lastRow = row;
      $('detail-panel').classList.add('is-open');
      $('detail-panel').setAttribute('role', 'dialog');
      $('detail-panel').setAttribute('aria-modal', 'true');
      document.body.classList.add('detail-open');
      document.querySelectorAll('.site-header, .page-heading, .catalog-pane, .site-footer').forEach(element => { element.inert = true; });
      $('detail-panel').scrollTop = 0;
      $('close-detail').focus();
    }
  }

  function closeDetail() {
    const wasOpen = $('detail-panel').classList.contains('is-open');
    $('detail-panel').classList.remove('is-open');
    $('detail-panel').removeAttribute('role');
    $('detail-panel').removeAttribute('aria-modal');
    document.body.classList.remove('detail-open');
    document.querySelectorAll('.site-header, .page-heading, .catalog-pane, .site-footer').forEach(element => { element.inert = false; });
    if (wasOpen) {
      const returnRow = lastRow?.isConnected ? lastRow : [...$('emoji-list').querySelectorAll('.emoji-row')].find(row => row.dataset.id === lastRow?.dataset.id);
      (returnRow || $('emoji-list').querySelector('.emoji-row') || $('search')).focus();
    }
    lastRow = null;
  }

  function notify(message) {
    clearTimeout(toastTimer);
    $('toast').textContent = message;
    $('toast').hidden = false;
    toastTimer = setTimeout(() => { $('toast').hidden = true; }, 3500);
  }

  async function copy(kind) {
    const item = byId.get(selectedId);
    if (!item) return;
    const value = kind === 'html' ? htmlFor(item) : item.id;
    try {
      await navigator.clipboard.writeText(value);
      notify(kind === 'html' ? 'HTML скопирован' : 'ID скопирован');
    } catch (_) {
      if (kind === 'html') {
        const range = document.createRange();
        range.selectNodeContents($('emoji-html'));
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      } else {
        $('emoji-id').focus();
        $('emoji-id').select();
      }
      notify('Не удалось скопировать автоматически. Текст выделен — скопируйте его вручную.');
    }
  }

  function setRating(value) {
    if (!selectedId) return;
    if (value === 0 || ratings[selectedId] === value) delete ratings[selectedId];
    else ratings[selectedId] = value;
    try { localStorage.setItem(RATING_KEY, JSON.stringify(ratings)); }
    catch (_) { notify('Оценка изменена, но браузер не разрешает сохранить её после закрытия страницы.'); }
    render();
  }

  function setView(next) {
    if (view === 'packs' || next === 'packs') $('search').value = '';
    view = next;
    $('pack-filter').value = 'all';
    page = 0;
    render();
  }

  function resetFilters() {
    $('search').value = '';
    $('pack-filter').value = 'all';
    $('style-filter').value = 'all';
    $('sort').value = 'catalog';
    saveStyle();
    view = 'all';
    page = 0;
    render();
    $('search').focus();
  }

  sections.forEach(section => $('pack-filter').add(new Option(`${section.name} · ${format(section.count)}`, section.id)));
  Object.entries(catalog.selection_policy.styles).forEach(([key, rule]) => $('style-filter').add(new Option(rule.label, key)));
  $('style-filter').value = savedStyle.style;
  $('pack-filter').value = savedStyle.pack;
  const ratingGroup = document.querySelector('.rating-buttons');
  for (let value = 1; value <= 5; value++) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'rating-button';
    button.dataset.rating = String(value);
    button.setAttribute('aria-label', `Оценить на ${value} из 5`);
    button.setAttribute('aria-pressed', 'false');
    button.addEventListener('click', () => setRating(value));
    ratingGroup.append(button);
  }

  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
  $('search').addEventListener('input', () => { page = 0; render(); });
  $('clear-search').addEventListener('click', () => { $('search').value = ''; page = 0; render(); $('search').focus(); });
  $('pack-filter').addEventListener('change', () => { saveStyle(); page = 0; render(); });
  $('style-filter').addEventListener('change', () => { $('pack-filter').value = 'all'; saveStyle(); page = 0; render(); });
  $('choose-pack-style').addEventListener('click', () => {
    const item = byId.get(selectedId);
    if (!item) return;
    $('style-filter').value = item.style_family;
    $('pack-filter').value = item.sections[0];
    $('search').value = '';
    saveStyle(); page = 0; render();
    notify(`Стиль пака ${item.pack} сохранён`);
  });
  $('export-style').addEventListener('click', async () => {
    const profile = styleProfile();
    if (!profile) return;
    const text = JSON.stringify(profile, null, 2);
    try { await navigator.clipboard.writeText(text); notify('Профиль выбранного пака скопирован. Передайте его ИИ вместе с задачей.'); }
    catch (_) {
      const blob = new Blob([text + '\n'], {type: 'application/json'});
      const url = URL.createObjectURL(blob), anchor = document.createElement('a');
      anchor.href = url; anchor.download = 'emoji-style.json'; anchor.click(); URL.revokeObjectURL(url);
      notify('Профиль стиля сохранён в файл');
    }
  });
  $('sort').addEventListener('change', () => { page = 0; render(); });
  $('reset-filters').addEventListener('click', resetFilters);
  $('focus-search').addEventListener('click', () => $('search').focus());
  $('emoji-list').addEventListener('click', event => {
    const row = event.target.closest('.emoji-row');
    if (row) selectItem(row.dataset.id, row);
  });
  $('emoji-list').addEventListener('keydown', event => {
    const row = event.target.closest('.emoji-row');
    if (!row || !['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    const rows = [...$('emoji-list').querySelectorAll('.emoji-row')];
    const current = rows.indexOf(row);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? rows.length - 1 : Math.max(0, Math.min(rows.length - 1, current + (event.key === 'ArrowDown' ? 1 : -1)));
    event.preventDefault();
    rows[next].focus();
    if (!mobile.matches) selectItem(rows[next].dataset.id, rows[next], false);
  });
  $('pack-list').addEventListener('click', event => {
    const button = event.target.closest('[data-pack]');
    if (!button) return;
    view = 'all';
    $('search').value = '';
    $('pack-filter').value = button.dataset.pack;
    const style = $('style-filter').value;
    if (style !== 'all' && !items.some(item => item.sections.includes(button.dataset.pack) && item.style_family === style)) $('style-filter').value = 'all';
    saveStyle();
    page = 0;
    render();
    $('emoji-list').querySelector('button')?.focus();
  });
  $('previous-page').addEventListener('click', () => { page--; render(); $('emoji-list').scrollTop = 0; });
  $('next-page').addEventListener('click', () => { page++; render(); $('emoji-list').scrollTop = 0; });
  $('close-detail').addEventListener('click', closeDetail);
  $('copy-id').addEventListener('click', () => copy('id'));
  $('copy-id-icon').addEventListener('click', () => copy('id'));
  $('copy-html').addEventListener('click', () => copy('html'));
  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-composition]');
    if (!button) return;
    const group = compositionsByKey.get(button.dataset.composition);
    if (!group) return;
    const value = button.dataset.copyKind === 'html' ? group.emoji_ids.map(id => htmlFor(byId.get(id))).join('') : group.emoji_ids.join(' ');
    try {
      await navigator.clipboard.writeText(value);
      notify(button.dataset.copyKind === 'html' ? 'HTML сборки скопирован' : 'ID сборки скопированы по порядку');
    } catch (_) {
      const code = button.closest('.composition-card').querySelector('.composition-code');
      code.hidden = false;
      code.textContent = value;
      const range = document.createRange();
      range.selectNodeContents(code);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      notify('Текст выделен — скопируйте его вручную.');
    }
  });
  $('reset-rating').addEventListener('click', () => setRating(0));
  window.addEventListener('storage', event => { if (event.key === RATING_KEY || event.key === null) { ratings = loadRatings(); render(); } });
  mobile.addEventListener('change', () => { if (!mobile.matches) closeDetail(); });
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if ($('detail-panel').classList.contains('is-open')) closeDetail();
      $('search').focus();
    }
    if (event.key === 'Escape') {
      if ($('detail-panel').classList.contains('is-open')) closeDetail();
      else if (document.activeElement === $('search')) { $('search').value = ''; page = 0; render(); }
    }
    if (event.key === 'Tab' && mobile.matches && $('detail-panel').classList.contains('is-open')) {
      const targets = [...$('detail-panel').querySelectorAll('button:not(:disabled), a[href], input')].filter(element => element.getClientRects().length);
      const first = targets[0], last = targets[targets.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  document.addEventListener('error', event => {
    const img = event.target;
    if (!(img instanceof HTMLImageElement) || !img.dataset.emojiImage || img.dataset.failed) return;
    img.dataset.failed = 'true';
    img.src = 'icons/bolt.svg';
    img.classList.add('icon');
    img.alt = 'Превью недоступно';
  }, true);
  render();
})();
