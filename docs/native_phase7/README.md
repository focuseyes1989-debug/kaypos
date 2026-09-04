# KAY POS Native — Phase 7

Date: 2026-09-04. Status: **core implementation delivered; full Phase 7 parity remains open** (see the remaining work below).

The Native app uses the existing POS Lite server at `https://192.168.110.112:8000`. Original KAY POS, POS Lite and Service Job Client entry points remain available. Source changes have not been committed/pushed or installed on the Server PC. No executable was built.

## Implemented

| Area | Native functionality |
| --- | --- |
| Employees | Employee profiles and account links; photo replacement; shifts and effective assignments; dated attendance corrections; leave creation/review; payroll creation/payment; portable document upload/download; salary advances/repayment; commission rules/performance; cash sessions |
| Settings | Shared tax/discount/loyalty, receipt text/shop identity and logo/QR images, regional, performance and customer-display YouTube URL settings |
| Receipt printing | Native-only preferences per Windows account for an installed printer, 58mm/80mm/A4 paper and 203/300/600 dpi; standard Print/PDF destination confirmation |
| Network printing / drawer | Explicit receipt PDF queue through the existing Printer Server and Agent; encrypted connection/recovery; online printer discovery; confirmed manual drawer pulse on this PC or existing POS Server |
| Database diagnostics | Read-only server connection/schema readiness checks, optional bounded SQLite quick_check, PostgreSQL metadata checks and local diagnostic JSON export |
| Users and roles | Create accounts, reset passwords, edit names/roles/active status, and create/edit custom roles. Deactivation preserves history. Built-in roles are maintained by the original POS; create a custom role for custom permissions. |
| ZKTeco | Device configuration, employee mappings, explicit connection check and attendance sync. Device reads happen before the database write transaction. |
| Backup | Server snapshots, checksum-verified downloads, and SQLite restoration into a separate server test copy. PostgreSQL snapshot support uses server `pg_dump`; live PostgreSQL validation remains pending. |
| AI Pages | Shared Myanmar/English intent parsing, all 17 Native summary/report shortcuts with dates, previous-period follow-up, all result tables and full selected-table CSV export; product lookup and permission-checked navigation. |
| Integrations | Telegram/cloud health and read-only connection tests; administrator Telegram and cloud server-file editors with recoverable credential/enable settings; shared YouTube URL editing. No Native listener or sync scheduler is started. |
| Activity log | Date/actor/action filtering, paging and CSV export; Native mutations record the server-confirmed actor and timestamp in the existing activity table. |

Employee/settings tables support filtering and CSV export. Detailed fields remain available below compact tables. Employee forms scroll, so their Save/Cancel buttons remain accessible at the minimum display size. Light/Dark screenshots were reviewed at a simulated 1366×768 screen with a 1366×728 work area.

## Transaction and compatibility behavior

- Native employee operations reuse `services/employee_service.py` through a request-local borrowed connection. Legacy callers still own their normal connections. Salary expense, employee mutation, audit and recovery result commit together.
- UUID commands are recorded in `native_admin_requests`. Repeating the same confirmed payroll payment/advance repayment does not repeat the mutation. Unknown transport outcomes retain the client recovery journal; confirmed validation/constraint rejections allow correction.
- Fresh server permissions, account activity and password-change requirements are checked for every request. Employee subpages check their own permissions in addition to `employees`. Account/role access changes require an administrator. The last active administrator and the current administrator's own access are protected.
- Revisions prevent silent overwrites of edited records. Employee edits preserve photo blobs, existing photo paths and device linkage. An inactive login account's existing employee link is preserved even when it is absent from active-account choices.
- Native schema preparation does not grant role permissions or rewrite an existing Morning shift. The original app's legacy migration defaults remain unchanged for ordinary legacy calls.
- Password/communication-key and attachment recovery payloads use Windows DPAPI while pending. Confirmed client journals discard credentials and uploaded file content. Passwords use the same salted PBKDF2 representation as POS Lite. APIs do not return password hashes, salts or device keys.
- ZKTeco reads one device snapshot outside the DB transaction. Before import, the server checks that the selected device and employee mappings still match. Existing punch uniqueness and manual attendance corrections are preserved. Confirmed request recovery works even if the device is subsequently offline.
- Cash-session reconciliation retains the original rule: opening cash plus completed cash sales attributed to the linked username since opening. It is not a full bank/cash-ledger reconciliation. Payroll advance deductions retain the original separate advance-repayment workflow.
- Receipt responses include shared receipt text and stored logo/QR images. Native preview escapes text and registers decoded images as local Qt document resources for preview/printing; arbitrary remote image URLs are ignored. The original receipt helper refreshes stale local images from shared database bytes.
- `ui.ai_pages` exports are now lazy. Pure parser imports do not import Qt, initialize a database, or start the legacy AI UI; public export names are retained.

