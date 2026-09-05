# KAY POS Touch - Phase W3

Date: 2026-09-05
Status: Product catalog implemented

W3 connects the authenticated Touch POS workspace to the existing POS Lite product and category data. Staff can browse categories, search by product name, SKU, or barcode text, refresh the list, and view touch-sized product tiles at the target 1366x768 layout.

## Catalog behavior

- `/api/touch-pos/categories` returns the current product categories after the same Touch POS sales permission check used by the session endpoint.
- `/api/touch-pos/products` forwards search text, category, limit, and offset to the existing product service, then returns only sale-screen display fields.
- Product cost and other internal fields are stripped before the browser receives catalog data.
- The product search is debounced while typing and runs immediately when Enter is pressed, which supports barcode scanners that submit an Enter key.
- Product tiles show image, name, category or SKU, price, and stock status. Out-of-stock stock items are disabled.
- Changing account state, sign out, or session expiry clears visible catalog data and aborts any pending product request.

Cart creation continues in [Phase W4](phase_w4.md). W3 does not mutate sales, stock, or payments.
