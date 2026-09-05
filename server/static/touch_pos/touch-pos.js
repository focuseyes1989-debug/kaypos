(() => {
  'use strict';
  const connection = document.querySelector('#connection'), clock = document.querySelector('#clock');
  const fullscreen = document.querySelector('#fullscreen'), install = document.querySelector('#install');
  const loginView = document.querySelector('#loginView'), appView = document.querySelector('#app');
  const loginForm = document.querySelector('#loginForm'), loginStatus = document.querySelector('#loginStatus');
  const signIn = document.querySelector('#signIn'), password = document.querySelector('#password');
  const username = document.querySelector('#username'), userButton = document.querySelector('#userButton');
  const userMenu = document.querySelector('#userMenu'), TOKEN_KEY = 'kay_touch_pos_token';
  let token = sessionStorage.getItem(TOKEN_KEY), installPrompt = null, products = [], selectedCategory = '';
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
  function toast(message) {
    const item = document.querySelector('#workspaceToast'); item.textContent = message; item.classList.add('show'); clearTimeout(toastTimer);
    toastTimer = setTimeout(() => item.classList.remove('show'), 2200);
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
      if (product) toast(`${product.name} selected · Cart starts in W4`);
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
      renderCategories(categories); await loadProducts(); document.querySelector('#workspaceStatus').textContent = 'Phase W3 · Product catalog';
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
      const access = await api('/api/touch-pos/session'); sessionStorage.setItem(TOKEN_KEY, token); showApp(access.user); await loadCatalog();
    } catch (error) {
      if (token) { try { await api('/api/touch-pos/logout', {method: 'POST'}); } catch (_) {} }
      token = null; sessionStorage.removeItem(TOKEN_KEY); password.value = ''; loginStatus.textContent = error.message; loginStatus.className = 'login-status'; password.focus();
    } finally { signIn.disabled = false; }
  });
  userButton.addEventListener('click', () => { userMenu.hidden = !userMenu.hidden; userButton.setAttribute('aria-expanded', String(!userMenu.hidden)); });
  document.querySelector('#signOut').addEventListener('click', async () => { try { await api('/api/touch-pos/logout', {method: 'POST'}); } catch (_) {} clearCatalog(); showLogin('Signed out.'); });
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
  updateClock(); checkServer(); validateSession(); setInterval(updateClock, 30000); setInterval(checkServer, 30000);
})();
