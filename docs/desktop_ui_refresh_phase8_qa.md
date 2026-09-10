# Desktop UI Refresh Phase 8

Status: automated workflow checks complete; physical-device and full business
acceptance remain pending. This is not a production release sign-off.

## Changes

- Added `--workflows` to the disposable desktop QA runner. Connections inside its
  temporary directory can use separate databases for backup/restore checks; all
  other application database paths remain redirected to the QA database.
- Added desktop cash checkout/refund, payment rejection, rollback, permission
  rejection, scanner submission, and network receipt-routing tests.
- Added backup/restore tests for committed WAL data and corrupt input rejection.
- Fixed desktop restore to reject a failing SQLite integrity check before
  closing application connections or overwriting the target database. Previously
  a validation exception was logged and restore continued anyway. Automatic
  repair is no longer attempted on the input backup by this restore path.

## Results

On 2026-09-10:

`python tests/run_desktop_qa.py --workflows --shell --platform windows`

33 tests passed, including the prior layout suite and 11-page native shell test.
The intentional `QA write failure` log exercises transaction rollback and is
expected. `git diff --check` passed.

The shop database SHA256 before and after testing was unchanged:
`28CF30B60FAB057B668172D58059740F4FF96BA0249F6C525DB053BBA3E670AC`.
No live sales, stock updates, restore, print jobs, or cart-backup deletion were
performed. Database tests used temporary files; network printing was mocked.

## Coverage Boundaries

- The real desktop checkout, stock deduction, sale-item persistence, and refund
  methods execute against temporary SQLite storage. Widget inputs, confirmation
  dialogs, completion UI, and post-checkout resets use test doubles.
- A cash sale deducts two units, preserves batch identity, and returns both on
  refund. A second refund is rejected. Underpayment and empty carts are rejected.
- Injected sale-item failure rolls back the sale and stock movement and keeps
  the cart backup. Permission rejection is tested with a mocked permission result,
  not a full cashier session.
- Existing variant stock reversal and batch allocation/restoration tests run in
  the same command. These are not full variant checkout-to-refund UI tests.
- Network receipt success/error routing is mocked. Failure leaves the sale
  completed and does not invoke a local printer. Queue delivery is not verified.
- Scanner submission checks leading zeros, trimmed input, clearing, and stopping
  the search timer. USB input timing and actual product selection remain untested.
- Backup uses the desktop SQLite file helpers with explicit disposable paths.
  Connection shutdown is mocked during restore. Archive images, PostgreSQL,
  existing-target locking, and restart/reopen acceptance remain untested.

## Manual Acceptance Checklist

- [ ] Cashier/admin login and role-specific actions at physical 1366x768.
- [ ] Actual cash, credit, partial-payment, discount, tax, and points workflows.
- [ ] Variant sale/refund with multiple batches and locations.
- [ ] Real scanner: repeated scans, unknown codes, and leading-zero codes.
- [ ] Receipt printer: Myanmar text, paper width, cutting, offline/retry, drawer.
- [ ] Backup archive with product images restored to a disposable app installation.
- [ ] Representative shop-sized data, searches, paging, and prolonged use.

Phase 9 continues source-only QA and fixes; EXE/release work is excluded per the
user's updated scope. See `desktop_ui_refresh_phase9_qa.md` for results and the
remaining manual checks.
