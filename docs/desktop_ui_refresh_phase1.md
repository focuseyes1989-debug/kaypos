# KAY POS APP: UI Refresh, Phase 1

Date: 2026-09-10
Status: source audit and design specification complete; visual QA pending.
Scope: main.py -> app/application.py -> PyQt desktop application.
This is the new six-phase UI refresh, following the earlier resolution work.
Touch POS, native_pos and lite_pos are separate interfaces.

## Baseline and Findings

The existing resolution work remains the baseline. ui/responsive_utils.py
defines a 56px header, 232/72px sidebar, 12/10px content margins and 8px
content spacing. Reuse these constants instead of creating another profile.

The existing design system is the implementation home:
ui/design_system/theme.py, stylesheet.py, buttons.py, search.py, table.py,
icon.py and dialog_styles.py. app/application.py applies the saved theme
through ui/themes/theme_manager.py.

Source inspection found these migration priorities, not confirmed screen bugs:

| Finding | Evidence | Follow-up |
| --- | --- | --- |
| Local styles can override shared tokens | ProductsPage, Settings Center and Sales product_grid define their own stylesheets | Migrate affected controls during their page phase |
| Table density differs | stylesheet.py uses 7/10px cell padding; table.py uses 8/12px and larger header padding | One compact table treatment, verified with Myanmar text |
| Focus can change control geometry | stylesheet.py changes input/combo borders from 1px to 2px | Reserve border space or compensate padding; verify focus size |
| Button heights include padding | Global button min-height is 28px plus 8px vertical padding and borders | Measure outer Qt geometry before standardizing height |
| Existing colors need readability review | Light text_muted is #b2bec3; theme contains separate semantic palettes | Do not use disabled/muted color for required information |
| Fixed window minimum is not physical screen size | main_window_ui.py clamps minimum to supplied window dimensions | Verify availableGeometry, taskbar and scaling, not only 1366x768 constants |

## Screen Inventory and Ownership

Registered pages are from main_window_ui.py page_definitions. Permissions and
lazy loading must remain functional during migration.

| Surface | Implementation | Refresh phase |
| --- | --- | --- |
| Header, sidebar, navigation, status | ui/main_window/ | 2 |
| Sales and checkout | ui/sales_page/ | 3 |
| Restaurant and kitchen workflows | ui/restaurant_page.py | 3 |
| Products and categories | ui/products_page/ | 4 |
| Discounts | ui/discount_page/ | 4 |
| Inventory and stock actions | ui/inventory_page/ | 4 |
| Receipts | ui/receipts_page/ | 4 |
| Customers and ledger | ui/customer_page/ (active page builder) | 4 |
| Expense | ui/expense/ | 4 |
| Employees | ui/employee_page.py | 4 |
| Suppliers and supplier ledger | Inventory-related dialogs; trace action entry points during phase 4 | 4 |
| Dashboard | ui/dashboard/ | 5 |
| Sales Summary and reports | ui/sales_summary/ and report dialogs | 5 |
| AI Pages | ui/ai_pages/ | 5 |
| Settings and secondary dialogs | ui/settings/ and main_window_menus.py actions | 5 |
| End-to-end screen and workflow QA | All migrated surfaces | 6 |

## Design Specification

All pixel measurements below are Qt logical pixels, not physical display pixels.
These are migration targets; existing controls have not all adopted them yet.

| Element | Standard |
| --- | --- |
| Typography | Existing Segoe UI/Myanmar fallback; body 10pt, secondary 9pt, page title 14pt semibold; no width-based font scaling |
| Spacing | Existing 4, 6, 8, 12, 16, 20, 24 scale; 8px control gaps, 12-16px section gaps |
| Shell | Keep existing compact constants; content expands on wider windows |
| Controls | Target 36px outer height; allow expansion for font metrics/scaling; 40px for prominent checkout action |
| Icon actions | 36px square target, centered 18px icon, tooltip and accessible name; use existing icon provider |
| Inputs | Labels above inputs; search expands; aligned filter/action baselines |
| Tables | Start at 36px rows, grow for multiline/Myanmar text; right-align amounts; secondary columns may scroll |
| Radius | Controls 6px, repeated cards at most 8px; unframed page sections |
| Colors | Existing theme roles; neutral surfaces, primary for actions/selection, semantic status colors with text/icon |
| Focus | Visible keyboard focus without resizing or shifting content |
| Actions | One clear primary action per context; secondary actions grouped; destructive action separate |
| Product tiles | Stable image area and reserved name/category/price space; increase columns with available content width |
| Dialogs | Fit available screen geometry; scroll form body; keep Save/Cancel reachable |

Text and price must never be vertically clipped. Elided names need a way to
read the full value. Normal text should reach 4.5:1 contrast; large text and
essential control boundaries should reach 3:1. Check both themes before
changing shared colors. Do not communicate stock/payment/error state by color
alone. Loading, empty results and failures require distinct states; retain
entered data on recoverable errors.

## Resolution and QA Contract

1366x768 is the physical-screen baseline at 100% Windows scaling. Window title
bar and taskbar reduce usable content height. Test maximized available geometry
as well as restored windows. Higher scaling reduces logical workspace and must
be tested separately, without assuming that a 1366px minimum guarantees fit.

| Physical screen | Scaling | Required checks |
| --- | --- | --- |
| 1366x768 | 100% | All primary actions reachable, internal scrolling, no page-level horizontal overflow |
| 1366x768 | 125% | Available-area fitting, dialog actions and navigation reachable; record remaining limits |
| 1920x1080 | 100%, 125%, 150% | Readable text, responsive tables and Sales split |
| 2560x1440 | 100%, 150% | More usable content, no oversized empty sections |
| 3840x2160 | 200% | Font/icon clarity, logical sizing, no clipping |

Each page phase must exercise populated, empty, loading, error, long Myanmar
text and keyboard focus states where applicable. Check permission-limited
navigation and Light/Dark themes. Sales QA includes adding a product, quantity,
discount, payment and receipt. Inventory QA includes variant selection and
movement history using test data. Use an isolated test database for writes.

## Completion Gates

1. Phase 1: source inventory, migration risks and design standards recorded.
2. Phase 2: shell/shared controls visually verified at baseline and Full HD.
3. Phase 3: complete sale and restaurant workflow verified with test data.
4. Phase 4: management filters, tables and forms verified at baseline.
5. Phase 5: reports/settings/dialogs verified with reachable actions.
6. Phase 6: resolution matrix and workflow results recorded; unresolved issues
   explicitly listed before calling the overall refresh complete.

For each implementation phase, record changed surfaces, checks performed,
remaining visual limitations and commit ID. Commit/push completed changes.
Phase 1 is documentation only: no runtime appearance change is claimed and no
live application or database workflow was exercised during this source audit.
