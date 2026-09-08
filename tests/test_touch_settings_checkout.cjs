const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('server/static/touch_pos/touch-pos.js','utf8');
const ctx={cart:new Map([['1',{qty:2,price:100}]]),checkoutSettings:{tax_enabled:true,tax_rate:5},document:{querySelector:s=>({value:s==='#checkoutDiscount'?'20':'189'})}};
vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('  function cartTotals'),source.indexOf('  function restoreCart')),ctx);
let totals=ctx.checkoutTotals();assert.equal(totals.tax,9);assert.equal(totals.total,189);assert.equal(totals.balance,0);
ctx.checkoutSettings.tax_enabled=false;assert.equal(ctx.checkoutTotals().total,180);
console.log('Shared tax applies after discount in Touch checkout totals.');
