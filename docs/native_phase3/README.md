# KAY POS Native — Phase 3 Sales pilot

The current source also includes [Phase 4 Products, Discounts and Inventory](../native_phase4/README.md). This document records the Phase 3 sales milestone.

Phase 3 adds a working server-backed Sales workspace to the separate Native application. The original KAY POS, POS Lite and Service Job Client remain available. Other Native business pages retain their phase placeholders.

## Run and deploy

Run `python kay_pos_native.py` or open `kay_pos_native.pyw`. Select **Server**, using the existing default `https://192.168.110.112:8000`, and sign in with a POS account. Direct SQLite/PostgreSQL practice adapters remain read-only and do not enable Sales.

The POS Server must contain this phase's `server/api.py`, `server/native_sales.py` and `server/cashier_service.py`, then be restarted. Native checks `/api/native/sales/capabilities` before enabling checkout. An older server displays an update message; Native does not fall back to an unsafe checkout endpoint. The user has postponed commit/push and the server PC update, so deployment has not been performed.

The minimum display is **1366 × 768**. The application reserves the actual Windows title-bar/taskbar area. **Cashier mode (Ctrl+Shift+C)** hides navigation and identity/banner rows and opens Sales; toggle it again to return to the full workspace. Appearance continues to use standard Qt styles, palettes and fonts, without application stylesheets or custom-painted controls.

## Sales workflow

1. Search products by name, filter a category, or scan a product/variant barcode or SKU and press Enter. Search uses pages of 60 products; Previous/Next navigate results. Double-click a product or choose Add selected. Variants use a native selection dialog; services ask for their unit price.
2. Change quantities with −/+, Quantity, Remove or Clear. The cart checks cached stock immediately. Its subtotal is explicitly an estimate: final product discounts, wholesale quantity tiers and tax come from the server.
3. Optionally find and select a customer. Choose an amount or percentage discount and a payment method. Credit requires a customer, `credit_sale` permission, a due date and a deposit between zero and the total. Credit notes are supported. Native does not allow overriding customer credit limits.
4. **Review sale (F9)** obtains the server calculation without saving a sale or changing stock. Check line prices, discount, tax and total, then enter payment and choose **Confirm sale**. Cancel leaves the cart intact. The final transaction checks stock, payment, credit limit and the reviewed total again. A changed total requires another review.
5. A successful sale clears the cart and opens its receipt. **Last receipt** remains available, including after restarting and signing back into the same server/account. **Print / PDF…** uses the native Qt/Windows printer dialog and requires `print_receipt`. Choose the receipt printer and its paper settings, or a PDF printer.

Keyboard shortcuts: **F2** product search, **F4** barcode field, **F9** review, **Ctrl+Shift+C** cashier mode. **F5 / Refresh access** retains the shell's sign-out/re-authenticate behavior. Product refresh uses Search or Connect / Refresh. Sign out/exit asks before discarding an unsaved cart.

**Open SERVER cash drawer** explicitly targets the printer/drawer configured on the POS Server. It asks before sending a pulse and never runs automatically after a sale or a receipt reprint. This is not a local-client USB drawer driver. A network error on a drawer command can mean the pulse was sent; inspect the drawer before repeating it.

## Transaction and recovery behavior

- Native routes check the current database account status, role and permissions (`sales`, `create_sale`, plus `credit_sale` for credit) rather than trusting the login-time permission snapshot. Existing Lite/browser request models remain compatible.
- Quotes and final sales share the existing server pricing/allocation code. Quote paths skip stock/movement writes and sequence synchronization and roll back the transaction. Native amount/percentage discounts are capped at the subtotal; Native money totals are rounded to two decimal places to match its payment fields.
- Before sending a confirmed checkout, Native atomically saves its UUID, exact payload and cart under `%APPDATA%\KAY\POSNative\checkout-<server-account-hash>.json`. Passwords and bearer tokens are not stored there. Failure to save prevents submission.
- The server creates an additive `native_sale_requests` table when first needed. A unique request claim, stock changes, sale/items, customer balance and saved receipt commit together. Repeating the same request returns the saved receipt. A different payload/account cannot reuse that request. PostgreSQL product/customer rows are locked in a stable order before allocation; physical PostgreSQL concurrency remains a deployment verification gate.
- If a response is lost, the cart is locked and **Recover pending checkout** becomes available. It sends the exact same request ID and payload; it can complete a request that never arrived, or retrieve the receipt of one already committed. Do not re-enter an unresolved sale in another POS. Closing and restarting preserves this recovery state.
- A known server validation rejection rolls back and unlocks the original cart for correction. Unknown/network errors keep the recovery record. A malformed or unwritable recovery record blocks another sale rather than silently discarding it. Keep the file for administrator assistance. If sale permissions are revoked while recovery is pending, an administrator must restore access or reconcile the saved request before proceeding.
- A confirmed receipt is saved locally before the cart is cleared. Closing while checkout runs still waits for the worker and saves a returned receipt without opening another dialog. Receipt printing failure does not create or repeat a sale.

## Verification

Command:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m unittest tests.test_native_pos_phase3 tests.test_native_pos_phase2 tests.test_native_pos_server tests.test_launcher
```

**41 tests passed** using disposable SQLite fixtures, a socket-free ASGI app and mocked HTTP/Qt interactions. Transaction tests execute the actual server functions and request models without importing the production database bootstrap. Coverage includes wholesale/amount/percentage discounts and tax, representative Native/Lite checkout parity, quote rollback, insufficient payment/stock, stale totals, variants/services, credit limits/balances, duplicate and concurrent retry, current server permission enforcement, barcode/cart limits, canceled review, lost-response recovery across restart, receipt persistence on close, escaped receipt text, old-server gating, minimum display sizing and existing shell/launcher regressions.

Offline visual previews: [Sales Light](sales-light.png), [Sales Dark](sales-dark.png). Regenerate with `python docs/native_phase3/render_preview.py`. The previews contain synthetic data and make no network requests.

Not yet verified on the server PC: live PostgreSQL integration, real sales using deployed user roles/settings, physical receipt printers/drawers/scanners, Windows DPI scaling and Myanmar font shaping. No production sales, stock changes, physical printing, drawer pulses, executable build or Git commit/push were performed during this phase.

This is the Phase 3 sales pilot, not full-app parity. Customer management, receipt history/refunds and restaurant flows remain Phase 5; advanced loyalty redemption, custom legacy receipt-template parity, local drawer drivers and customer-display/device integrations remain open acceptance items for subsequent integration work. Cash sales with a selected customer still use the existing server's automatic earned-points behavior. The next planned phase is **Phase 4 — Products, Discounts and Inventory**.
