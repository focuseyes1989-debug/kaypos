const assert=require('node:assert/strict');
const {normalize,collector}=require('../server/static/touch_pos/touch-scanner.js');
const myanmar=Array.from({length:10},(_,i)=>String.fromCharCode(0x1040+i)).join('');
assert.equal(normalize(myanmar),'0123456789');
function scan(text,gap=20){const c=collector();let t=1000;for(const key of text){assert.equal(c.key(key,t),'');t+=gap;}return c.key('Enter',t);}
assert.equal(scan('8850123456789'),'8850123456789');
assert.equal(scan(myanmar),'0123456789');
assert.equal(scan('SKU-001'),'SKU-001');
assert.equal(scan('12345',250),'');
const c=collector();c.key('1',0);c.key('2',20);c.key('3',40);c.reset();assert.equal(c.key('Enter',60),'');
assert.equal(c.key('Enter',100),'');
console.log('Scanner normalization, timing, reset and duplicate terminator checks passed');

const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('server/static/touch_pos/touch-pos.js','utf8');
const start=source.indexOf('  async function scanToCart('),end=source.indexOf("  document.addEventListener('keydown', event => {",start);
const added=[];
const context={scannerReady:()=>true,token:'session',window:{KayTouchScanner:{normalize}},api:async path=>{assert.equal(path,'/api/products/scan/885');return {product:{id:1,name:'Water',stock:113,price:1000}};},chooseProduct:p=>added.push(p),toast:message=>assert.fail(message)};
vm.createContext(context);vm.runInContext(source.slice(start,end),context);
(async()=>{await context.scanToCart('885',false);assert.equal(added[0].stock,113);console.log('Scanner uses full product lookup and preserves stock');})().catch(e=>{console.error(e);process.exitCode=1;});
