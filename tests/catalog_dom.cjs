// Behavior checks in a DOM simulator, not a browser-rendering or clipboard test.
// Setup: npm install --prefix .runtime/catalog-qa --no-audit --no-fund jsdom
// Run after generation: node tests/catalog_dom.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM, VirtualConsole} = require(path.join(__dirname, '../.runtime/catalog-qa/node_modules/jsdom'));
const html = fs.readFileSync(path.join(__dirname, '../site/index.html'), 'utf8');
const payload = JSON.parse(html.match(/<script type="application\/json" id="catalog-data">(.*?)<\/script>/s)[1]);
const first = payload.items[0];
const animal = payload.items.find(item => item.sections.includes('18'));
const KEY = 'premiumEmojiRatings:v1';
const tick = () => new Promise(resolve => setImmediate(resolve));
let checks = 0;

function create({mobile = false, ratings = {}, deniedStorage = false} = {}) {
  const errors = [];
  const writes = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', error => errors.push(error));
  const dom = new JSDOM(html, {
    url: 'https://catalog.test/', runScripts: 'dangerously', virtualConsole,
    beforeParse(window) {
      window.matchMedia = () => ({matches: mobile, addEventListener() {}, removeEventListener() {}});
      window.localStorage.setItem(KEY, JSON.stringify(ratings));
      if (deniedStorage) window.Storage.prototype.setItem = () => { throw new Error('storage denied'); };
      Object.defineProperty(window.navigator, 'clipboard', {value: {writeText: async text => { writes.push(text); }}});
    }
  });
  const window = dom.window, document = window.document;
  const get = id => document.getElementById(id);
  const search = query => { get('search').value = query; get('search').dispatchEvent(new window.Event('input', {bubbles: true})); };
  const rows = () => [...document.querySelectorAll('.emoji-row')];
  const selected = () => document.querySelector('.emoji-row.selected')?.dataset.id;
  const change = (id, value) => { get(id).value = value; get(id).dispatchEvent(new window.Event('change', {bubbles: true})); };
  return {dom, window, document, errors, writes, get, search, rows, selected, change};
}

function check(name, callback) {
  callback();
  checks++;
  console.log(`PASS ${name}`);
}

