const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const s=fs.readFileSync('server/static/touch_pos/touch-pos.js','utf8');
const red={variant_id:1,regular_price:1000,price:1000,wholesale_min_qty:12,wholesale_price:800,qty:6};
const blue={...red,variant_id:2};const c={cart:new Map([[1,red],[2,blue]])};vm.createContext(c);vm.runInContext(s.slice(s.indexOf('  function repriceVariantCart'),s.indexOf('  function saveCart')),c);
c.repriceVariantCart();assert.equal(red.price,1000);assert.equal(blue.price,1000);red.qty=12;c.repriceVariantCart();assert.equal(red.price,800);assert.equal(blue.price,1000);red.qty=11;c.repriceVariantCart();assert.equal(red.price,1000);console.log('Variant wholesale quantity isolation and price restoration passed.');
