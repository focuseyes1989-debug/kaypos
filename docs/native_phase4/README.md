# KAY POS Native — Phase 4

Native Products, Discounts and Inventory now replace their shell placeholders. The existing Sales pilot continues to work. These pages use standard Qt widgets, dialogs, styles and palettes and fit the 1366 × 768 screen baseline with Windows title-bar/taskbar space reserved.

## Start and server update

Run `python kay_pos_native.py` or open `kay_pos_native.pyw`. Sign in using **Server**, default `https://192.168.110.112:8000`, with the existing POS account.

The server PC needs the pending Phase 2–4 changes, including `server/native_catalog.py`, `server/native_sales.py`, `server/api.py` and `server/cashier_service.py`, followed by a POS Server restart. Older servers leave catalog editing disabled and display an update/connection message. Direct SQLite/PostgreSQL practice login adapters remain read-only.

Commit/push and the server PC update remain postponed as requested. No production catalog edits, stock transactions, imports, printing or drawer operations were used for this implementation.

## Products and categories

- Search by name/SKU/barcode, filter categories, page through 60 records at a time and inspect low stock on the loaded page. Details include variants, locations/batches, expiry rules, promotions and wholesale tiers.
- Create/edit Each, Service or Variants products, descriptions, units, pack setup, regular price, cost, low-stock threshold and optional PNG/JPEG/WEBP/BMP images up to 8 MB. Images are validated and stored in the existing image-blob columns; replacing an image does not write an orphan file before a transaction commits.
- Product creation starts at zero stock. Receive stock through Inventory. Editing metadata never writes a submitted stock value. Existing variant IDs and balances are retained, so old sale and movement references continue pointing at the same variants. Removing a zero-stock variant deactivates it. Stocked variants cannot be removed/deactivated. Existing product modes cannot be changed in place.
- Categories support new/edit, parent selection, rename and deletion of empty categories. Cycles, duplicate names and deleting a category containing products/children are rejected. Renames update product category names. Native Sales reloads its categories/products on the next visit after a catalog change; its cart remains intact.
- **Delete unused** removes only products with zero stock and no product-linked history. It checks all existing tables with a `product_id` column before deleting dependent variant/location/pricing records. A shared master-product archive state is not available in the existing API; this phase does not invent an archive flag that the original apps would ignore.

## Discounts and wholesale

Select an Each product in Discounts and open **Edit discounts / wholesale**. Product promotions support percentage or fixed sale price, calendar start/end dates, active status and notes. Wholesale tiers support minimum quantity, unit price, label/multiplier, barcode metadata and active status. Remove a row to delete that pricing rule on Save.

The server validates dates, numbers, ownership and the pricing revision. Rules use the existing `product_discounts` and `product_price_tiers` schema, so Native Sales quotes use the same server calculations. A wholesale threshold continues to override the product promotion price as in the existing cashier service. Existing location expiry-discount fields are preserved and visible in Details; editing those clearance rules remains in the existing POS. Product/variant barcode scanning and label printing are supported; tier-barcode metadata does not add a new pack-scanning protocol.

## Inventory and history

- **Stock In** records quantity, unit cost, location, batch, optional expiry, reason, reference and notes. Product cost follows the existing weighted-average rule; a selected variant records its received unit cost. The signed-in username is the audit actor.
- **Stock Out** removes stock only from the selected location, consuming dated batches first. It does not silently drain a different location. Service products cannot receive stock; variant products require a selected active variant.
- **Set counted stock** sets a product/variant total. The difference is added to or removed from the selected location. It checks that the selected location can cover a reduction.
- **Transfer** moves Each-product stock between two locations without changing product total/cost and retains batch/expiry information. It creates paired audit entries. Variant location transfers are not supported by the shared schema.
- Legacy stock with no location rows is first represented at **Shop**. Existing master/location or master/variant discrepancies are rejected for reconciliation in the existing POS, preventing a receipt from silently hiding older stock.
- **Movement history** shows the latest 200 movements. **Reverse selected Native operation** reverses the entire Native receipt/issue/adjustment/transfer only when its stock, costs and batches still match the saved post-operation snapshot. It restores the prior quantities, locations, costs and variant balances, retains original history and appends a reversal entry. A transfer's two entries are reversed together. An operation can only be reversed once. If later activity has occurred, use a reviewed adjustment; legacy movements retain the existing POS reversal workflow.

## CSV and barcode labels

**Products → Export metadata CSV** exports the currently displayed page using fresh server detail records, UTF-8 with BOM and spreadsheet-formula-safe text. It includes product IDs/revisions and `variants_json`. Inventory/Discounts export their displayed summary rows instead. These are page exports, not a full database backup.

