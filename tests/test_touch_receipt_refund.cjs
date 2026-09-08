const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync('server/static/touch_pos/touch-pos.js', 'utf8');
const elements = new Map();
function element(key) {
  if (!elements.has(key)) elements.set(key, {value:'', hidden:false, disabled:false, textContent:'', innerHTML:'', querySelector:element, querySelectorAll:()=>[], focus(){}, scrollIntoView(){}});
  return elements.get(key);
}
let receipt = {status:'completed', payment_type:'Cash', total:500, items:[]};
let fail = false, pending, posts = [], notices = [];
const ctx = {document:{querySelector:element,querySelectorAll:()=>[]}, window:{matchMedia:()=>({matches:false})}, URLSearchParams, Date,
  money:String, escapeHtml:s=>String(s??''), toast:s=>notices.push(s),
  api:async (url, options) => {
    if (options) { posts.push({url,options}); if (pending) await pending; if (fail) throw Error('Refund rejected'); receipt.status='refunded'; }
    if (url.includes('overview')) return {summary:{},rows:[],total_count:0};
    return {receipt};
  }};
vm.createContext(ctx);
vm.runInContext(source.slice(source.indexOf('  let receiptsOffset'), source.indexOf('  function showSalesView')), ctx);
(async()=>{
  await ctx.openTouchReceipt(7);
  assert.match(element('#receiptsDetail').innerHTML,/data-refund-open/);
  const form=element('[data-refund-form]');
  const submit=element('[data-refund-submit]');
  await form.onsubmit({preventDefault(){}});
  assert.equal(posts.length,0);
  element('input').value='Customer return';
  fail=true;
  await form.onsubmit({preventDefault(){}});
  assert.equal(element('[data-refund-error]').textContent,'Refund rejected');
  assert.equal(submit.disabled,false);
  fail=false;
  let release; pending=new Promise(resolve=>{release=resolve;});
  const refund=form.onsubmit({preventDefault(){}});
  await form.onsubmit({preventDefault(){}});
  assert.equal(posts.length,2,'double submit must not send another refund');
  release(); await refund;
  assert.equal(posts[1].url,'/api/sales/7/refund');
  assert.equal(posts[1].options.method,'POST');
  assert.equal(JSON.parse(posts[1].options.body).reason,'Customer return');
  assert.equal(notices.length,1);
  assert.ok(!element('#receiptsDetail').innerHTML.includes('data-refund-open'));
  receipt={...receipt,status:'completed',payment_type:'Credit'};
  await ctx.openTouchReceipt(8);
  assert.match(element('#receiptsDetail').innerHTML,/Credit refunds must/);
  assert.ok(!element('#receiptsDetail').innerHTML.includes('data-refund-open'));
  console.log('Receipt refund eligibility, reason, failure, duplicate submission and refresh passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
