const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync('server/static/touch_pos/touch-pos.js', 'utf8');
let total = 2500, received = 2500, buttons = [], activated = false, updated = false;
const container = {innerHTML:'', querySelectorAll:()=>buttons};
const input = {value:'', dispatchEvent:()=>{updated=true;}};
const ctx = {Number, Set, money:String, Event:class {}, checkoutTotals:()=>({total,received}),
 document:{querySelector:s=>s==='#checkoutReceivedSuggestions'?container:input},
 activateCheckoutKeypad:el=>{assert.equal(el,input);activated=true;}};
vm.createContext(ctx);
vm.runInContext(source.slice(source.indexOf('  function suggestedReceivedAmounts'),source.indexOf('  function renderCheckoutSummary')),ctx);
for(const [amount, expected] of [[500,[500,1000,5000,10000]],[2500,[2500,3000,5000,10000]],[3000,[3000,5000,10000]],[4000,[4000,5000,10000]],[15000,[15000,20000]],[20000,[20000]],[25100,[25100,30000]],[0,[]]]) {
 assert.deepEqual(Array.from(ctx.suggestedReceivedAmounts(amount)),expected);
}
const button={dataset:{receivedAmount:'5000'},addEventListener:(event,fn)=>button.click=fn};
buttons=[button];ctx.renderReceivedSuggestions();assert.match(container.innerHTML,/2500.*aria-pressed="true"/);
button.click();assert.equal(input.value,'5000');assert.ok(activated && updated);
total=4000;ctx.renderReceivedSuggestions();assert.doesNotMatch(container.innerHTML,/data-received-amount="2500"/);
console.log('Quick received amounts: examples, total changes and input interaction passed.');
