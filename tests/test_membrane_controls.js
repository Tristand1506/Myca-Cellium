const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
class Node {
  constructor() {this.handlers={};this.hidden=false;this.checked=false;this.disabled=false;this.dataset={};this.children=[];this.style={setProperty(){}};}
  addEventListener(type,fn) {this.handlers[type]=fn;}
  querySelectorAll() {return [];}
  replaceChildren() {this.children=[];}
  append(node) {this.children.push(node);}
  scrollIntoView() {}
}
const nodes={};
for(const id of ['membrane-direction','membrane-selection-status','membrane-compare-button',
                 'membrane-comparison','membrane-comparison-grid','membrane-clear']) nodes[id]=new Node();
nodes['membrane-comparison'].hidden=true;
nodes['membrane-compare-button'].disabled=true;
const tools=new Node();
const sections=['petal','lace','empty'].map(id=>{const n=new Node();n.dataset.direction=id;return n;});
const cards=['a','b','c','d','e','a'].map(id=>{
 const article=new Node();article.dataset.compareId=id;
 article.cloneNode=()=>({picker:{removed:false,remove(){this.removed=true;}},limit:{open:false},
                         querySelector(selector){return selector==='.compare-picker'?this.picker:this.limit;}});
 const input=new Node();const picker=new Node();picker.hidden=true;
 input.closest=selector=>selector==='[data-compare-id]'?article:picker;
 return {article,input,picker};
});
const code=fs.readFileSync(path.join(__dirname,'../web/membrane-compare.js'),'utf8');
vm.runInNewContext(code,{document:{
 getElementById:id=>nodes[id],
 querySelector:()=>tools,
 querySelectorAll:selector=>selector==='[data-compare-select]'?cards.map(c=>c.input):
   selector==='[data-direction]'?sections:[],
},console});
const choose=(index,checked=true)=>{cards[index].input.checked=checked;cards[index].input.handlers.change();};
assert.equal(tools.hidden,false);
assert.ok(cards.every(c=>!c.picker.hidden));
choose(0);
assert.equal(nodes['membrane-compare-button'].disabled,true);
assert.equal(cards[5].input.checked,true); // The same source in another group.
choose(1);
assert.equal(nodes['membrane-compare-button'].disabled,false);
nodes['membrane-direction'].value='empty';nodes['membrane-direction'].handlers.change();
assert.deepEqual(sections.map(n=>n.hidden),[true,true,false]);
assert.equal(cards[0].input.checked,true);
nodes['membrane-compare-button'].handlers.click();
assert.equal(nodes['membrane-comparison-grid'].children.length,2);
assert.ok(nodes['membrane-comparison-grid'].children.every(n=>n.limit.open&&n.picker.removed));
choose(2);choose(3);
assert.equal(nodes['membrane-comparison-grid'].children.length,4);
choose(4);
assert.equal(cards[4].input.checked,false);
assert.match(nodes['membrane-selection-status'].textContent,/Four studies/);
choose(5,false);
assert.equal(cards[0].input.checked,false);
assert.equal(nodes['membrane-comparison-grid'].children.length,3);
nodes['membrane-clear'].handlers.click();
assert.equal(nodes['membrane-comparison'].hidden,true);
assert.equal(nodes['membrane-compare-button'].disabled,true);
assert.ok(cards.every(c=>!c.input.checked));
console.log('Membrane controls passed: persistent filtering, duplicate-source synchronization, 2–4 panels, visible limitations, item limit and clear.');
