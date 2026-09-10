# Desktop Component Consistency

Shared desktop controls now use `ui/design_system/metrics.py`. Sizes are logical
pixels and remain independent of screen resolution and DPI scaling.

| Component | Contract |
| --- | --- |
| Normal action | 38px target height, 9pt text, 6px radius |
| Compact action | 32px target; specialized dense controls may override |
| Dialog | 16px outer padding, 8px gaps; size follows content |
| Table | 38px default row, 4px/10px cell padding |
| Summary card | 120px minimum; 140px with progress; 8px radius |
| Tab | Shared underline selection, 9pt text, 8px/12px padding |

Applied to the application stylesheet, design-system buttons/table/cards/dialog,
ModernButton, BaseFormDialog, message-box action sizing, legacy dialog helpers,
dashboard/summary/expense cards, and Inventory/Receipts/Sales Summary tabs.
Semantic primary/danger colors and existing confirmation/default-button behavior
remain intact. Cards can grow for content; product tiles and chart panels are not
forced into KPI-card dimensions. No transaction logic or EXE release changes.

## Validation

The native Windows isolated shell/workflow suite passes 38 tests. Component
previews were inspected in Light and Dark. Offscreen 125% scaling passes 37
tests without the shell. The preview exposed a gray dark-mode table header and
an old dashboard-card palette; both were moved to theme-aware colors.

## Migration Boundary

This is the shared-component migration, not an assertion that every historical
screen is visually identical. Per-widget styles override application QSS in Qt.
The follow-up migrates Employees, Expense, AI pages/assistant, Restaurant,
Category Form, and report dialogs to the shared tab stylesheet. Specialized
login, payment keypad, and print dialogs still require individual visual review.
Do not globally erase their styles or fixed geometry:
that would remove semantic states and can clip specialized controls.

New screens should use the shared components and helpers. Existing local styles
should migrate screen by screen with long Myanmar labels, theme switching,
keyboard actions, and 1366x768 client-area checks before being marked complete.

## Follow-Up Results

- Removed duplicated tab QSS rather than stacking a second style over it.
- Profit Report tables now use the shared legacy table helper and 38px rows.
- Base report Close action is bottom-right, with shared outer padding.
- Removed the report-only 85px fixed summary-card height. Report cards use the
  shared minimum size and flat theme surface; AI metric cards use the same
  minimum height and padding. Chart and kitchen ticket dimensions remain distinct.
- Native Windows isolated suite: 40 tests passed. Offscreen at 125%: 39 passed.
- Theme-refresh tests compare migrated page styles in Light/Dark/Light order.
  A real base report dialog checks footer placement, card height, and Close.
  Style-method tests use lightweight widget fixtures, not full report workers.
- Light/Dark report previews were inspected. Existing shell checks cover 11
  pages; a full restaurant kitchen workflow is not included in that shell suite.
- No database schema, business logic, EXE packaging, or release changes.