## Backup operation

Backups are stored under `database/native_backups` on the **server**, with UUID filenames. SQLite uses its online backup API rather than copying a possibly incomplete WAL database file. A server OS file lock serializes duplicate snapshot requests. Downloads are streamed into a unique temporary file, verified against size/SHA-256, then moved into place.

“Restore separate copy” creates `database/native_backups/restore_rehearsals/<backup name>` and checks SQLite integrity. It never replaces the running POS database. The copied database uses the existing application schema, including stored image blobs. External image/document files need a separate file backup; this is not the original `.zaybackup` package exporter.

## Employee attachments and receipt images

- Employees → select employee → **Photo…** uploads/replaces, previews, downloads or removes the employee photo. Documents → create/select a document record → **File…** provides the same controls for its attachment.
- Settings → Receipt → **Logo / QR…** selects the shared receipt image. Receipt QR payment name remains in Edit settings. Native receipt preview and Print/PDF use the stored image.
- Uploads accept PNG/JPEG/WebP, plus PDF for employee documents, with an 8 MB limit. Images are decoded, stripped of metadata and normalized to PNG, at most 1600×1600; inputs exceeding 16 million pixels are rejected. PDF checks validate basic file markers, not document contents. Downloads are explicit; PDF files are not automatically opened.
- Photos use the existing employee blob; logo/QR use the existing settings data URLs. Documents use `native_employee_documents` linked to the existing document record, so bytes travel with database snapshots. The original document list retains the filename reference; portable downloading is provided by Native. Existing local-only file references are displayed but never opened on the server or automatically imported.
- Fresh permissions, attachment revisions, atomic audit and UUID recovery apply to uploads/removals. An unresolved upload is visible on administration pages and uses **Recover pending change** after reconnecting. Removing an attachment retains its employee/document record. Windows DPAPI protects pending local upload bytes.

PostgreSQL snapshots require matching `pg_dump` client tools on the server. The active connection supplies the target and credentials through the child environment, not command-line arguments. Restoring a PostgreSQL dump requires a separately provisioned test database and `pg_restore`; Native does not replace a live server database.

Native starts **zero** backup, cloud-sync or Telegram schedulers. Existing server/original-app owners retain those responsibilities. The integration status page reports configuration, not a verified count of running processes.

## Local receipt printer settings

Settings → **Receipt printer settings · this PC…** saves printer name, paper and quality in the Native configuration, not the shared server database. Receipt printing from Sales, Receipts and report detail uses these preferences. Missing saved printers remain visible in settings; printing reports the missing device and opens the standard destination dialog for a new choice. No print is sent merely by saving settings.

Roll paper uses a 297mm page length and 3mm margins; long receipts paginate. The final driver/dialog may constrain supported paper and margins, so physical thermal-printer acceptance is still required. With no selected device the print dialog starts from PDF, avoiding unsupported paper substitution by the default Windows driver. Report and kitchen printing retain their existing behavior.

## Network receipt PDF and cash drawer

