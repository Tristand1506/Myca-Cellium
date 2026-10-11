// Runs the real UI code against a synthetic DOM. Not a visual browser test.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
class Node {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase(); this.children = []; this.style = {}; this.dataset = {};
    this.handlers = {}; this.hidden = false; this.checked = false; this.disabled = false;
    this.textContent = ''; this.attributes = {}; this._value = ''; this.open = false;
    this.naturalWidth = 600; this.naturalHeight = 900; this.complete = true;
    this.clientWidth = 800; this.clientHeight = 500;
    const classes = new Set(); this.classList = {add: x => classes.add(x), remove: x => classes.delete(x),
      toggle: (x, force) => { const enabled = force ?? !classes.has(x); enabled ? classes.add(x) : classes.delete(x); return enabled; }};
  }
  append(...nodes) { this.children.push(...nodes); for (const node of nodes) if (node instanceof Node) node.parentElement = this; }
  replaceChildren(...nodes) { this.children = [...nodes]; }
  addEventListener(type, fn) { (this.handlers[type] ||= []).push(fn); }
  setAttribute(name, value) { this.attributes[name] = value; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  focus() {}
  setPointerCapture() {}
  getBoundingClientRect() { return {left: 10, top: 20, width: 100, height: 200}; }
  get value() { return this._value || (this.tagName === 'SELECT' ? this.children[0]?.value || '' : ''); }
  set value(v) { this._value = String(v); }
}
const html = fs.readFileSync(path.join(__dirname, '../web/review-desk/index.html'), 'utf8');
const nodes = {};
for (const match of html.matchAll(/<([a-z]+)[^>]*\bid="([^"]+)"[^>]*>/g)) nodes[match[2]] = new Node(match[1]);
nodes.kind.value = 'all'; nodes.sort.value = 'name'; nodes.zoom.value = 'fit';
const sha1 = '1'.repeat(64), sha2 = '2'.repeat(64);
const asset = (sha, id, title, experimental = false) => ({sha256: sha, stored_filename: title + '.png', filename_aliases: [title + '.png'], size_bytes: 1024,
  url: '/image/' + sha, classification: experimental ? ['experimental membrane design'] : ['supporting reference'], archived: false,
  references: [{reference_id: id, design_registry: {title, approved_scope: 'Lichen only', known_defects: 'Do not inherit cap height'}}]});
let server = {public: {schema_version: 1, revision: 0, collections: [{id: 'lichen', name: 'Lichen', assets: [], details: []}], details: [], archived: []},
  assets: [asset(sha1, 'R08', '<script>lichen</script>'), asset(sha2, 'R33', 'Membrane', true)], notes: {}, version: 0, undo_count: 0};
const requests = [];
const clone = x => JSON.parse(JSON.stringify(x));
let timer = 0;
const context = vm.createContext({document: {getElementById: id => nodes[id], createElement: tag => new Node(tag), createTextNode: text => text},
  window: {addEventListener() {}}, setTimeout: () => ++timer, clearTimeout() {}, console,
  fetch: async (url, options) => {
    if (!options) return {ok: true, json: async () => ({...clone(server), token: 'token'})};
    const payload = JSON.parse(options.body); requests.push(payload);
    assert.equal(payload.version, server.version);
    assert.equal(options.headers['X-Review-Token'], 'token');
    if (payload.action === 'collection_assign') server.public.collections[0].assets = payload.assets;
    if (payload.action === 'note') server.notes[payload.id] = payload.text;
    if (payload.action === 'archive') { server.public.archived.push(...payload.assets); server.assets.forEach(a => { a.archived = server.public.archived.includes(a.sha256); }); }
    if (payload.action === 'detail_save') server.public.details.push({id: 'view-test', title: payload.title, asset_sha256: payload.asset_sha256, rect: payload.rect});
    server.version++; server.undo_count++; return {ok: true, json: async () => clone(server)};
  }});
context.fixture = clone(server);
const code = fs.readFileSync(path.join(__dirname, '../web/review-desk/desk.js'), 'utf8').replace(/init\(\);\s*$/, '');
vm.runInContext(code, context);
const evaluate = source => vm.runInContext(source, context);
(async () => {
  evaluate('state = fixture; token = "token"; bind(); render();');
  assert.equal(nodes.grid.children.length, 2);
  assert.match(nodes['library-summary'].textContent, /2 preserved images/);
  assert.equal(nodes['selection-bar'].hidden, true);
  nodes.search.value = 'r08 LICHEN'; evaluate('render()'); assert.equal(nodes.grid.children.length, 1);
  const title = nodes.grid.children[0].children[2].children[1];
  assert.equal(title.textContent, '<script>lichen</script>'); assert.equal(title.children.length, 0);
  nodes.search.value = ''; nodes.kind.value = 'experiments'; evaluate('render()'); assert.equal(nodes.grid.children.length, 1);
  nodes.kind.value = 'all'; evaluate(`selection.add('${sha1}'); selectionBar();`);
  assert.equal(nodes.compare.disabled, true);
  evaluate(`selection.add('${sha2}'); selectionBar();`); assert.equal(nodes.compare.disabled, false);
  evaluate('openCompare()'); assert.equal(nodes['compare-grid'].children.length, 2);
  evaluate('view = "lichen"; render();'); assert.equal(nodes.grid.children.length, 0);
  await evaluate(`mutate('collection_assign', {id: 'lichen', assets: ['${sha1}']})`);
  assert.equal(nodes.grid.children.length, 1);
  await evaluate(`openViewer('${sha1}')`); assert.equal(nodes.viewer.open, true);
  assert.match(nodes['viewer-id'].textContent, /R08/);
  evaluate('startRegion()'); assert.equal(nodes['region-form'].hidden, false);
  nodes['image-stage'].handlers.pointerdown[0]({clientX: 30, clientY: 60, button: 0, pointerId: 1, preventDefault() {}});
  nodes['image-stage'].handlers.pointermove[0]({clientX: 90, clientY: 180});
  assert.deepEqual(JSON.parse(evaluate('JSON.stringify(rect)')), [.2, .2, .8, .8]);
  await evaluate(`mutate('detail_save', {asset_sha256: '${sha1}', title: 'Lichen region', rect})`);
  assert.equal(server.public.details.length, 1);
  const detailNode = evaluate('regionImage(findItem("view-test"))');
  const container = new Node(); container.append(detailNode);
  detailNode.children[0].handlers.load[0]();
  assert.equal(Number(detailNode.style.aspectRatio), 2 / 3);
  nodes['private-note'].value = 'private sentinel'; nodes['private-note'].oninput();
  await evaluate('flushNote()'); assert.equal(server.notes[sha1], 'private sentinel');
  assert.equal(JSON.stringify(server.public).includes('private sentinel'), false);
  await evaluate(`mutate('archive', {assets: ['${sha1}']})`);
  evaluate('view = "active"; render();'); assert.equal(nodes.grid.children.length, 1);
  evaluate('view = "archive"; render();'); assert.equal(nodes.grid.children.length, 2); // Original + its linked detail.
  await evaluate('openViewer("view-test")'); assert.equal(nodes['image-stage'].dataset.focused, 'true');
  evaluate('startRegion()'); assert.equal(nodes['image-stage'].dataset.focused, 'false');
  assert.match(nodes['note-status'].textContent, /autosave/);
  console.log('Review Desk UI: filtering, safe labels, collections, pair comparison, region drawing/focus, private notes and archive views passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
