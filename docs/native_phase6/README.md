# KAY POS Native — Phase 6

Date: 2026-09-04. Status: **source implementation complete; 94 Native/launcher tests pass using disposable fixtures.**

Phase 6 replaces the Native Dashboard and Sales Summary placeholders and adds a permission-controlled Reports page. Existing route IDs remain stable; Reports uses Native route 12. The original KAY POS entry point and UI remain available. Native still defaults to the POS Lite server at `https://192.168.110.112:8000`.

## Delivered

- Dashboard: selected-period revenue, invoice totals, COGS, expenses, invoice profit, refunds, previous-period comparison, daily totals, top products, and current stock/credit snapshots where authorized.
- Sales Summary: daily/hourly totals, items/top sellers, wholesale savings, categories, immediate parent categories, category groups, payment types, and refunded items.
- Reports: financial summary, monthly profit and loss, sales invoices with authorized receipt drilldown, expense categories and entries, credit balances/collections, inventory valuation and movements.
- Native Qt table models provide numeric sorting and filtering across the complete loaded result, without creating a widget for every cell. Summary cards retain the full selected-period totals; table filtering affects visible rows and exports only.
- CSV exports the selected table. XLSX exports all loaded tables plus report dates, currency, snapshot time, filters, metrics and definitions. Exports use the captured snapshot and atomic file replacement; text cannot become spreadsheet formulas.
- A4 landscape report preview uses `QPrintPreviewWidget`, with page navigation and the native Print/PDF dialog. Standard Qt palettes, widgets and fonts are retained; no application stylesheets, custom chart painting, or WebEngine were added. Daily/comparison tables are the Phase 6 native presentation for trends.

## Calculation definitions and intentional corrections

The existing UI contains inconsistent reporting queries. Phase 6 uses one documented calculation boundary rather than duplicating those discrepancies:

1. Completed sales exclude `refunded` and `deleted` receipts. Returns are shown separately by the original sale date because the existing sales schema has no refund-date ledger. Refunded receipts are not subtracted again from already-completed-only totals.
2. Item gross is quantity × actual sold unit price. Net item sales are gross minus the receipt discount, counted once. Discounts are allocated proportionally across receipt items; the final line receives the rounding remainder. Items, categories and payment types reconcile to the same net amount. Receipt counts may overlap across groups.
3. Invoice total is the sum of completed `sales.total`; it can include tax/adjustments. Financial invoice profit is invoice total minus COGS and expenses, matching the existing financial report's invoice-total basis. It is labeled separately from net item sales.
4. Recorded sale-item cost is used, including a valid zero cost. Only missing cost falls back to current variant/product cost and is flagged as estimated. Unlike older reports that use current product cost or `NULLIF(cost,0)`, changing a product cost does not rewrite known historical COGS. Service costs are included when recorded.
5. Products/categories are resolved to a single record, avoiding multiplied totals from duplicate product names. Category/group assignments remain current metadata, as in the original reporting model.
6. New checkout rows retain wholesale price/savings metadata when the existing schema supports it. Historical wholesale savings that were never recorded are not reconstructed from today's prices.
7. Credit and inventory balances are current snapshots, independent of the report dates. Credit collections use payment dates and do not increase sales revenue again. Outstanding credit uses the greater customer/invoice balance, preserving the existing Dashboard safeguard.

The definitions are available in the UI and included in report exports/printouts. No legacy UI queries or business records were rewritten.

## Server and access

`GET /api/native/reports` accepts a fixed section/view and ISO start/end dates. Views are whitelisted; no caller-supplied SQL is accepted. Each request checks the current account/role permissions. Dashboard requires `dashboard`, Sales Summary requires `sales_summary`, and Reports requires `reports`; credit/inventory detail additionally requires `credit`/`inventory`. Receipt drilldown separately checks receipt access.

All report queries run in one read-only snapshot: SQLite query-only transaction or PostgreSQL repeatable-read/read-only transaction. Reports perform no schema migration or data writes. Dates are inclusive at the day level, implemented as a start-inclusive/end-exclusive range. Requests are limited to ten years and 20,000 rows per table; oversized results fail explicitly instead of returning partial totals. Actual production-scale PostgreSQL performance remains a deployment check.

## Verification

The suite has **94 passing tests**: the earlier 77 tests plus 17 Phase 6 tests. The navigation tests now derive the route count from the registry because Reports adds one Native page.

Phase 6 verification covers receipt reconciliation, one-time discounts, penny remainder allocation, refund separation, recorded/zero/missing costs, wholesale audit data, duplicate names, category/payment/day/hour breakdowns, expenses, current credit/inventory, collection and movement dates, empty/invalid ranges, current permissions, read-only behavior, concurrent reads, and a writer committing between report queries without mixing snapshots. UI/export tests cover the 1366×768 screen baseline, numeric sorting/filtering, stale-date/error clearing, CSV/XLSX formula safety, atomic-export failure, escaped HTML, and PDF output without a physical printer.

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m unittest tests.test_native_pos_phase6 tests.test_native_pos_phase5 tests.test_native_pos_phase4 tests.test_native_pos_phase3 tests.test_native_pos_phase2 tests.test_native_pos_server tests.test_launcher
python docs/native_phase6/render_preview.py
```

The renderer uses a disposable database and mocked network transport. Checked previews:

- [Dashboard](dashboard-light.png)
- [Sales Summary](sales-summary-light.png)
- [Financial report — light](financial-light.png)
- [Financial report — dark](financial-dark.png)
- [A4 print preview](print-preview.png)

## Deployment still pending

No live server/database or physical printer was used. Update/restart the POS Server before using the new endpoint, install the Native requirements (including `openpyxl` for XLSX), and verify actual staff roles, PostgreSQL behavior/performance, display scaling and printer output on the server/client PCs. No executable was built. Git commit/push remains postponed as requested.