- Settings → **Network printer / recover print…** configures the printer-server origin, client API key, certificate verification, Agent ID and printer. **Find online printers** reads the existing registry; no enrollment, scheduler or test print is started. Connection editing requires `edit_settings`. The API key is protected with Windows DPAPI in Native configuration.
- Receipt preview → **Network PDF…** generates the same Qt receipt document as a PDF, preserving Myanmar text and receipt images, and explicitly queues one copy after destination confirmation. This requires the updated POS Server `/api/native/printing/authorize` endpoint plus the existing Printer Server PDF upload endpoint and a PDF-capable Agent. Queue status is not physical-print confirmation; inspect Printer Server for failed/completed jobs.
- Before upload, Native durably stores the PDF, destination and UUID in a Windows-encrypted journal scoped to the POS server/account. On a lost response, close/reopen and use **Recover pending print** from Settings or any receipt's Network PDF dialog. Recovery retains the original PDF/destination/UUID; an expired API key can be replaced. Confirmed journals discard the PDF and API key. A first confirmed rejection permits correction; rejection after an unknown attempt retains the original request because it may already be queued. No automatic local fallback, duplicate copy, job retry or cancellation is issued.
- Printing is reauthorized against fresh POS account permissions before network submission/recovery. Transport uses the printer client API key, explicit TLS verification choice and disabled HTTP redirects. Errors omit credential-bearing request details.
- In **Receipt printer settings · this PC…**, choose **Cash drawer target**: existing POS Server printer (default, preserving prior behavior) or the selected Windows printer on this PC. Sales → **Open cash drawer…** confirms the actual destination. Local pulses require a fresh sales permission check, send the standard ESC/POS pulse through Windows RAW printing, check bytes written and close spooler handles. They are manual and are not automatically retried after uncertain failures. Remote Printer Agent drawer pulses and automatic post-sale opening are not added.
- No physical print, drawer pulse, live network queue submission or printer credential change was performed during development. Deployment must include the new POS permission endpoint before network/local-drawer testing.

## Assistant report continuation

AI Pages now offers a report selector and start/end dates for all Native Sales Summary and Reports views. **Run report** sends an allowlisted command such as `report summary/hourly 2026-09-01 2026-09-04`; free text never becomes SQL. English report names such as `hourly sales today`, `payment types yesterday`, `stock movements 2026-09-01 2026-09-04` and `monthly profit this month` also work. Existing Myanmar prompts and navigation remain available.

The result table selector exposes every table returned by the report, including secondary credit/collection or financial tables previously omitted from assistant display. Each preview shows at most 200 rows with a visible row-count notice. **Export selected table CSV…** exports every row of that selected table from the captured snapshot, including period/snapshot metadata and spreadsheet-formula escaping. **Previous period** reruns the same view for the preceding equal-length date range. Current-state inventory/credit values remain current-state where the report's notes say so; changing dates does not invent historical stock snapshots.

Fresh `ai_pages` plus the report's own permissions apply to each question. Invalid report names, dates and reversed ranges are rejected. Scheduled digests, saved questions, advanced diagnostics and other legacy AI workflows remain open.

## Database diagnostics

Settings → **Server database diagnostics…** → **Run checks** reads the connected POS Server, requiring fresh `settings` and `edit_settings` permissions. The response identifies SQLite/PostgreSQL version and checks a defined subset of core and optional Native tables/columns. **Needs attention** means required columns are missing. **Not initialized** means optional feature tables have not yet been provisioned. No migration, schema preparation, row edits, database selection changes, reset or restore runs here.

The optional **Include SQLite quick_check** checkbox performs a read-only scan with at most 20 reported problems and a 10-second execution budget; a connection without a progress-handler capability cannot run this scan. This check excludes foreign-key checks and full index consistency verification. Large databases may require offline maintenance. PostgreSQL uses a read-only transaction and bounded statement execution to inspect metadata; its physical integrity/restore status is explicitly **Not supported**, not passed.

**Export diagnostic JSON…** saves the displayed snapshot locally. Reports contain expected table/column metadata and check outcomes, not business records, passwords, connection strings or database paths. Server failures return a generic diagnostic error without credential-bearing exception details. Update/restart the POS Server to provide `/api/native/database/diagnostics` before real-device acceptance.

## Telegram server configuration

Integrations → **Telegram server settings…** edits the Telegram entries in the server's `.env` file. Fresh administrator access plus `settings`/`edit_settings` is required. The editor shows stored-file enable/listener flags and Chat ID, whether a token is configured, and the names of process/environment overrides. It never returns the existing token. Leave the replacement field blank to preserve it, supply a replacement, or explicitly clear it while disabled. Numeric Chat IDs and `@channel_name` are supported.