**Import CSV** accepts 1–200 products and a file up to 8 MB. Export a Native metadata page for the complete column template. At minimum, a new row needs `name` and `sold_by` (`Each`, `Service`, or `Variants`). Existing IDs require their exported revision. Blank IDs create zero-stock products; to clone a variant product, also remove variant IDs inside `variants_json`. Numeric/date/schema errors are reported with row numbers. Preview every row before confirming. The server applies the entire import atomically; one invalid/stale row rolls back all rows. Stock balances and images are not imported from CSV. XLSX import and richer legacy spreadsheet layouts remain in the original POS.

**Barcode label** prints a product or selected variant barcode/SKU through native Qt Print Preview and Print/PDF dialogs. Code128 B encoding matches the original barcode dialog. Set label width, height and copies, then choose the printer. Each label is one page. Quiet zones are reserved, and widths that would make modules smaller than 0.25 mm are rejected. Printable ASCII codes are required. Actual printer scaling, media size, copies and scanner readability remain target-device checks; no physical label was printed during development.

## Permissions, concurrency and recovery

Read access uses `products` or `inventory`; command permission is checked again against the current active server account and role. Product add/edit/delete, stock in/out/adjustment and transfers use their corresponding permissions. Transfers require both stock-in and stock-out. Pricing/category edits require product-edit. CSV imports require add/edit permissions for the rows they contain. Reversal requires adjustment permission. The UI disables unavailable actions and the server independently rejects unauthorized commands.

Metadata, pricing and stock revisions prevent stale forms from overwriting newer data. Product metadata revisions exclude stock, so a sale does not cause an edit to restore an old balance. Stock revisions include quantities/costs/variants/locations. PostgreSQL commands lock relevant products before changes; metadata/category/import commands use table locks, while stock uses product row locks in the same order as Native Sales. Native interactive writes no longer reset PostgreSQL ID sequences; schema setup/restore owns sequence initialization. Physical PostgreSQL concurrency with the deployed legacy clients still needs rehearsal.

Each confirmed catalog command is saved before submission in a server/account-scoped Native recovery file under `%APPDATA%\KAY\POSNative`. It uses a namespace distinct from sales checkout recovery. A single command channel is shared across all three pages. An unresolved command locks new catalog edits across them, including after restart; use **Recover pending change** to send the same UUID/payload. It can complete a request that never arrived or return the saved result of one already committed. Do not recreate an unresolved change in another POS.

The additive `native_catalog_requests` table commits request identity, audit/result and the business changes together. Repeated identical requests do not apply twice; different payloads cannot reuse the same ID. `native_catalog_reversals` records completed reversals. Known validation rejection rolls back and unlocks editing; unsaved dialog values may need re-entry after correcting or refreshing. Unknown/network errors keep the recovery record. Corrupt/unwritable records block further editing instead of silently discarding recovery state. Closing during a command waits for the worker and saves its returned result.

## Verification and acceptance

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m unittest tests.test_native_pos_phase4 tests.test_native_pos_phase3 tests.test_native_pos_phase2 tests.test_native_pos_server tests.test_launcher
```

**60 tests passed**: 19 Phase 4 tests plus 41 prior regressions. Tests use disposable SQLite fixtures, actual catalog transactions, the existing server sales calculation functions, socket-free ASGI routes and mocked Qt/API interactions. They cover variant identity and stock retention, metadata edits after sales, code uniqueness, safe deletion, image validation/rollback, category rename/cycles, discount-to-quote parity, weighted costs, concurrent duplicate retry, location-specific issues, transfer batch/expiry retention, counted stock, service restrictions, legacy unallocated stock, server permissions, reversal snapshots/repeats/later-activity rejection, atomic CSV rollback/round-trip/invalid-row reporting, dialog cancellation, old-server gating, shared recovery/restart/close behavior and minimum-display layout. Barcode checks cover checksum, parity with original patterns, quiet zones, minimum width and rendered bars.

Offline visual inspections: [Products Light](products-light.png), [Inventory Dark](inventory-dark.png), [Product editor](product-editor.png), [Discount editor](discount-editor.png), [Barcode preview](barcode-preview.png). Regenerate with `python docs/native_phase4/render_preview.py`; it makes no network requests and does not print physically.

Source implementation is ready for deployment testing. Remaining acceptance gates are the live server schema/PostgreSQL environment, real roles and representative production data, original-app coexistence, real label printers/scanners and high-DPI/Myanmar font rendering. No executable build or Git commit/push was performed. Broader legacy spreadsheet/expiry-clearance/master-archive coverage remains explicitly open rather than being counted as complete parity.

Next planned milestone: **Phase 5 — Customers/Credit, Receipts/Refunds, Expenses and Restaurant workflows**.
