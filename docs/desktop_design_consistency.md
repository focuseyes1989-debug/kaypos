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
Remaining local tab styles include Employees, Expense, AI, Restaurant, and report
dialogs; specialized login, payment keypad, and print dialogs also require
individual visual review. Do not globally erase their styles or fixed geometry:
that would remove semantic states and can clip specialized controls.

New screens should use the shared components and helpers. Existing local styles
should migrate screen by screen with long Myanmar labels, theme switching,
keyboard actions, and 1366x768 client-area checks before being marked complete.
