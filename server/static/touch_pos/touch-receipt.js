(function(root) {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = value => Number.isFinite(Number(value)) ? Number(value) : 0;
  const money = value => number(value).toLocaleString('en-US', {maximumFractionDigits:2});
  function paper(value) { return ({'0':'80','1':'58','2':'a4','58':'58','80':'80','a4':'a4'})[String(value).toLowerCase()] || '80'; }
  function documentHtml(receipt, paid, size) {
    const s = receipt.receipt_settings || {}, format = paper(size), a4 = format === 'a4';
    const items = Array.isArray(receipt.items) ? receipt.items : [];
    const total = number(receipt.total), payment = number(paid ?? receipt.paid_amount ?? receipt.payment);
    const subtotal = receipt.subtotal ?? items.reduce((sum,i) => sum + number(i.total ?? number(i.qty)*number(i.price)), 0);
    const currency = s.currency_symbol || 'Ks';
    const amount = value => `${money(value)} ${esc(currency)}`;
    const text = value => value ? `<p>${esc(value)}</p>` : '';
    const image = (value, cls) => /^data:image\/(png|jpeg);base64,[a-z0-9+/=\s]+$/i.test(value || '') ? `<img class="${cls}" src="${esc(value)}" alt="${cls === 'logo' ? 'Shop logo' : 'Payment QR code'}">` : '';
    const row = (label,value,cls='') => `<div class="sum ${cls}"><span>${esc(label)}</span><strong>${amount(value)}</strong></div>`;
    return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(receipt.invoice_no || 'Receipt')}</title><style>
@page{size:${a4 ? 'A4' : 'auto'};margin:${a4 ? '12mm' : '0'}}
*{box-sizing:border-box}html,body{margin:0;background:white;color:black;font-family:"Myanmar Text","Noto Sans Myanmar","Segoe UI",sans-serif;font-size:${a4 ? '11pt' : format === '58' ? '9pt' : '10pt'};line-height:1.5}
.receipt{width:${a4 ? '100%' : format === '58' ? '48mm' : '72mm'};max-width:100%;margin:${a4 ? '0' : '0 auto'};padding:3mm 0}header,footer{text-align:center}h1{font-size:1.4em;margin:0}h2{font-size:1.1em;margin:2mm 0}p{margin:1mm 0;white-space:pre-wrap;overflow-wrap:anywhere}.meta{border-block:1px dashed #000;padding:2mm 0;margin:3mm 0}table{border-collapse:collapse;width:100%;table-layout:fixed}th,td{text-align:right;vertical-align:top;padding:2mm 0;overflow-wrap:anywhere}th:first-child,td:first-child{text-align:left;width:${a4 ? '46%' : '58%'}}th{border-bottom:1px solid black}td{border-bottom:1px dotted #aaa}tr,.sum,header,footer{break-inside:avoid}thead{display:table-header-group}.item-detail{font-size:.9em}.totals{margin:3mm 0 3mm auto;${a4 ? 'width:85mm;max-width:100%' : ''}}.sum{display:flex;justify-content:space-between;gap:3mm;margin:1mm 0}.sum strong{text-align:right;overflow-wrap:anywhere;min-width:0}.grand{font-size:1.2em;border-block:1px solid black;padding:2mm 0}.logo{max-width:30mm;max-height:20mm}.qr{width:28mm;max-width:100%}footer{border-top:1px dashed black;padding-top:3mm}h1{overflow-wrap:anywhere}
</style></head><body><article class="receipt"><header>${image(s.shop_logo_image,'logo')}<h1>${esc(s.shop_name || 'KAY POS')}</h1>${text(s.shop_phone)}${text(s.shop_address)}${text(s.receipt_header)}<h2>${String(receipt.status).toLowerCase()==='refunded' ? 'REFUNDED RECEIPT' : 'RECEIPT'}</h2></header><div class="meta">${text(receipt.invoice_no)}${text(receipt.created_at)}${s.show_customer_name === false || s.show_customer_name === '0' ? '' : text(receipt.customer_name || 'Walk-in Customer')}${text(receipt.payment_type || 'Cash')}</div><table><thead><tr><th>Item${a4?'':' / Qty × Price'}</th>${a4?'<th>Qty</th><th>Price</th>':''}<th>Amount</th></tr></thead><tbody>${items.map(i=>`<tr><td>${esc(i.product_name || i.name || 'Item')}${i.variant_label?text(i.variant_label):''}${a4?'':`<div class="item-detail">${money(i.qty)} × ${money(i.price)}</div>`}</td>${a4?`<td>${money(i.qty)}</td><td>${money(i.price)}</td>`:''}<td>${money(i.total ?? number(i.qty)*number(i.price))}</td></tr>`).join('')}</tbody></table><div class="totals">${row('Subtotal',subtotal)}${row('Discount',receipt.discount_amount ?? 0)}${row('Tax',receipt.tax_amount ?? receipt.tax ?? Math.max(0, total - number(subtotal) + number(receipt.discount_amount)))}${row('Total',total,'grand')}${row('Paid',payment)}${row('Change',Math.max(0,payment-total))}${String(receipt.payment_type).toLowerCase()==='credit' || number(receipt.balance_amount)>0 ? row('Credit balance',receipt.balance_amount ?? Math.max(0,total-payment)) : ''}</div><footer>${image(s.shop_qr_code_image,'qr')}${text(s.shop_qr_name)}${text(s.receipt_footer)}${text(s.shop_footer_message)}${text(s.receipt_thank_you_text || 'Thank you.')}</footer></article></body></html>`;
  }
  async function print(receipt, paid, size) {
    document.querySelector('#touchReceiptPrintFrame')?.remove();
    const frame = document.createElement('iframe');
    frame.id='touchReceiptPrintFrame'; frame.title='Receipt print document';
    frame.style.cssText='position:fixed;left:-10000px;top:0;width:800px;height:600px;border:0';
    const loaded = new Promise(resolve => { frame.onload=resolve; });
    frame.srcdoc=documentHtml(receipt,paid,size); document.body.appendChild(frame);
    await loaded;
    await frame.contentDocument.fonts.ready;
    await Promise.all(Array.from(frame.contentDocument.images, img => img.decode().catch(()=>{})));
    frame.contentWindow.focus(); frame.contentWindow.print();
  }
  const api={paper,documentHtml,print};
  if(typeof module !== 'undefined' && module.exports) module.exports=api;
  else root.KayTouchReceipt=api;
})(typeof window !== 'undefined' ? window : globalThis);
