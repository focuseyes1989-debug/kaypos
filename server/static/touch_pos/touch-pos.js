(() => {
  'use strict';
  const connection = document.querySelector('#connection'), clock = document.querySelector('#clock');
  const fullscreen = document.querySelector('#fullscreen'), install = document.querySelector('#install');
  const loginView = document.querySelector('#loginView'), appView = document.querySelector('#app');
  const loginForm = document.querySelector('#loginForm'), loginStatus = document.querySelector('#loginStatus');
  const signIn = document.querySelector('#signIn'), password = document.querySelector('#password');
  const username = document.querySelector('#username'), userButton = document.querySelector('#userButton');
  const userMenu = document.querySelector('#userMenu'), TOKEN_KEY = 'kay_touch_pos_token';
  const CART_KEY = 'kay_touch_pos_cart';
  let token = sessionStorage.getItem(TOKEN_KEY), installPrompt = null, products = [], customers = [], categories = [], selectedCategory = '';
  let cart = new Map();
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
  function renderCart() {
    const {items, count, subtotal, total} = cartTotals();
    const root = document.querySelector('#cartItems');
    document.querySelector('#cartCount').textContent = String(count);
    document.querySelector('#mobileCartCount').textContent = String(count);
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
  function clearCatalog() {
    clearTimeout(searchTimer); searchTimer = null;
    if (productsController) { productsController.abort(); productsController = null; }
    products = []; categories = []; selectedCategory = ''; document.querySelector('#productSearch').value = ''; document.querySelector('#categorySearch').value = '';
    document.querySelector('#productSearch').disabled = true; document.querySelector('#categorySearch').disabled = true; document.querySelector('#refreshProducts').disabled = true;
    document.querySelector('#categoryCount').textContent = '0'; document.querySelector('#productCount').textContent = '0 items';
    document.querySelector('#categoryList').innerHTML = '<div class="category-loading">Sign in to load</div>';
    document.querySelector('#productGrid').classList.add('loaded');
    document.querySelector('#productGrid').innerHTML = '<div class="catalog-message">Sign in to view products.</div>';
  }
  function showLogin(message = '') {
    clearCatalog();
    clearCart();
    token = null; sessionStorage.removeItem(TOKEN_KEY); password.value = '';
    loginStatus.textContent = message; loginStatus.className = 'login-status';
    userMenu.hidden = true; appView.hidden = true; loginView.hidden = false; setTimeout(() => username.focus(), 0);
  }
  function showApp(user) {
    const name = user.full_name || user.username;
    document.querySelector('#userInitials').textContent = initials(user); document.querySelector('#userName').textContent = name;
    document.querySelector('#userRole').textContent = user.role || 'Staff'; document.querySelector('#menuUserName').textContent = name;
    document.querySelector('#menuUserRole').textContent = `${user.role || 'Staff'} · Sales access`;
    loginView.hidden = true; appView.hidden = false; password.value = ''; loginStatus.textContent = '';
  }
  function renderCategories() {
    const root = document.querySelector('#categoryList'); root.replaceChildren();
    const query = document.querySelector('#categorySearch').value.trim().toLowerCase();
    const visibleCategories = query ? categories.filter(name => String(name || '').toLowerCase().includes(query)) : categories;
    if (query && selectedCategory && !visibleCategories.includes(selectedCategory)) selectedCategory = '';
    for (const name of ['', ...visibleCategories]) {
      const button = document.createElement('button'); button.type = 'button'; button.className = `category${name === selectedCategory ? ' active' : ''}`;
      button.textContent = name || 'All products'; button.setAttribute('aria-pressed', String(name === selectedCategory));
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
    root.innerHTML = products.map(product => {
      const service = isService(product), variants = soldByMode(product.sold_by) === 'variants';
      const variantRows = Array.isArray(product.variants) ? product.variants : [];
      const variantOut = variants && (!variantRows.length || variantRows.every(item => Number(item.stock || 0) <= 0));
      const out = Boolean(product.is_out_of_stock) || (!service && (variants ? variantOut : Number(product.stock || 0) <= 0));
      const low = Boolean(product.is_low_stock), image = String(product.thumbnail_url || '').trim();
      const badge = out ? '<span class="product-badge out">Out of stock</span>' : (low ? '<span class="product-badge">Low stock</span>' : (service ? '<span class="product-badge">Service</span>' : (variants ? '<span class="product-badge">Variants</span>' : '')));
      const stockBadge = service ? '' : `<span class="product-stock">${money(variants ? variantRows.reduce((sum, item) => sum + Number(item.stock || 0), 0) : product.stock)}</span>`;
      return `<button class="product-card" type="button" data-product-id="${Number(product.id)}" ${out ? 'disabled' : ''}><span class="product-image">${image ? `<img src="${escapeHtml(image)}" alt="" loading="lazy">` : '▦'}</span>${badge}<span class="product-info"><span class="product-name">${escapeHtml(product.name)}</span><span class="product-meta">${escapeHtml(product.category || product.sku || 'Uncategorized')}</span><span class="product-price">${money(product.price)} Ks</span></span>${stockBadge}</button>`;
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
      products = []; document.querySelector('#productCount').textContent = 'Unavailable';
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
  openCart.addEventListener('click', () => setCartOpen(true));
  closeCart.addEventListener('click', () => setCartOpen(false, true));
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && saleCart.classList.contains('open')) setCartOpen(false, true); });
  compactCart.addEventListener('change', syncCartMode);
  syncCartMode();
  userButton.addEventListener('click', () => { userMenu.hidden = !userMenu.hidden; userButton.setAttribute('aria-expanded', String(!userMenu.hidden)); });
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
