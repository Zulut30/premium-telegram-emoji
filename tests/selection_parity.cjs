// Compare browser and AI shortlists against the same real catalog and user requests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {JSDOM} = require(path.join(__dirname, '../.runtime/catalog-qa/node_modules/jsdom'));
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'site/index.html'), 'utf8');
const dom = new JSDOM(html, {url: 'https://catalog.test/', runScripts: 'dangerously',
  beforeParse(window) { window.matchMedia = () => ({matches: false, addEventListener() {}}); }});
const data = JSON.parse(dom.window.document.getElementById('catalog-data').textContent);
const cases = [
  {query: 'значок напоминания', style: 'minimal'},
  {query: 'какой эмодзи подойдет для кнопки уведомлений'},
  {query: 'пиксельное сердце'}, {query: 'неоновое сердце'},
  {query: 'скачать', pack: 'sfsymbols'}, {query: 'копирование'}, {query: 'ссылки'},
  {query: 'образование'}, {query: 'medicine'}, {query: 'оплата'},
  {query: 'GitHub', pack: 'SocialEmojis'}, {query: 'готово', style: 'minimal'},
  {query: '6021536113108196448'}, {query: 'nexus_base'},
  {query: 'wi_pixelru', include_special: true}, {query: 'qzxnonexistent999'},
  ...JSON.parse(fs.readFileSync(path.join(__dirname, 'selection_cases.json'), 'utf8')).map(({expect, ...query}) => query),
  {query: 'notification not static'}, {query: 'black and white notifications'},
  {query: 'статичные уведомления', constraints: {animation: 'animated'}},
  {query: 'сердце не неоновое'}, {query: 'удалить покупку'},
  {query: 'reminders'}, {query: 'information'}, {query: 'checkmark'},
  {query: 'Education2026'}, {query: 'copyright'}, {query: 'LinkedIn'}
];
const program = 'import json,sys; from generate_site import catalog_data,parse_catalog; from emoji_selection import search; data=catalog_data(parse_catalog(),{}); cases=json.load(sys.stdin); results=[search(data,limit=50,**case) for case in cases]; fields=["id","score","match","recommended","matched_intents","direct_intents","matched_context"]; print(json.dumps([{**r,"candidates":[{k:i[k] for k in fields} for i in r["candidates"]]} for r in results]))';
const python = process.env.EMOJI_QA_PYTHON || (process.platform === 'win32' ? path.join(root, '.venv/Scripts/python.exe') : 'python3');
const expected = JSON.parse(execFileSync(python, ['-X', 'utf8', '-c', program], {cwd: root, input: JSON.stringify(cases), encoding: 'utf8'}));
cases.forEach((example, index) => {
  const plan = dom.window.EmojiSelection.plan(example.query, example.style || '', example.constraints || {});
  const ranked = data.items.map(item => ({item, result: dom.window.EmojiSelection.rank(item, plan,
    {pack: example.pack || '', includeSpecial: !!example.include_special})})).filter(entry => entry.result)
    .sort((a, b) => b.result.score - a.result.score || a.item.order - b.item.order);
  const actual = {query: plan, count: ranked.length,
    decision: dom.window.EmojiSelection.decision(plan, ranked.map(entry => entry.result)),
    candidates: ranked.slice(0, 50).map(entry => ({id: entry.item.id, ...entry.result}))};
  assert.deepEqual(JSON.parse(JSON.stringify(actual)), expected[index], example.query);
});
dom.window.close();
console.log(`${cases.length} browser/AI comparisons passed: plans, decisions, IDs, evidence and scores.`);
