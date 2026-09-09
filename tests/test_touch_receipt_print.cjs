const assert=require('node:assert/strict');
const {paper,documentHtml}=require('../server/static/touch_pos/touch-receipt.js');
const receipt={invoice_no:'TEST-001',created_at:'2026-09-09 12:00',total:945,discount_amount:100,payment:1000,items:[{product_name:'မြန်မာစာ ပစ္စည်းအမည်ရှည် <script>alert(1)</script>',qty:2,price:500,total:1000}],receipt_settings:{shop_name:'KAY & POS',show_customer_name:'0'}};
for(const [value,expected] of [['0','80'],['1','58'],['2','a4'],['bad','80']])assert.equal(paper(value),expected);
for(const format of ['58','80','a4']){
 const html=documentHtml(receipt,undefined,format);
 assert.ok(html.includes(format==='a4'?'size:A4':format==='58'?'width:48mm':'width:72mm'));
 assert.ok(html.includes('KAY &amp; POS'));assert.ok(!html.includes('<script>'));
 assert.ok(html.includes('45 Ks'));assert.ok(html.includes('55 Ks'));assert.ok(!html.includes('Walk-in Customer'));
}
const zero=documentHtml({...receipt,total:0,discount_amount:1000},0,'58');assert.ok(zero.includes('<strong>0 Ks</strong>'));
const credit=documentHtml({...receipt,payment_type:'Credit',balance_amount:445},500,'80');assert.ok(credit.includes('Credit balance'));assert.ok(credit.includes('445 Ks'));
const image=documentHtml({...receipt,receipt_settings:{shop_logo_image:'javascript:alert(1)'}},1000,'80');assert.ok(!image.includes('<img'));
console.log('Receipt paper sizes, escaping, tax, zero totals, credit and image validation passed.');