This edits file configuration, not necessarily the effective configuration of an already-running process. Existing process/system environment values take precedence. Apply/restart through the existing server/listener owner and check effective health afterward; externally defined overrides may continue to take precedence after restart. Native does not start/stop a listener or send a Telegram message. The original settings UI retains its existing listener lifecycle behavior.

Saves preserve other `.env` entries/comments and use an atomic file replacement under a shared cross-process configuration lock. A server-side recovery marker contains only request ownership and before/after fingerprints, not tokens. File changes and DB audit cannot be one filesystem/database transaction: the marker keeps interrupted work recoverable until audit and UUID result commit. **Recover Telegram save** repeats the same request from the originating account/PC; file changes are not reapplied and audit is not duplicated after a confirmed commit. Windows DPAPI protects a pending replacement token in the client journal; confirmed journals remove it. Tokens are absent from DB audit/request results.

While a recovery marker exists, the original Telegram writer, generic legacy environment writers and other Native configuration edits are blocked from overwriting it. If someone manually edits the server `.env` during recovery, or the original client journal is lost, administrator review is required; Native does not overwrite an unexpected file state. `.env` and `.env.telegram.*` recovery/lock/temp files are ignored by Git. The server-local configuration is separate from Native database-only snapshots.

Only temporary configuration files and disposable databases were edited in development. No live token, Chat ID, environment variable, listener, message or server restart was changed.

## Cloud server configuration

Integrations → **Cloud server settings…** lets administrators with `settings`/`edit_settings` edit the server-file cloud enable flag, PostgreSQL URL and sync interval (60–86400 seconds). The existing URL is never returned: the editor shows only host, port and database. A blank replacement preserves it; replacement and explicit removal are supported. The destination validator rejects obvious matches to the configured primary host/port/database and target overrides in URL query parameters; it cannot establish whether DNS aliases refer to the same database.

Saving stages `.env` configuration only. It does not connect to cloud storage, sync, pull, update process environment or start a scheduler. The existing cloud owner must apply/reload these settings; process/system overrides may still take precedence. Connection tests on the integration page check effective process settings, not necessarily the newly saved file.

Cloud saves reuse the atomic file/DB-audit recovery protocol above. **Recover cloud save** resumes the originating account/PC's request. Windows DPAPI encrypts pending replacement URLs; confirmed journals discard them. Telegram, cloud and generic legacy environment writers share the same lock and recovery marker (the `.env.telegram.*` filenames are retained for compatibility), preventing one writer from overwriting an unfinished save. Server `.env` configuration is not included in database-only snapshots.

Cloud tests cover masked reads, preservation of unrelated settings, UUID replay, stale revisions, audit-failure recovery, shared legacy-writer blocking, validation and primary-target checks, fresh permissions, route/OpenAPI registration, encrypted journals and unchanged process environment. All use temporary files and disposable databases; no cloud connection or transfer was performed.

## Remaining Phase 7 work

These are source/parity gaps, distinct from hardware acceptance:

1. Advanced original AI queries, diagnostics, saved questions/digests and remaining follow-up actions; Native summary/report views and previous-period queries are implemented. WebEngine playback remains in the existing customer display.
2. Live Telegram listener lifecycle controls and explicit summary/backup delivery remain with the original application/server owner. Native server-file configuration and health checks are implemented. Cloud server-file credential configuration is implemented; sync/pull controls remain open. No Telegram messages or cloud uploads were sent during development.
3. Full settings-center parity: database connection administration/maintenance and launcher update controls; automatic post-sale network printing/drawer preferences and remote Agent drawer pulses. Read-only database diagnostics, local printer/paper/quality, explicit network receipt PDF and manual local/server drawer controls are implemented; connection and native appearance remain available at login/Appearance.
4. Complete portable backup packages for external files, PostgreSQL restore rehearsal and production maintenance-window restore. SQLite restore-copy proof includes uploaded document bytes; automatic schedules remain owned by existing applications.
5. Optional Native service-job companion page (N24) is not added. Staff Start/Complete remains in Service Job Client and collection/payment-note behavior is unchanged.

