(() => {
  'use strict';
  const connection = document.querySelector('#connection'), clock = document.querySelector('#clock');
  const fullscreen = document.querySelector('#fullscreen'), install = document.querySelector('#install');
  const loginView = document.querySelector('#loginView'), appView = document.querySelector('#app');
  const loginForm = document.querySelector('#loginForm'), loginStatus = document.querySelector('#loginStatus');
  const signIn = document.querySelector('#signIn'), password = document.querySelector('#password');
  const username = document.querySelector('#username'), userButton = document.querySelector('#userButton');
  const userMenu = document.querySelector('#userMenu'), TOKEN_KEY = 'kay_touch_pos_token';
  const sideMenuButton = document.querySelector('#sideMenuButton'), sideMenu = document.querySelector('#sideMenu');
  const sideMenuOverlay = document.querySelector('#sideMenuOverlay'), closeSideMenuButton = document.querySelector('#closeSideMenu');
  const CART_KEY = 'kay_touch_pos_cart';
  let token = sessionStorage.getItem(TOKEN_KEY), installPrompt = null, products = [], customers = [], categories = [], selectedCategory = '';
  let managedProducts = [], managedCategories = [], editingProduct = null, editingCategory = null, barcodeProduct = null, managerSearchTimer = null;
  let cart = new Map(), avatarUrl = '';
  let searchTimer = null, productsController = null, toastTimer = null, choiceState = null;

  function setConnection(ok) {
    for (const item of [connection, document.querySelector('#loginConnection')]) {
      item.className = `connection ${ok ? 'online' : 'offline'}`;
      item.querySelector('span').textContent = ok ? 'Server connected' : 'Server unavailable';
    }
  }
  async function api(path, options = {}) {
    const headers = {'Content-Type': 'application/json', ...(options.headers || {})};
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(path, {...options, headers, cache: 'no-store'});
    const text = await response.text(); let value = {};
    try { value = text ? JSON.parse(text) : {}; } catch (_) { value = {detail: text}; }
    if (response.status === 401 && path !== '/api/login') showLogin('Session expired. Please sign in again.');
    if (!response.ok) throw new Error(value.detail || `Request failed (${response.status})`);
    return value;
  }
  function initials(user) { return String(user.full_name || user.username || '?').trim().split(/\s+/).slice(0, 2).map(value => value[0]).join('').toUpperCase(); }
  function escapeHtml(value) { return String(value ?? '').replace(/[&<>'"]/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[character])); }
  function money(value) { return Number(value || 0).toLocaleString(undefined, {maximumFractionDigits: 0}); }
  const code128Patterns = ["212222","222122","222221","121223","121322","131222","122213","122312","132212","221213","221312","231212","112232","122132","122231","113222","123122","123221","223211","221132","221231","213212","223112","312131","311222","321122","321221","312212","322112","322211","212123","212321","232121","111323","131123","131321","112313","132113","132311","211313","231113","231311","112133","112331","132131","113123","113321","133121","313121","211331","231131","213113","213311","213131","311123","311321","331121","312113","312311","332111","314111","221411","431111","111224","111422","121124","121421","141122","141221","112214","112412","122114","122411","142112","142211","241211","221114","413111","241112","134111","111242","121142","121241","114212","124112","124211","411212","421112","421211","212141","214121","412121","111143","111341","131141","114113","114311","411113","411311","113141","114131","311141","411131","211412","211214","211232","2331112"];
  function soldByMode(value) {
    const mode = String(value || 'each').trim().toLowerCase().replace(/_/g, ' ').replace(/\s+/g, ' ');
    if (mode === 'service' || mode === 'services' || mode.endsWith(' service')) return 'service';
    if (mode === 'variant' || mode === 'variants' || mode.endsWith(' variants')) return 'variants';
    return mode;
  }
  function toast(message) {
    const item = document.querySelector('#workspaceToast'); item.textContent = message; item.classList.add('show'); clearTimeout(toastTimer);
    toastTimer = setTimeout(() => item.classList.remove('show'), 2200);
  }
  function cartKey(product, variant = null) { return `${Number(product.id) || 0}:${Number((variant || {}).variant_id) || 0}`; }
  function variantLabel(variant) { return [variant?.color, variant?.size].filter(Boolean).join(' / '); }
  function stockFor(product, variant = null) { return Number((variant || product).stock || 0); }
  function isService(product) { return soldByMode(product.sold_by) === 'service' || Boolean(product.is_service); }
  function productOutOfStock(product) {
    const service = isService(product), variants = soldByMode(product.sold_by) === 'variants';
    const variantRows = Array.isArray(product.variants) ? product.variants : [];
    const variantOut = variants && (!variantRows.length || variantRows.every(item => Number(item.stock || 0) <= 0));
    return Boolean(product.is_out_of_stock) || (!service && (variants ? variantOut : Number(product.stock || 0) <= 0));
  }
  function variantName(variant, index = 0) {
    return variantLabel(variant) || variant?.sku || variant?.barcode || `Variant ${index + 1}`;
  }
  function saveCart() {
    sessionStorage.setItem(CART_KEY, JSON.stringify([...cart.values()]));
  }
  function cartTotals() {
    const items = [...cart.values()], count = items.reduce((sum, item) => sum + Number(item.qty || 0), 0);
    const subtotal = items.reduce((sum, item) => sum + Number(item.price || 0) * Number(item.qty || 0), 0);
    return {items, count, subtotal, discount: 0, total: subtotal};
  }
  function checkoutTotals() {
    const {items, count, subtotal} = cartTotals();
    const rawDiscount = Math.max(0, Number(document.querySelector('#checkoutDiscount')?.value || 0));
    const discount = Math.min(subtotal, rawDiscount);
    const total = Math.max(0, subtotal - discount);
    const received = Math.max(0, Number(document.querySelector('#checkoutReceived')?.value || 0));
    return {items, count, subtotal, rawDiscount, discount, total, received, change: Math.max(0, received - total), balance: Math.max(0, total - received)};
  }
  function restoreCart() {
    try {
      cart = new Map(JSON.parse(sessionStorage.getItem(CART_KEY) || '[]').map(item => [item.key, item]));
    } catch (_) {
      cart = new Map(); sessionStorage.removeItem(CART_KEY);
    }
    renderCart();
  }
  function clearCart() {
    cart.clear(); sessionStorage.removeItem(CART_KEY);
    renderCart();
  }
  function clearAvatar() {
    if (avatarUrl) URL.revokeObjectURL(avatarUrl);
    avatarUrl = '';
    for (const image of [document.querySelector('#userAvatar'), document.querySelector('#sideMenuAvatar')]) {
      image.hidden = true;
      image.removeAttribute('src');
    }
    document.querySelector('#userInitials').hidden = false;
    document.querySelector('#sideMenuInitials').hidden = false;
  }
  async function loadAvatar() {
    clearAvatar();
    try {
      const response = await fetch('/api/user/avatar', {
        headers: token ? {Authorization: `Bearer ${token}`} : {},
        cache: 'no-store',
      });
      if (!response.ok) return;
      avatarUrl = URL.createObjectURL(await response.blob());
      for (const image of [document.querySelector('#userAvatar'), document.querySelector('#sideMenuAvatar')]) {
        image.src = avatarUrl;
        image.hidden = false;
      }
      document.querySelector('#userInitials').hidden = true;
      document.querySelector('#sideMenuInitials').hidden = true;
    } catch (_) {
      clearAvatar();
    }
  }
  function renderCart() {
    const {items, count, subtotal, total} = cartTotals();
    const root = document.querySelector('#cartItems');
    document.querySelector('#cartCount').textContent = String(count);
    document.querySelector('#mobileCartCount').textContent = String(count);
    document.querySelector('#sideCartBadge').textContent = String(count);
    document.querySelector('#cartSubtotal').textContent = `${money(subtotal)} Ks`;
    document.querySelector('#cartTotal').textContent = `${money(total)} Ks`;
    document.querySelector('#clearCart').disabled = count === 0;
    document.querySelector('#paymentButton').disabled = count === 0;
    document.querySelector('#cartHint').textContent = count ? `${items.length} line${items.length === 1 ? '' : 's'} in cart` : 'Tap products to add';
    if (!items.length) {
      root.innerHTML = '<div class="cart-empty"><span>🛒</span><strong>Cart is empty</strong><small>Tap a product to add it to this sale.</small></div>';
      return;
    }
    root.innerHTML = items.map(item => `<div class="cart-row" data-cart-key="${escapeHtml(item.key)}"><div class="cart-row-main"><span class="cart-row-title">${escapeHtml(item.name)}</span><span class="cart-row-meta">${escapeHtml(item.variant_label || item.sku || 'Standard')} · ${money(item.price)} Ks each</span></div><div class="cart-row-total">${money(Number(item.price || 0) * Number(item.qty || 0))} Ks</div><div class="qty-controls"><button type="button" data-cart-action="minus">−</button><output>${Number(item.qty || 0)}</output><button type="button" data-cart-action="plus">+</button><button class="remove" type="button" data-cart-action="remove">×</button></div></div>`).join('');
    root.querySelectorAll('[data-cart-action]').forEach(button => button.addEventListener('click', () => changeCart(button.closest('[data-cart-key]').dataset.cartKey, button.dataset.cartAction)));
  }
  function addToCart(sourceProduct, selectedVariant = null, manualPrice = null) {
    if (!sourceProduct) return;
    const product = sourceProduct, variant = selectedVariant, service = isService(product), stock = stockFor(product, variant);
    if (!service && stock <= 0) return toast(`${product.name} is out of stock.`);
    const price = Number(manualPrice ?? (variant || product).price ?? 0);
    if (service && price < 0) return toast('Enter a valid service price.');
    const key = service ? `${cartKey(product, variant)}:service:${price.toFixed(2)}` : cartKey(product, variant);
    const item = cart.get(key) || {
      key, product_id: Number(product.id), variant_id: Number(variant?.variant_id || 0) || null,
      name: product.name, sku: variant?.sku || product.sku || product.barcode || '', variant_label: variantLabel(variant),
      price, stock, qty: 0, is_service: service,
    };
    if (!service && item.qty + 1 > stock) return toast(`Only ${stock} left: ${item.name}`);
    item.qty += 1; cart.set(key, item); saveCart(); renderCart(); toast(`${item.name} added to cart.`);
  }
  function closeChoice() {
    document.querySelector('#productChoiceModal').hidden = true;
    document.querySelector('#productChoiceModal').classList.remove('service-price-open');
    choiceState = null;
  }
  function openServicePrice(product) {
    choiceState = {type: 'service', product};
    document.querySelector('#productChoiceModal').classList.add('service-price-open');
    document.querySelector('#choiceTitle').textContent = product.name || 'Service';
    document.querySelector('#choiceSubtitle').textContent = 'Enter service price';
    document.querySelector('#confirmChoice').textContent = 'Add';
    document.querySelector('#choiceBody').innerHTML = `<label class="choice-field"><span>Price</span><input id="servicePriceInput" type="text" inputmode="none" enterkeyhint="done" autocomplete="off" readonly value=""></label><div class="service-keypad" aria-label="Service price keypad">${['1','2','3','4','5','6','7','8','9','00','0','⌫'].map(value => `<button type="button" data-keypad="${value}">${value}</button>`).join('')}<button type="button" data-keypad="clear">Clear</button></div>`;
    document.querySelector('#productChoiceModal').hidden = false;
    document.querySelectorAll('[data-keypad]').forEach(button => button.addEventListener('click', () => pressServiceKey(button.dataset.keypad)));
    const focusPriceInput = () => {
      const input = document.querySelector('#servicePriceInput');
      if (!input) return;
      input.focus({preventScroll: true});
    };
    focusPriceInput();
    requestAnimationFrame(focusPriceInput);
    setTimeout(focusPriceInput, 120);
  }
  function pressServiceKey(key) {
    const input = document.querySelector('#servicePriceInput');
    if (!input) return;
    if (key === 'clear') input.value = '';
    else if (key === '⌫') input.value = String(input.value || '').slice(0, -1);
    else input.value = `${String(input.value || '').replace(/^0+(?=\d)/, '')}${key}`;
    input.focus({preventScroll: true});
  }
  function handleServiceKeydown(event) {
    if (!choiceState || choiceState.type !== 'service' || document.querySelector('#productChoiceModal').hidden) return;
    if (/^\d$/.test(event.key)) {
      event.preventDefault(); pressServiceKey(event.key); return;
    }
    if (event.key === 'Backspace') {
      event.preventDefault(); pressServiceKey('⌫'); return;
    }
    if (event.key === 'Delete') {
      event.preventDefault(); pressServiceKey('clear'); return;
    }
    if (event.key === 'Enter') {
      event.preventDefault(); confirmChoice();
    }
  }
  function openVariantChoice(product) {
    const variants = (Array.isArray(product.variants) ? product.variants : []).filter(Boolean);
    if (!variants.length) return toast(`${product.name} has no variants.`);
    choiceState = {type: 'variant', product};
    document.querySelector('#productChoiceModal').classList.remove('service-price-open');
    document.querySelector('#choiceTitle').textContent = product.name || 'Choose variant';
    document.querySelector('#choiceSubtitle').textContent = 'Choose one variant';
    document.querySelector('#confirmChoice').textContent = 'Add';
    document.querySelector('#choiceBody').innerHTML = `<div class="variant-list">${variants.map((variant, index) => {
      const stock = stockFor(product, variant), disabled = stock <= 0;
      return `<label class="variant-choice ${disabled ? 'disabled' : ''}"><input type="radio" name="variantChoice" value="${index}" ${disabled ? 'disabled' : ''}><span><strong>${escapeHtml(variantName(variant, index))}</strong><small>${escapeHtml(variant.sku || variant.barcode || '')}</small></span><em>${money(variant.price || product.price)} Ks · Stock ${money(stock)}</em></label>`;
    }).join('')}</div>`;
    const firstAvailable = [...document.querySelectorAll('input[name="variantChoice"]:not(:disabled)')][0];
    if (firstAvailable) firstAvailable.checked = true;
    document.querySelector('#productChoiceModal').hidden = false;
  }
  function chooseProduct(product) {
    if (!product) return;
    if (isService(product)) return openServicePrice(product);
    if (soldByMode(product.sold_by) === 'variants') return openVariantChoice(product);
    addToCart(product);
  }
  function confirmChoice() {
    if (!choiceState) return closeChoice();
    if (choiceState.type === 'service') {
      const price = Number(document.querySelector('#servicePriceInput')?.value || 0);
      if (!Number.isFinite(price) || price < 0) return toast('Enter a valid service price.');
      addToCart(choiceState.product, null, price); closeChoice(); return;
    }
    if (choiceState.type === 'variant') {
      const selected = document.querySelector('input[name="variantChoice"]:checked');
      if (!selected) return toast('Choose a variant.');
      const variants = Array.isArray(choiceState.product.variants) ? choiceState.product.variants : [];
      addToCart(choiceState.product, variants[Number(selected.value)] || null); closeChoice();
    }
  }
  function changeCart(key, action) {
    const item = cart.get(key); if (!item) return;
    if (action === 'remove') cart.delete(key);
    else if (action === 'minus') item.qty -= 1;
    else if (action === 'plus') {
      if (!item.is_service && item.qty + 1 > Number(item.stock || 0)) return toast(`Only ${item.stock || 0} left: ${item.name}`);
      item.qty += 1;
    }
    if (item.qty <= 0) cart.delete(key);
    saveCart(); renderCart();
  }
  function receiptLines(receipt, paid) {
    const total = Number(receipt.total || 0), items = Array.isArray(receipt.items) ? receipt.items : [];
    const lines = ['KAY POS', receipt.invoice_no || 'Receipt', receipt.created_at || new Date().toLocaleString(), ''];
    for (const item of items) {
      const name = String(item.product_name || item.name || 'Item');
      const qty = Number(item.qty || 0), price = Number(item.price || 0), amount = Number(item.total || qty * price);
      lines.push(name);
      lines.push(`  ${qty} x ${money(price)} = ${money(amount)} Ks`);
    }
    lines.push('', `Subtotal: ${money(receipt.subtotal || total)} Ks`, `Discount: ${money(receipt.discount_amount || 0)} Ks`, `Total: ${money(total)} Ks`, `Paid: ${money(paid)} Ks`, `Change: ${money(Math.max(0, paid - total))} Ks`, '', 'Thank you.');
    return lines.join('\n');
  }
  function showReceipt(receipt, paid) {
    const modal = document.querySelector('#receiptModal'), total = Number(receipt.total || cartTotals().total || 0);
    document.querySelector('#receiptInvoice').textContent = receipt.invoice_no || '';
    document.querySelector('#printReceipt').textContent = receiptLines(receipt, paid);
    document.querySelector('#receiptBody').innerHTML = [
      ['Items', String((receipt.items || []).reduce((sum, item) => sum + Number(item.qty || 0), 0) || cartTotals().count)],
      ['Subtotal', `${money(receipt.subtotal || total)} Ks`],
      ['Discount', `${money(receipt.discount_amount || 0)} Ks`],
      ['Paid', `${money(paid)} Ks`],
      ['Change', `${money(Math.max(0, paid - total))} Ks`],
      ['Total', `${money(total)} Ks`, 'receipt-total'],
    ].map(row => `<div class="${row[2] || ''}"><span>${escapeHtml(row[0])}</span><strong>${escapeHtml(row[1])}</strong></div>`).join('');
    modal.hidden = false;
  }
  async function checkoutCashSale() {
    const {items, total} = cartTotals(), payment = total;
    if (!items.length) return toast('Cart is empty.');
    const button = document.querySelector('#paymentButton'); button.disabled = true; button.textContent = 'Saving...';
    try {
      const data = await api('/api/touch-pos/sales', {
        method: 'POST',
        body: JSON.stringify({
          items: items.map(item => ({product_id: item.product_id, variant_id: item.variant_id, qty: item.qty, manual_price: item.is_service ? Number(item.price || 0) : null})),
          payment, payment_type: 'Cash', sale_mode: 'Cash', discount_amount: 0, points_used: 0, customer_id: null,
        }),
      });
      const receipt = data.receipt || {};
      clearCart(); renderCart(); await loadProducts(); showReceipt(receipt, payment);
      toast(`Saved ${receipt.invoice_no || 'sale'}.`);
    } catch (error) {
      toast(error.message);
    } finally {
      button.textContent = 'Checkout'; renderCart();
    }
  }
  function customerLabel(customer) {
    return `${customer.name || 'Customer'}${customer.phone ? ` · ${customer.phone}` : ''}`;
  }
  function selectedCheckoutCustomer() {
    const id = Number(document.querySelector('#checkoutCustomer')?.value || 0);
    return customers.find(customer => Number(customer.id) === id) || null;
  }
  function renderCheckoutCustomers() {
    const select = document.querySelector('#checkoutCustomer');
    select.innerHTML = `<option value="">Walk-in Customer</option>${customers.map(customer => `<option value="${Number(customer.id)}">${escapeHtml(customerLabel(customer))}</option>`).join('')}`;
  }
  async function loadCheckoutCustomers() {
    const select = document.querySelector('#checkoutCustomer');
    select.innerHTML = '<option value="">Loading customers...</option>';
    try {
      const result = await api('/api/customers?limit=200');
      customers = Array.isArray(result.customers) ? result.customers : [];
      renderCheckoutCustomers();
    } catch (error) {
      customers = [];
      select.innerHTML = '<option value="">Walk-in Customer</option>';
      toast(error.message);
    }
  }
  function renderCheckoutSummary() {
    const customer = selectedCheckoutCustomer();
    const mode = document.querySelector('#checkoutSaleMode').value;
    const totals = checkoutTotals();
    const customerInfo = document.querySelector('#checkoutCustomerInfo');
    const messages = [];
    if (customer) {
      const balance = Number(customer.current_balance || 0), limit = Number(customer.credit_limit || 0);
      customerInfo.textContent = `Points ${money(customer.points || 0)} · Balance ${money(balance)} Ks · Credit limit ${money(limit)} Ks · Available ${money(Math.max(0, limit - balance))} Ks`;
    } else {
      customerInfo.textContent = mode === 'Credit' ? 'Select a customer for credit sale.' : 'Walk-in customer';
    }
    if (!totals.items.length) messages.push('Cart is empty.');
    if (mode === 'Credit' && !customer) messages.push('Select a customer for credit sale.');
    if (mode === 'Cash' && totals.received < totals.total) messages.push('Received amount is less than total.');
    if (mode === 'Credit' && totals.received > totals.total) messages.push('Credit received amount cannot exceed total.');
    if (totals.rawDiscount > totals.subtotal) messages.push('Discount cannot exceed subtotal.');
    document.querySelector('#checkoutSummary').innerHTML = [
      ['Items', String(totals.count)],
      ['Subtotal', `${money(totals.subtotal)} Ks`],
      ['Discount', `${money(totals.discount)} Ks`],
      ['Total', `${money(totals.total)} Ks`, 'checkout-total'],
      ['Received', `${money(totals.received)} Ks`],
      [mode === 'Credit' ? 'Credit Balance' : 'Change', `${money(mode === 'Credit' ? totals.balance : totals.change)} Ks`],
    ].map(row => `<div class="${row[2] || ''}"><span>${escapeHtml(row[0])}</span><strong>${escapeHtml(row[1])}</strong></div>`).join('');
    document.querySelector('#checkoutValidation').textContent = messages[0] || 'Ready to save.';
    document.querySelector('#checkoutValidation').classList.toggle('ok', messages.length === 0);
    document.querySelector('#saveCheckout').disabled = messages.length > 0;
  }
  async function openCheckoutDetails() {
    const {items, total} = cartTotals();
    if (!items.length) return toast('Cart is empty.');
    const modal = document.querySelector('#checkoutModal');
    document.querySelector('#checkoutDiscount').value = '0';
    document.querySelector('#checkoutReceived').value = String(Math.round(total));
    document.querySelector('#checkoutSaleMode').value = 'Cash';
    modal.hidden = false;
    await loadCheckoutCustomers();
    renderCheckoutSummary();
    setTimeout(() => document.querySelector('#checkoutReceived').select(), 0);
  }
  function closeCheckout() {
    document.querySelector('#checkoutModal').hidden = true;
    document.querySelector('#saveCheckout').disabled = false;
    document.querySelector('#saveCheckout').textContent = 'Save Sale';
  }
  async function submitCheckoutSale() {
    const mode = document.querySelector('#checkoutSaleMode').value;
    const customer = selectedCheckoutCustomer();
    const totals = checkoutTotals();
    if (!totals.items.length) return toast('Cart is empty.');
    if (mode === 'Credit' && !customer) return toast('Select a customer for credit sale.');
    if (mode === 'Cash' && totals.received < totals.total) return toast('Received amount is less than total.');
    if (mode === 'Credit' && totals.received > totals.total) return toast('Credit received amount cannot exceed total.');
    const button = document.querySelector('#saveCheckout');
    button.disabled = true; button.textContent = 'Saving...';
    try {
      const data = await api('/api/touch-pos/sales', {
        method: 'POST',
        body: JSON.stringify({
          items: totals.items.map(item => ({product_id: item.product_id, variant_id: item.variant_id, qty: item.qty, manual_price: item.is_service ? Number(item.price || 0) : null})),
          payment: totals.received, payment_type: mode, sale_mode: mode, discount_amount: totals.discount, points_used: 0,
          customer_id: customer ? Number(customer.id) : null,
        }),
      });
      const receipt = data.receipt || {};
      closeCheckout(); clearCart(); renderCart(); await loadProducts(); showReceipt(receipt, totals.received);
      toast(`Saved ${receipt.invoice_no || 'sale'}.`);
    } catch (error) {
      toast(error.message);
    } finally {
      button.disabled = false; button.textContent = 'Save Sale'; renderCheckoutSummary();
    }
  }
  function setupInventoryActions(p, detail, request) {
    const variants=p.variants || [], hasVariants=variants.length || soldByMode(p.sold_by)==='variants';
    const stockIn=detail.querySelector('#inventoryStockIn');
    stockIn.insertAdjacentHTML('beforebegin','<div class="receipt-tabs inventory-action-tabs" aria-label="Stock action"><button type="button" data-stock-action="in" aria-pressed="true">Stock In</button><button type="button" data-stock-action="out" aria-pressed="false">Stock Out</button><button type="button" data-stock-action="adjust" aria-pressed="false">Adjustment</button></div>');
    stockIn.insertAdjacentHTML('afterend',`<form id="inventoryChange" class="inventory-stock-form" hidden><h3 data-change-title>Stock Out</h3><p data-change-help></p>${hasVariants ? `<label>Variant<select name="variant" required><option value="">Select variant</option>${variants.map(v=>`<option value="${Number(v.variant_id)}">${escapeHtml(variantLabel(v) || v.sku || v.variant_id)} · Stock ${money(v.stock)}</option>`).join('')}</select></label>` : ''}<label>Location<select name="location" >${[...new Set(['Shop',...inventoryLocations,...(p.locations || []).map(l=>l.location),...(p.variant_batches || []).map(l=>l.location)])].map(l=>`<option>${escapeHtml(l)}</option>`).join('')}</select></label><label><span data-change-quantity-label>Quantity to remove</span><input name="quantity" type="number" min="1" max="1000000" step="1" required></label><label>Reason<input name="reason" maxlength="500" required placeholder="Damage, return or stock count correction"></label><label>Handled by<input name="actor" maxlength="200" required></label><label class="full">Notes<input name="notes" maxlength="2000"></label><strong class="full" data-change-preview aria-live="polite"></strong><button type="submit" class="full receipt-apply" data-change-save>Review Stock Out</button><small class="full" role="alert" data-change-error></small></form>`);
    const form=detail.querySelector('#inventoryChange'),field=name=>form.elements.namedItem(name),save=form.querySelector('[data-change-save]');
    let mode='out',busy=false;
    const current=()=>Number((variants.find(v=>Number(v.variant_id)===Number(field('variant')?.value)) || p).stock || 0);
    const preview=()=>{
      const before=current(),qty=Number(field('quantity').value),after=mode==='out' ? before-qty : qty;
      form.querySelector('[data-change-preview]').textContent=field('quantity').value==='' ? `Current stock: ${money(before)}` : `Current: ${money(before)} → After: ${money(after)} · Change: ${after-before>0?'+':''}${money(after-before)}`;
    };
    detail.querySelectorAll('[data-stock-action]').forEach(button=>button.onclick=()=>{
      if(busy || stockIn.querySelector('button[type="submit"]').disabled) return;
      const action=button.dataset.stockAction;
      detail.querySelectorAll('[data-stock-action]').forEach(tab=>tab.setAttribute('aria-pressed',String(tab===button)));
      stockIn.hidden=action!=='in';form.hidden=action==='in';
      if(action==='in') return;
      mode=action;field('quantity').value='';field('quantity').min=mode==='out'?'1':'0';
      form.querySelector('[data-change-title]').textContent=mode==='out'?'Stock Out':'Adjustment';
      form.querySelector('[data-change-help]').textContent=mode==='out'?'Remove stock from the selected location. Quantity is in base stock units.':'Enter the counted TOTAL stock across all locations (or the selected variant). The difference is applied to the selected location. Cost stays unchanged.';
      form.querySelector('[data-change-quantity-label]').textContent=mode==='out'?'Quantity to remove':'Counted total stock';
      save.textContent=mode==='out'?'Review Stock Out':'Review Adjustment';
      form.querySelector('[data-change-error]').textContent='';preview();
    });
    field('quantity').oninput=preview;if(field('variant'))field('variant').onchange=preview;
    form.onsubmit=async event=>{
      event.preventDefault();if(busy || !form.reportValidity())return;
      const qty=Number(field('quantity').value),before=current(),after=mode==='out'?before-qty:qty;
      const error=form.querySelector('[data-change-error]'),reason=field('reason').value.trim(),actor=field('actor').value.trim();
      if(!Number.isInteger(qty)||qty<(mode==='out'?1:0)||qty>1000000||after<0||!reason||!actor){error.textContent='Enter a valid quantity, reason and handler. Stock cannot be negative.';return;}
      if(mode==='adjust' && after===before){error.textContent='The count matches current stock. No adjustment is needed.';return;}
      if(!window.confirm(`${mode==='out'?'Stock Out':'Adjustment'}: ${p.name}\nLocation: ${field('location').value}\nStock: ${before} → ${after}\nReason: ${reason}`))return;
      busy=true;save.disabled=true;error.textContent='';
      detail.querySelectorAll('[data-stock-action]').forEach(button=>button.disabled=true);
      const common={product_id:Number(p.id),variant_id:Number(field('variant')?.value)||null,location:field('location').value,reason,notes:field('notes').value.trim()};
      try {
        await api(mode==='out'?'/api/stock/adjust':'/api/stock/adjustment',{method:'POST',body:JSON.stringify(mode==='out'?{...common,adjustment:-qty,restrict_location:true,issued_by:actor}:{...common,new_quantity:qty,expected_stock:before,adjustment_type:'Count correction',adjusted_by:actor})});
      } catch(e){error.textContent=e.message;busy=false;save.disabled=false;detail.querySelectorAll('[data-stock-action]').forEach(button=>button.disabled=false);return;}
      toast(mode==='out'?'Stock Out saved.':'Adjustment saved.');
      if(request!==inventoryDetailRequest)return;
      const expected=inventoryRequest+1;await loadInventory();
      if(inventoryRequest===expected&&!document.querySelector('#touchInventory').hidden)await openInventoryProduct(Number(p.id));
    };
  }

  let inventoryRequest = 0, inventoryDetailRequest = 0, inventoryOffset = 0;
  let inventoryProducts = [], inventoryLocations = [], inventorySuppliers = [];
  function hideInventory() {
    inventoryRequest++; inventoryDetailRequest++;
    document.querySelector('#touchInventory').hidden = true;
    document.querySelector('#inventoryDetail').replaceChildren();
  }
  async function showInventoryPage() {
    receiptsRequest++;
    document.querySelector('.workspace').hidden = true;
    document.querySelector('#productManager').hidden = true;
    document.querySelector('#touchReceipts').hidden = true;
    document.querySelector('#touchInventory').hidden = false;
    document.querySelector('#workspaceStatus').textContent = 'Inventory · Stock and movements';
    inventoryOffset = 0;
    await loadInventory();
  }
  async function loadInventory() {
    const request = ++inventoryRequest;
    inventoryDetailRequest++;
    const rows = document.querySelector('#inventoryRows');
    document.querySelector('#inventoryDetail').innerHTML = '<div class="receipt-detail-empty"><strong>Select a product</strong><p>Review stock, receive new stock and view movements.</p></div>';
    rows.textContent = 'Loading inventory...';
    document.querySelector('#inventoryPrev').disabled = true;
    document.querySelector('#inventoryNext').disabled = true;
    try {
      const query = new URLSearchParams({q:document.querySelector('#inventorySearch').value.trim(),limit:'50',offset:String(inventoryOffset)});
      const [data, locations, suppliers] = await Promise.all([api(`/api/products?${query}`),api('/api/stock/locations'),api('/api/suppliers')]);
      if (request !== inventoryRequest) return;
      inventoryProducts = data.products || []; inventoryLocations = locations.locations || []; inventorySuppliers = suppliers.suppliers || [];
      rows.innerHTML = inventoryProducts.map(p=>`<button type="button" class="receipt-history-row inventory-product-row" data-inventory-id="${Number(p.id)}"><span class="manager-thumb" aria-hidden="true">${p.thumbnail_url ? `<img src="${escapeHtml(p.thumbnail_url)}" alt="" loading="lazy">` : '▦'}</span><span class="inventory-product-name"><strong>${escapeHtml(p.name)}</strong><small>${escapeHtml(p.sku || p.barcode || p.category || '')}</small></span><span><strong>${soldByMode(p.sold_by)==='service' ? 'Service' : money(p.stock)+' '+escapeHtml(p.base_unit || p.unit || 'pcs')}</strong><small>${soldByMode(p.sold_by)==='service' ? 'No stock tracking' : Number(p.stock)<=Number(p.low_stock || 0) ? 'Low stock' : 'In stock'}</small></span></button>`).join('') || '<p>No products found. Try another search.</p>';
      rows.querySelectorAll('.manager-thumb img').forEach(image=>image.addEventListener('error',()=>{image.parentElement.textContent='▦';},{once:true}));
      rows.querySelectorAll('[data-inventory-id]').forEach(button=>button.onclick=()=>openInventoryProduct(Number(button.dataset.inventoryId)));
      document.querySelector('#inventoryPageInfo').textContent = inventoryProducts.length ? `${inventoryOffset+1}–${inventoryOffset+inventoryProducts.length}` : 'No results';
      document.querySelector('#inventoryPrev').disabled = inventoryOffset===0;
      document.querySelector('#inventoryNext').disabled = inventoryProducts.length<50;
    } catch(error) { if(request===inventoryRequest) rows.textContent=error.message; }
  }
  async function openInventoryProduct(id) {
    const p = inventoryProducts.find(p=>Number(p.id)===id); if (!p) return;
    const request = ++inventoryDetailRequest, detail=document.querySelector('#inventoryDetail');
    const variants = p.variants || [], service=soldByMode(p.sold_by)==='service';
    detail.innerHTML = `<div class="receipt-page-head"><div><strong>${escapeHtml(p.name)}</strong><small>Current stock: ${money(p.stock)} ${escapeHtml(p.base_unit || p.unit || 'pcs')} · Cost: ${money(p.cost)} Ks</small></div></div><div class="inventory-locations">${(p.locations || []).map(l=>`<small>${escapeHtml(l.location)}: ${money(l.quantity)}</small>`).join('')}</div>`;
    if (p.variant_batches?.length) detail.innerHTML += `<div class="inventory-locations"><h3>Variant batches</h3>${p.variant_batches.map(b=>`<small>${escapeHtml(variantLabel(variants.find(v=>Number(v.variant_id)===Number(b.variant_id))) || b.variant_id)} · ${escapeHtml(b.location)} · ${escapeHtml(b.batch_no)} · ${money(b.quantity)} · ${b.expiry_unknown ? 'Expiry unknown (legacy / count)' : escapeHtml(b.expire_date || 'No expiry')}</small>`).join('')}</div>`;
    if (!service) {
      detail.innerHTML += `<form id="inventoryStockIn" class="inventory-stock-form"><h3>Stock In</h3><p>Enter quantity and cost per base stock unit (${escapeHtml(p.base_unit || p.unit || 'pcs')}).</p>${variants.length || soldByMode(p.sold_by)==='variants' ? `<label>Variant<select name="variant_id" required><option value="">Select variant</option>${variants.map(v=>`<option value="${Number(v.variant_id)}">${escapeHtml(variantLabel(v) || v.sku || String(v.variant_id))} · Stock ${money(v.stock)}</option>`).join('')}</select></label>` : ''}<label>Location<select name="location" required>${[...new Set(['Shop',...inventoryLocations])].map(l=>`<option>${escapeHtml(l)}</option>`).join('')}</select></label><label>Quantity<input name="quantity" type="number" min="1" max="1000000" step="1" required></label><label>Unit cost (Ks)<input name="cost" type="number" min="0" step="0.01" required></label><label>Supplier<select name="supplier_id"><option value="">None</option>${inventorySuppliers.map(s=>`<option value="${Number(s.id)}">${escapeHtml(s.name)}</option>`).join('')}</select></label><label>Batch number<input name="batch_no" maxlength="100"></label><label class="full">Expiry<select name="expiry_mode" aria-describedby="inventoryExpiryHelp"><option value="none">No expiry</option><option value="date">Enter expiry date</option></select><small id="inventoryExpiryHelp">Choose No expiry or enter the date printed on the product.</small></label><label class="full" data-expiry-date>Expiry date<input name="expire_date" type="date" required></label><label class="full">Notes<input name="notes" maxlength="2000"></label><strong class="full" data-stock-preview>Enter quantity and cost to review.</strong><button class="full receipt-apply" type="submit">Save Stock In</button><small class="full" role="alert" data-stock-error></small></form>`;
      const form=detail.querySelector('#inventoryStockIn'), field=name=>form.elements.namedItem(name);
      field('expire_date').value='';
      field('expiry_mode').value='none';
      const updateExpiry=()=>{
        const none=field('expiry_mode').value==='none';
        field('expire_date').disabled=none; field('expire_date').required=!none;
        form.querySelector('[data-expiry-date]').hidden=none;
      };
      field('expiry_mode').onchange=updateExpiry;
      updateExpiry();
      const update=()=>{
        const variant=variants.find(v=>Number(v.variant_id)===Number(field('variant_id')?.value));
        const qty=Number(field('quantity').value), cost=Number(field('cost').value);
        form.querySelector('[data-stock-preview]').textContent=`Stock after: ${money(Number((variant || p).stock)+qty)} · Total cost: ${money(qty*cost)} Ks`;
      };
      field('cost').value=Number(p.cost || 0);
      if(field('variant_id')) {
        field('variant_id').onchange=()=>{const v=variants.find(v=>Number(v.variant_id)===Number(field('variant_id').value));field('cost').value=Number(v?.cost || 0);update();};
      }
      field('quantity').oninput=update; field('cost').oninput=update;
      form.onsubmit=async event=>{
        event.preventDefault();
        const button=form.querySelector('button[type="submit"]'), error=form.querySelector('[data-stock-error]');
        if(button.disabled || !form.reportValidity()) return;
        const quantity=Number(field('quantity').value), cost=Number(field('cost').value);
        if(!Number.isInteger(quantity) || quantity<1 || quantity>1000000 || !Number.isFinite(cost) || cost<0) {error.textContent='Enter a valid quantity and cost.';return;}
        if(!window.confirm(`Receive ${quantity} stock units of "${p.name}"?\nTotal cost: ${money(quantity*cost)} Ks\nExpiry: ${field('expiry_mode').value==='none' ? 'No expiry' : field('expire_date').value}`)) return;
        button.disabled=true; error.textContent='';
        try {
          const data=await api('/api/stock/adjust',{method:'POST',body:JSON.stringify({product_id:id,variant_id:Number(field('variant_id')?.value)||null,adjustment:quantity,unit_cost:cost,location:field('location').value,supplier_id:Number(field('supplier_id').value)||null,batch_no:field('batch_no').value.trim(),expire_date:field('expiry_mode').value==='none' ? '' : field('expire_date').value,notes:field('notes').value.trim(),reason:'Touch POS Stock In'})});
          toast('Stock In saved.');
          if(request!==inventoryDetailRequest) return;
          inventoryProducts=inventoryProducts.map(item=>Number(item.id)===id ? data.product : item);
          const expected=inventoryRequest+1; await loadInventory();
          if(inventoryRequest===expected && !document.querySelector('#touchInventory').hidden) await openInventoryProduct(id);
        } catch(e) {error.textContent=e.message;button.disabled=false;}
      };
      setupInventoryActions(p, detail, request);
    } else detail.innerHTML+='<p>Service products do not track inventory.</p>';
    detail.insertAdjacentHTML('beforeend', '<div class="inventory-history"><h3>Recent movements</h3><div id="inventoryMovements">Loading movements...</div></div>');
    if (window.matchMedia('(max-width: 900px)').matches) detail.scrollIntoView({behavior:'smooth',block:'start'});
    try {
      const data=await api(`/api/stock/movements?product_id=${id}&limit=50`);
      if(request!==inventoryDetailRequest) return;
      detail.querySelector('#inventoryMovements').innerHTML=(data.movements || []).map(m=>`<div class="inventory-movement"><strong>${escapeHtml(m.type)} · ${money(m.quantity)}</strong><small>${escapeHtml(m.created_at)} · ${escapeHtml(m.location)} · ${escapeHtml([m.color,m.size].filter(Boolean).join(' / '))}</small><small>${money(m.old_stock)} → ${money(m.new_stock)} · ${escapeHtml(m.created_by)}</small><small>${escapeHtml(m.reason)}</small></div>`).join('') || '<p>No stock movements yet.</p>';
    } catch(error) {if(request===inventoryDetailRequest) detail.querySelector('#inventoryMovements').textContent=error.message;}
  }

  let receiptsOffset = 0, receiptsRequest = 0;
  function resetReceiptDetail() {
    const detail = document.querySelector('#receiptsDetail'); detail.hidden = false;
    detail.innerHTML = '<div class="receipt-detail-empty"><img src="/assets/icons/receipt.svg" alt=""><strong>Select a receipt</strong><p>Items and payment details will appear here.</p></div>';
    document.querySelectorAll('[data-receipt-id]').forEach(button=>button.setAttribute('aria-pressed','false'));
  }
  async function showReceiptsPage() {
    hideInventory();
    document.querySelector('.workspace').hidden = true;
    document.querySelector('#productManager').hidden = true;
    document.querySelector('#touchReceipts').hidden = false;
    document.querySelector('#workspaceStatus').textContent = 'Receipts · Sales history';
    if (!document.querySelector('#receiptsFrom').value) {
      const now = new Date(), day = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
      document.querySelector('#receiptsFrom').value = day; document.querySelector('#receiptsTo').value = day;
    }
    receiptsOffset = 0; await loadTouchReceipts();
  }
  async function loadTouchReceipts() {
    const request = ++receiptsRequest, root = document.querySelector('#receiptsRows');
    resetReceiptDetail();
    document.querySelector('#receiptsPrev').disabled = true; document.querySelector('#receiptsNext').disabled = true;
    root.textContent = 'Loading receipts...';
    const query = new URLSearchParams({from_date:document.querySelector('#receiptsFrom').value,to_date:document.querySelector('#receiptsTo').value,tab:document.querySelector('#receiptsTab').value,q:document.querySelector('#receiptsSearch').value.trim(),limit:'30',offset:String(receiptsOffset)});
    try {
      const data = await api(`/api/receipts/overview?${query}`); if (request !== receiptsRequest) return;
      const summary = data.summary || {};
      document.querySelector('#receiptsSummary').innerHTML = [['receipts','Receipts'],['sales','Sales'],['discount','Discount'],['refund','Refund'],['credit','Credit']].map(([key,label])=>`<div class="panel receipt-metric metric-${key}"><small>${label}</small><strong>${money(summary[key])}${key === 'receipts' ? '' : ' Ks'}</strong></div>`).join('') + '<small class="receipt-summary-note">Summary for the selected date range, across all receipt tabs.</small>';
      root.innerHTML = (data.rows || []).map(row=>`<button type="button" class="receipt-history-row" aria-pressed="false" data-receipt-id="${Number(row.id)}"><span><strong>${escapeHtml(row.invoice_no)}</strong><small>${escapeHtml(row.created_at)} · ${escapeHtml(row.customer_name)}</small></span><span><strong>${money(row.total)} Ks</strong><small>${escapeHtml(row.payment_type)} <span class="receipt-status ${row.status === 'refunded' ? 'is-refunded' : 'is-completed'}">${escapeHtml(row.status)}</span></small></span></button>`).join('') || '<div class="receipt-empty"><strong>No receipts found</strong><p>Try a different date range or search term.</p></div>';
      root.querySelectorAll('[data-receipt-id]').forEach(button=>button.addEventListener('click',()=>openTouchReceipt(Number(button.dataset.receiptId))));
      document.querySelector('#receiptsPageInfo').textContent = data.total_count ? `${receiptsOffset+1}–${Math.min(receiptsOffset+30,data.total_count)} / ${data.total_count}` : '0 receipts';
      document.querySelector('#receiptsPrev').disabled = receiptsOffset === 0;
      document.querySelector('#receiptsNext').disabled = receiptsOffset + 30 >= data.total_count;
    } catch(error) { if(request !== receiptsRequest) return; root.textContent=error.message; document.querySelector('#receiptsSummary').replaceChildren(); document.querySelector('#receiptsPageInfo').textContent=''; }
  }
  async function openTouchReceipt(id) {
    const request = ++receiptsRequest, detail = document.querySelector('#receiptsDetail');
    detail.hidden = false; detail.textContent = 'Loading receipt...';
    document.querySelectorAll('[data-receipt-id]').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.receiptId)===id)));
    try {
      const data = await api(`/api/receipts/${id}`); if(request !== receiptsRequest) return;
      const r = data.receipt;
      detail.innerHTML = `<div class="receipt-page-head"><div><strong>${escapeHtml(r.invoice_no)}</strong><small>${escapeHtml(r.created_at)} · ${escapeHtml(r.customer_name || 'Walk-in Customer')} · ${escapeHtml(r.status)}</small></div><button type="button" data-close-detail>Close</button></div><div class="receipt-table-wrap"><table><thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Total</th></tr></thead><tbody>${(r.items || []).map(item=>`<tr><td>${escapeHtml(item.product_name)}</td><td>${money(item.qty)}</td><td>${money(item.price)}</td><td>${money(item.total)}</td></tr>`).join('')}</tbody></table></div><div class="receipt-detail-totals">${[['Payment method',escapeHtml(r.payment_type)],['Discount',money(r.discount_amount)+' Ks'],['Total',money(r.total)+' Ks'],['Paid',money(r.paid_amount ?? r.payment)+' Ks'],['Change',money(r.change_amount)+' Ks'],...(String(r.payment_type).toLowerCase()==='credit' ? [['Credit balance',money(r.balance_amount ?? Math.max(0,Number(r.total)-Number(r.payment)))+' Ks']] : [])].map(([label,value])=>`<div><span>${label}</span><strong>${value}</strong></div>`).join('')}</div>`;
      const completed = String(r.status || 'completed').toLowerCase() === 'completed';
      const credit = String(r.payment_type || '').toLowerCase() === 'credit';
      if (completed && !credit) {
        detail.innerHTML += `<div class="receipt-refund"><button type="button" data-refund-open>Refund</button><form data-refund-form hidden><strong>Refund ${money(r.total)} Ks?</strong><p>This refunds the entire receipt and restores its stock.</p><label>Reason<input name="reason" required maxlength="500" placeholder="Customer return"></label><div><button type="submit" data-refund-submit>Confirm refund</button><button type="button" data-refund-cancel>Cancel</button></div><small data-refund-error role="alert"></small></form></div>`;
        const form = detail.querySelector('[data-refund-form]');
        const open = detail.querySelector('[data-refund-open]');
        open.onclick = () => { form.hidden = false; open.hidden = true; form.querySelector('input').focus(); };
        detail.querySelector('[data-refund-cancel]').onclick = () => { form.hidden = true; open.hidden = false; open.focus(); };
        form.onsubmit = event => { event.preventDefault(); return refundTouchReceipt(id, form, request); };
      } else if (completed && credit) {
        detail.innerHTML += '<p class="receipt-refund-note">Credit refunds must be processed in the full KAY POS app.</p>';
      }
      detail.querySelector('[data-close-detail]').onclick=resetReceiptDetail;
      if (window.matchMedia('(max-width: 900px)').matches) detail.scrollIntoView({behavior:'smooth',block:'start'});
    } catch(error) { if(request === receiptsRequest) detail.textContent=error.message; }
  }
  async function refundTouchReceipt(id, form, request) {
    const submit = form.querySelector('[data-refund-submit]');
    if (submit.disabled) return;
    const reason = form.querySelector('input').value.trim();
    const errorNode = form.querySelector('[data-refund-error]');
    if (!reason) { errorNode.textContent = 'Enter a refund reason.'; return; }
    submit.disabled = true;
    submit.textContent = 'Refunding…';
    errorNode.textContent = '';
    try {
      await api(`/api/sales/${id}/refund`, {method:'POST', body:JSON.stringify({reason})});
    } catch (error) {
      errorNode.textContent = error.message;
      submit.disabled = false;
      submit.textContent = 'Confirm refund';
      return;
    }
    toast('Receipt refunded successfully.');
    if (request !== receiptsRequest) return;
    const refreshRequest = receiptsRequest + 1;
    await loadTouchReceipts();
    if (receiptsRequest === refreshRequest && !document.querySelector('#touchReceipts').hidden) await openTouchReceipt(id);
  }
  function showSalesView() {
    const fromInventory = !document.querySelector('#touchInventory').hidden;
    hideInventory();
    if (fromInventory) loadProducts();
    receiptsRequest += 1;
    document.querySelector('#touchReceipts').hidden = true;
    document.querySelector('.workspace').hidden = false;
    document.querySelector('#productManager').hidden = true;
    document.querySelector('#workspaceStatus').textContent = 'Phase W7 · Receipt print';
  }
  async function showProductManager() {
    hideInventory();
    receiptsRequest += 1;
    document.querySelector('#touchReceipts').hidden = true;
    document.querySelector('.workspace').hidden = true;
    document.querySelector('#productManager').hidden = false;
    document.querySelector('#workspaceStatus').textContent = 'Product page · Manage catalog';
    await loadProductManager();
  }
  async function loadProductManager() {
    if (!token) return;
    const query = new URLSearchParams({q: document.querySelector('#managerProductSearch').value.trim(), limit: '300'});
    document.querySelector('#managerProductList').innerHTML = '<div class="category-loading">Loading products...</div>';
    document.querySelector('#managerCategoryList').innerHTML = '<div class="category-loading">Loading categories...</div>';
    try {
      const [productResult, categoryResult] = await Promise.all([api(`/api/products?${query}`), api('/api/categories/manage')]);
      managedProducts = Array.isArray(productResult.products) ? productResult.products : [];
      managedCategories = Array.isArray(categoryResult.categories) ? categoryResult.categories : [];
      renderManagerProducts(); renderManagedCategories(); populateCategoryOptions();
    } catch (error) {
      toast(error.message);
      document.querySelector('#managerProductList').innerHTML = `<div class="category-loading">${escapeHtml(error.message)}</div>`;
      document.querySelector('#managerCategoryList').innerHTML = `<div class="category-loading">${escapeHtml(error.message)}</div>`;
    }
  }
  function populateCategoryOptions() {
    const options = ['<option value="">No category</option>', ...managedCategories.filter(item => String(item.status || 'active') === 'active').map(item => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.parent_name ? `${item.parent_name} / ${item.name}` : item.name)}</option>`)];
    document.querySelector('#itemCategory').innerHTML = options.join('');
    const parentOptions = ['<option value="">No parent</option>', ...managedCategories.filter(item => !editingCategory || Number(item.id) !== Number(editingCategory.id)).map(item => `<option value="${Number(item.id)}">${escapeHtml(item.parent_name ? `${item.parent_name} / ${item.name}` : item.name)}</option>`)];
    document.querySelector('#categoryParent').innerHTML = parentOptions.join('');
  }
  function renderManagerProducts() {
    const root = document.querySelector('#managerProductList');
    document.querySelector('#managerProductCount').textContent = String(managedProducts.length);
    if (!managedProducts.length) { root.innerHTML = '<div class="catalog-message"><strong>No products found</strong>Add an item to start.</div>'; return; }
    root.innerHTML = managedProducts.map(product => {
      const barcode = product.barcode || product.sku || '';
      const image = String(product.thumbnail_url || '').trim();
      return `<div class="manager-row product-manager-row"><span class="manager-thumb">${image ? `<img src="${escapeHtml(image)}" alt="" loading="lazy">` : '▦'}</span><div class="manager-row-main"><strong>${escapeHtml(product.name)}</strong><small>${escapeHtml(product.category || 'No category')} · ${money(product.price)} Ks · Stock ${money(product.stock)}${barcode ? ` · ${escapeHtml(barcode)}` : ''}</small></div><div class="manager-row-actions"><button type="button" title="Edit" data-manager-edit="${Number(product.id)}">Edit</button><button type="button" title="Delete item" class="manager-delete" data-manager-delete="${Number(product.id)}">Delete</button></div></div>`;
    }).join('');
    root.querySelectorAll('.manager-thumb img').forEach(image => image.addEventListener('error', () => { image.parentElement.textContent = '▦'; }, {once: true}));
    root.querySelectorAll('[data-manager-edit]').forEach(button => button.addEventListener('click', () => openItemModal(managedProducts.find(item => Number(item.id) === Number(button.dataset.managerEdit)))));
    root.querySelectorAll('[data-manager-delete]').forEach(button => button.addEventListener('click', () => deleteManagedItem(managedProducts.find(item => Number(item.id) === Number(button.dataset.managerDelete)), button)));
  }
  async function deleteManagedItem(product, button) {
    if (!product || !window.confirm(`Delete "${product.name}"?\n\nThis cannot be undone. Products with stock or transaction history cannot be deleted.`)) return;
    button.disabled = true; button.textContent = 'Deleting...';
    try {
      const current = await api(`/api/native/catalog?section=products&product_id=${Number(product.id)}`);
      const result = await api('/api/native/catalog/commands', {method: 'POST', body: JSON.stringify({
        request_id: crypto.randomUUID(), operation: 'product.delete', values: {id: Number(product.id), revision: current.revision},
      })});
      if (result.rejected) throw new Error(result.rejected);
      for (const [key, item] of cart) if (Number(item.product_id) === Number(product.id)) cart.delete(key);
      saveCart(); renderCart();
      await loadCatalog(); await loadProductManager(); toast('Item deleted.');
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; button.textContent = 'Delete'; }
  }
  function renderManagedCategories() {
    const root = document.querySelector('#managerCategoryList');
    if (!managedCategories.length) { root.innerHTML = '<div class="catalog-message"><strong>No categories</strong>Add parent and child categories here.</div>'; return; }
    const childrenByParent = new Map();
    managedCategories.forEach(item => childrenByParent.set(Number(item.parent_id || 0), [...(childrenByParent.get(Number(item.parent_id || 0)) || []), item]));
    const query = document.querySelector('#managerCategorySearch').value.trim().normalize('NFC').toLocaleLowerCase();
    const visibleIds = new Set();
    if (query) {
      const byId = new Map(managedCategories.map(item => [Number(item.id), item]));
      managedCategories.filter(item => String(item.name || '').normalize('NFC').toLocaleLowerCase().includes(query)).forEach(item => {
        const path = new Set();
        while (item && !path.has(Number(item.id))) {
          path.add(Number(item.id)); visibleIds.add(Number(item.id));
          item = byId.get(Number(item.parent_id || 0));
        }
      });
    }
    const rows = [], visited = new Set();
    const renderRows = (parentId, depth) => (childrenByParent.get(parentId) || []).forEach(item => {
      if (query && !visibleIds.has(Number(item.id))) return;
      if (visited.has(Number(item.id))) return;
      visited.add(Number(item.id));
      const level = depth === 0 ? 'Parent' : depth === 1 ? 'Child' : depth === 2 ? 'Sub Child' : `Level ${depth + 1}`;
      rows.push(`<div class="category-tree-row${depth ? ' category-descendant' : ''}" data-category-level="${Math.min(depth, 2)}" style="--category-depth:${depth}"><div class="manager-row"><div class="manager-row-main"><strong title="${level}: ${escapeHtml(item.name)}">${escapeHtml(item.name)}</strong><small>${escapeHtml(item.status || 'active')} · ${Number(item.product_count || 0)} products</small></div><div class="manager-row-actions"><button type="button" data-category-edit="${Number(item.id)}">Edit</button><button type="button" class="manager-delete" data-category-delete="${Number(item.id)}">Delete</button></div></div></div>`);
      renderRows(Number(item.id), depth + 1);
    });
    renderRows(0, 0);
    root.innerHTML = rows.join('') || '<div class="catalog-message"><strong>No matching categories</strong>Try another name or clear the search.</div>';
    root.querySelectorAll('[data-category-edit]').forEach(button => button.addEventListener('click', () => openCategoryModal(managedCategories.find(item => Number(item.id) === Number(button.dataset.categoryEdit)))));
    root.querySelectorAll('[data-category-delete]').forEach(button => button.addEventListener('click', () => deleteManagedCategory(managedCategories.find(item => Number(item.id) === Number(button.dataset.categoryDelete)), button)));
  }
  async function deleteManagedCategory(category, button) {
    if (!category || !window.confirm(`Delete category "${category.name}"?\n\nThis cannot be undone. Categories containing products or child categories cannot be deleted.`)) return;
    button.disabled = true; button.textContent = 'Deleting...';
    try {
      const catalog = await api('/api/native/catalog?section=products');
      const current = catalog.categories.find(item => Number(item.id) === Number(category.id));
      if (!current) throw new Error('Category no longer exists. Refresh the list.');
      const result = await api('/api/native/catalog/commands', {method: 'POST', body: JSON.stringify({
        request_id: crypto.randomUUID(), operation: 'category.delete', values: {id: Number(category.id), revision: current.revision},
      })});
      if (result.rejected) throw new Error(result.rejected);
      await loadCatalog(); await loadProductManager(); toast('Category deleted.');
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; button.textContent = 'Delete'; }
  }
  let itemImageUrl = '';
  const variantFields = [['color', 'Color'], ['size', 'Size'], ['sku', 'SKU'], ['barcode', 'Barcode'], ['price', 'Price', 0], ['cost', 'Cost', 0], ['stock', 'Stock', 0, 1], ['low_stock', 'Low stock', 0, 1]];
  const tierFields = [['min_qty', 'Minimum qty', 1, 1], ['unit_label', 'Unit label'], ['unit_multiplier', 'Qty / unit', 1, 1], ['barcode', 'Barcode'], ['unit_price', 'Wholesale price', 0.01], ['note', 'Note']];
  function addItemRow(kind, values = {}) {
    const row = document.createElement('div'); row.className = 'item-detail-row';
    const fields = kind === 'variants' ? variantFields : tierFields;
    row.innerHTML = fields.map(([key, label, min, step]) => `<label ${kind === 'variants' && ['cost', 'stock'].includes(key) ? 'hidden' : ''}><span>${label}</span><input data-field="${key}" ${min === undefined ? 'maxlength="160"' : `type="number" min="${min}" step="${step || 'any'}" required`} value="${escapeHtml(String(values[key] ?? (min === undefined ? '' : min)))}"></label>`).join('') + '<button type="button" class="remove-item-row">Remove</button>';
    row.querySelector('button').addEventListener('click', () => row.remove());
    document.querySelector(kind === 'variants' ? '#itemVariants' : '#itemTiers').appendChild(row);
  }
  function readItemRows(selector) {
    return [...document.querySelector(selector).children].map(row => Object.fromEntries([...row.querySelectorAll('[data-field]')].map(input => [input.dataset.field, input.type === 'number' ? Number(input.value) : input.value.trim()])));
  }
  function updateItemMode() {
    const mode = soldByMode(document.querySelector('#itemSoldBy').value);
    document.querySelectorAll('[data-item-mode]').forEach(section => {
      section.hidden = section.dataset.itemMode !== mode;
      section.querySelectorAll('input').forEach(input => { input.disabled = section.hidden; });
    });
    ['itemStock', 'itemLowStock', 'itemUnit'].forEach(id => {
      const input = document.getElementById(id); input.closest('label').hidden = mode !== 'each'; input.disabled = mode !== 'each';
    });
    ['itemPrice', 'itemCost'].forEach(id => {
      const input = document.getElementById(id); input.closest('label').hidden = mode === 'variants'; input.disabled = mode === 'variants';
    });
    ['itemCost', 'itemStock'].forEach(id => {
      const input = document.getElementById(id); input.closest('label').hidden = true; input.disabled = true;
    });
  }
  function previewItemImage() {
    const fileInput = document.querySelector('#itemImage'), file = fileInput.files[0];
    if (itemImageUrl) URL.revokeObjectURL(itemImageUrl); itemImageUrl = '';
    if (file && (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024)) {
      fileInput.value = ''; toast('Choose a JPEG, PNG or WebP image up to 5 MB.');
    }
    const selected = fileInput.files[0];
    if (selected) itemImageUrl = URL.createObjectURL(selected);
    const preview = document.querySelector('#itemImagePreview');
    preview.src = itemImageUrl || editingProduct?.thumbnail_url || ''; preview.hidden = !preview.getAttribute('src');
    document.querySelector('#itemImagePlaceholder').hidden = !preview.hidden;
  }
  function openItemModal(product = null) {
    editingProduct = product || null; populateCategoryOptions();
    const soldBy = soldByMode(product?.sold_by) === 'service' ? 'Service' : (soldByMode(product?.sold_by) === 'variants' ? 'Variants' : 'Each');
    document.querySelector('#itemModalTitle').textContent = product ? 'Edit Item' : 'Add Item';
    document.querySelector('#itemModalSubtitle').textContent = product ? product.name : 'Product details';
    document.querySelector('#itemName').value = product?.name || ''; document.querySelector('#itemCategory').value = product?.category || '';
    document.querySelector('#itemSoldBy').value = soldBy; document.querySelector('#itemPrice').value = product?.original_price ?? product?.price ?? 0;
    document.querySelector('#itemCost').value = product?.cost ?? 0; document.querySelector('#itemStock').value = product?.stock ?? 0;
    document.querySelector('#itemLowStock').value = product?.low_stock ?? 0; document.querySelector('#itemUnit').value = product?.unit || 'pcs';
    document.querySelector('#itemSku').value = product?.sku || ''; document.querySelector('#itemBarcode').value = product?.barcode || '';
    document.querySelector('#itemDescription').value = product?.description || ''; document.querySelector('#itemModal').hidden = false;
    document.querySelector('#itemUnit').value = product?.base_unit || product?.unit || 'pcs';
    document.querySelector('#itemPackUnit').value = product?.pack_unit || '';
    document.querySelector('#itemPackSize').value = product?.pack_size || 1;
    document.querySelector('#itemVariants').replaceChildren(); document.querySelector('#itemTiers').replaceChildren();
    (product?.variants || []).forEach(row => addItemRow('variants', row));
    (product?.wholesale_tiers || []).forEach(row => addItemRow('tiers', row));
    document.querySelector('#itemImage').value = ''; previewItemImage(); updateItemMode();
    document.querySelector('#itemForm .item-editor-layout').scrollTop = 0;
    setTimeout(() => document.querySelector('#itemName').focus(), 0);
  }
  function closeItemModal() { document.querySelector('#itemModal').hidden = true; editingProduct = null; if (itemImageUrl) URL.revokeObjectURL(itemImageUrl); itemImageUrl = ''; }
  function itemPayload() {
    const soldBy = document.querySelector('#itemSoldBy').value;
    const variants = soldByMode(soldBy) === 'variants' ? readItemRows('#itemVariants') : [];
    if (!editingProduct) variants.forEach(variant => { variant.cost = 0; variant.stock = 0; });
    return {
      name: document.querySelector('#itemName').value.trim(), category: document.querySelector('#itemCategory').value,
      description: document.querySelector('#itemDescription').value.trim(), sold_by: soldBy,
      price: Number(document.querySelector('#itemPrice').value || 0), cost: editingProduct ? Number(document.querySelector('#itemCost').value || 0) : 0,
      sku: document.querySelector('#itemSku').value.trim(), barcode: document.querySelector('#itemBarcode').value.trim(),
      stock: !editingProduct || soldByMode(soldBy) === 'service' ? 0 : Number(document.querySelector('#itemStock').value || 0), low_stock: soldByMode(soldBy) === 'each' ? Number(document.querySelector('#itemLowStock').value || 0) : 0,
      unit: document.querySelector('#itemUnit').value.trim() || 'pcs', base_unit: document.querySelector('#itemUnit').value.trim() || 'pcs',
      pack_unit: document.querySelector('#itemPackUnit').value.trim(), pack_size: Number(document.querySelector('#itemPackSize').value || 1), variants,
      wholesale_tiers: soldByMode(soldBy) === 'each' ? readItemRows('#itemTiers') : [],
    };
  }
  async function saveItemForm(event) {
    event.preventDefault();
    const payload = itemPayload(); if (!payload.name) return toast('Product name is required.');
    if (soldByMode(payload.sold_by) === 'variants' && !payload.variants.length) return toast('Add at least one variant.');
    if (new Set(payload.wholesale_tiers.map(t => t.min_qty)).size !== payload.wholesale_tiers.length) return toast('Wholesale minimum quantities must be unique.');
    const button = document.querySelector('#saveItem'); button.disabled = true; button.textContent = 'Saving...';
    const productId = editingProduct?.id;
    try {
      const file = document.querySelector('#itemImage').files[0];
      if (file) {
        const data = await new Promise((resolve, reject) => {
          const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error('Unable to read image.')); reader.readAsDataURL(file);
        });
        payload.image_base64 = String(data).split(',')[1]; payload.image_filename = file.name; payload.image_mime = file.type;
      }
      const path = productId ? `/api/products/manage/${Number(productId)}` : '/api/products/manage';
      await api(path, {method: productId ? 'PUT' : 'POST', body: JSON.stringify(payload)});
      closeItemModal(); await loadCatalog(); await loadProductManager(); toast('Item saved.');
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; button.textContent = 'Save Item'; }
  }
  function openCategoryModal(category = null) {
    editingCategory = category || null; populateCategoryOptions();
    document.querySelector('#categoryModalTitle').textContent = category ? 'Edit Category' : 'Add Category';
    document.querySelector('#categoryName').value = category?.name || ''; document.querySelector('#categoryParent').value = category?.parent_id || '';
    document.querySelector('#categorySort').value = category?.sort_order ?? 0; document.querySelector('#categoryStatus').value = category?.status || 'active';
    document.querySelector('#categoryDescription').value = category?.description || ''; document.querySelector('#categoryModal').hidden = false;
    setTimeout(() => document.querySelector('#categoryName').focus(), 0);
  }
  function closeCategoryModal() { document.querySelector('#categoryModal').hidden = true; editingCategory = null; }
  async function saveCategoryForm(event) {
    event.preventDefault();
    const payload = {
      name: document.querySelector('#categoryName').value.trim(), description: document.querySelector('#categoryDescription').value.trim(),
      parent_id: Number(document.querySelector('#categoryParent').value || 0) || null,
      sort_order: Number(document.querySelector('#categorySort').value || 0), status: document.querySelector('#categoryStatus').value || 'active',
    };
    if (!payload.name) return toast('Category name is required.');
    const button = document.querySelector('#saveCategory'); button.disabled = true; button.textContent = 'Saving...';
    try {
      const path = editingCategory ? `/api/categories/manage/${Number(editingCategory.id)}` : '/api/categories/manage';
      await api(path, {method: editingCategory ? 'PUT' : 'POST', body: JSON.stringify(payload)});
      closeCategoryModal(); await loadCatalog(); await loadProductManager(); toast('Category saved.');
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; button.textContent = 'Save Category'; }
  }
  function code128Svg(value) {
    const text = String(value || '').trim();
    if (!/^[\x20-\x7E]+$/.test(text)) throw new Error('Code128 supports printable ASCII only.');
    const values = [104, ...[...text].map(character => character.charCodeAt(0) - 32)];
    let checksum = 104; for (let index = 1; index < values.length; index += 1) checksum += values[index] * index;
    values.push(checksum % 103, 106);
    let x = 0, rects = '';
    for (const code of values) {
      const pattern = code128Patterns[code];
      for (let index = 0; index < pattern.length; index += 1) {
        const width = Number(pattern[index]);
        if (index % 2 === 0) rects += `<rect x="${x}" y="0" width="${width}" height="48"></rect>`;
        x += width;
      }
    }
    return `<svg viewBox="0 0 ${x} 48" role="img" aria-label="Barcode ${escapeHtml(text)}" xmlns="http://www.w3.org/2000/svg">${rects}</svg>`;
  }
  function barcodeLabel(product) {
    const code = product?.barcode || product?.sku || '';
    return `<div class="barcode-label">${code128Svg(code)}<div class="barcode-name">${escapeHtml(product?.name || 'Product')}</div><div class="barcode-number">${escapeHtml(code)}</div></div>`;
  }
  function refreshBarcodePrintArea() {
    if (!barcodeProduct) return;
    const qty = Math.max(1, Math.min(200, Number(document.querySelector('#barcodeQty').value || 1)));
    document.querySelector('#barcodePrintArea').innerHTML = Array.from({length: qty}, () => barcodeLabel(barcodeProduct)).join('');
  }
  function openBarcodeModal(product) {
    const code = product?.barcode || product?.sku || '';
    if (!code) return toast('This product has no barcode or SKU.');
    barcodeProduct = product; document.querySelector('#barcodeModalSubtitle').textContent = product.name || '';
    document.querySelector('#barcodeQty').value = '1';
    try {
      document.querySelector('#barcodePreview').innerHTML = barcodeLabel(product);
      refreshBarcodePrintArea(); document.querySelector('#barcodeModal').hidden = false;
    } catch (error) { toast(error.message); barcodeProduct = null; }
  }
  function closeBarcodeModal() { document.querySelector('#barcodeModal').hidden = true; barcodeProduct = null; }
  function clearCatalog() {
    hideInventory();
    receiptsRequest += 1;
    document.querySelector('#touchReceipts').hidden = true;
    document.querySelector('#receiptsRows').replaceChildren();
    document.querySelector('#receiptsDetail').replaceChildren();
    document.querySelector('#receiptsSummary').replaceChildren();
    clearTimeout(searchTimer); searchTimer = null;
    if (productsController) { productsController.abort(); productsController = null; }
    products = []; categories = []; selectedCategory = ''; document.querySelector('#productSearch').value = ''; document.querySelector('#categorySearch').value = '';
    document.querySelector('#productSearch').disabled = true; document.querySelector('#categorySearch').disabled = true; document.querySelector('#refreshProducts').disabled = true;
    document.querySelector('#categoryCount').textContent = '0'; document.querySelector('#productCount').textContent = '0 items';
    document.querySelector('#sideProductBadge').textContent = '0';
    document.querySelector('#categoryList').innerHTML = '<div class="category-loading">Sign in to load</div>';
    document.querySelector('#productGrid').classList.add('loaded');
    document.querySelector('#productGrid').innerHTML = '<div class="catalog-message">Sign in to view products.</div>';
    document.querySelector('#productManager').hidden = true;
    document.querySelector('.workspace').hidden = false;
  }
  function showLogin(message = '') {
    clearCatalog();
    clearCart();
    clearAvatar();
    setSideMenuOpen(false);
    token = null; sessionStorage.removeItem(TOKEN_KEY); password.value = '';
    loginStatus.textContent = message; loginStatus.className = 'login-status';
    userMenu.hidden = true; appView.hidden = true; loginView.hidden = false; setTimeout(() => username.focus(), 0);
  }
  function showApp(user) {
    const name = user.full_name || user.username;
    document.querySelector('#userInitials').textContent = initials(user); document.querySelector('#userName').textContent = name;
    document.querySelector('#sideMenuInitials').textContent = initials(user);
    document.querySelector('#userRole').textContent = user.role || 'Staff'; document.querySelector('#menuUserName').textContent = name;
    document.querySelector('#menuUserRole').textContent = `${user.role || 'Staff'} · Sales access`;
    document.querySelector('#sideMenuUser').textContent = `${name} · ${user.role || 'Staff'}`;
    loadAvatar();
    loginView.hidden = true; appView.hidden = false; password.value = ''; loginStatus.textContent = '';
  }
  function renderCategories() {
    const root = document.querySelector('#categoryList'); root.replaceChildren();
    const query = document.querySelector('#categorySearch').value.trim().toLowerCase();
    const visibleCategories = query ? categories.filter(name => String(name || '').toLowerCase().includes(query)) : categories;
    if (query && selectedCategory && !visibleCategories.includes(selectedCategory)) selectedCategory = '';
    for (const name of ['', ...visibleCategories]) {
      const button = document.createElement('button'); button.type = 'button'; button.className = `category${name === selectedCategory ? ' active' : ''}`;
      const label = name || 'All products';
      button.title = label;
      button.innerHTML = `<span class="category-name">${escapeHtml(label)}</span>`;
      button.setAttribute('aria-pressed', String(name === selectedCategory));
      button.addEventListener('click', () => { selectedCategory = name; renderCategories(); loadProducts(); }); root.appendChild(button);
    }
    document.querySelector('#categoryCount').textContent = query ? `${visibleCategories.length}/${categories.length}` : String(categories.length);
  }
  function filterCategories() {
    const previousCategory = selectedCategory;
    renderCategories();
    if (previousCategory !== selectedCategory) loadProducts();
  }
  function renderProducts() {
    const root = document.querySelector('#productGrid'); root.classList.add('loaded');
    document.querySelector('#productCount').textContent = `${products.length} item${products.length === 1 ? '' : 's'}`;
    document.querySelector('#sideProductBadge').textContent = String(products.length);
    if (!products.length) { root.innerHTML = '<div class="catalog-message"><strong>No products found</strong>Try another category or search.</div>'; return; }
    const displayProducts = products.map((product, index) => ({product, index})).sort((left, right) => {
      const leftOut = productOutOfStock(left.product), rightOut = productOutOfStock(right.product);
      return Number(leftOut) - Number(rightOut) || left.index - right.index;
    }).map(entry => entry.product);
    root.innerHTML = displayProducts.map(product => {
      const service = isService(product), variants = soldByMode(product.sold_by) === 'variants';
      const variantRows = Array.isArray(product.variants) ? product.variants : [];
      const out = productOutOfStock(product);
      const low = Boolean(product.is_low_stock), image = String(product.thumbnail_url || '').trim();
      const badge = out ? '<span class="product-badge out">Out of stock</span>' : (low ? '<span class="product-badge">Low stock</span>' : (service ? '<span class="product-badge">Service</span>' : (variants ? '<span class="product-badge">Variants</span>' : '')));
      const stockBadge = service ? '' : `<span class="product-stock">${money(variants ? variantRows.reduce((sum, item) => sum + Number(item.stock || 0), 0) : product.stock)}</span>`;
      return `<button class="product-card" type="button" data-product-id="${Number(product.id)}" ${out ? 'disabled' : ''}><span class="product-image">${image ? `<img src="${escapeHtml(image)}" alt="" loading="lazy">` : '▦'}</span>${badge}<span class="product-info"><span class="product-name">${escapeHtml(product.name)}</span><span class="product-price">${money(product.price)} Ks</span></span>${stockBadge}</button>`;
    }).join('');
    root.querySelectorAll('.product-image img').forEach(image => image.addEventListener('error', () => { image.parentElement.textContent = '▦'; }, {once: true}));
    root.querySelectorAll('[data-product-id]').forEach(button => button.addEventListener('click', () => {
      const product = products.find(item => Number(item.id) === Number(button.dataset.productId));
      if (product) chooseProduct(product);
    }));
  }
  async function loadProducts() {
    if (!token) return; if (productsController) productsController.abort();
    productsController = new AbortController(); const controller = productsController;
    const root = document.querySelector('#productGrid'); root.classList.add('loaded'); root.innerHTML = '<div class="catalog-message">Loading products…</div>';
    const query = new URLSearchParams({q: document.querySelector('#productSearch').value.trim(), category: selectedCategory, limit: '200'});
    try {
      const result = await api(`/api/touch-pos/products?${query}`, {signal: controller.signal}); if (controller !== productsController) return;
      products = Array.isArray(result.products) ? result.products : []; renderProducts();
    } catch (error) {
      if (error.name === 'AbortError' || controller !== productsController) return;
      products = []; document.querySelector('#productCount').textContent = 'Unavailable'; document.querySelector('#sideProductBadge').textContent = '0';
      root.innerHTML = `<div class="catalog-message"><strong>Could not load products</strong>${escapeHtml(error.message)}<br><button id="retryProducts" type="button">Retry</button></div>`;
      document.querySelector('#retryProducts').addEventListener('click', loadProducts);
    } finally { if (controller === productsController) productsController = null; }
  }
  async function loadCatalog() {
    document.querySelector('#productSearch').disabled = false; document.querySelector('#refreshProducts').disabled = false;
    try {
      const result = await api('/api/touch-pos/categories');
      categories = Array.isArray(result.categories) ? result.categories : [];
      document.querySelector('#categorySearch').disabled = false;
      renderCategories(); await loadProducts(); document.querySelector('#workspaceStatus').textContent = 'Phase W7 · Receipt print';
    } catch (error) {
      document.querySelector('#categoryList').innerHTML = `<div class="category-loading">${escapeHtml(error.message)}</div>`;
      document.querySelector('#workspaceStatus').textContent = 'Catalog unavailable · Retry when server reconnects';
    }
  }
  async function validateSession() {
    if (!token) return showLogin();
    try { showApp((await api('/api/touch-pos/session')).user); await loadCatalog(); }
    catch (error) { if (token) { try { await api('/api/touch-pos/logout', {method: 'POST'}); } catch (_) {} } showLogin(error.message); }
  }
  loginForm.addEventListener('submit', async event => {
    event.preventDefault(); if (!username.value.trim() || !password.value) return;
    signIn.disabled = true; loginStatus.textContent = 'Signing in…'; loginStatus.className = 'login-status info';
    try {
      const result = await api('/api/login', {method: 'POST', body: JSON.stringify({username: username.value.trim(), password: password.value})}); token = result.token;
      const access = await api('/api/touch-pos/session'); sessionStorage.setItem(TOKEN_KEY, token); showApp(access.user); restoreCart(); await loadCatalog();
    } catch (error) {
      if (token) { try { await api('/api/touch-pos/logout', {method: 'POST'}); } catch (_) {} }
      token = null; sessionStorage.removeItem(TOKEN_KEY); password.value = ''; loginStatus.textContent = error.message; loginStatus.className = 'login-status'; password.focus();
    } finally { signIn.disabled = false; }
  });
  const saleCart = document.querySelector('#saleCart'), openCart = document.querySelector('#openCart'), closeCart = document.querySelector('#closeCart');
  const compactCart = window.matchMedia('(max-width: 760px)');
  function setCartOpen(open, restoreFocus = false) {
    if (!compactCart.matches) {
      saleCart.classList.remove('open');
      saleCart.inert = false;
      openCart.setAttribute('aria-expanded', 'false');
      return;
    }
    saleCart.classList.toggle('open', open);
    saleCart.inert = !open;
    openCart.setAttribute('aria-expanded', String(open));
    if (open) closeCart.focus();
    else if (restoreFocus) openCart.focus();
  }
  function syncCartMode() {
    if (compactCart.matches) setCartOpen(saleCart.classList.contains('open'));
    else setCartOpen(false);
  }
  function setSideMenuOpen(open, restoreFocus = false) {
    if (open) sideMenu.hidden = false;
    sideMenu.classList.toggle('open', open);
    sideMenuOverlay.hidden = !open;
    sideMenu.setAttribute('aria-hidden', String(!open));
    sideMenuButton.setAttribute('aria-expanded', String(open));
    if (open) {
      userMenu.hidden = true; userButton.setAttribute('aria-expanded', 'false'); closeSideMenuButton.focus();
    } else if (restoreFocus) {
      sideMenuButton.focus();
    }
    if (!open) sideMenu.hidden = true;
  }
  function runSideMenuAction(action) {
    setSideMenuOpen(false, true);
    if (action === 'inventory') { showInventoryPage(); return; }
    if (action === 'receipts') { showReceiptsPage(); return; }
    if (['products', 'categories', 'search', 'cart'].includes(action)) showSalesView();
    if (action === 'products') document.querySelector('#productSearch').focus();
    else if (action === 'product-page') showProductManager();
    else if (action === 'categories') document.querySelector('#categorySearch').focus();
    else if (action === 'search') document.querySelector('#productSearch').focus();
    else if (action === 'cart') setCartOpen(true);
    else if (action === 'fullscreen') fullscreen.click();
    else if (action === 'profile') userButton.click();
    else if (action === 'refresh') loadCatalog();
  }
  openCart.addEventListener('click', () => setCartOpen(true));
  closeCart.addEventListener('click', () => setCartOpen(false, true));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && sideMenu.classList.contains('open')) setSideMenuOpen(false, true);
    else if (event.key === 'Escape' && saleCart.classList.contains('open')) setCartOpen(false, true);
  });
  compactCart.addEventListener('change', syncCartMode);
  syncCartMode();
  sideMenuButton.addEventListener('click', () => setSideMenuOpen(!sideMenu.classList.contains('open')));
  closeSideMenuButton.addEventListener('click', () => setSideMenuOpen(false, true));
  sideMenuOverlay.addEventListener('click', () => setSideMenuOpen(false, true));
  document.querySelectorAll('[data-side-action]').forEach(button => button.addEventListener('click', () => runSideMenuAction(button.dataset.sideAction)));
  document.querySelector('#sideSignOut').addEventListener('click', () => document.querySelector('#signOut').click());
  userButton.addEventListener('click', () => {
    setSideMenuOpen(false);
    userMenu.hidden = !userMenu.hidden; userButton.setAttribute('aria-expanded', String(!userMenu.hidden));
  });
  document.querySelector('#signOut').addEventListener('click', async () => { try { await api('/api/touch-pos/logout', {method: 'POST'}); } catch (_) {} clearCatalog(); showLogin('Signed out.'); });
  document.querySelector('#clearCart').addEventListener('click', () => { clearCart(); toast('Cart cleared.'); });
  document.querySelector('#paymentButton').addEventListener('click', openCheckoutDetails);
  document.querySelector('#closeCheckout').addEventListener('click', closeCheckout);
  document.querySelector('#cancelCheckout').addEventListener('click', closeCheckout);
  document.querySelector('#saveCheckout').addEventListener('click', submitCheckoutSale);
  document.querySelector('#checkoutCustomer').addEventListener('change', renderCheckoutSummary);
  document.querySelector('#checkoutSaleMode').addEventListener('change', renderCheckoutSummary);
  document.querySelector('#checkoutDiscount').addEventListener('input', renderCheckoutSummary);
  document.querySelector('#checkoutReceived').addEventListener('input', renderCheckoutSummary);
  document.querySelector('#checkoutModal').addEventListener('click', event => { if (event.target.id === 'checkoutModal') closeCheckout(); });
  document.querySelector('#closeChoice').addEventListener('click', closeChoice);
  document.querySelector('#cancelChoice').addEventListener('click', closeChoice);
  document.querySelector('#confirmChoice').addEventListener('click', confirmChoice);
  document.querySelector('#productChoiceModal').addEventListener('click', event => { if (event.target.id === 'productChoiceModal') closeChoice(); });
  document.querySelector('#productChoiceModal').addEventListener('keydown', event => { if (event.key === 'Enter') confirmChoice(); });
  document.addEventListener('keydown', handleServiceKeydown);
  document.querySelector('#closeReceipt').addEventListener('click', () => { document.querySelector('#receiptModal').hidden = true; });
  document.querySelector('#printReceiptButton').addEventListener('click', () => window.print());
  document.querySelector('#newSale').addEventListener('click', () => { document.querySelector('#receiptModal').hidden = true; document.querySelector('#productSearch').focus(); });
  document.querySelector('#productSearch').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadProducts, 250); });
  document.querySelector('#productSearch').addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); clearTimeout(searchTimer); loadProducts(); } });
  document.querySelector('#categorySearch').addEventListener('input', filterCategories);
  document.querySelector('#refreshProducts').addEventListener('click', loadCatalog);
  document.querySelector('#backToSales').addEventListener('click', showSalesView);
  document.querySelector('#managerRefresh').addEventListener('click', loadProductManager);
  document.querySelector('#managerAddItem').addEventListener('click', () => openItemModal());
  document.querySelector('#managerAddCategory').addEventListener('click', () => openCategoryModal());
  document.querySelector('#managerProductSearch').addEventListener('input', () => { clearTimeout(managerSearchTimer); managerSearchTimer = setTimeout(loadProductManager, 250); });
  document.querySelector('#managerCategorySearch').addEventListener('input', renderManagedCategories);
  document.querySelectorAll('[data-receipts-tab]').forEach(button=>button.addEventListener('click',()=>{
    document.querySelector('#receiptsTab').value=button.dataset.receiptsTab;
    document.querySelectorAll('[data-receipts-tab]').forEach(tab=>tab.setAttribute('aria-pressed',String(tab===button)));
    receiptsOffset=0;loadTouchReceipts();
  }));
  document.querySelectorAll('[data-receipts-days]').forEach(button=>button.addEventListener('click',()=>{
    const end=new Date(), start=new Date();start.setDate(end.getDate()-Number(button.dataset.receiptsDays)+1);
    const dateText=date=>`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
    document.querySelector('#receiptsFrom').value=dateText(start);document.querySelector('#receiptsTo').value=dateText(end);
    receiptsOffset=0;loadTouchReceipts();
  }));
  document.querySelector('#inventorySales').onclick=showSalesView;
  document.querySelector('#inventoryFilters').onsubmit=event=>{event.preventDefault();inventoryOffset=0;loadInventory();};
  document.querySelector('#inventoryPrev').onclick=()=>{inventoryOffset=Math.max(0,inventoryOffset-50);loadInventory();};
  document.querySelector('#inventoryNext').onclick=()=>{inventoryOffset+=50;loadInventory();};
  document.querySelector('#receiptsSales').addEventListener('click', showSalesView);
  document.querySelector('#receiptsFilters').addEventListener('submit', event=>{event.preventDefault();receiptsOffset=0;loadTouchReceipts();});
  document.querySelector('#receiptsTab').addEventListener('change', ()=>{receiptsOffset=0;loadTouchReceipts();});
  document.querySelector('#receiptsPrev').addEventListener('click', ()=>{receiptsOffset=Math.max(0,receiptsOffset-30);loadTouchReceipts();});
  document.querySelector('#receiptsNext').addEventListener('click', ()=>{receiptsOffset+=30;loadTouchReceipts();});
  document.querySelector('#itemForm').addEventListener('submit', saveItemForm);
  document.querySelector('#itemSoldBy').addEventListener('change', updateItemMode);
  document.querySelector('#addItemVariant').addEventListener('click', () => addItemRow('variants'));
  document.querySelector('#addItemTier').addEventListener('click', () => addItemRow('tiers'));
  document.querySelector('#itemImage').addEventListener('change', previewItemImage);
  document.querySelector('#closeItemModal').addEventListener('click', closeItemModal);
  document.querySelector('#cancelItemModal').addEventListener('click', closeItemModal);
  document.querySelector('#itemModal').addEventListener('click', event => { if (event.target.id === 'itemModal') closeItemModal(); });
  document.querySelector('#categoryForm').addEventListener('submit', saveCategoryForm);
  document.querySelector('#closeCategoryModal').addEventListener('click', closeCategoryModal);
  document.querySelector('#cancelCategoryModal').addEventListener('click', closeCategoryModal);
  document.querySelector('#categoryModal').addEventListener('click', event => { if (event.target.id === 'categoryModal') closeCategoryModal(); });
  document.querySelector('#closeBarcodeModal').addEventListener('click', closeBarcodeModal);
  document.querySelector('#cancelBarcodeModal').addEventListener('click', closeBarcodeModal);
  document.querySelector('#barcodeQty').addEventListener('input', refreshBarcodePrintArea);
  document.querySelector('#printBarcodeButton').addEventListener('click', () => { refreshBarcodePrintArea(); window.print(); });
  async function checkServer() {
    try { const response = await fetch('/health', {cache: 'no-store'}), value = await response.json(); setConnection(response.ok && value.ok === true); }
    catch (_) { setConnection(false); }
  }
  function updateClock() { clock.textContent = new Intl.DateTimeFormat(undefined, {dateStyle: 'medium', timeStyle: 'short'}).format(new Date()); }
  fullscreen.addEventListener('click', async () => { try { if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen(); } catch (_) {} });
  document.addEventListener('fullscreenchange', () => { fullscreen.textContent = document.fullscreenElement ? 'Exit Full Screen' : 'Full Screen'; });
  window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); installPrompt = event; install.hidden = false; });
  install.addEventListener('click', async () => { if (!installPrompt) return; installPrompt.prompt(); await installPrompt.userChoice; installPrompt = null; install.hidden = true; });
  if ('serviceWorker' in navigator && window.isSecureContext) navigator.serviceWorker.register('/touch-pos/service-worker.js', {scope: '/touch-pos/'}).catch(() => {});
  restoreCart(); updateClock(); checkServer(); validateSession(); setInterval(updateClock, 30000); setInterval(checkServer, 30000);
})();
