# KAY POS APP 1366x768 UI/UX Audit - Phase 1

Date: 2026-09-10
Scope: `main.py` desktop app entry and the PyQt main application launched through `app.application.Application`.
Target baseline: usable at 1366x768 minimum resolution, with graceful behavior on larger screens.

## Entry Point Summary

- `main.py` is a launcher/guard entry point. It starts `app.application.Application`.
- The main UI is built by `ui/main_window/main_window_ui.py`, `ui/main_window/sidebar.py`, `ui/main_window/header.py`, and page modules under `ui/`.
- `app/application.py` shows the main window maximized after startup.
- `ui/main_window/main_window_ui.py` and `ui/main_window/main_window_actions.py` already clamp the minimum window size to `min(1366, width)` and `min(768, height)`.

## 1366x768 Baseline Risks

1. Main shell consumes significant space before page content.
   - Header: fixed 64px in `ui/main_window/header.py`.
   - Sidebar: fixed 260px expanded width in `ui/main_window/sidebar.py`.
   - Content margins: 20px horizontal and 16px vertical in `ui/main_window/main_window_ui.py`.
   - Status bar and OS title/task bars reduce usable height below the nominal 768px.

2. Sales page is the most important 1366x768 workflow risk.
   - `ui/sales_page/sales_page.py` uses a horizontal product/cart split with the right side stacking customer, cart, totals, payment, actions, and extra buttons.
   - The right side has 14px margins and several fixed-height controls.
   - At 1366x768, this can feel crowded vertically, especially with cart rows and payment controls visible.

3. Product browsing toolbar can overflow horizontally.
   - `ui/sales_page/product_grid.py` uses fixed widths for category filter (`180`), discount filter (`150`), and view selector (`140`), alongside a search box.
   - `ui/products_page/products_page.py` combines filters and action toolbar in one horizontal row.
   - `ui/customers_page/customers_page.py` uses a search widget, fixed add button, action toolbar, and a wide 10-column table.

4. Settings has nested sidebar width pressure.
   - Main sidebar is 260px.
   - `ui/settings/settings_center.py` adds another fixed 260px settings sidebar.
   - At 1366px width, the actual settings form area may become too narrow for two-column settings forms.

5. Several dialogs are too tall for 1366x768 after OS chrome.
   - `ui/customer_page/customer_ledger_dialog.py`: `setMinimumSize(1100, 800)` exceeds the target height.
   - `ui/inventory_page/adjustment_ui.py`: `resize(950, 780)`, minimum height `700`.
   - `ui/inventory_page/stock_movement_dialog.py`: `setMinimumSize(1000, 650)`, `resize(1120, 720)`.
   - `ui/expense_comparison_dialog.py`: `setMinimumSize(1000, 700)`.
   - `ui/restaurant_page.py`: kitchen dialog `resize(980, 760)`.

6. Inventory pages have many horizontal tabs and wide tables.
   - `ui/inventory_page/inventory_tabs.py` has 7 top tabs.
   - `ui/inventory_page/current_stock_tab.py` fixes image/history columns and uses many resize-to-content columns.
   - Stock movement and expiry dialogs use many table columns, which need horizontal scroll and compact defaults.

7. AI/dashboard visual widgets include fixed heights that may crowd the viewport.
   - `ui/ai_pages/ai_dashboard/dashboard_widget.py`: fixed chart/card heights.
   - `ui/ai_pages/ai_dashboard/dashboard_charts.py`: chart container fixed height `612`.

## Priority Fix Order

### P0 - Shell And Core Sales

- Add a shared 1366x768 layout profile for the main shell.
- Keep the app minimum target at 1366x768, but reduce shell chrome at that size:
  - Sidebar width from 260 to a more compact expanded width for 1366.
  - Header height from 64 to a compact baseline when vertical space is limited.
  - Content margins from 20/16 to a tighter 12/12 or 14/12 profile.
- Make Sales page right panel vertically denser.
- Ensure cart/payment/checkout controls remain visible without awkward clipping.

### P1 - High-Risk Dialogs

- Replace oversized minimum heights with available-screen-aware sizing.
- Add scroll areas inside tall dialogs instead of requiring the whole dialog to be taller than the screen.
- Start with:
  - Customer ledger dialog.
  - Stock adjustment dialog.
  - Stock movement dialog.
  - Expense comparison dialog.
  - Kitchen queue dialog.

### P2 - Toolbars And Tables

- Convert crowded toolbars to wrapping or compact action-toolbar behavior at 1366 width.
- Review these pages first:
  - Products.
  - Customers.
  - Inventory.
  - Receipts.
  - Expense.
- Prefer one primary button plus More actions where horizontal space is tight.

### P3 - Settings And Secondary Pages

- Make settings center sidebar responsive or collapsible.
- Keep two-column forms only when enough width exists; otherwise use one-column form sections.
- Review receipt/general/restaurant settings first because they contain fixed preview heights and dense controls.

## Acceptance Checklist For Phase 2+

- App opens maximized and usable at 1366x768.
- Sidebar, header, status bar, and content fit without hiding primary page controls.
- Sales page can complete a sale at 1366x768 without opening oversized dialogs unexpectedly.
- All high-risk dialogs fit inside available screen height and scroll internally.
- Tables remain readable with important columns visible; secondary columns may scroll.
- No page requires dragging the window beyond the screen to access Save, Close, Checkout, or Apply buttons.

## Recommended Next Phase

Phase 2 should implement the shared 1366x768 shell profile first:

1. Add reusable constants or helper methods for compact desktop metrics.
2. Tune main sidebar/header/content margins for 1366x768.
3. Apply compact Sales page layout rules.
4. Verify the app still looks comfortable at 1600x900 and 1920x1080.

## Phase 2 Implementation Notes

Implemented on 2026-09-10.

- Reduced the main sidebar expanded width from 260px to 232px and collapsed width from 84px to 72px.
- Reduced sidebar navigation height and internal spacing so all primary navigation remains reachable at 768px height.
- Reduced header height from 64px to 56px and tightened its horizontal margins.
- Reduced main content margins from 20/16 to 12/10.
- Tightened Sales page spacing, right-panel padding, and secondary action button heights.
- Reduced Sales product filter control widths so the product search row has more usable space at 1366px width.

## Phase 3 Implementation Notes

Implemented on 2026-09-10.

- Added a reusable dialog fitter that sizes dialogs against the active screen's available geometry.
- Reduced oversized minimum heights on Customer Ledger, Stock Adjustment, Stock Movements, Expense Comparison, and Kitchen Queue dialogs.
- Tightened dialog margins and spacing so primary actions and table/list content fit more comfortably at 1366x768.
- Reduced Customer Ledger table row height to improve visible rows on shorter screens.

Phase 4 should continue with toolbars, table defaults, and dense secondary pages listed in P2/P3.
