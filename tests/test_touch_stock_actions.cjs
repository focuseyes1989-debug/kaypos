const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('server/static/touch_pos/touch-pos.js','utf8');
const map=new Map(),tabs=['in','out','adjust'].map(stockAction=>({dataset:{stockAction},setAttribute(){},disabled:false}));
function node(key){if(!map.has(key))map.set(key,{value:'',hidden:false,disabled:false,innerHTML:'',textContent:'',insertAdjacentHTML(){},reportValidity:()=>true,querySelector:node,querySelectorAll:()=>tabs,elements:{namedItem:name=>name==='variant'?null:node(name)}});return map.get(key);}
let confirmed=true,fail=false,posts=[],resolve,pending;
const ctx={soldByMode:s=>s,escapeHtml:String,money:String,variantLabel:()=>'',inventoryLocations:['Shop'],inventoryDetailRequest:2,inventoryRequest:0,toast:()=>{},window:{confirm:()=>confirmed},api:async(url,options)=>{posts.push({url,body:JSON.parse(options.body)});if(pending)await pending;if(fail)throw Error('Insufficient stock');}};
vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('  function setupInventoryActions'),source.indexOf('  let inventoryRequest')),ctx);
(async()=>{
ctx.setupInventoryActions({id:1,name:'Test',stock:10,sold_by:'each'},node('detail'),1);
tabs[1].onclick();node('quantity').value='3';node('reason').value='Damage';node('actor').value='Tester';node('location').value='Shop';
const form=node('#inventoryChange'),event={preventDefault(){}};
confirmed=false;await form.onsubmit(event);assert.equal(posts.length,0);
confirmed=true;fail=true;await form.onsubmit(event);assert.equal(node('[data-change-error]').textContent,'Insufficient stock');assert.equal(node('[data-change-save]').disabled,false);
assert.equal(posts[0].body.adjustment,-3);assert.equal(posts[0].body.restrict_location,true);
tabs[2].onclick();node('quantity').value='7';fail=false;pending=new Promise(r=>resolve=r);const save=form.onsubmit(event);await form.onsubmit(event);assert.equal(posts.length,2);resolve();await save;
assert.equal(posts[1].url,'/api/stock/adjustment');assert.equal(posts[1].body.expected_stock,10);assert.equal(posts[1].body.new_quantity,7);assert.equal(posts[1].body.adjusted_by,'Tester');
console.log('Stock action switching, cancellation, location payload, count guard, retry and duplicate prevention passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
