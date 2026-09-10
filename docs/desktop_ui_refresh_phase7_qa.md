# Desktop UI Refresh Phase 7

## Scope

Native Windows Qt smoke testing of the real desktop MainWindow with an isolated
temporary SQLite database. This phase targets window sizing and layout, not
production transaction acceptance.

## Fixes

- Separate the 1366x768 physical-screen baseline from the 1024x600 minimum client
  area so Windows borders and the taskbar do not force content below the screen.
- Keep the shared header solid when the theme is refreshed.
- Keep the header clock white and readable in the light theme.
- Align management toolbar actions to the left instead of spreading them out.

## Verification

Command: `python -X faulthandler tests/run_desktop_qa.py --shell --platform windows`

Result: 16 tests passed on 2026-09-10, including the real MainWindow shell test.
The shell test loads Sales, Dashboard, Sales Summary, Products, Customers,
Inventory, Receipts, Expenses, AI, Discounts, and Employees. Each page is opened
at client sizes 1350x680, 1366x700, and 1920x1000. Native maximize and restore
also pass. Window geometry assertions verify that minimum sizes do not prevent
the requested dimensions; they do not prove every child control is unclipped.

Sales, Products, and Employees screenshots were visually inspected. Existing
focused tests additionally cover payment, reports, settings, wrapping toolbars,
and sale-details dialogs. The shell uses sample products and a customer, not
live business records. Cart file loading/saving and dashboard digests are mocked.

## Remaining Acceptance Work

- Physical monitor resolution was not changed; client-size tests ran on the host
  display. Native DPI combinations need separate acceptance testing.
- Shell navigation uses an administrator account. Other roles and mode-specific
  Restaurant screens are outside this shell test.
- Warning/critical message boxes are suppressed to prevent unattended blocking;
  passing this suite does not certify the absence of application warnings.
- Real checkout, refunds, stock workflows, receipt printers, barcode scanners,
  backup/restore, and production data-volume testing remain for Phase 8.
- Final fixes and release acceptance should follow those workflow checks.
