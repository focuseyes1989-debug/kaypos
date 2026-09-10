# Desktop UI Refresh: Phase 6 QA

Date: 2026-09-10
Result: automated checks passed; live acceptance remains open.

## Reproduce

Run `python tests/run_desktop_qa.py` from the repository root.
The runner redirects SQLite connections to temporary storage before application
imports and creates the real schema there. It does not run main.py or submit
sales. Application imports can still initialize non-database utilities; this
is database isolation, not a filesystem/network sandbox.

## Results

| QT_SCALE_FACTOR | Tests | Result |
| --- | --- | --- |
| 1 | 15 | Passed |
| 1.25 | 15 | Passed |
| 1.5 | 15 | Passed |
| 2 | 15 | Passed |

All 60 executions passed. The shop database SHA256 was identical before and
after this run. Scaling factors do not emulate Windows taskbar geometry or
automatically shrink the tests' logical workspace dimensions.

Coverage: shell constants, focus geometry, maximum payment amount, management
search/actions, employee toolbar wrapping, Dashboard card containment, chart
scrolling, Settings cards/navigation, and real default Settings page construction
at 1100x620 using the temporary schema. Permission-gated Backup/Users pages are
not included in the default Settings integration test.

Actual Sales/Restaurant Sale Details builders are tested with fixture controls:
Cancel retains the old discount, OK applies the new discount and recalculates,
and the footer remains reachable at 460x360. This is not an end-to-end sale.

## Release Limits

No automated failure required a production UI change in this phase. Tests of
outer geometry do not establish every populated label's readability. Some
data refresh and AI widgets remain stubbed in component tests.

Still unverified:

- Physical 1366x768 Windows maximized/restored behavior, taskbar and display
  scaling; Full HD and higher-resolution live desktop sessions.
- Complete sale/receipt, held sale, credit, inventory reversal and Restaurant
  settlement against practice data.
- Printer/cash drawer, attendance device and AI network responses.
- All permission-limited roles and populated Backup/Users pages.

These are open acceptance checks, not passing results. The overall UI refresh
must not be described as fully QA-approved on the basis of this run.
