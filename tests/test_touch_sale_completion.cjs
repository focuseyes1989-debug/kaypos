const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('server/static/touch_pos/touch-pos.js','utf8');
let enabled='0',fail=false;const calls=[],status={textContent:''},button={disabled:false};
const ctx={document:{querySelector:s=>s==='#receiptPaper'?{value:'58'}:s==='#printReceiptButton'?button:status},window:{KayTouchReceipt:{settings:()=>({touch_auto_print_receipt:enabled}),print:async(...args)=>{calls.push(args);if(fail)throw Error('Print unavailable');}}}};
vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('  async function runSaleCompletionActions'),source.indexOf('  async function checkoutCashSale')),ctx);
(async()=>{
 const receipt={id:12};await ctx.runSaleCompletionActions(receipt,100);assert.equal(calls.length,0);
 enabled='1';await ctx.runSaleCompletionActions(receipt,100);assert.deepEqual(calls[0],[receipt,100,'58']);assert.equal(button.disabled,false);
 fail=true;await ctx.runSaleCompletionActions(receipt,100);assert.match(status.textContent,/Sale saved/);assert.match(status.textContent,/Print unavailable/);assert.equal(button.disabled,false);
 assert.ok(!source.includes('/api/cashdrawer/open'));
 console.log('Browser auto-print off/on, selected paper, saved-sale failure and button recovery passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
