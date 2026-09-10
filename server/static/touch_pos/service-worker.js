const CACHE = 'kay-pos-touch-w7-v142';
const SHELL = [
  '/static/touch_pos/touch-locations.js?v=20260910-tablet-cards2',
  '/static/touch_pos/touch-suppliers.js?v=20260910-tablet-cards2',
  '/static/touch_pos/touch-customers.js?v=20260910-tablet-cards2',
  '/static/touch_pos/touch-dashboard.js?v=20260910-tablet-cards2',
  '/static/touch_pos/touch-scanner.js?v=20260910-tablet-cards2',
  '/touch-pos/',
  '/static/touch_pos/touch-pos.css?v=20260910-tablet-cards2',
  '/static/touch_pos/touch-pos.js?v=20260910-tablet-cards2',
  '/static/touch_pos/touch-settings.js?v=20260910-tablet-cards2',
  '/static/touch_pos/touch-receipt.js?v=20260910-tablet-cards2',
  '/static/touch_pos/touch-expenses.js?v=20260910-tablet-cards2',
  '/static/touch_pos/manifest.webmanifest',
  '/assets/kay/kay_128x128.png',
  '/assets/icons/dashboard.svg',
  '/assets/icons/maximize.svg',
  '/assets/icons/aspect_ratio.svg',
  '/assets/icons/point_of_sale.svg',
  '/assets/icons/receipt_long.svg',
  '/assets/icons/inventory_2.svg',
  '/assets/icons/location_on.svg',
  '/assets/icons/supplier.svg',
  '/assets/icons/person.svg',
  '/assets/icons/local_atm.svg',
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
    if (response.ok && SHELL.includes(url.pathname + url.search)) caches.open(CACHE).then(cache => cache.put(event.request, response.clone()));
    return response;
  }).catch(() => caches.match(event.request)));
});
