# Desktop UI Refresh Phase 9: Source-Only QA

Per the user's request, this phase excludes EXE builds, packaging, version bumps,
and release publishing. It continues desktop workflow hardening for source use.

## Fix

Desktop checkout previously caught any sale-item insertion error and retried
without product, variant, or batch identity. This could report a successful sale
while losing the information needed for a correct stock refund.

Removed that fallback. The existing checkout transaction now rolls back when
the full sale-item record cannot be saved. Normal schema initialization already
adds these columns; an incomplete migration must no longer silently downgrade
the receipt data.

A database-trigger regression test failed before the fix (checkout returned a
successful sale despite the rejected metadata) and passes afterward. It verifies
that the sale and stock roll back and the cart backup is not deleted.

## Additional Checks

- Variant checkout splits two units across Shop/batch A and Warehouse/batch B.
  Refund restores the original batch ledger and product/variant stock totals.
- Credit checkout creates a credit record. Partial payment leaves the expected
  balance; overpayment is rejected; final payment clears the customer balance.
  Credit-limit approval is mocked, so this is not a credit-limit policy test.

## Results (2026-09-10)

- `python tests/run_desktop_qa.py --workflows --shell --platform windows`:
  36 tests passed, including 11 real MainWindow pages and maximize/restore.
- `python tests/run_desktop_qa.py --workflows` with `QT_SCALE_FACTOR=1.25`:
  35 tests passed using the offscreen Qt platform.
- Same offscreen command with `QT_SCALE_FACTOR=1.5`: 35 tests passed.
- `git diff --check`: passed.

Intentional write-failure error logs belong to rollback tests. Transaction inputs
and dialogs use test doubles; these are not complete mouse-driven workflows.
The physical monitor resolution and Windows display scaling were not changed.

The live database SHA256 remained unchanged before and after testing:
`28CF30B60FAB057B668172D58059740F4FF96BA0249F6C525DB053BBA3E670AC`.

## Still Requires Manual Testing

Real printer/scanner behavior, physical 1366x768 operation, full cashier/admin
sessions, discounts/tax/points interactions, credit refunds, archive restore with
images and app restart, PostgreSQL, and shop-sized data remain unverified.
No EXE or release is needed to perform those checks. Use a disposable source-app
installation for transaction and restore acceptance, not the live shop database.
