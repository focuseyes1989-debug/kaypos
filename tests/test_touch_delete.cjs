const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('server/static/touch_pos/touch-pos.js', 'utf8');
const fn = source.slice(source.indexOf('  async function deleteManagedItem'), source.indexOf('  function renderManagedCategories'));
async function run(confirmed, rejected) {
 const calls = [], messages = [];
 const context = {window:{confirm:()=>confirmed}, crypto:{randomUUID:()=> 'qa-id'}, cart:new Map([['a',{product_id:1}],['b',{product_id:2}]]),
 api:async(path, options)=>{calls.push([path,options]); return options ? (rejected ? {rejected} : {result:{}}) : {revision:'r1'};},
 saveCart:()=>calls.push('saveCart'),renderCart:()=>calls.push('renderCart'),loadCatalog:async()=>calls.push('catalog'),loadProductManager:async()=>calls.push('manager'),toast:x=>messages.push(x)};
 vm.createContext(context); vm.runInContext(fn, context);
 const button={disabled:false,textContent:'Delete'};
 await context.deleteManagedItem({id:1,name:'QA item'},button);
 assert.equal(button.disabled,false);
 if(!confirmed){assert.equal(calls.length,0);return;}
 assert.equal(JSON.parse(calls[1][1].body).values.revision,'r1');
 if(rejected){assert.equal(context.cart.size,2);assert.deepEqual(messages,[rejected]);return;}
 assert.equal(context.cart.has('a'),false);assert.equal(context.cart.has('b'),true);
 assert.deepEqual(messages,['Item deleted.']);assert.equal(button.textContent,'Delete');
}
(async()=>{await run(false);await run(true);await run(true,'Product has history');console.log('Delete workflow: 3 checks passed');})();
