# KAY POS Native — Phase 1 audit and migration plan

Date: 2026-09-04. Status: **Phase 1 static audit complete. Phase 2 preview implemented; see [Phase 2 delivery](../native_phase2/README.md).**
Baseline commit: `52a2d7e04a605467b53ac1c978cf746608fbefa0`. The generated inventory describes the working-tree source available during this audit.

## Objective and boundary

Keep the existing KAY POS application available and create a separately launched **KAY POS Native** with standard PyQt6 widgets. Preserve business behavior, permissions, data, shortcuts, and printing. This phase creates an implementation backlog and source inventory, not a runnable Native application.

The primary parity target is `main.py` → `app/application.py` → `ui/main_window/main_window.py`. Cashier mode is part of that target. POS Lite, Service Job Client, Car Management, Server Manager, and Printer Agent remain companion applications. Their code is a reuse/reference source; this project does not silently replace them. Service Jobs is currently evidenced in POS Lite and Service Job Client, not in the main-window page registry: adding it to Native is an explicit integration item, not an already-existing main-page parity claim.

## Evidence and limits

The static scan parsed 411 Python files in ten application directories without syntax errors. Of 297 files under `ui/` (121,498 source lines), 178 contain `.setStyleSheet(`, with 1,620 textual occurrences; 142 import database modules. There are 79 dialog-class candidates and 14 textual `paintEvent` definitions. These are scope indicators, not 79 confirmed reachable screens or 1,620 runtime style applications.

- [summary.json](summary.json): counts, scope, baseline, limitations.
- [files.csv](files.csv): every scanned file, style/paint/SQL markers and dependency flags.
- [classes.csv](classes.csv): class names, bases, source lines, dialog candidates.
- [imports.csv](imports.csv): static import edges, including lazy and conditional imports.
- [shortcuts.csv](shortcuts.csv): shortcut expressions and source locations, including dynamic helper calls.
- [acceptance.csv](acceptance.csv): feature-by-feature migration and verification backlog.
- [generate_inventory.py](generate_inventory.py): repeatable scan; run `python docs/native_phase1/generate_inventory.py` from the repository root.

No application modules were imported by the scan. No live database, credentials, customer records, printer, cloud account, or device was accessed. Runtime screen reachability, actual deployment backend, device behavior, and performance remain implementation/release verification items. Source existence alone is not a feature pass.

## Confirmed main-page registry

`ui/main_window/main_window_ui.py:183` registers 12 lazy-loaded page definitions. Permission filtering affects availability, so testing only as admin is insufficient.

| ID | Page | Permission key | Native phase |
|---|---|---|---|
| 0 | Dashboard | dashboard | 6 |
| 1 | Sales Summary | sales_summary | 6 |
| 2 | Products | products | 4 |
| 9 | Discounts | products | 3–4 |
| 8 | AI Pages | ai_pages | 7 |
| 3 | Inventory | inventory | 4 |
| 4 | Receipts | receipts | 5 |
| 5 | Sales | sales | 3 |
| 10 | Restaurant | sales | 5 |
| 6 | Customers | customers | 5 |
| 7 | Expense | expense | 5 |
| 11 | Employees | employees | 7 |

Menu-driven scope includes credit/outstanding collection, role management, cash drawer, customer display, cashier mode, activity log, report dialogs and settings. Evidence: `ui/main_window/main_window_menus.py`, `main_window_actions.py`, and `utils/permissions.py`. Settings include general, receipt, print, database connection, restaurant, regional, backup/reset, users, updates, Telegram, YouTube, performance, and ZKTeco source modules under `ui/settings/`.

## Architecture decision for implementation

**Superseded connection choice (user update):** Native now defaults to the existing POS Lite server API at `https://192.168.110.112:8000`, with 1366×768 minimum display support. The earlier direct test-database plan below is retained as audit history; local adapters are optional development tools. See the Phase 2 guide for the implemented server-first architecture and remaining API-parity work.

