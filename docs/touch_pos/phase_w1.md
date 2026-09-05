# KAY POS Touch — Phase W1

Date: 2026-09-05  
Status: Foundation implemented

Open the preview from the existing POS Server at:

```text
https://192.168.110.112:8000/touch-pos
```

W1 adds a separate FastAPI page and static PWA shell. It includes the KAY identity, server health indicator, full-screen action, install-prompt support, a desktop three-column layout for the 1366×768 baseline, and tablet breakpoints. Category, product and cart controls are deliberately disabled preview elements in W1; staff login starts in W2 and live product data starts in W3.

The service worker caches only the static application shell. API and health requests always go to the network and no authentication or sale response is cached.

## Acceptance

- `/touch-pos` and `/touch-pos/` serve the isolated page with `no-store`.
- The service worker is scoped to `/touch-pos/` and is served with `no-cache`.
- Desktop layout uses fixed category/cart areas with a flexible product area.
- Tablet breakpoints are present at 1099 px and 760 px.
- Interactive controls have a 48 px minimum target in compact layouts.
- Page-level scrolling is disabled; future product/cart lists own their scrolling.
- Existing dashboard, cashier, POS Lite, Service Job Client and Native entry points are unchanged.

