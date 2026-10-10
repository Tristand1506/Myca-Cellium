// The real enhancement script runs against a small synthetic DOM.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const callbacks = {};
const field = value => ({value, addEventListener(type, fn) {callbacks[type] = fn;}});
const search = field('');
const kind = field('all');
const form = {addEventListener(type, fn) {callbacks[type] = fn;}};
const count = {textContent: ''};
const empty = {hidden: true};
const cards = [
  {dataset: {search: 'r08 selected lichen', kind: 'source'}},
  {dataset: {search: 'c01 leg proportions', kind: 'crop'}},
  {dataset: {search: 'r24 missing', kind: 'missing'}},
];
const elements = {'.filters': form, '#gallery-search': search, '#gallery-kind': kind,
                  '#gallery-count': count, '#gallery-empty': empty};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../web/gallery.js'), 'utf8'), {
  document: {querySelector: selector => elements[selector], querySelectorAll: () => cards},
  setTimeout: fn => fn(),
});
search.value = 'R08 LICHEN'; callbacks.input();
assert.deepEqual(cards.map(card => card.hidden), [false, true, true]);
assert.equal(count.textContent, '1 of 3 items shown');
kind.value = 'crop'; callbacks.change();
assert.equal(empty.hidden, false);
search.value = ''; callbacks.input();
assert.deepEqual(cards.map(card => card.hidden), [true, false, true]);
kind.value = 'all'; callbacks.reset();
assert.deepEqual(cards.map(card => card.hidden), [false, false, false]);
assert.equal(empty.hidden, true);
let prevented = false; callbacks.submit({preventDefault() {prevented = true;}});
assert.equal(prevented, true);
console.log('Gallery search, multiword/case matching, kind filtering, empty state, reset and submission passed.');