Deployment/acceptance still needed: update/restart the real POS Server, test PostgreSQL concurrency and backup tools, exercise the physical ZKTeco device, confirm configured Telegram/cloud connectivity, and perform original POS/POS Lite coexistence and Windows DPI/printer checks. Phase 8 release sign-off should follow completion/acceptance of the applicable Phase 7 gaps.

## Validation

The following suite passes **165 tests** (20 Phase 7 core tests, 6 attachment tests, 3 local printing tests, 10 network/drawer tests, 4 assistant-report tests, 6 database-diagnostic tests, 8 Telegram configuration tests, 7 cloud configuration tests, 2 original environment-loader tests, 94 earlier Native/launcher tests and 5 original Burmese-parser tests):

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m unittest tests.test_native_pos_cloud_config tests.test_env_loader tests.test_native_pos_telegram tests.test_native_pos_database tests.test_native_pos_assistant_reports tests.test_native_pos_network_print tests.test_native_pos_printing tests.test_native_pos_files tests.test_native_pos_phase7 tests.test_native_pos_phase6 tests.test_native_pos_phase5 tests.test_native_pos_phase4 tests.test_native_pos_phase3 tests.test_native_pos_phase2 tests.test_native_pos_server tests.test_launcher tests.test_ai_burmese_normalizer
python docs/native_phase7/render_preview.py
```

Evidence covers concurrent/retried salary payment, atomic audit rollback, duplicate attendance checks, retained manual corrections, advance limits, account protection/password hashing, custom-role round trips, fresh permissions, settings revisions, shared receipt text, device deduplication, concurrent DB writes during device reads, recovery while the device is offline, WAL snapshot fidelity, restore-copy checks, path/checksum guards, DPAPI recovery, reference-link preservation and minimum-screen layout.

Tests use disposable SQLite fixtures and mocked device/integration adapters. An initial parser test exposed an eager legacy package import that opened a local database connection and ran its default-role check (the log reported those roles already up to date). That import path was removed. A fresh-process regression guard now rejects any database or Qt bootstrap during parser/server-assistant import. No business mutation was intentionally run against the live/local POS database, and no live server, physical printer/device or external message/upload was exercised.

Attachment tests additionally cover image normalization, stale edits/replay, invalid files, permission revocation, audit rollback, document bytes in restored backups, shared receipt images, stale legacy image caches and encrypted upload recovery.

Printing tests verify local preference round trips, preserved server configuration, unavailable-printer handling, malformed preferences and PDF generation at each configured paper width. No physical jobs are sent.

Network/drawer tests cover lost-response recovery after dialog restart, retained UUID/PDF, first rejection versus rejected recovery, encrypted credentials, read-only connection controls, discovery/redirect handling, fresh server authorization, exact drawer pulse bytes and cleanup after partial writes/start failures. HTTP and Windows spooler are mocked.

Assistant tests exercise all 17 report commands on a disposable database, period/view preservation, invalid input and fresh permissions, secondary tables, preview truncation versus full CSV export, formula escaping and previous-period/date-selector commands.

Database tests compare complete SQLite schema/data dumps before and after checks, verify missing-column reporting without repair, fresh authorization and sanitized errors, interrupted-scan cleanup, PostgreSQL read-only SQL via a protocol stub, and diagnostic JSON export. Live PostgreSQL diagnostics remain unverified.

Telegram tests cover masked reads, preserved unrelated config/token, replacement/removal validation, stale revisions, fresh administrator access, busy/unknown responses, file/audit failures, commit-before-cleanup recovery, manual-edit conflicts, legacy writer compatibility/blocking and DPAPI recovery. The legacy save function is tested in isolation without importing its database/listener bootstrap.

Preview artifacts: `employees-light.png`, `employees-dark.png`, `payroll-light.png`, `settings-light.png`, `users-light.png`, `employee-form.png`, `employee-photo.png`, `receipt-image.png`, `printer-settings.png`, `network-printer.png`, `assistant-reports.png`, `database-diagnostics.png`, `telegram-settings.png`, `cloud-settings.png`.
