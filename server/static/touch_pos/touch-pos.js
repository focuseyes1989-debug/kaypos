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
  function showSalesView() {
    document.querySelector('.workspace').hidden = false;
    document.querySelector('#productManager').hidden = true;
    document.querySelector('#workspaceStatus').textContent = 'Phase W7 · Receipt print';
  }
  async function showProductManager() {
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
      return `<div class="manager-row"><div class="manager-row-main"><strong>${escapeHtml(product.name)}</strong><small>${escapeHtml(product.category || 'No category')} · ${money(product.price)} Ks · Stock ${money(product.stock)}${barcode ? ` · ${escapeHtml(barcode)}` : ''}</small></div><div class="manager-row-actions"><button type="button" title="Edit" data-manager-edit="${Number(product.id)}">Edit</button><button type="button" title="Print barcode" data-manager-barcode="${Number(product.id)}">Print</button></div></div>`;
    }).join('');
    root.querySelectorAll('[data-manager-edit]').forEach(button => button.addEventListener('click', () => openItemModal(managedProducts.find(item => Number(item.id) === Number(button.dataset.managerEdit)))));
    root.querySelectorAll('[data-manager-barcode]').forEach(button => button.addEventListener('click', () => openBarcodeModal(managedProducts.find(item => Number(item.id) === Number(button.dataset.managerBarcode)))));
  }
  function renderManagedCategories() {
    const root = document.querySelector('#managerCategoryList');
    if (!managedCategories.length) { root.innerHTML = '<div class="catalog-message"><strong>No categories</strong>Add parent and child categories here.</div>'; return; }
    const childrenByParent = new Map();
    managedCategories.forEach(item => childrenByParent.set(Number(item.parent_id || 0), [...(childrenByParent.get(Number(item.parent_id || 0)) || []), item]));
    const rows = [];
    const renderRows = (parentId, child) => (childrenByParent.get(parentId) || []).forEach(item => {
      rows.push(`<div class="${child ? 'category-child' : ''}"><div class="manager-row"><div class="manager-row-main"><strong>${child ? '- ' : ''}${escapeHtml(item.name)}</strong><small>${escapeHtml(item.status || 'active')} · ${Number(item.product_count || 0)} products</small></div><div class="manager-row-actions"><button type="button" data-category-edit="${Number(item.id)}">Edit</button></div></div></div>`);
      renderRows(Number(item.id), true);
    });
    renderRows(0, false);
    root.innerHTML = rows.join('');
    root.querySelectorAll('[data-category-edit]').forEach(button => button.addEventListener('click', () => openCategoryModal(managedCategories.find(item => Number(item.id) === Number(button.dataset.categoryEdit)))));
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
    setTimeout(() => document.querySelector('#itemName').focus(), 0);
  }
  function closeItemModal() { document.querySelector('#itemModal').hidden = true; editingProduct = null; }
  function itemPayload() {
    const soldBy = document.querySelector('#itemSoldBy').value;
    const variants = soldByMode(soldBy) === 'variants' && Array.isArray(editingProduct?.variants) ? editingProduct.variants.map(variant => ({
      color: variant.color || '', size: variant.size || '', sku: variant.sku || '', barcode: variant.barcode || '',
      price: Number(variant.price || 0), cost: Number(variant.cost || 0), stock: Number(variant.stock || 0),
      low_stock: Number(variant.low_stock || 0), active: true,
    })) : [];
    return {
      name: document.querySelector('#itemName').value.trim(), category: document.querySelector('#itemCategory').value,
      description: document.querySelector('#itemDescription').value.trim(), sold_by: soldBy,
      price: Number(document.querySelector('#itemPrice').value || 0), cost: Number(document.querySelector('#itemCost').value || 0),
      sku: document.querySelector('#itemSku').value.trim(), barcode: document.querySelector('#itemBarcode').value.trim(),
      stock: Number(document.querySelector('#itemStock').value || 0), low_stock: Number(document.querySelector('#itemLowStock').value || 0),
      unit: document.querySelector('#itemUnit').value.trim() || 'pcs', base_unit: document.querySelector('#itemUnit').value.trim() || 'pcs',
      pack_unit: '', pack_size: 1, variants,
    };
  }
  async function saveItemForm(event) {
    event.preventDefault();
    const payload = itemPayload(); if (!payload.name) return toast('Product name is required.');
    const button = document.querySelector('#saveItem'); button.disabled = true; button.textContent = 'Saving...';
    try {
      const path = editingProduct ? `/api/products/manage/${Number(editingProduct.id)}` : '/api/products/manage';
      await api(path, {method: editingProduct ? 'PUT' : 'POST', body: JSON.stringify(payload)});
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
  document.querySelector('#itemForm').addEventListener('submit', saveItemForm);
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
