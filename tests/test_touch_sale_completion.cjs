const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('server/static/touch_pos/touch-pos.js','utf8');
const calls=[],status={textContent:''};let drawerFail=false,printFail=false,settings={};
const ctx={document:{querySelector:s=>s==='#receiptPaper'?{value:'80'}:status},window:{KayLocalPrinter:{settings:()=>settings,jobKey:()=> 'test-key',drawer:async()=>{calls.push('/drawer');if(drawerFail)throw Error('Printer offline');},print:async()=>{calls.push('print');if(printFail)throw Error('Blocked');}}}};
vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('  async function runSaleCompletionActions'),source.indexOf('  async function checkoutCashSale')),ctx);
(async()=>{
 for(const drawer of ['0','1'])for(const print of ['0','1']){
  calls.length=0;settings={touch_auto_open_drawer:drawer,touch_auto_print_receipt:print};await ctx.runSaleCompletionActions({},100);
  assert.deepEqual(calls,[...(drawer==='1'?['/drawer']:[]),...(print==='1'?['print']:[])]);assert.equal(status.textContent,'');
 }
 calls.length=0;drawerFail=true;printFail=true;
 settings={touch_auto_open_drawer:'1',touch_auto_print_receipt:'1'};await ctx.runSaleCompletionActions({},100);
 assert.deepEqual(calls,['/drawer','print']);assert.match(status.textContent,/Sale saved/);assert.match(status.textContent,/Printer offline/);assert.match(status.textContent,/Blocked/);
 calls.length=0;settings={};await ctx.runSaleCompletionActions({},100);assert.equal(calls.length,0);
 console.log('Sale completion: independent options, off defaults and isolated peripheral failures passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