Create `kay_pos_native.py` and `kay_pos_native.pyw`, a `native_pos/` package, a separate build output, and a launcher entry in Phase 2. These paths were planned in Phase 1 and are now implemented by Phase 2. Leave the current entry points and custom UI intact.

Use QMainWindow/QMenuBar/QToolBar/QStatusBar for the shell, QStackedWidget with QListWidget or QTreeView for navigation, QDialog/QFormLayout for forms, and QTableView plus a model for larger data lists. Use native button painting, focus and selection indicators. Keep semantic status colors and branded icons when they convey meaning. Avoid copying the existing global stylesheet or importing old pages as the final Native implementation.

Default to the platform style exposed by the installed Qt runtime; enumerate `QStyleFactory.keys()` rather than assume a Windows style is available. Offer Fusion as an alternative. Light/Dark palettes must be paired and verified per style; native OS style behavior and palette changes are not identical. UI settings belong in a separate application namespace/local settings file. Do not change the old application's appearance preferences.

Keep one authoritative business data model. Phase 2 uses a test database/isolated PostgreSQL schema for development. Reuse current database connection/compatibility and service modules through adapters, without creating a divergent schema. The main app is not an API-only client today: an API-only rewrite would add scope. Do not assume `server/cashier_service.py` or Lite already has full main-app parity.

`CheckoutProcessor` under `ui/sales_page/checkout_handler/` writes transactions while reading `parent` and `handler` state. It is a candidate for extracting an input/result-based service, not a drop-in independent backend. Compare discount/expiry/wholesale, variant, batch/location allocation, customer credit, and audit behavior before reusing server or Lite checkout code. Keep legacy callers working while extracting only the operations needed by each phase.

## Side-by-side operation and data risks

1. **Single instance:** `main.py` uses `Global\\KAY_POS_Main_SingleInstance_v1`. Native needs its own identity. Separate installation is required; simultaneous production use is a later tested capability, not an assumption.
2. **Backend/path:** `models/database/connection.py` derives SQLite paths from source/executable location and supports PostgreSQL through `utils/db_compat.py`. A different EXE folder can accidentally point at another database. Native must show/validate the configured target and never silently initialize an unintended production database.
3. **Startup side effects:** `app/application.py` initializes and may recover database state. Main UI setup also ensures employee schema. Avoid instantiating the legacy application simply to borrow its shell.
4. **Duplicate services:** legacy main-window lifecycle owns backup, cloud sync, Telegram listener/watchdog, customer display and timers. Native must not start duplicate listeners, port bindings, scheduled backups or notifications. Establish one owner or explicit ownership coordination in Phase 2 before enabling them.
5. **Shared transactions:** test competing sale/refund/stock writes and invoice uniqueness on both supported backend types before permitting simultaneous use. A mutex per application is not database concurrency protection.
6. **Credentials and settings:** preserve authentication and permission checks. Keep display settings separate; use the configured shared business settings intentionally. Do not duplicate secrets into the audit or source control.
7. **Rollback:** retaining the old EXE is insufficient if Native changes schema or data semantics. Prefer additive compatible changes, verify old-app reads/writes after migrations, and validate restore on disposable data before release.

## Shortcut and device baseline

Source: `ui/sales_page/sales_page.py:521`, `ui/main_window/main_window_menus.py:271`, `main_window_handlers.py:102`; full candidate list is in shortcuts.csv.

| Context | Keys | Behavior to preserve |
|---|---|---|
| Sales | F2 / Ctrl+F | Product search |
| Sales | F3 / F4 / F6 | Customer / payment amount / payment type |
| Sales | F7 / F8 | Toggle discount / focus discount |
| Sales | F9 / F10 | Cash / credit sale |
| Sales | F12 | Checkout |
| Sales | Ctrl+Backspace / Ctrl+Delete | Clear cart / remove selected item |
| Sales | Ctrl+E | Expense dialog |
| Main | F5 / Ctrl+R | Refresh |
| Main | Ctrl+Shift+C | Cashier mode |
| Main | Ctrl+D / Ctrl+Shift+D | Customer display / cash drawer |

