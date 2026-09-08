const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('server/static/touch_pos/touch-pos.js','utf8');
const nodes=new Map();
function node(key){if(!nodes.has(key))nodes.set(key,{value:'',disabled:false,hidden:false,innerHTML:'',textContent:'',querySelector:node,querySelectorAll:()=>[],replaceChildren(){this.innerHTML='';},insertAdjacentHTML(_,html){this.innerHTML+=html;},scrollIntoView(){},reportValidity:()=>true,elements:{namedItem:node}});return nodes.get(key);}
let product={id:1,name:'<Product>',stock:5,cost:100,sold_by:'variants',variants:[{variant_id:9,size:'Large',stock:5,cost:100}]};
let confirm=true,fail=false,posts=[],calls=[],pending;
const ctx={document:{querySelector:node},window:{confirm:()=>confirm,matchMedia:()=>({matches:false})},URLSearchParams,
money:String,escapeHtml:s=>String(s??'').replaceAll('<','&lt;'),soldByMode:s=>s,variantLabel:v=>v.size,toast:()=>{},receiptsRequest:0,
api:async(url,options)=>{calls.push(url);if(options){posts.push(JSON.parse(options.body));if(pending)await pending;if(fail)throw Error('Save failed');return{product};}if(url.includes('movements'))return{movements:[]};if(url.includes('locations'))return{locations:['Shop']};if(url.includes('suppliers'))return{suppliers:[]};return{products:[product]};}};
vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('  let inventoryRequest'),source.indexOf('  let receiptsOffset')),ctx);
(async()=>{
await ctx.showInventoryPage();assert.equal(node('#touchInventory').hidden,false);assert.match(node('#inventoryRows').innerHTML,/&lt;Product>/);assert.ok(calls.some(url=>url.includes('offset=0')));
await ctx.openInventoryProduct(1);assert.match(node('#inventoryDetail').innerHTML,/No expiry/);assert.equal(node('location').disabled,true);node('variant_id').value='9';node('quantity').value='3';node('cost').value='120';
const form=node('#inventoryStockIn'),event={preventDefault(){}};
confirm=false;await form.onsubmit(event);assert.equal(posts.length,0);
confirm=true;fail=true;await form.onsubmit(event);assert.equal(node('[data-stock-error]').textContent,'Save failed');assert.equal(node('button[type="submit"]').disabled,false);
fail=false;let release;pending=new Promise(resolve=>release=resolve);const saving=form.onsubmit(event);await form.onsubmit(event);assert.equal(posts.length,2);release();await saving;
assert.equal(posts[1].variant_id,9);assert.equal(posts[1].adjustment,3);assert.equal(posts[1].unit_cost,120);assert.equal(posts[1].product_id,1);
product={...product,sold_by:'service'};await ctx.loadInventory();await ctx.openInventoryProduct(1);assert.ok(!node('#inventoryDetail').innerHTML.includes('inventoryStockIn'));ctx.hideInventory();assert.equal(node('#touchInventory').hidden,true);
console.log('Inventory navigation, escaping, variant stock-in, cancel, retry, duplicate prevention and service exclusion passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
