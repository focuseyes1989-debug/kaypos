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
  const HELD_CART_KEY = 'kay_touch_pos_held_cart';
  let token = sessionStorage.getItem(TOKEN_KEY), installPrompt = null, products = [], selectedCategory = '';
  let cart = new Map();
  let searchTimer = null, productsController = null, toastTimer = null;

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
  function saleProduct(product) {
    if (soldByMode(product.sold_by) !== 'variants') return {product, variant: null};
    const variants = Array.isArray(product.variants) ? product.variants : [];
    const variant = variants.find(item => Number(item.stock || 0) > 0) || variants[0] || null;
    return {product, variant};
  }
  function saveCart() {
    sessionStorage.setItem(CART_KEY, JSON.stringify([...cart.values()]));
  }
  function savedHeldCart() {
    try { return JSON.parse(sessionStorage.getItem(HELD_CART_KEY) || '{}'); }
    catch (_) { sessionStorage.removeItem(HELD_CART_KEY); return {}; }
  }
  function clearHeldCart() {
    sessionStorage.removeItem(HELD_CART_KEY);
  }
  function cartTotals() {
    const items = [...cart.values()], count = items.reduce((sum, item) => sum + Number(item.qty || 0), 0);
    const subtotal = items.reduce((sum, item) => sum + Number(item.price || 0) * Number(item.qty || 0), 0);
    return {items, count, subtotal, discount: 0, total: subtotal};
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
    document.querySelector('#paymentAmount').value = '';
    renderCart();
  }
  function holdCart() {
    const {items, count, total} = cartTotals();
    if (!count) return toast('Cart is empty.');
    sessionStorage.setItem(HELD_CART_KEY, JSON.stringify({items, total, held_at: new Date().toISOString()}));
    clearCart(); toast('Sale held on this tablet.');
  }
  function restoreHeldCart() {
    const held = savedHeldCart();
    if (!Array.isArray(held.items) || !held.items.length) return toast('No held sale found.');
    if (cartTotals().count) return toast('Clear the current cart before restoring.');
    cart = new Map(held.items.map(item => [item.key, item]));
    sessionStorage.removeItem(HELD_CART_KEY); saveCart(); renderCart(); toast('Held sale restored.');
  }
  function renderCart() {
    const {items, count, subtotal, discount, total} = cartTotals();
    const root = document.querySelector('#cartItems');
    document.querySelector('#cartCount').textContent = String(count);
    document.querySelector('#mobileCartCount').textContent = String(count);
    document.querySelector('#cartItemCount').textContent = String(count);
    document.querySelector('#cartSubtotal').textContent = `${money(subtotal)} Ks`;
    document.querySelector('#cartDiscount').textContent = `${money(discount)} Ks`;
    document.querySelector('#cartTotal').textContent = `${money(total)} Ks`;
    document.querySelector('#clearCart').disabled = count === 0;
    document.querySelector('#holdCart').disabled = count === 0;
    document.querySelector('#restoreHeldCart').disabled = !(savedHeldCart().items || []).length;
    document.querySelector('#paymentButton').disabled = count === 0;
    document.querySelector('#paymentAmount').disabled = count === 0;
    document.querySelectorAll('[data-cash]').forEach(button => { button.disabled = count === 0; });
    document.querySelector('#cartHint').textContent = count ? `${items.length} line${items.length === 1 ? '' : 's'} in cart` : 'Tap products to add';
    updatePayment();
    if (!items.length) {
      root.innerHTML = '<div class="cart-empty"><span>🛒</span><strong>Cart is empty</strong><small>Tap a product to add it to this sale.</small></div>';
      return;
    }
    root.innerHTML = items.map(item => `<div class="cart-row" data-cart-key="${escapeHtml(item.key)}"><div class="cart-row-main"><span class="cart-row-title">${escapeHtml(item.name)}</span><span class="cart-row-meta">${escapeHtml(item.variant_label || item.sku || 'Standard')} · ${money(item.price)} Ks each</span></div><div class="cart-row-total">${money(Number(item.price || 0) * Number(item.qty || 0))} Ks</div><div class="qty-controls"><button type="button" data-cart-action="minus">−</button><output>${Number(item.qty || 0)}</output><button type="button" data-cart-action="plus">+</button><button class="remove" type="button" data-cart-action="remove">×</button></div></div>`).join('');
    root.querySelectorAll('[data-cart-action]').forEach(button => button.addEventListener('click', () => changeCart(button.closest('[data-cart-key]').dataset.cartKey, button.dataset.cartAction)));
  }
  function addToCart(sourceProduct) {
    if (!sourceProduct) return;
    const {product, variant} = saleProduct(sourceProduct), service = isService(product), stock = stockFor(product, variant);
    if (!service && stock <= 0) return toast(`${product.name} is out of stock.`);
    const key = service ? `${cartKey(product, variant)}:service:${Number((variant || product).price || 0).toFixed(2)}` : cartKey(product, variant);
    const item = cart.get(key) || {
      key, product_id: Number(product.id), variant_id: Number(variant?.variant_id || 0) || null,
      name: product.name, sku: variant?.sku || product.sku || product.barcode || '', variant_label: variantLabel(variant),
      price: Number((variant || product).price || 0), stock, qty: 0, is_service: service,
    };
    if (!service && item.qty + 1 > stock) return toast(`Only ${stock} left: ${item.name}`);
    item.qty += 1; cart.set(key, item); saveCart(); renderCart(); toast(`${item.name} added to cart.`);
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
  function updatePayment() {
    const total = cartTotals().total, payment = Number(document.querySelector('#paymentAmount').value || 0);
    document.querySelector('#changeDue').textContent = `${money(Math.max(0, payment - total))} Ks`;
    document.querySelector('#paymentButton').disabled = total <= 0 || payment < total;
  }
  function setQuickCash(action) {
    const input = document.querySelector('#paymentAmount'), total = cartTotals().total;
    if (action === 'exact') input.value = total ? String(Math.ceil(total)) : '';
    else input.value = String(Number(input.value || 0) + Number(action || 0));
    updatePayment(); input.focus(); input.select();
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
    const {items, total} = cartTotals(), payment = Number(document.querySelector('#paymentAmount').value || 0);
    if (!items.length) return toast('Cart is empty.');
    if (payment < total) return toast('Insufficient payment.');
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
      clearCart(); document.querySelector('#paymentAmount').value = ''; renderCart(); await loadProducts(); showReceipt(receipt, payment);
      toast(`Saved ${receipt.invoice_no || 'sale'}.`);
    } catch (error) {
      toast(error.message);
    } finally {
      button.textContent = 'Complete Cash Sale'; updatePayment();
    }
  }
  function clearCatalog() {
    clearTimeout(searchTimer); searchTimer = null;
    if (productsController) { productsController.abort(); productsController = null; }
    products = []; selectedCategory = ''; document.querySelector('#productSearch').value = '';
    document.querySelector('#productSearch').disabled = true; document.querySelector('#refreshProducts').disabled = true;
    document.querySelector('#categoryCount').textContent = '0'; document.querySelector('#productCount').textContent = '0 items';
    document.querySelector('#categoryList').innerHTML = '<div class="category-loading">Sign in to load</div>';
    document.querySelector('#productGrid').classList.add('loaded');
    document.querySelector('#productGrid').innerHTML = '<div class="catalog-message">Sign in to view products.</div>';
  }
  function showLogin(message = '') {
    clearCatalog();
    clearCart();
    clearHeldCart();
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
  function renderCategories(categories) {
    const root = document.querySelector('#categoryList'); root.replaceChildren();
    for (const name of ['', ...categories]) {
      const button = document.createElement('button'); button.type = 'button'; button.className = `category${name === selectedCategory ? ' active' : ''}`;
      button.textContent = name || 'All products'; button.setAttribute('aria-pressed', String(name === selectedCategory));
      button.addEventListener('click', () => { selectedCategory = name; renderCategories(categories); loadProducts(); }); root.appendChild(button);
    }
    document.querySelector('#categoryCount').textContent = String(categories.length);
  }
  function renderProducts() {
    const root = document.querySelector('#productGrid'); root.classList.add('loaded');
    document.querySelector('#productCount').textContent = `${products.length} item${products.length === 1 ? '' : 's'}`;
    if (!products.length) { root.innerHTML = '<div class="catalog-message"><strong>No products found</strong>Try another category or search.</div>'; return; }
    root.innerHTML = products.map(product => {
      const service = Boolean(product.is_service), out = Boolean(product.is_out_of_stock) || (!service && Number(product.stock || 0) <= 0);
      const low = Boolean(product.is_low_stock), image = String(product.thumbnail_url || '').trim();
      const badge = out ? '<span class="product-badge out">Out of stock</span>' : (low ? '<span class="product-badge">Low stock</span>' : (service ? '<span class="product-badge">Service</span>' : ''));
      return `<button class="product-card" type="button" data-product-id="${Number(product.id)}" ${out ? 'disabled' : ''}><span class="product-image">${image ? `<img src="${escapeHtml(image)}" alt="" loading="lazy">` : '▦'}</span>${badge}<span class="product-info"><span class="product-name">${escapeHtml(product.name)}</span><span class="product-meta">${escapeHtml(product.category || product.sku || 'Uncategorized')}</span><span class="product-price">${money(product.price)} Ks</span></span></button>`;
    }).join('');
    root.querySelectorAll('.product-image img').forEach(image => image.addEventListener('error', () => { image.parentElement.textContent = '▦'; }, {once: true}));
    root.querySelectorAll('[data-product-id]').forEach(button => button.addEventListener('click', () => {
      const product = products.find(item => Number(item.id) === Number(button.dataset.productId));
      if (product) addToCart(product);
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
      const result = await api('/api/touch-pos/categories'), categories = Array.isArray(result.categories) ? result.categories : [];
      renderCategories(categories); await loadProducts(); document.querySelector('#workspaceStatus').textContent = 'Phase W7 · Receipt print';
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
  const saleCart = document.querySelector('#saleCart'), openCart = document.querySelector('#openCart');
  const mobileCartMedia = window.matchMedia('(max-width: 760px)');
  function setCartOpen(open, restoreFocus = false) {
    saleCart.classList.toggle('open', open);
    saleCart.inert = mobileCartMedia.matches && !open;
    openCart.setAttribute('aria-expanded', String(open));
    if (open) document.querySelector('#closeCart').focus();
    else if (restoreFocus) openCart.focus();
  }
  openCart.addEventListener('click', () => setCartOpen(true));
  document.querySelector('#closeCart').addEventListener('click', () => setCartOpen(false, true));
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && mobileCartMedia.matches && saleCart.classList.contains('open')) setCartOpen(false, true); });
  mobileCartMedia.addEventListener('change', () => setCartOpen(false));
  setCartOpen(false);
  userButton.addEventListener('click', () => { userMenu.hidden = !userMenu.hidden; userButton.setAttribute('aria-expanded', String(!userMenu.hidden)); });
  document.querySelector('#signOut').addEventListener('click', async () => { try { await api('/api/touch-pos/logout', {method: 'POST'}); } catch (_) {} clearCatalog(); showLogin('Signed out.'); });
  document.querySelector('#clearCart').addEventListener('click', () => { clearCart(); toast('Cart cleared.'); });
  document.querySelector('#holdCart').addEventListener('click', holdCart);
  document.querySelector('#restoreHeldCart').addEventListener('click', restoreHeldCart);
  document.querySelector('#paymentAmount').addEventListener('input', updatePayment);
  document.querySelectorAll('[data-cash]').forEach(button => button.addEventListener('click', () => setQuickCash(button.dataset.cash)));
  document.querySelector('#paymentButton').addEventListener('click', checkoutCashSale);
  document.querySelector('#closeReceipt').addEventListener('click', () => { document.querySelector('#receiptModal').hidden = true; });
  document.querySelector('#printReceiptButton').addEventListener('click', () => window.print());
  document.querySelector('#newSale').addEventListener('click', () => { document.querySelector('#receiptModal').hidden = true; document.querySelector('#productSearch').focus(); });
  document.querySelector('#productSearch').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadProducts, 250); });
  document.querySelector('#productSearch').addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); clearTimeout(searchTimer); loadProducts(); } });
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
