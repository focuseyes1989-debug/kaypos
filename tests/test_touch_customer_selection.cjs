const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let source=fs.readFileSync('server/static/touch_pos/touch-customers.js','utf8').replace(' window.KayTouchCustomers=', ' window.test={load,set:(r,c)=>{root=r;ctx=c;}};window.KayTouchCustomers=');
const nodes={};const get=s=>nodes[s]||(nodes[s]={value:'',innerHTML:'',disabled:false});const actions={};
get('[data-customer-detail]').querySelector=s=>actions[s]||(actions[s]={});
const button={dataset:{select:'1'},setAttribute(k,v){this[k]=v}};
const root={hidden:false,querySelector:get,querySelectorAll:s=>s==='[data-select]'?[button]:[]};
const sandbox={window:{matchMedia:()=>({matches:false})},URLSearchParams};vm.createContext(sandbox);vm.runInContext(source,sandbox);
sandbox.window.test.set(root,{api:async()=>({customers:[{id:1,name:'<Alice>',phone:'123',current_balance:200,credit_limit:1000,points:5}]}),escapeHtml:s=>String(s).replaceAll('<','&lt;').replaceAll('>','&gt;')});
(async()=>{await sandbox.window.test.load();button.onclick();assert.equal(button['aria-pressed'],'true');assert.match(get('[data-customer-detail]').innerHTML,/&lt;Alice&gt;/);assert.match(get('[data-customer-detail]').innerHTML,/1,000 Ks/);for(const s of ['[data-edit]','[data-ledger]','[data-collect]','[data-delete]'])assert.equal(typeof actions[s].onclick,'function');console.log('Customer selection, escaped details and action wiring passed.');})().catch(e=>{console.error(e);process.exitCode=1});
