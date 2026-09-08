const CACHE = 'kay-pos-touch-w7-v32';
const SHELL = [
  '/touch-pos/',
  '/static/touch_pos/touch-pos.css',
  '/static/touch_pos/touch-pos.js',
  '/static/touch_pos/manifest.webmanifest',
  '/assets/kay/kay_128x128.png',
  '/assets/icons/dashboard.svg',
  '/assets/icons/shopping_cart.svg',
  '/assets/icons/maximize.svg',
  '/assets/icons/inventory.svg',
  '/assets/icons/category.svg',
  '/assets/icons/products.svg',
  '/assets/icons/search.svg',
  '/assets/icons/settings.svg',
  '/assets/icons/refresh.svg',
  '/assets/icons/logout.svg',
  '/assets/icons/close.svg',
  '/assets/icons/receipt.svg'
];
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener('activate', event => event.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('kay-pos-touch-') && key !== CACHE).map(key => caches.delete(key))))
    .then(() => self.clients.claim())
));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/') || url.pathname === '/health') return;
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok && SHELL.includes(url.pathname)) caches.open(CACHE).then(cache => cache.put(event.request, response.clone()));
    return response;
  }).catch(() => caches.match(event.request)));
});
