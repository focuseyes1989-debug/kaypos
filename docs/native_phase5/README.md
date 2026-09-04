# KAY POS Native — Phase 5

Date: 2026-09-04. Status: **source implementation complete; disposable SQLite acceptance suite passed.**

Phase 5 adds four standard-widget pages to the separate KAY POS Native application. The original KAY POS, POS Lite, and Service Job Client entry points remain available. Native continues to use the configured POS Lite server, whose default is `https://192.168.110.112:8000` with the existing self-signed TLS option.

## Delivered workflows

- Customers: search, add, edit, safe deletion, credit limit and current outstanding balance. A customer with balances or transaction history cannot be deleted.
- Credit: outstanding invoices, complete payment history, and authorized payment collection. Payments validate the latest invoice revision and customer balance in the same transaction.
- Receipts: date/search filters, details, Qt print/PDF, and the existing full-refund workflow. Eligible stock is restored by variant and location/batch; Service and Restaurant lines do not change stock. The existing app has no item-level/amount-level partial-refund path. A partially paid credit receipt remains blocked from refund; unpaid and fully paid credit receipts reconcile balances and audit rows.
- Expenses: date/search filters with filtered totals, add/edit/delete, category rename/deactivation, monthly budgets, prior-month comparison, and UTF-8 CSV export with spreadsheet-formula escaping.
- Restaurant: table setup, dine-in/takeaway orders, server-owned modifiers and prices, saved item changes/additions, kitchen tickets and status progression, ticket print/PDF, whole-order cancel/reopen, and checkout. Checkout records stock/credit sale data and marks the order settled in one transaction. A failed settlement rolls both sides back. Sent kitchen lines cannot be removed or replaced in the order editor; cancel the whole order to replace them.
- Products: the Phase 4 editor now includes Restaurant mode and a modifier grid. Restaurant menu items follow the established no-stock behavior and cannot be added directly through the regular Sales cart.

## Transaction and recovery boundary

Every Phase 5 write has a UUID stored with the command result. Retrying the same UUID returns the first committed result. A reused UUID with changed content or another account is rejected. The desktop persists the exact unresolved command before sending it and blocks another business write until recovery succeeds or the server gives a definite rejection. Payment, refund, expense, order, kitchen, and checkout operations use this shared recovery channel.

The server reads role and user permissions again inside each write transaction. Admin retains its existing superuser behavior. Other accounts require the page permission plus the action permission, such as `payment_collection`, `refund_receipt`, `add_expense`, or `create_sale`.

## Verification

The complete Native suite has 77 passing tests. Phase 5 tests exercise real SQL against disposable databases and include concurrent retry, altered-payload rejection, stale revisions, revoked access, payment reconciliation, overpayment rollback, cash/credit refunds, variant/batch/Service stock behavior, expense totals and budgets, server-owned modifier prices, table occupancy, kitchen idempotency, cancel/reopen, atomic Restaurant settlement, restart recovery, minimum-screen layout, and stock Qt dialogs. The earlier 60 Phase 2–4 and launcher/server tests remain green.

Run from the repository root:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m unittest tests.test_native_pos_phase5 tests.test_native_pos_phase4 tests.test_native_pos_phase3 tests.test_native_pos_phase2 tests.test_native_pos_server tests.test_launcher
python docs/native_phase5/render_preview.py
```

The renderer uses a temporary fixture database and mocked network client. Its checked screenshots cover light/dark Restaurant pages, Customers, Receipts, Expenses, customer credit, order editing, and modifier selection at the 1366×768 screen baseline.

## Deployment checks still required

No production server, live customer data, physical printer, cash drawer, or kitchen printer was used. Before daily use, update and restart the POS Server, test with a disposable record using actual staff roles, and verify PostgreSQL transaction behavior and each configured printer. Git commit/push remains postponed as previously requested.
