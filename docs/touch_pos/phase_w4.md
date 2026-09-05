# KAY POS Touch - Phase W4

Date: 2026-09-05
Status: Cart builder implemented

W4 turns the Touch POS product catalog into a usable browser cart without submitting a sale. Staff can tap products to add them, increase or decrease quantities, remove individual lines, clear the sale, and see live item count, subtotal, discount, and total values.

## Cart behavior

- Cart data is kept in `sessionStorage`, so a page refresh in the same browser tab keeps the current sale draft.
- Sign out, session expiry, and account changes clear the cart.
- Stock products cannot be added past their available stock.
- Out-of-stock products stay disabled in the catalog.
- Service items are allowed without stock limits.
- Variant products keep their variant id, SKU, price, stock, and display label in the cart draft.
- Payment continues in [Phase W5](phase_w5.md). Hold-sale remains for a later phase.

W4 does not call the sale API and does not mutate stock, payments, invoices, or receipts.