(async () => {
  const env = create({ratings: {[first.id]: 2, [animal.id]: 5}});
  const {window, document, get, search, rows, selected, change, writes} = env;
  check('real catalog, string IDs, bounded rows and migrated personal ratings', () => {
    assert.ok(payload.items.length > 30);
    assert.equal(new Set(payload.items.map(item => item.id)).size, payload.items.length);
    assert.ok(payload.sections.length > 1);
    assert.ok(payload.items.every(item => typeof item.id === 'string'));
    assert.equal(rows().length, 30);
    assert.equal(document.querySelectorAll('.rating-button').length, 5);
    assert.equal(get('emoji-id').value, first.id);
    assert.equal(get('rating-value').textContent, '2/5');
  });
  get('copy-id').click(); await tick();
  check('copy preserves all ID digits', () => assert.equal(writes.at(-1), first.id));
  get('copy-html').click(); await tick();
  check('HTML export preserves ID and real catalog fallback', () => assert.equal(writes.at(-1), `<tg-emoji emoji-id="${first.id}">${first.fallback}</tg-emoji>`));
  search(first.id);
  check('exact ID lookup and visible result count', () => {
    assert.equal(rows().length, 1);
    assert.equal(selected(), first.id);
    assert.match(get('results-count').textContent, /1 эмодзи/);
  });
  const duplicate = payload.items.find(item => item.aliases.length);
  search(duplicate.aliases[0].name);
  check('merged duplicate remains searchable by alternate name', () => assert.ok(rows().some(row => row.dataset.id === duplicate.id)));
  search('');
  change('sort', 'rating');
  check('rating sort works across all packs', () => assert.equal(rows()[0].dataset.id, animal.id));
  search(first.id);
  document.querySelector('[data-rating="4"]').click();
  check('personal rating is saved in existing storage format', () => assert.equal(JSON.parse(window.localStorage.getItem(KEY))[first.id], 4));
  document.querySelector('[data-view="ratings"]').click(); search('');
  check('my ratings filters unrated emoji', () => {
    assert.equal(rows().length, 2);
    assert.equal(rows()[0].dataset.id, animal.id);
  });
  document.querySelector('[data-view="all"]').click();
  change('pack-filter', '17'); search('Batman');
  check('English franchise query combines with pack filter', () => {
    assert.ok(rows().length > 0);
    assert.ok(rows().every(row => payload.items.find(item => item.id === row.dataset.id).sections.includes('17')));
  });
  search('not-a-real-emoji-987654321');
  check('empty search hides stale actions and can reset', () => {
    assert.equal(get('empty-state').hidden, false);
    assert.equal(get('detail-content').hidden, true);
    get('reset-filters').click();
    assert.equal(get('empty-state').hidden, true);
    assert.equal(get('pack-filter').value, 'all');
    assert.equal(rows().length, 30);
  });
  document.querySelector('[data-view="packs"]').click();
  check('pack navigation opens a real filtered catalog', () => {
    assert.equal(document.querySelectorAll('.pack-card').length, payload.sections.length);
    document.querySelector('[data-pack="11"]').click();
    assert.equal(get('pack-filter').value, '11');
    assert.ok(rows().every(row => payload.items.find(item => item.id === row.dataset.id).sections.includes('11')));
  });
  document.querySelector('[data-view="all"]').click();
  const originalFirst = rows()[0].dataset.id;
  get('next-page').click();
  check('pagination changes data and can return to first page', () => {
    assert.notEqual(rows()[0].dataset.id, originalFirst);
    assert.equal(get('page-number').textContent, `2 из ${Math.ceil(payload.items.length / 30)}`);
    get('previous-page').click();
    assert.equal(rows()[0].dataset.id, originalFirst);
  });
  rows()[0].focus();
  rows()[0].dispatchEvent(new window.KeyboardEvent('keydown', {key: 'ArrowDown', bubbles: true}));
  check('keyboard list navigation selects the next item', () => {
    assert.equal(document.activeElement, rows()[1]);
    assert.equal(selected(), rows()[1].dataset.id);
  });
  document.dispatchEvent(new window.KeyboardEvent('keydown', {key: 'k', ctrlKey: true, bubbles: true}));
  check('search keyboard shortcut', () => assert.equal(document.activeElement, get('search')));
  window.navigator.clipboard.writeText = async () => { throw new Error('clipboard denied'); };
  get('copy-id').click(); await tick();
  check('clipboard refusal selects the exact ID and reports failure', () => {
    assert.match(get('toast').textContent, /Не удалось скопировать/);
    assert.equal(get('emoji-id').selectionStart, 0);
    assert.equal(get('emoji-id').selectionEnd, get('emoji-id').value.length);
  });
  get('copy-html').click(); await tick();
  check('HTML fallback selects plain code when clipboard refuses', () => assert.equal(window.getSelection().toString(), get('emoji-html').textContent));
  search('percent');
  get('copy-html').click(); await tick();
  check('non-emoji fallback is replaced only in HTML export', () => assert.match(get('emoji-html').textContent, />💯<\/tg-emoji>$/));
  check('no script errors in desktop DOM simulator', () => assert.deepEqual(env.errors, []));

  const restored = create({ratings: JSON.parse(window.localStorage.getItem(KEY))});
  check('personal rating survives a new document', () => assert.equal(restored.get('rating-value').textContent, '4/5'));
  const phone = create({mobile: true, deniedStorage: true});
  phone.rows()[1].click();
  check('mobile details open with dialog semantics and isolated background', () => {
    assert.equal(phone.get('detail-panel').getAttribute('aria-modal'), 'true');
    assert.equal(phone.get('detail-panel').classList.contains('is-open'), true);
    assert.equal(phone.document.querySelector('.catalog-pane').inert, true);
  });
  phone.document.querySelector('[data-rating="3"]').click();
  check('denied storage keeps browsing and gives useful feedback', () => assert.match(phone.get('toast').textContent, /не разрешает сохранить/));
  phone.get('close-detail').click();
  check('mobile return closes dialog and restores background', () => {
    assert.equal(phone.get('detail-panel').classList.contains('is-open'), false);
    assert.equal(phone.document.querySelector('.catalog-pane').inert, false);
    assert.equal(phone.get('detail-panel').hasAttribute('aria-modal'), false);
    assert.equal(phone.document.activeElement.dataset.id, payload.items[1].id);
  });
  phone.rows()[0].click();
  phone.document.dispatchEvent(new phone.window.KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
  check('Escape closes mobile details', () => assert.equal(phone.get('detail-panel').classList.contains('is-open'), false));
  check('no script errors in mobile DOM simulator', () => assert.deepEqual(phone.errors, []));
  if (payload.compositions?.length) {
    env.window.navigator.clipboard.writeText = async text => { env.writes.push(text); };
    const chain = payload.compositions.find(group => group.key === 'nexus_circle_chain');
    const member = payload.items.find(item => item.id === chain.emoji_ids[0]);
    env.change('pack-filter', member.sections[0]);
    check('pack filter exposes ordered composition examples', () => {
      assert.equal(env.get('composition-panel').hidden, false);
      assert.ok(env.get('composition-list').querySelector(`[data-composition="${chain.key}"]`));
    });
    env.get('composition-list').querySelector(`[data-composition="${chain.key}"][data-copy-kind="html"]`).click();
    await tick();
    check('composition HTML preserves repeated IDs and has no inter-emoji spaces', () => {
      const text = env.writes.at(-1);
      assert.deepEqual([...text.matchAll(/emoji-id="(\d+)"/g)].map(match => match[1]), chain.emoji_ids);
      assert.equal(text.includes('</tg-emoji> <tg-emoji'), false);
    });
    env.get('composition-list').querySelector(`[data-composition="${chain.key}"][data-copy-kind="ids"]`).click();
    await tick();
    check('composition ID export preserves exact order and repetitions', () => assert.equal(env.writes.at(-1), chain.emoji_ids.join(' ')));
    env.search(member.id);
    check('part details expose its composition membership', () => assert.equal(env.get('composition-detail').hidden, false));
  }
  restored.dom.window.close(); phone.dom.window.close(); env.dom.window.close();
  console.log(`${checks} DOM behavior checks passed. Browser visual QA remains separate.`);
})().catch(error => { console.error(error); process.exitCode = 1; });
