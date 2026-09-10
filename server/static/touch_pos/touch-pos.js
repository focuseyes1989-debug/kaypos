(() => {
  'use strict';
  const clock = document.querySelector('#clock');
  const fullscreen = document.querySelector('#fullscreen'), install = document.querySelector('#install');
  const loginView = document.querySelector('#loginView'), appView = document.querySelector('#app');
  const loginForm = document.querySelector('#loginForm'), loginStatus = document.querySelector('#loginStatus');
  const signIn = document.querySelector('#signIn'), password = document.querySelector('#password');
  const username = document.querySelector('#username');
  const TOKEN_KEY = 'kay_touch_pos_token';
  const sideMenuButton = document.querySelector('#sideMenuButton'), sideMenu = document.querySelector('#sideMenu');
  const sideMenuOverlay = document.querySelector('#sideMenuOverlay'), closeSideMenuButton = document.querySelector('#closeSideMenu');
  const CART_KEY = 'kay_touch_pos_cart';
  const REMEMBER_KEY = 'kay_touch_pos_remember';
  function clearLoginStorage() {
    sessionStorage.removeItem(TOKEN_KEY);localStorage.removeItem(REMEMBER_KEY);
  }
  function readLoginToken() {
    try {
      const saved=JSON.parse(localStorage.getItem(REMEMBER_KEY) || 'null');
      if(saved && typeof saved.token==='string' && saved.expires>Date.now())return saved.token;
      localStorage.removeItem(REMEMBER_KEY);
    }catch(_){localStorage.removeItem(REMEMBER_KEY);}
    return sessionStorage.getItem(TOKEN_KEY);
  }
  function saveLoginToken(value, remember) {
    clearLoginStorage();
    if(remember)localStorage.setItem(REMEMBER_KEY,JSON.stringify({token:value,expires:Date.now()+30*24*60*60*1000}));
    else sessionStorage.setItem(TOKEN_KEY,value);
  }
  let token = readLoginToken(), installPrompt = null, products = [], customers = [], categories = [], selectedCategory = '';
  let managedProducts = [], managedCategories = [], editingProduct = null, editingCategory = null, barcodeProduct = null, managerSearchTimer = null;
  let cart = new Map(), avatarUrl = '';
  let checkoutSettings = {};
  let searchTimer = null, productsController = null, toastTimer = null, choiceState = null;

  function setConnection(ok) {
    for (const item of [document.querySelector('#loginConnection')]) {
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
  function setTouchView(view) {
    appView.dataset.touchView = view;
    const activeAction = {
      sales: 'products',
      products: 'product-page',
      categories: 'category-page',
      receipts: 'receipts',
      inventory: 'inventory',
      dashboard: 'dashboard',
      expenses: 'expenses',
      settings: 'settings',
      customers: 'customers',
      suppliers: 'suppliers',
      locations: 'locations'
    }[view];
    document.querySelectorAll('[data-side-action]').forEach(button => {
      button.toggleAttribute('aria-current', button.dataset.sideAction === activeAction);
    });
  }
  function categoryTone(category) {
    let hash = 0;
    for (const char of String(category || 'No category').trim().toLowerCase()) hash = (hash * 31 + char.codePointAt(0)) >>> 0;
    return hash % 6;
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
  function repriceVariantCart() {
    for (const item of cart.values()) {
      if (!item.variant_id || item.regular_price === undefined) continue;
      item.price=item.wholesale_min_qty>0 && item.wholesale_price>0 && item.qty>=item.wholesale_min_qty ? item.wholesale_price : item.regular_price;
    }
  }
  function saveCart() {
    repriceVariantCart();
    sessionStorage.setItem(CART_KEY, JSON.stringify([...cart.values()]));
  }
  function cartTotals() {
    repriceVariantCart();
    const items = [...cart.values()], count = items.reduce((sum, item) => sum + Number(item.qty || 0), 0);
    const subtotal = items.reduce((sum, item) => sum + Number(item.price || 0) * Number(item.qty || 0), 0);
    return {items, count, subtotal, discount: 0, total: subtotal};
  }
  function checkoutTotals() {
    const {items, count, subtotal} = cartTotals();
    const rawDiscount = Math.max(0, Number(document.querySelector('#checkoutDiscount')?.value || 0));
    const discount = Math.min(subtotal, rawDiscount);
    const afterDiscount = Math.max(0, subtotal - discount);
    const tax = checkoutSettings.tax_enabled ? Math.round(afterDiscount * Number(checkoutSettings.tax_rate || 0)) / 100 : 0;
    const total = Math.round((afterDiscount + tax) * 100) / 100;
    const received = Math.max(0, Number(document.querySelector('#checkoutReceived')?.value || 0));
    return {items, count, subtotal, rawDiscount, discount, tax, total, received, change: Math.max(0, received - total), balance: Math.max(0, total - received)};
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
    for (const image of [document.querySelector('#sideMenuAvatar')]) {
      image.hidden = true;
      image.removeAttribute('src');
    }
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
      for (const image of [document.querySelector('#sideMenuAvatar')]) {
        image.src = avatarUrl;
        image.hidden = false;
      }
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
    const sideCartBadge = document.querySelector('#sideCartBadge');
    if (sideCartBadge) sideCartBadge.textContent = String(count);
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
      price, regular_price:price, wholesale_min_qty:Number(variant?.wholesale_min_qty || 0), wholesale_price:Number(variant?.wholesale_price || 0), stock, qty: 0, is_service: service,
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
    const settings=receipt.receipt_settings || {};
    const lines = [settings.shop_name || 'KAY POS', settings.shop_phone || '', settings.shop_address || '', settings.receipt_header || '', receipt.invoice_no || 'Receipt', receipt.created_at || new Date().toLocaleString(), ''];
    for (const item of items) {
      const name = String(item.product_name || item.name || 'Item');
      const qty = Number(item.qty || 0), price = Number(item.price || 0), amount = Number(item.total || qty * price);
      lines.push(name);
      lines.push(`  ${qty} x ${money(price)} = ${money(amount)} Ks`);
    }
    lines.push('', `Subtotal: ${money(receipt.subtotal ?? total)} Ks`, `Discount: ${money(receipt.discount_amount || 0)} Ks`, `Total: ${money(total)} Ks`, `Paid: ${money(paid)} Ks`, `Change: ${money(Math.max(0, paid - total))} Ks`, '', settings.receipt_footer || '', settings.shop_footer_message || '', settings.receipt_thank_you_text || 'Thank you.');
    return lines.join('\n');
  }
  let activePrintReceipt = null;
  function updateReceiptPreview() {
    if (!activePrintReceipt) return;
    const paper = document.querySelector('#receiptPaper').value;
    document.querySelector('#receiptPreviewSize').textContent = paper === 'a4' ? 'A4' : `${paper}mm`;
    document.querySelector('#receiptPaperHint').textContent = paper === 'a4' ? 'Full-page layout for A4 printers.' : 'Compact layout for your thermal paper roll.';
    document.querySelector('#receiptPreview').srcdoc = window.KayTouchReceipt.documentHtml(activePrintReceipt.receipt, activePrintReceipt.paid, paper);
  }
  function showReceipt(receipt, paid) {
    document.querySelector('#receiptCompletionStatus').textContent = '';
    activePrintReceipt = {receipt, paid};
    document.querySelector('#receiptState').textContent = String(receipt.status).toLowerCase() === 'refunded' ? 'Refunded receipt' : 'Sale saved';
    document.querySelector('#receiptPaper').value = window.KayTouchReceipt.paper(window.KayTouchReceipt.settings().receipt_paper_size);
    updateReceiptPreview();
    const modal = document.querySelector('#receiptModal'), total = Number(receipt.total ?? 0);
    document.querySelector('#receiptInvoice').textContent = receipt.invoice_no || '';
    document.querySelector('#printReceipt').textContent = receiptLines(receipt, paid);
    document.querySelector('#receiptBody').innerHTML = [
      ['Items', String((receipt.items || []).reduce((sum, item) => sum + Number(item.qty || 0), 0) || cartTotals().count)],
      ['Subtotal', `${money(receipt.subtotal ?? total)} Ks`],
      ['Discount', `${money(receipt.discount_amount || 0)} Ks`],
      ['Paid', `${money(paid)} Ks`],
      ['Change', `${money(Math.max(0, paid - total))} Ks`],
      ['Total', `${money(total)} Ks`, 'receipt-total'],
    ].map(row => `<div class="${row[2] || ''}"><span>${escapeHtml(row[0])}</span><strong>${escapeHtml(row[1])}</strong></div>`).join('');
    modal.hidden = false;
  }
  async function runSaleCompletionActions(receipt, paid) {
    if (window.KayTouchReceipt.settings().touch_auto_print_receipt !== '1') return;
    const button = document.querySelector('#printReceiptButton');
    button.disabled = true;
    try { await window.KayTouchReceipt.print(receipt, paid, document.querySelector('#receiptPaper').value); }
    catch (error) { document.querySelector('#receiptCompletionStatus').textContent = `Sale saved. Could not open print dialog: ${error.message}. Use Print Receipt to retry.`; }
    finally { button.disabled = false; }
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
      clearCart(); renderCart(); showReceipt(receipt, payment);
      await runSaleCompletionActions(receipt, payment);
      await loadProducts();
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
  function suggestedReceivedAmounts(total) {
    if (!Number.isFinite(total) || total <= 0) return [];
    const step = total < 5000 ? 1000 : total < 10000 ? 5000 : 10000;
    return [...new Set([total, Math.ceil(total / step) * step, 500, 1000, 5000, 10000])]
      .filter(amount => amount >= total).sort((a, b) => a - b);
  }
  function renderReceivedSuggestions() {
    const container = document.querySelector('#checkoutReceivedSuggestions');
    if (!container) return;
    const {total, received} = checkoutTotals();
    container.innerHTML = suggestedReceivedAmounts(total).map(amount =>
      `<button type="button" data-received-amount="${amount}" aria-pressed="${received === amount}">${money(amount)} Ks</button>`
    ).join('');
    container.querySelectorAll('[data-received-amount]').forEach(button => {
      button.addEventListener('click', () => {
        const input = document.querySelector('#checkoutReceived');
        input.value = button.dataset.receivedAmount;
        activateCheckoutKeypad(input);
        input.dispatchEvent(new Event('input', {bubbles: true}));
      });
    });
  }
  function renderCheckoutSummary() {
    renderReceivedSuggestions();
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
    if (mode !== 'Credit' && totals.received < totals.total) messages.push('Received amount is less than total.');
    if (mode === 'Credit' && totals.received > totals.total) messages.push('Credit received amount cannot exceed total.');
    if (totals.rawDiscount > totals.subtotal) messages.push('Discount cannot exceed subtotal.');
    document.querySelector('#checkoutSummary').innerHTML = [
      ['Items', String(totals.count)],
      ['Subtotal', `${money(totals.subtotal)} Ks`],
      ['Discount', `${money(totals.discount)} Ks`],
      ['Tax', `${money(totals.tax)} Ks`],
      ['Total', `${money(totals.total)} Ks`, 'checkout-total'],
      ['Received', `${money(totals.received)} Ks`],
      [mode === 'Credit' ? 'Credit Balance' : 'Change', `${money(mode === 'Credit' ? totals.balance : totals.change)} Ks`],
    ].map(row => `<div class="${row[2] || ''}"><span>${escapeHtml(row[0])}</span><strong>${escapeHtml(row[1])}</strong></div>`).join('');
    document.querySelector('#checkoutValidation').textContent = messages[0] || 'Ready to save.';
    document.querySelector('#checkoutValidation').classList.toggle('ok', messages.length === 0);
    document.querySelector('#saveCheckout').disabled = messages.length > 0;
  }
  let checkoutKeypadField = 'checkoutReceived';
  let checkoutKeypadReplace = true;
  function activateCheckoutKeypad(input) {
    checkoutKeypadField = input.id;
    checkoutKeypadReplace = true;
    document.querySelector('#checkoutKeypadTarget').textContent = `Keypad · ${input.id === 'checkoutDiscount' ? 'Discount' : 'Received'}`;
    ['checkoutDiscount', 'checkoutReceived'].forEach(id => document.querySelector(`#${id}`).classList.toggle('keypad-active', id === input.id));
    input.select();
  }
  function pressCheckoutKey(key) {
    const input = document.querySelector(`#${checkoutKeypadField}`);
    let value = input.value || '';
    if (key === 'clear') value = '';
    else if (key === 'backspace') value = checkoutKeypadReplace ? '' : value.slice(0, -1);
    else {
      if (checkoutKeypadReplace) value = '';
      if (key !== '.' || !value.includes('.')) value += key;
      if (value.startsWith('.')) value = `0${value}`;
      value = value.replace(/^0+(?=\d)/, '');
    }
    checkoutKeypadReplace = false;
    input.value = value;
    input.dispatchEvent(new Event('input', {bubbles: true}));
  }
  async function openCheckoutDetails() {
    const {items, total} = cartTotals();
    if (!items.length) return toast('Cart is empty.');
    const modal = document.querySelector('#checkoutModal');
    try {
      const data=await api('/api/settings/cashier');checkoutSettings=data.settings || {};
      const methods=[...new Set(['Cash',...(checkoutSettings.payment_types || []),'Credit'])];
      document.querySelector('#checkoutSaleMode').innerHTML=methods.map(name=>`<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join('');
    }catch(error){toast(error.message);return;}
    const subtotal=cartTotals().subtotal;
    const defaultDiscount=checkoutSettings.discount_enabled ? (checkoutSettings.discount_type==='percentage' ? subtotal*Number(checkoutSettings.discount_value || 0)/100 : checkoutSettings.discount_type==='fixed' ? Number(checkoutSettings.discount_value || 0) : 0) : 0;
    document.querySelector('#checkoutDiscount').value = String(Math.min(subtotal,defaultDiscount));
    document.querySelector('#checkoutReceived').value = String(checkoutTotals().total);
    document.querySelector('#checkoutSaleMode').value = 'Cash';
    modal.hidden = false;
    await loadCheckoutCustomers();
    renderCheckoutSummary();
    document.querySelector('#checkoutReceived').focus();
    activateCheckoutKeypad(document.querySelector('#checkoutReceived'));
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
    if (mode !== 'Credit' && totals.received < totals.total) return toast('Received amount is less than total.');
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
      closeCheckout(); clearCart(); renderCart(); showReceipt(receipt, totals.received);
      await runSaleCompletionActions(receipt, totals.received);
      await loadProducts();
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
    stockIn.insertAdjacentHTML('beforebegin','<div class="receipt-tabs inventory-action-tabs" aria-label="Stock action"><button type="button" data-stock-action="in" aria-pressed="true" data-icon="arrow_circle_down">Stock In</button><button type="button" data-stock-action="out" aria-pressed="false" data-icon="arrow_circle_up">Stock Out</button><button type="button" data-stock-action="adjust" aria-pressed="false" data-icon="swap_horiz">Adjustment</button></div>');
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

  function showInventoryMovements(product) {
    const dialog=document.createElement('dialog');
    dialog.className='inventory-movement-dialog';
    dialog.setAttribute('aria-labelledby','movementTitle');
    dialog.innerHTML=`<header><div><h2 id="movementTitle">Stock Movements</h2><p>${escapeHtml(product.name)} · ${escapeHtml(product.sku || '')}</p></div><button type="button" data-close data-icon="close">Close</button></header>
      <form class="movement-filters"><label>From<input type="date" name="from_date"></label><label>To<input type="date" name="to_date"></label><label>Type<select name="movement_type"><option value="">All movements</option><option value="in">Stock In</option><option value="out">Stock Out</option><option value="adjustment">Adjustment</option><option value="sale">Sale</option><option value="refund">Refund</option><option value="transfer">Transfer</option></select></label><button type="submit" data-icon="check_circle">Apply filters</button></form>
      <p role="status" data-status></p><div class="movement-results"></div><footer><button type="button" data-prev data-icon="arrow_circle_left">Previous</button><span data-page></span><button type="button" data-next data-icon="arrow_circle_right">Next</button></footer>`;
    document.body.appendChild(dialog);
    const opener=document.activeElement, form=dialog.querySelector('form'), results=dialog.querySelector('.movement-results'), status=dialog.querySelector('[data-status]');
    let offset=0, sequence=0, changed=false, busy=false;
    dialog.querySelector('[data-close]').onclick=()=>{if(!busy) dialog.close();};
    dialog.oncancel=e=>{if(busy)e.preventDefault();};
    dialog.onclose=()=>{sequence++;dialog.remove();opener?.focus();if(changed)loadInventory();};
    const load=async()=>{
      const token=++sequence;
      status.textContent='Loading movements…';results.replaceChildren();
      dialog.querySelector('[data-prev]').disabled=true;dialog.querySelector('[data-next]').disabled=true;
      const query=new URLSearchParams({product_id:product.id,limit:51,offset,from_date:form.elements.from_date.value,to_date:form.elements.to_date.value,movement_type:form.elements.movement_type.value});
      try {
        const data=await api(`/api/stock/movements?${query}`);
        if(token!==sequence || !dialog.open)return;
        const rows=data.movements || [];
        status.textContent=rows.length ? '' : 'No movements match these filters.';
        dialog.querySelector('[data-page]').textContent=`Page ${Math.floor(offset/50)+1}`;
        dialog.querySelector('[data-prev]').disabled=offset===0;dialog.querySelector('[data-next]').disabled=rows.length<=50;
        const names={in:'Stock In',stock_in:'Stock In',out:'Stock Out',stock_out:'Stock Out',adjustment:'Adjustment',sale:'Sale',refund:'Refund',transfer:'Transfer'};
        results.innerHTML=rows.slice(0,50).map(m=>{
          const reversed=String(m.notes||'').includes('[REVERSED]') || String(m.reference||'').endsWith('-REV');
          const canReverse=['in','stock_in','out','stock_out','adjustment'].includes(m.type) && !reversed && !String(m.reference||'').startsWith('REV-');
          return `<article class="movement-card"><div class="movement-card-head"><strong>${escapeHtml(names[m.type] || m.type)} · ${money(m.quantity)}</strong><span>${reversed?'Reversed':`#${Number(m.id)}`}</span></div><p>${escapeHtml(m.created_at)} · ${escapeHtml(m.created_by || '—')}</p><dl><div><dt>Stock before → after</dt><dd>${money(m.old_stock)} → ${money(m.new_stock)}</dd></div><div><dt>Location / variant</dt><dd>${escapeHtml(m.location || '—')} · ${escapeHtml([m.color,m.size].filter(Boolean).join(' / ') || '—')}</dd></div><div><dt>Reference</dt><dd>${escapeHtml(m.reference || '—')}</dd></div><div><dt>Reason / notes</dt><dd>${escapeHtml([m.reason,m.notes].filter(Boolean).join(' · ') || '—')}</dd></div></dl>${canReverse?`<button type="button" class="danger" data-reverse="${Number(m.id)}">Reverse movement</button>`:''}</article>`;
        }).join('');
        results.querySelectorAll('[data-reverse]').forEach(button=>button.onclick=async()=>{
          if(busy)return;
          const reason=window.prompt('Reason for reversing this stock movement:');
          if(!reason?.trim())return;
          if(!window.confirm('Reverse this movement? This will change stock balances.'))return;
          busy=true;dialog.querySelectorAll('button').forEach(b=>b.disabled=true);status.textContent='Reversing movement…';
          try {
            await api(`/api/stock/movements/${Number(button.dataset.reverse)}/reverse`,{method:'POST',body:JSON.stringify({reason:reason.trim()})});
            changed=true;toast('Stock movement reversed.');
          } catch(error){window.alert(error.message);}
          finally {busy=false;dialog.querySelectorAll('button').forEach(b=>b.disabled=false);await load();}
        });
      }catch(error){if(token===sequence){status.textContent=error.message;dialog.querySelector('[data-prev]').disabled=offset===0;}}
    };
    form.onsubmit=e=>{e.preventDefault();if(busy)return;offset=0;load();};
    dialog.querySelector('[data-prev]').onclick=()=>{offset=Math.max(0,offset-50);load();};
    dialog.querySelector('[data-next]').onclick=()=>{offset+=50;load();};
    dialog.showModal();load();
  }

  let inventoryRequest = 0, inventoryDetailRequest = 0, inventoryOffset = 0;
  let inventoryProducts = [], inventoryLocations = [], inventorySuppliers = [];
  function hideInventory() {
    inventoryRequest++; inventoryDetailRequest++;
    document.querySelector('#touchInventory').hidden = true;
    document.querySelector('#inventoryDetail').replaceChildren();
  }
  async function showInventoryPage() {
    window.KayTouchLocations?.hide();
    window.KayTouchSuppliers?.hide();
    window.KayTouchCustomers?.hide();
    window.KayTouchDashboard?.hide();
    window.KayTouchSettings?.hide();
    window.KayTouchExpenses?.hide();
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
      const query = new URLSearchParams({q:document.querySelector('#inventorySearch').value.trim(),category:document.querySelector('#inventoryCategory').value,limit:'50',offset:String(inventoryOffset)});
      const [data, locations, suppliers, categoryData] = await Promise.all([api(`/api/products?${query}`),api('/api/stock/locations'),api('/api/suppliers'),api('/api/categories/manage')]);
      if (request !== inventoryRequest) return;
      const categoryFilter = document.querySelector('#inventoryCategory'), selectedCategory = categoryFilter.value;
      categoryFilter.innerHTML = '<option value="">All categories</option>' + (categoryData.categories || []).map(c=>`<option value="${escapeHtml(c.name)}">${escapeHtml(c.parent_name ? c.parent_name + ' / ' + c.name : c.name)}</option>`).join('');
      categoryFilter.value = selectedCategory;
      inventoryProducts = data.products || []; inventoryLocations = locations.locations || []; inventorySuppliers = suppliers.suppliers || [];
      rows.innerHTML = inventoryProducts.map(p=>`<button type="button" class="receipt-history-row inventory-product-row" data-inventory-id="${Number(p.id)}" aria-pressed="false"><span class="manager-thumb" aria-hidden="true">${p.thumbnail_url ? `<img src="${escapeHtml(p.thumbnail_url)}" alt="" loading="lazy">` : '▦'}</span><span class="inventory-product-name"><strong>${escapeHtml(p.name)}</strong><span class="inventory-kind kind-${soldByMode(p.sold_by)==='service' ? 'service' : soldByMode(p.sold_by)==='variants' ? 'variants' : 'each'}">${soldByMode(p.sold_by)==='service' ? 'Service' : soldByMode(p.sold_by)==='variants' ? 'Variants' : 'Each'}</span><small>${escapeHtml(p.sku || p.barcode || p.category || '')}</small></span><span><strong>${soldByMode(p.sold_by)==='service' ? 'Service' : money(p.stock)+' '+escapeHtml(p.base_unit || p.unit || 'pcs')}</strong><small class="stock-state stock-${soldByMode(p.sold_by)==='service' ? 'service' : Number(p.stock)<=0 ? 'out' : Number(p.stock)<=Number(p.low_stock || 0) ? 'low' : 'ok'}">${soldByMode(p.sold_by)==='service' ? 'No stock tracking' : Number(p.stock)<=0 ? 'Out of stock' : Number(p.stock)<=Number(p.low_stock || 0) ? 'Low stock' : 'In stock'}</small></span></button>`).join('') || '<p>No products found. Try another search.</p>';
      rows.querySelectorAll('.manager-thumb img').forEach(image=>image.addEventListener('error',()=>{image.parentElement.textContent='▦';},{once:true}));
      rows.querySelectorAll('[data-inventory-id]').forEach(button=>button.onclick=()=>openInventoryProduct(Number(button.dataset.inventoryId)));
      document.querySelector('#inventoryPageInfo').textContent = inventoryProducts.length ? `${inventoryOffset+1}–${inventoryOffset+inventoryProducts.length}` : 'No results';
      document.querySelector('#inventoryPrev').disabled = inventoryOffset===0;
      document.querySelector('#inventoryNext').disabled = inventoryProducts.length<50;
    } catch(error) { if(request===inventoryRequest) rows.textContent=error.message; }
  }
  async function openInventoryProduct(id) {
    const p = inventoryProducts.find(p=>Number(p.id)===id); if (!p) return;
    document.querySelectorAll('[data-inventory-id]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.inventoryId)===id)));
    const request = ++inventoryDetailRequest, detail=document.querySelector('#inventoryDetail');
    const variants = p.variants || [], service=soldByMode(p.sold_by)==='service';
    detail.innerHTML = `<div class="receipt-page-head"><div><strong>${escapeHtml(p.name)}</strong><small>Current stock: ${money(p.stock)} ${escapeHtml(p.base_unit || p.unit || 'pcs')} · Cost: ${money(p.cost)} Ks</small></div></div><div class="inventory-locations">${(p.locations || []).map(l=>`<small>${escapeHtml(l.location)}: ${money(l.quantity)}</small>`).join('')}</div>`;
    if (p.variant_batches?.length) detail.innerHTML += `<div class="inventory-locations"><h3>Variant batches</h3>${p.variant_batches.map(b=>`<small>${escapeHtml(variantLabel(variants.find(v=>Number(v.variant_id)===Number(b.variant_id))) || b.variant_id)} · ${escapeHtml(b.location)} · ${escapeHtml(b.batch_no)} · ${money(b.quantity)} · ${b.expiry_unknown ? 'Expiry unknown (legacy / count)' : escapeHtml(b.expire_date || 'No expiry')}</small>`).join('')}</div>`;
    if (!service) {
      detail.innerHTML += `<form id="inventoryStockIn" class="inventory-stock-form"><h3>Stock In</h3><p>Enter quantity and cost per base stock unit (${escapeHtml(p.base_unit || p.unit || 'pcs')}).</p>${variants.length || soldByMode(p.sold_by)==='variants' ? `<label>Variant<select name="variant_id" required><option value="">Select variant</option>${variants.map(v=>`<option value="${Number(v.variant_id)}">${escapeHtml(variantLabel(v) || v.sku || String(v.variant_id))} · Stock ${money(v.stock)}</option>`).join('')}</select></label>` : ''}<label>Location<select name="location" required>${[...new Set(['Shop',...inventoryLocations])].map(l=>`<option>${escapeHtml(l)}</option>`).join('')}</select></label><label>Quantity<input name="quantity" type="number" min="1" max="1000000" step="1" required></label><label>Unit cost (Ks)<input name="cost" type="number" min="0" step="0.01" required></label><label>Supplier<select name="supplier_id"><option value="">None</option>${inventorySuppliers.map(s=>`<option value="${Number(s.id)}">${escapeHtml(s.name)}</option>`).join('')}</select></label><label>Batch number<input name="batch_no" maxlength="100"></label><label class="full">Expiry<select name="expiry_mode" aria-describedby="inventoryExpiryHelp"><option value="none">No expiry</option><option value="date">Enter expiry date</option></select><small id="inventoryExpiryHelp">Choose No expiry or enter the date printed on the product.</small></label><label class="full" data-expiry-date>Expiry date<input name="expire_date" type="date" required></label><label class="full">Notes<input name="notes" maxlength="2000"></label><strong class="full" data-stock-preview>Enter quantity and cost to review.</strong><button class="full receipt-apply" type="submit" data-icon="save">Save Stock In</button><small class="full" role="alert" data-stock-error></small></form>`;
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
    detail.insertAdjacentHTML('afterbegin', '<div class="inventory-detail-actions"><button type="button" id="inventoryViewMovements" data-icon="history">View Movements</button></div>');
    detail.querySelector('#inventoryViewMovements').onclick=()=>showInventoryMovements(p);
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
    window.KayTouchLocations?.hide();
    window.KayTouchSuppliers?.hide();
    window.KayTouchCustomers?.hide();
    window.KayTouchDashboard?.hide();
    window.KayTouchSettings?.hide();
    window.KayTouchExpenses?.hide();
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
      detail.innerHTML = `<div class="receipt-page-head"><div><strong>${escapeHtml(r.invoice_no)}</strong><small>${escapeHtml(r.created_at)} · ${escapeHtml(r.customer_name || 'Walk-in Customer')} · ${escapeHtml(r.status)}</small></div><button type="button" data-close-detail data-icon="close">Close</button></div><div class="receipt-table-wrap"><table><thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Total</th></tr></thead><tbody>${(r.items || []).map(item=>`<tr><td>${escapeHtml(item.product_name)}</td><td>${money(item.qty)}</td><td>${money(item.price)}</td><td>${money(item.total)}</td></tr>`).join('')}</tbody></table></div><div class="receipt-detail-totals">${[['Payment method',escapeHtml(r.payment_type)],['Discount',money(r.discount_amount)+' Ks'],['Total',money(r.total)+' Ks'],['Paid',money(r.paid_amount ?? r.payment)+' Ks'],['Change',money(r.change_amount)+' Ks'],...(String(r.payment_type).toLowerCase()==='credit' ? [['Credit balance',money(r.balance_amount ?? Math.max(0,Number(r.total)-Number(r.payment)))+' Ks']] : [])].map(([label,value])=>`<div><span>${label}</span><strong>${value}</strong></div>`).join('')}</div>`;
      const completed = String(r.status || 'completed').toLowerCase() === 'completed';
      const credit = String(r.payment_type || '').toLowerCase() === 'credit';
      detail.innerHTML += `<div class="receipt-detail-actions">${completed && !credit ? '<button type="button" data-refund-open data-icon="undo">Refund</button>' : ''}<button type="button" data-reprint-receipt data-icon="print">Print Receipt</button></div>`;
      if (completed && !credit) {
        detail.innerHTML += `<div class="receipt-refund"><form data-refund-form hidden><strong>Refund ${money(r.total)} Ks?</strong><p>This refunds the entire receipt and restores its stock.</p><label>Reason<input name="reason" required maxlength="500" placeholder="Customer return"></label><div><button type="submit" data-refund-submit>Confirm refund</button><button type="button" data-refund-cancel data-icon="cancel">Cancel</button></div><small data-refund-error role="alert"></small></form></div>`;
        const form = detail.querySelector('[data-refund-form]');
        const open = detail.querySelector('[data-refund-open]');
        open.onclick = () => { form.hidden = false; open.hidden = true; form.querySelector('input').focus(); };
        detail.querySelector('[data-refund-cancel]').onclick = () => { form.hidden = true; open.hidden = false; open.focus(); };
        form.onsubmit = event => { event.preventDefault(); return refundTouchReceipt(id, form, request); };
      } else if (completed && credit) {
        detail.innerHTML += '<p class="receipt-refund-note">Credit refunds must be processed in the full KAY POS app.</p>';
      }
      detail.querySelector('[data-close-detail]').onclick=resetReceiptDetail;
      detail.querySelector('[data-reprint-receipt]').onclick = () => showReceipt(r, r.paid_amount ?? r.payment ?? 0);
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
  function showTouchLocations() {
    setTouchView('locations');
    window.KayTouchSuppliers?.hide();window.KayTouchCustomers?.hide();window.KayTouchDashboard?.hide();window.KayTouchSettings?.hide();window.KayTouchExpenses?.hide();hideInventory();receiptsRequest++;
    document.querySelector('#touchReceipts').hidden=true;document.querySelector('#productManager').hidden=true;document.querySelector('.workspace').hidden=true;
    document.querySelector('#workspaceStatus').textContent='Locations';window.KayTouchLocations.show({api,escapeHtml,toast,onExit:showSalesView});
  }
  function showTouchSuppliers() {
    setTouchView('suppliers');
    window.KayTouchLocations?.hide();
    window.KayTouchCustomers?.hide();window.KayTouchDashboard?.hide();window.KayTouchSettings?.hide();window.KayTouchExpenses?.hide();hideInventory();receiptsRequest++;
    document.querySelector('#touchReceipts').hidden=true;document.querySelector('#productManager').hidden=true;document.querySelector('.workspace').hidden=true;
    document.querySelector('#workspaceStatus').textContent='Suppliers';
    window.KayTouchSuppliers.show({api,escapeHtml,toast,onExit:showSalesView});
  }
  function showTouchCustomers() {
    setTouchView('customers');
    window.KayTouchLocations?.hide();
    window.KayTouchSuppliers?.hide();
    window.KayTouchDashboard?.hide();window.KayTouchSettings?.hide();window.KayTouchExpenses?.hide();hideInventory();receiptsRequest++;
    document.querySelector('#touchReceipts').hidden=true;document.querySelector('#productManager').hidden=true;document.querySelector('.workspace').hidden=true;
    document.querySelector('#workspaceStatus').textContent='Customers';
    window.KayTouchCustomers.show({api,escapeHtml,toast,onExit:showSalesView});
  }
  function showTouchDashboard() {
    setTouchView('dashboard');
    window.KayTouchLocations?.hide();
    window.KayTouchSuppliers?.hide();
    window.KayTouchCustomers?.hide();
    window.KayTouchSettings?.hide();window.KayTouchExpenses?.hide();hideInventory();receiptsRequest++;
    document.querySelector('#touchReceipts').hidden=true;
    document.querySelector('#productManager').hidden=true;
    document.querySelector('.workspace').hidden=true;
    document.querySelector('#workspaceStatus').textContent='Dashboard';
    window.KayTouchDashboard.show({api,escapeHtml,onExit:showSalesView});
  }
  function showTouchExpenses(addNew = false) {
    setTouchView('expenses');
    window.KayTouchLocations?.hide();
    window.KayTouchSuppliers?.hide();
    window.KayTouchCustomers?.hide();
    window.KayTouchDashboard?.hide();
    window.KayTouchSettings?.hide();hideInventory();receiptsRequest++;
    document.querySelector('#touchReceipts').hidden=true;
    document.querySelector('#productManager').hidden=true;
    document.querySelector('.workspace').hidden=true;
    document.querySelector('#workspaceStatus').textContent='Expenses';
    window.KayTouchExpenses.show({api,escapeHtml,toast,onExit:showSalesView}, addNew);
  }
  function showTouchSettings() {
    setTouchView('settings');
    window.KayTouchLocations?.hide();
    window.KayTouchSuppliers?.hide();
    window.KayTouchCustomers?.hide();
    window.KayTouchDashboard?.hide();
    window.KayTouchExpenses?.hide();
    hideInventory(); receiptsRequest++;
    document.querySelector('#touchReceipts').hidden=true;
    document.querySelector('#productManager').hidden=true;
    document.querySelector('.workspace').hidden=true;
    document.querySelector('#workspaceStatus').textContent='Settings';
    window.KayTouchSettings.show({api, escapeHtml, toast, onExit:showSalesView});
  }
  function showSalesView() {
    setTouchView('sales');
    window.KayTouchLocations?.hide();
    window.KayTouchSuppliers?.hide();
    window.KayTouchCustomers?.hide();
    window.KayTouchDashboard?.hide();
    window.KayTouchSettings?.hide();
    window.KayTouchExpenses?.hide();
    const fromInventory = !document.querySelector('#touchInventory').hidden;
    hideInventory();
    if (fromInventory) loadProducts();
    receiptsRequest += 1;
    document.querySelector('#touchReceipts').hidden = true;
    document.querySelector('.workspace').hidden = false;
    document.querySelector('#productManager').hidden = true;
    document.querySelector('#workspaceStatus').textContent = 'Phase W7 · Receipt print';
  }
  async function showProductManager(page = 'products') {
    setTouchView(page === 'categories' ? 'categories' : 'products');
    window.KayTouchLocations?.hide();
    window.KayTouchSuppliers?.hide();
    window.KayTouchCustomers?.hide();
    window.KayTouchDashboard?.hide();
    const categoriesPage = page === 'categories';
    const manager = document.querySelector('#productManager');
    manager.dataset.page = categoriesPage ? 'categories' : 'products';
    manager.setAttribute('aria-label', categoriesPage ? 'Category management' : 'Product management');
    document.querySelector('#managerPageTitle').textContent = categoriesPage ? 'Categories' : 'Products';
    document.querySelector('#managerPageDescription').textContent = categoriesPage ? 'Manage parent and child categories.' : 'Add products, edit item details and print barcodes.';
    document.querySelector('.manager-products').hidden = categoriesPage;
    document.querySelector('.manager-categories').hidden = !categoriesPage;
    document.querySelector('#managerAddItem').hidden = categoriesPage;
    window.KayTouchSettings?.hide();
    window.KayTouchExpenses?.hide();
    hideInventory();
    receiptsRequest += 1;
    document.querySelector('#touchReceipts').hidden = true;
    document.querySelector('.workspace').hidden = true;
    document.querySelector('#productManager').hidden = false;
    document.querySelector('#workspaceStatus').textContent = categoriesPage ? 'Categories · Manage categories' : 'Products · Manage products';
    await loadProductManager();
  }
  let managerLoadGeneration = 0;
  let managerHasMore = false, managerLoading = false;
  async function loadProductManager(append = false) {
    append = append === true;
    if (append && managerLoading) return;
    managerLoading = true;
    const request = ++managerLoadGeneration;
    if (!token) return;
    const query = new URLSearchParams({q: document.querySelector('#managerProductSearch').value.trim(), category: document.querySelector('#managerCategoryFilter').value, product_type: document.querySelector('#managerTypeFilter').value, limit: '50', offset: String(append ? managedProducts.length : 0)});
    if (!append) document.querySelector('#managerProductList').innerHTML = '<div class="category-loading">Loading products...</div>';
    else {const more=document.querySelector('#managerLoadMore');more.disabled=true;more.setAttribute('aria-busy','true');more.textContent='Loading products…';}
    document.querySelector('#managerCategoryList').innerHTML = '<div class="category-loading">Loading categories...</div>';
    try {
      const [productResult, categoryResult] = await Promise.all([api(`/api/products?${query}`), api('/api/categories/manage')]);
      if (request !== managerLoadGeneration) return;
      const batch = Array.isArray(productResult.products) ? productResult.products : [];
      managerHasMore = batch.length === 50;
      managedProducts = append ? managedProducts.concat(batch) : batch;
      managedCategories = Array.isArray(categoryResult.categories) ? categoryResult.categories : [];
      const filter = document.querySelector('#managerCategoryFilter'), selected = filter.value;
      filter.innerHTML = '<option value="">All categories</option>' + managedCategories.map(c => `<option value="${escapeHtml(c.name)}">${escapeHtml(c.parent_name ? c.parent_name + ' / ' + c.name : c.name)}</option>`).join('');
      filter.value = selected;
      renderManagerProducts(); renderManagedCategories(); populateCategoryOptions();
    } catch (error) {
      if (request !== managerLoadGeneration) return;
      toast(error.message);
      if (!append) document.querySelector('#managerProductList').innerHTML = `<div class="category-loading">${escapeHtml(error.message)}</div>`;
    } finally {if (request === managerLoadGeneration) {managerLoading=false;const more=document.querySelector('#managerLoadMore');if(more){more.disabled=false;more.removeAttribute('aria-busy');if(more.textContent==='Loading products…')more.textContent='Try again';}}}
  }

  function populateCategoryOptions() {
    const options = ['<option value="">No category</option>', ...managedCategories.filter(item => String(item.status || 'active') === 'active').map(item => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.parent_name ? `${item.parent_name} / ${item.name}` : item.name)}</option>`)];
    document.querySelector('#itemCategory').innerHTML = options.join('');
    const parentOptions = ['<option value="">No parent</option>', ...managedCategories.filter(item => !editingCategory || Number(item.id) !== Number(editingCategory.id)).map(item => `<option value="${Number(item.id)}">${escapeHtml(item.parent_name ? `${item.parent_name} / ${item.name}` : item.name)}</option>`)];
    document.querySelector('#categoryParent').innerHTML = parentOptions.join('');
  }
  function renderManagerProducts() {
    const root = document.querySelector('#managerProductList');
    const type = document.querySelector('#managerTypeFilter').value;
    const visible = managedProducts.filter(p => !type || (type === 'wholesale' ? (p.wholesale_tiers || []).length > 0 : (isService(p) ? 'service' : soldByMode(p.sold_by)) === type));
    document.querySelector('#managerProductCount').textContent = `${visible.length} loaded${managerHasMore ? ' · more available' : ''}`;
    if (!visible.length) { root.innerHTML = '<div class="catalog-message"><strong>No products found</strong>Try another search or filter, or add a product.</div>'; return; }
    root.innerHTML = visible.map(product => {
      const barcode = product.barcode || product.sku || '';
      const image = String(product.thumbnail_url || '').trim();
      const kind = isService(product) ? 'service' : soldByMode(product.sold_by) === 'variants' ? 'variants' : 'each';
      const badges = `<span class="product-kind kind-${kind}">${kind === 'service' ? 'Service' : kind === 'variants' ? 'Variants' : 'Each'}</span>${(product.wholesale_tiers || []).length ? '<span class="product-kind kind-wholesale">Wholesale</span>' : ''}`;
      return `<div class="manager-row product-manager-row"><span class="manager-thumb">${image ? `<img src="${escapeHtml(image)}" alt="" loading="lazy">` : '▦'}</span><div class="manager-row-main"><div class="product-name-line"><strong>${escapeHtml(product.name)}</strong><span class="product-kind-list">${badges}</span></div><small>${escapeHtml(product.category || 'No category')}${barcode ? ` · ${escapeHtml(barcode)}` : ''}</small></div><div class="product-manager-price"><strong>${money(product.price)} Ks</strong><small>${kind === 'service' ? 'No stock tracking' : `Stock: ${money(product.stock)}`}</small></div><div class="manager-row-actions"><button type="button" title="Edit" data-manager-edit="${Number(product.id)}" data-icon="edit">Edit</button><button type="button" title="Delete item" class="manager-delete" data-manager-delete="${Number(product.id)}" data-icon="delete">Delete</button></div></div>`;
    }).join('');
    if(managerHasMore){root.insertAdjacentHTML('beforeend',`<div class="catalog-more-area"><span class="catalog-more-count">${managedProducts.length} products loaded</span><button id="managerLoadMore" class="catalog-load-more" type="button" aria-label="Load more products"><span>Load more products</span></button><small>Show up to 50 more</small></div>`);root.querySelector('#managerLoadMore').onclick=()=>loadProductManager(true);}
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
    document.querySelector('#managerCategorySummary').textContent = `${managedCategories.length} categories · ${managedCategories.filter(c => !c.parent_id).length} parents · Search includes parent context`;
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
      rows.push(`<div class="category-tree-row${depth ? ' category-descendant' : ''}" data-category-level="${Math.min(depth, 2)}" style="--category-depth:${depth}"><div class="manager-row"><div class="manager-row-main"><div class="category-name-line"><strong title="${level}: ${escapeHtml(item.name)}">${escapeHtml(item.name)}</strong><span class="category-depth-badge">${level}</span><span class="category-state ${(item.status || 'active') === 'active' ? 'is-active' : 'is-inactive'}">${escapeHtml(item.status || 'active')}</span></div><small>${Number(item.product_count || 0)} products · ${(childrenByParent.get(Number(item.id)) || []).length} child categories${item.parent_name ? ` · Under ${escapeHtml(item.parent_name)}` : ''}</small></div><div class="manager-row-actions"><button type="button" class="category-add-child" data-category-child="${Number(item.id)}">+ Child</button><button type="button" data-category-edit="${Number(item.id)}" data-icon="edit">Edit</button><button type="button" class="manager-delete" data-category-delete="${Number(item.id)}" data-icon="delete">Delete</button></div></div></div>`);
      renderRows(Number(item.id), depth + 1);
    });
    renderRows(0, 0);
    root.innerHTML = rows.join('') || '<div class="catalog-message"><strong>No matching categories</strong>Try another name or clear the search.</div>';
    root.querySelectorAll('[data-category-child]').forEach(button => button.addEventListener('click', () => { openCategoryModal(); document.querySelector('#categoryParent').value = button.dataset.categoryChild; }));
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
  const variantFields = [['color', 'Color'], ['size', 'Size'], ['sku', 'SKU'], ['barcode', 'Barcode'], ['price', 'Price', 0], ['cost', 'Cost', 0], ['stock', 'Stock', 0, 1], ['low_stock', 'Low stock', 0, 1], ['wholesale_min_qty', 'Wholesale minimum qty (0 = off)', 0, 1], ['wholesale_price', 'Wholesale price / unit', 0]];
  const tierFields = [['min_qty', 'Minimum qty', 1, 1], ['unit_label', 'Unit label'], ['unit_multiplier', 'Qty / unit', 1, 1], ['barcode', 'Barcode'], ['unit_price', 'Wholesale price', 0.01], ['note', 'Note']];
  function addItemRow(kind, values = {}) {
    const row = document.createElement('div'); row.className = 'item-detail-row';
    const fields = kind === 'variants' ? variantFields : tierFields;
    row.innerHTML = fields.map(([key, label, min, step]) => `<label ${kind === 'variants' && ['cost', 'stock'].includes(key) ? 'hidden' : ''}><span>${label}</span><input data-field="${key}" ${min === undefined ? 'maxlength="160"' : `type="number" min="${min}" step="${step || 'any'}" required`} value="${escapeHtml(String(values[key] ?? (min === undefined ? '' : min)))}"></label>`).join('') + '<button type="button" class="remove-item-row">Remove</button>';
    row.dataset.kind = kind;
    const heading = document.createElement('strong'); heading.className='item-row-heading';
    heading.textContent=kind==='variants'?'Variant details':'Wholesale tier';row.prepend(heading);
    const summary=document.createElement('small');summary.className='item-row-summary';row.appendChild(summary);
    const updateSummary=()=>{
      const value=key=>row.querySelector(`[data-field="${key}"]`)?.value || '';
      summary.textContent=kind==='variants' ? `${[value('color'),value('size')].filter(Boolean).join(' / ') || 'Variant'} · ${money(value('price'))} Ks per unit` : `Buy ${value('min_qty')} or more stock units → ${money(value('unit_price'))} Ks per stock unit`;
    };
    row.addEventListener('input',updateSummary);updateSummary();
    row.querySelector('button').setAttribute('aria-label',kind==='variants'?'Remove variant':'Remove wholesale tier');
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
    window.KayTouchSettings?.hide();
    window.KayTouchExpenses?.hide();
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
    document.querySelector('#categoryList').innerHTML = '<div class="category-loading">Sign in to load</div>';
    document.querySelector('#productGrid').classList.add('loaded');
    document.querySelector('#productGrid').innerHTML = '<div class="catalog-message">Sign in to view products.</div>';
    document.querySelector('#productManager').hidden = true;
    document.querySelector('.workspace').hidden = false;
  }
  function showLogin(message = '') {
    window.KayTouchLocations?.hide();
    window.KayTouchSuppliers?.hide();
    window.KayTouchCustomers?.hide();
    window.KayTouchDashboard?.hide();
    clearCatalog();
    clearCart();
    clearAvatar();
    setSideMenuOpen(false);
    token = null; clearLoginStorage(); password.value = '';
    loginStatus.textContent = message; loginStatus.className = 'login-status';
    appView.hidden = true; loginView.hidden = false; setTimeout(() => username.focus(), 0);
  }
  function showApp(user) {
    setTouchView('sales');
    const name = user.full_name || user.username;
    document.querySelector('#sideMenuInitials').textContent = initials(user);
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
      button.dataset.categoryTone = categoryTone(label);
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
      return `<button class="product-card" type="button" data-product-id="${Number(product.id)}" ${out ? 'disabled' : ''}><span class="product-image">${image ? `<img src="${escapeHtml(image)}" alt="" loading="lazy">` : '▦'}</span>${badge}<span class="product-info"><span class="product-name">${escapeHtml(product.name)}</span><span class="product-category" data-category-tone="${categoryTone(product.category)}" title="${escapeHtml(product.category || 'No category')}">${escapeHtml(product.category || 'No category')}</span><span class="product-price">${money(product.price)} Ks</span></span>${stockBadge}</button>`;
    }).join('');
    root.querySelectorAll('.product-image img').forEach(image => image.addEventListener('error', () => { image.parentElement.textContent = '▦'; }, {once: true}));
    if(salesHasMore){root.insertAdjacentHTML('beforeend',`<div class="catalog-more-area"><span class="catalog-more-count">${products.length} products loaded</span><button id="salesLoadMore" class="catalog-load-more" type="button" aria-label="Load more products"><span>Load more products</span></button><small>Show up to 50 more</small></div>`);root.querySelector('#salesLoadMore').onclick=()=>loadProducts(true);}
    root.querySelectorAll('[data-product-id]').forEach(button => button.addEventListener('click', () => {
      const product = products.find(item => Number(item.id) === Number(button.dataset.productId));
      if (product) chooseProduct(product);
    }));
  }
  let salesHasMore = false;
  async function loadProducts(append = false) {
    append = append === true;
    if(append && productsController)return;
    if (!token) return; if (productsController) productsController.abort();
    productsController = new AbortController(); const controller = productsController;
    const root = document.querySelector('#productGrid'); root.classList.add('loaded'); if(!append)root.innerHTML = '<div class="catalog-message">Loading products…</div>';else {const more=document.querySelector('#salesLoadMore');more.disabled=true;more.setAttribute('aria-busy','true');more.textContent='Loading products…';}
    const query = new URLSearchParams({q: document.querySelector('#productSearch').value.trim(), category: selectedCategory, limit: '50', offset: String(append ? products.length : 0)});
    try {
      const result = await api(`/api/touch-pos/products?${query}`, {signal: controller.signal}); if (controller !== productsController) return;
      const batch=Array.isArray(result.products)?result.products:[];salesHasMore=batch.length===50;products=append?products.concat(batch):batch;renderProducts();
    } catch (error) {
      if (error.name === 'AbortError' || controller !== productsController) return;
      if(append){toast(error.message);const more=document.querySelector('#salesLoadMore');if(more){more.disabled=false;more.removeAttribute('aria-busy');more.textContent='Try again';}return;}
      products = []; document.querySelector('#productCount').textContent = 'Unavailable';
      root.innerHTML = `<div class="catalog-message"><strong>Could not load products</strong>${escapeHtml(error.message)}<br><button id="retryProducts" type="button">Retry</button></div>`;
      document.querySelector('#retryProducts').addEventListener('click', loadProducts);
    } finally { if (controller === productsController) productsController = null; }
  }
  async function loadCatalog() {
    window.KayTouchSettings?.applyTheme();
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
      const access = await api('/api/touch-pos/session'); saveLoginToken(token, document.querySelector('#rememberMe').checked); password.value=''; showApp(access.user); restoreCart(); await loadCatalog();
    } catch (error) {
      if (token) { try { await api('/api/touch-pos/logout', {method: 'POST'}); } catch (_) {} }
      token = null; clearLoginStorage(); password.value = ''; loginStatus.textContent = error.message; loginStatus.className = 'login-status'; password.focus();
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
      closeSideMenuButton.focus();
    } else if (restoreFocus) {
      sideMenuButton.focus();
    }
    if (!open) sideMenu.hidden = true;
  }
  function runSideMenuAction(action) {
    setSideMenuOpen(false, true);
    if (action === 'locations') {showTouchLocations();return;}
    if (action === 'suppliers') {showTouchSuppliers();return;}
    if (action === 'customers') {showTouchCustomers();return;}
    if (action === 'dashboard') {showTouchDashboard();return;}
    if (action === 'expenses') {showTouchExpenses();return;}
    if (action === 'settings') { showTouchSettings(); return; }
    if (action === 'inventory') { showInventoryPage(); return; }
    if (action === 'receipts') { showReceiptsPage(); return; }
    if (['products', 'cart'].includes(action)) showSalesView();
    if (action === 'products') document.querySelector('#productSearch').focus();
    else if (action === 'product-page') showProductManager();
    else if (action === 'category-page') showProductManager('categories');
    else if (action === 'cart') setCartOpen(true);
    else if (action === 'fullscreen' && fullscreen) fullscreen.click();
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
  document.querySelector('#sideSignOut').addEventListener('click', async () => { try { await api('/api/touch-pos/logout', {method: 'POST'}); } catch (_) {} clearCatalog(); showLogin('Signed out.'); });
  document.querySelector('#clearCart').addEventListener('click', () => { clearCart(); toast('Cart cleared.'); });
  document.querySelector('#paymentButton').addEventListener('click', openCheckoutDetails);
  document.querySelector('#closeCheckout').addEventListener('click', closeCheckout);
  document.querySelector('#cancelCheckout').addEventListener('click', closeCheckout);
  document.querySelector('#saveCheckout').addEventListener('click', submitCheckoutSale);
  document.querySelector('#checkoutCustomer').addEventListener('change', renderCheckoutSummary);
  document.querySelector('#checkoutSaleMode').addEventListener('change', renderCheckoutSummary);
  document.querySelector('#checkoutDiscount').addEventListener('input', renderCheckoutSummary);
  document.querySelector('#checkoutReceived').addEventListener('input', renderCheckoutSummary);
  ['checkoutDiscount', 'checkoutReceived'].forEach(id => {
    const input = document.querySelector(`#${id}`);
    input.type = 'text';
    input.inputMode = 'none';
    input.autocomplete = 'off';
    input.addEventListener('focus', () => activateCheckoutKeypad(input));
    input.addEventListener('input', () => {
      input.value = input.value.replace(/[^0-9.]/g, '').replace(/(\..*)\./g, '$1');
      checkoutKeypadReplace = false;
      renderCheckoutSummary();
    });
  });
  document.querySelectorAll('[data-checkout-key]').forEach(button => {
    button.addEventListener('pointerdown', event => event.preventDefault());
    button.addEventListener('click', () => pressCheckoutKey(button.dataset.checkoutKey));
  });
  document.querySelector('#checkoutModal').addEventListener('click', event => { if (event.target.id === 'checkoutModal') closeCheckout(); });
  document.querySelector('#closeChoice').addEventListener('click', closeChoice);
  document.querySelector('#cancelChoice').addEventListener('click', closeChoice);
  document.querySelector('#confirmChoice').addEventListener('click', confirmChoice);
  document.querySelector('#productChoiceModal').addEventListener('click', event => { if (event.target.id === 'productChoiceModal') closeChoice(); });
  document.querySelector('#productChoiceModal').addEventListener('keydown', event => { if (event.key === 'Enter') confirmChoice(); });
  document.addEventListener('keydown', handleServiceKeydown);
  document.querySelector('#closeReceipt').addEventListener('click', () => { document.querySelector('#receiptModal').hidden = true; });
  document.querySelector('#receiptPaper').addEventListener('change', updateReceiptPreview);
  document.querySelector('#printReceiptButton').addEventListener('click', async () => {
    if (!activePrintReceipt) return;
    const button = document.querySelector('#printReceiptButton'); button.disabled = true;
    try { await window.KayTouchReceipt.print(activePrintReceipt.receipt, activePrintReceipt.paid, document.querySelector('#receiptPaper').value); }
    catch (error) { toast(`Could not open print dialog: ${error.message}`); }
    finally { button.disabled = false; }
  });
  document.querySelector('#newSale').addEventListener('click', () => { document.querySelector('#receiptModal').hidden = true; });
  document.querySelector('#receiptModal').addEventListener('keydown', event => { if(event.key === 'Escape') document.querySelector('#receiptModal').hidden = true; });
  document.querySelector('#productSearch').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadProducts, 250); });
  const scanner = window.KayTouchScanner.collector();
  let scanQueue = Promise.resolve();
  function scannerReady() {
    return Boolean(token) && !appView.hidden && !document.querySelector('.workspace').hidden &&
      !document.querySelector('.modal-backdrop:not([hidden]), dialog[open]') && !sideMenu.classList.contains('open');
  }
  function handleCheckoutEnter(event) {
    if (event.key !== 'Enter' || event.defaultPrevented || event.isComposing || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey || !token || appView.hidden) return;
    if (document.querySelector('dialog[open]')) return;
    const checkout = document.querySelector('#checkoutModal');
    const receipt = document.querySelector('#receiptModal');
    const modal = !checkout.hidden ? checkout : !receipt.hidden ? receipt : null;
    if (!modal || [...document.querySelectorAll('.modal-backdrop:not([hidden])')].some(item => item !== modal)) return;
    const button = document.querySelector(modal === checkout ? '#saveCheckout' : '#printReceiptButton');
    const control = event.target?.closest('button,input,select,textarea,a,[contenteditable]:not([contenteditable="false"])');
    // Preserve Enter for other controls (Cancel, paper selection, etc.).
    if (control && modal.contains(control) && control !== button && !(modal === checkout && control.id === 'checkoutReceived')) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!event.repeat && !button.disabled) button.click();
  }
  document.addEventListener('keydown', handleCheckoutEnter, true);
  let checkoutShortcutPending = false;
  async function handleSaleShortcut(event) {
    if (event.defaultPrevented || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey || event.isComposing) return;
    if (!['F2', 'F4'].includes(event.key) || !scannerReady()) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    scanner.reset();
    if (event.repeat) return;
    if (event.key === 'F2') {
      const search = document.querySelector('#productSearch');
      search.focus();
      search.select();
      return;
    }
    if (checkoutShortcutPending || document.querySelector('#paymentButton').disabled) return;
    checkoutShortcutPending = true;
    try { await openCheckoutDetails(); }
    finally { checkoutShortcutPending = false; }
  }
  document.addEventListener('keydown', handleSaleShortcut, true);
  async function scanToCart(code, fromSearch) {
    if (!scannerReady()) return;
    const session = token;
    try {
      const result = await api(`/api/products/scan/${encodeURIComponent(window.KayTouchScanner.normalize(code).trim())}`);
      if (!scannerReady() || token !== session) return;
      if (!result.product) {if(fromSearch)loadProducts();else toast('Barcode not found: ' + code);return;}
      const product = result.product;
      if(fromSearch){document.querySelector('#productSearch').value='';loadProducts();}
      if(product.matched_variant_id){
        const variant=(product.variants || []).find(v=>Number(v.variant_id)===Number(product.matched_variant_id));
        if(!variant)return toast('Barcode variant is unavailable.');
        addToCart(product,variant);
      } else chooseProduct(product);
    } catch(error){toast(error.message);}
  }
  document.addEventListener('keydown', event => {
    const target=event.target, search=target?.id==='productSearch';
    if(!scannerReady() || event.ctrlKey || event.altKey || event.metaKey || event.isComposing ||
       (!search && target?.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"])'))){scanner.reset();return;}
    const scanned=scanner.key(event.key,performance.now());
    const code=event.key==='Enter' && search ? window.KayTouchScanner.normalize(target.value).trim() : scanned;
    if(!code)return;
    event.preventDefault();event.stopImmediatePropagation();clearTimeout(searchTimer);
    scanQueue=scanQueue.then(()=>scanToCart(code,search));
  },true);
  document.querySelector('#categorySearch').addEventListener('input', filterCategories);
  document.querySelector('#refreshProducts').addEventListener('click', loadCatalog);
  document.querySelector('#backToSales').addEventListener('click', showSalesView);
  document.querySelector('#managerRefresh').addEventListener('click', loadProductManager);
  document.querySelector('#managerAddItem').addEventListener('click', () => openItemModal());
  document.querySelector('#managerCategoryReset').addEventListener('click', () => { document.querySelector('#managerCategorySearch').value = ''; renderManagedCategories(); document.querySelector('#managerCategorySearch').focus(); });
  document.querySelector('#managerAddCategory').addEventListener('click', () => openCategoryModal());
  document.querySelector('#managerCategoryFilter').addEventListener('change', loadProductManager);
  document.querySelector('#managerTypeFilter').addEventListener('change', loadProductManager);
  document.querySelector('#managerResetFilters').addEventListener('click', () => { clearTimeout(managerSearchTimer); for (const id of ['managerProductSearch','managerCategoryFilter','managerTypeFilter']) document.getElementById(id).value = ''; loadProductManager(); });
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
  document.querySelector('#headerAddExpense').onclick=()=>showTouchExpenses(true);
  document.querySelector('#inventoryReset').onclick=()=>{document.querySelector('#inventorySearch').value='';document.querySelector('#inventoryCategory').value='';inventoryOffset=0;loadInventory();};
  document.querySelector('#inventorySales').onclick=showSalesView;
  document.querySelector('#inventoryCategory').onchange=()=>{inventoryOffset=0;loadInventory();};
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
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch('/health', {cache: 'no-store', signal: controller.signal});
      const value = await response.json();
      setConnection(response.ok && value.ok === true);
    }
    catch (_) { setConnection(false); }
    finally { clearTimeout(timeout); }
  }
  function updateClock() { clock.textContent = new Intl.DateTimeFormat(undefined, {dateStyle: 'medium', timeStyle: 'short'}).format(new Date()); }
  if (fullscreen) {
    fullscreen.addEventListener('click', async () => { try { if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen(); } catch (_) {} });
    document.addEventListener('fullscreenchange', () => {
      const label = document.fullscreenElement ? 'Exit Full Screen' : 'Full Screen';
      fullscreen.textContent = label;
      fullscreen.setAttribute('aria-label', label);
    });
  }
  window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); installPrompt = event; install.hidden = false; });
  install.addEventListener('click', async () => { if (!installPrompt) return; installPrompt.prompt(); await installPrompt.userChoice; installPrompt = null; install.hidden = true; });
  if ('serviceWorker' in navigator && window.isSecureContext) navigator.serviceWorker.register('/touch-pos/service-worker.js', {scope: '/touch-pos/'}).catch(() => {});
  restoreCart(); updateClock(); checkServer(); validateSession(); setInterval(updateClock, 30000); setInterval(checkServer, 30000);
})();
