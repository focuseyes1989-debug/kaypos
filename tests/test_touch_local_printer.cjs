const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const calls=[],data=new Map();
const ctx={window:{},localStorage:{getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v)},crypto:{randomUUID:()=> 'uuid-test'},AbortController,TypeError,Error,setTimeout,clearTimeout,fetch:async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({status:'sent',printers:['Local only']})};}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('server/static/touch_pos/touch-local-printer.js','utf8'),ctx);
(async()=>{
 const api=ctx.window.KayLocalPrinter;
 assert.equal(api.settings().touch_auto_print_receipt,'0');
 await assert.rejects(()=>api.printers(),/pairing key/);
 api.save({bridge_key:'private-local-key',receipt_printer_name:'Local only',receipt_paper_size:'1'});
 assert.equal(api.settings().receipt_printer_name,'Local only');
 await api.printers();await api.print({items:[]},0);await api.drawer('sale-123');
 assert.ok(calls.every(c=>c.url.startsWith('http://127.0.0.1:17861/')));
 assert.equal(JSON.parse(calls[1].options.body).paper,'58');
 assert.equal(calls[0].options.headers['X-Kay-Bridge-Key'],'private-local-key');
 assert.equal(calls[0].options.credentials,'omit');
 assert.equal(JSON.parse(calls[2].options.body).request_key,'sale-123');
 data.clear();assert.equal(api.settings().receipt_printer_name,'');
 console.log('Local printer browser preferences, pairing, loopback requests and paper selection passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
