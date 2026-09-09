const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('server/static/touch_pos/touch-pos.js','utf8');
let ready=true,disabled=false,opens=0,focus=0,resolve;
const ctx={scannerReady:()=>ready,scanner:{reset(){}},document:{querySelector:s=>s==='#paymentButton'?{disabled}:{focus(){focus++},select(){}},addEventListener(){}},openCheckoutDetails:()=>{opens++;return new Promise(r=>resolve=r)}};
vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('  let checkoutShortcutPending'),source.indexOf('  async function scanToCart')),ctx);
const key=(key,extra={})=>({key,preventDefault(){},stopImmediatePropagation(){},...extra});
(async()=>{
 await ctx.handleSaleShortcut(key('F2'));assert.equal(focus,1);
 const pending=ctx.handleSaleShortcut(key('F4'));await ctx.handleSaleShortcut(key('F4'));assert.equal(opens,1);resolve();await pending;
 for(const extra of [{repeat:true},{altKey:true},{ctrlKey:true},{isComposing:true}])await ctx.handleSaleShortcut(key('F4',extra));
 disabled=true;await ctx.handleSaleShortcut(key('F4'));disabled=false;ready=false;await ctx.handleSaleShortcut(key('F4'));await ctx.handleSaleShortcut(key('F2'));assert.equal(opens,1);assert.equal(focus,1);
 console.log('Sale shortcuts: F2, F4, pending/repeat, modifiers, empty cart and modal/page guards passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