F5 exists in both menu and shortcut setup; Native should register one effective action per context and test duplicate activation. Do not infer a fixed sequence from dynamic shortcut-helper entries.

Receipt templates/images, receipt dialogs, barcode printing, network printer client and server printer service require separate output verification (`utils/receipt_template.py`, `utils/receipt_images.py`, `ui/receipt_dialog.py`, `ui/print_barcode_dialog.py`, `services/network_printer_client.py`, `server/printer_service.py`). Verify the deployed printer, paper width, Myanmar text, QR/barcode readability, copies, failures/retry, and cash drawer exactly once. Customer display includes UI and a server; test monitor selection and listener ownership. Test barcode scanners as actual input devices in Phase 8; do not equate keyboard simulation with hardware validation.

## Eight-phase delivery plan and exit gates

| Phase | Delivery | Exit gate |
|---|---|---|
| 1 | Static inventory, architecture boundaries, risk register, acceptance backlog | Source inventory parses; all 12 registered pages mapped; gaps explicitly listed |
| 2 | Separate Native startup/login/shell, styles/settings, launcher identity, data adapter boundary | Original app unchanged; Native runs against test data; role filtering and startup/shutdown work; no duplicate services |
| 3 | Sales/cashier, pricing, barcode, payment, basic customer selection, checkout, receipt/drawer | Representative sales match legacy totals, stock, credit and audit; canceled/failed checkout does not partially commit |
| 4 | Products/categories/variants, discounts administration, inventory and import/export | CRUD and stock movement parity including location/batch/expiry; representative large lists stay responsive |
| 5 | Customers/credit collection, receipts/refunds, expenses and restaurant operations | End-to-end daily operation including table/order flows, customer balances and refund stock restoration |
| 6 | Dashboard, sales summary, financial/inventory reports and exports | Same filters produce matching totals on a shared fixture; print/export checked |
| 7 | Employee suite, AI/integrations, remaining settings, permissions, backup/update | All inventory rows implemented or explicitly accepted as out of scope; device/integration adapters verified |
| 8 | Deployment rehearsal, regression, real devices, DPI/font/accessibility, coexistence and rollback | Feature parity checklist complete; original app still works; target-machine acceptance passed |

Phase 3 is a pilot sales milestone, not full-app parity. Restaurant and employee/AI/integration work make Phases 5 and 7 substantial; they may use sub-milestones. Eight is a delivery grouping, not eight equal-duration tasks. A credible calendar estimate needs the Phase 2 shell and Phase 3 checkout-extraction spike plus target hardware/data volume measurements.

## Phase 2 ready-to-start backlog

- [ ] Create Native entry points/package without importing legacy UI at startup.
- [ ] Add separate app ID, single-instance key, icon and settings namespace.
- [ ] Add launcher entry while preserving existing launch commands.
- [ ] Build native login and permission-filtered shell with the 12 page IDs represented in a route map; unfinished pages clearly identified during development.
- [ ] Enumerate styles and persist Native-only palette/font/window preferences.
- [ ] Add an explicit test-data connection path and connection diagnostics.
- [ ] Define authenticated user/session and service adapter interfaces; audit UI imports before reusing service functions.
- [ ] Define background-service ownership and clean shutdown, including pending worker handling.
- [ ] Verify keyboard focus, Myanmar/English text, 100/125/150/200% DPI, light/dark and old-app startup.

## Remaining observations, not blockers to Phase 2

Runtime reachability of all dialog candidates and conditional features is unverified. Confirm actual printer/scanner/display models, deployed database mode, largest table sizes and daily user roles during pilot preparation. No legacy feature is dropped automatically; unresolved features stay in acceptance.csv. Service Job Client continues staff Start/Complete actions and POS Lite continues customer collection; any Native Service Jobs integration should honor that division. No production data migration, runtime code changes, commit/push, or Native app build was performed in Phase 1.
