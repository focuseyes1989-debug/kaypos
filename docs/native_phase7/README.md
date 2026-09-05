# KAY POS Native — Phase 7

Date: 2026-09-05. Status: **Phase 7 source implementation complete; physical/live acceptance moves to Phase 8** (see the boundaries below).

The Native app uses the existing POS Lite server at `https://192.168.110.112:8000`. Original KAY POS, POS Lite and Service Job Client entry points remain available. Source changes have not been committed/pushed or installed on the Server PC. No executable was built.

## Implemented

| Area | Native functionality |
| --- | --- |
| Employees | Employee profiles and account links; photo replacement; shifts and effective assignments; dated attendance corrections; leave creation/review; payroll creation/payment; portable document upload/download; salary advances/repayment; commission rules/performance; cash sessions |
| Settings | Shared tax/discount/loyalty, receipt text/shop identity and logo/QR images, regional, performance and customer-display YouTube URL settings |
| Receipt printing | Native-only preferences per Windows account for an installed printer, 58mm/80mm/A4 paper and 203/300/600 dpi; standard Print/PDF destination confirmation; post-sale receipt display/drawer-prompt choice |
| Network printing / drawer | Explicit receipt PDF queue through the existing Printer Server and Agent; encrypted connection/recovery; online printer discovery; confirmed manual drawer pulse on this PC or existing POS Server |
| Database diagnostics | Read-only server connection/schema readiness checks, optional bounded SQLite quick_check, PostgreSQL metadata checks and local diagnostic JSON export |
| Users and roles | Create accounts, reset passwords, edit names/roles/active status, and create/edit custom roles. Deactivation preserves history. Built-in roles are maintained by the original POS; create a custom role for custom permissions. |
| ZKTeco | Device configuration, employee mappings, explicit connection check and attendance sync. Device reads happen before the database write transaction. |
| Backup | Server snapshots and managed-file ZIP packages; checksum-verified downloads; SQLite snapshot/package restoration into separate server rehearsal copies. PostgreSQL snapshot/index support uses server tools; live test-database restore is Phase 8 acceptance. |
| AI Pages | Shared Myanmar/English intent parsing, all 17 Native summary/report shortcuts with dates, previous-period follow-up, all result tables and full selected-table CSV export; product lookup and permission-checked navigation. |
| Integrations | Telegram/cloud health checks; recoverable Telegram/cloud server-file editors; explicit replay-safe one-shot cloud sync/pull; shared YouTube URL editing. Native starts no duplicate listener or sync scheduler. |
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

Fresh `ai_pages` plus the report's own permissions apply to each question. Invalid report names, dates and reversed ranges are rejected. Local saved questions, pasted-error diagnostics and on-demand sales digests are implemented. Scheduled executive digests and broader legacy AI workflows remain with the original application by design.

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

## Local error diagnostics

AI Pages → **Error diagnostics…** opens a stock Qt dialog for pasted errors/tracebacks. It reuses the original side-effect-free diagnostic rules for network failures, permission problems, database locks, duplicate values, SQL type mismatches and unclassified errors. This is rule-based guidance, not a live system inspection or repair. No server request, business query, external AI call, file save or automatic retry is performed.

Input is limited to 20,000 characters for analysis. Results contain static guidance only and never echo pasted signatures or credentials. Editing input clears stale results; closing the dialog clears both text fields and input undo history. Existing server-backed report permissions remain unchanged. Tests cover known/unknown rules, secret omission, input limits, stale-result clearing, close cleanup and minimum dialog sizing.

## Saved questions

AI Pages → **Saved questions…** supports named question creation, editing, deletion and loading (50 questions per scope; names up to 80 characters and queries up to 1,000). Loading fills the question box without executing it. Ask uses the existing authenticated server API and fresh permissions. Literal dates remain fixed; relative phrases such as `today sales` resolve when asked. Report results and diagnostic input are not automatically saved.

Bookmarks are local to this PC and scoped by backend/server/database/schema and POS account identity. Windows DPAPI encrypts each file under the Native config directory; these are not server-synced bookmarks or portable database backups. A Qt file lock and revision check reject concurrent/stale edits. Atomic replacement preserves the previous file on write failure. Corrupt or undecryptable data blocks opening rather than silently replacing it. Tests cover encryption, account/server isolation, validation, file failure/stale edits and the save/edit/load/delete flow.

## On-demand sales digest

AI Pages → **Sales digest** summarizes the selected dates from the authorized Sales Summary overview snapshot. Commands `digest daily`, `digest weekly` (Monday through today), `digest monthly` (month start through today), and `digest YYYY-MM-DD YYYY-MM-DD` are also supported and can be bookmarked. This is an English, deterministic narrative of completed invoice counts/totals, average invoice, separate refunds and comparison with the preceding equal-length period. It preserves source-report caveats and displays no percentage when the previous total is zero.

The existing server report reads both periods in one read-only transaction and rechecks `ai_pages` and `sales_summary` permissions. Comparison/daily tables, full CSV export and source-page navigation remain available. This does not create a closing record, persist a digest, schedule generation, send messages or imply cash reconciliation. Scheduled executive digests and broader dashboard narratives remain with the original application and Phase 8 acceptance.

## Package update information

Help → **Check for updates…** opens a stock Qt dialog. Only **Check now** contacts the existing Launcher GitHub version source, in a worker with the Launcher's bounded request timeout. It displays local/published package versions and plain-text release notes. Numeric major/minor/patch comparison distinguishes newer, matching and older metadata; unknown/prerelease versions require manual review. A matching package version does not establish matching source commits.

This is shared KAY POS package metadata, not a verified Native installer or the connected POS Server version. Native never downloads/executes the returned asset URL, runs Git, installs an update or restarts a process. The current shared manifest does not establish a Native release; installer/update lifecycle is a Phase 8 distribution boundary. Failed checks show a retry message without changing application files. Tests mock metadata/network operations and cover comparison, invalid metadata, explicit invocation, busy guards and literal release-note rendering.

## Verify selected backup

Backup / Restore → **Verify snapshot** checks the selected server artifact using its displayed SHA-256. Fresh `backup` permission is required. SQLite opens read-only with query-only mode, runs `quick_check(20)` with a 30-second SQL progress deadline, and reports the user-table count. PostgreSQL uses installed `pg_restore --list` with a 60-second timeout and no database target. Archive output is not returned or executed; index readability does not verify all data blocks or prove a successful restore.

The file checksum is checked before and after verification. Stale selection, corrupted SQLite files, unreadable PostgreSQL indexes and missing client tools produce errors. This operation creates no restored copy, changes no business data and starts no scheduler. Full PostgreSQL restore rehearsal remains pending; managed-file ZIP packaging is described below. Tests use disposable SQLite snapshots and mocked PostgreSQL processes, covering file/database preservation, corruption, stale checksums and fresh permission rejection.

## Database + managed-file packages

Backup / Restore → **Create backup… → Database + managed files package** creates a fresh database snapshot and a ZIP on the POS Server. It includes managed `database/images`, `logos`, `product_images` and `network_print_assets`, plus `manifest.json` with relative names, sizes and SHA-256 hashes. Native uploaded documents/photos and receipt image data already reside inside the database snapshot. Arbitrary external/client paths, `.env`, certificates and other backups are outside this package's coverage. The ZIP is a normal unencrypted backup file.

Package creation is UUID-recoverable under an OS lock. A confirmed ZIP is reused on retry rather than rebuilt from newer data; after an interrupted attempt its existing UUID database snapshot is reused. Failed package writes leave no final ZIP and retain the database snapshot. Creation permits up to 10,000 managed files and 2 GiB of source data, rejects links/reparse points and unsupported file types, and detects changes to asset inventory/size/mtime during capture. Database and files are not one atomic transaction: pause asset edits while packaging and review coverage before relying on it.

Download uses the existing whole-file checksum verification. **Verify snapshot** on a ZIP validates member names, the manifest and every member checksum without extracting files. It does not prove database restore compatibility. For SQLite packages, **Restore separate copy…** now verifies the ZIP, extracts it into a new `package_rehearsals` directory, rechecks every extracted member, runs full SQLite integrity checking and records table counts. Retry reuses the isolated copy only when its source checksum and every extracted file still match. Production files are never replaced. PostgreSQL package rehearsal and production restore require Phase 8 disposable-target/maintenance acceptance; map any legacy absolute paths before deployment.

Tests use disposable snapshots and managed-file fixtures, checking manifest coverage, file bytes, isolated restored SQLite integrity, replay, fresh permissions, limits, failure cleanup, changing assets, interrupted extraction, altered rehearsal copies, PostgreSQL rejection and tampered/unsafe archives.

## After-sale display and drawer prompt

Settings → **Receipt printer · this PC** now offers three local after-sale choices: **Show receipt** (the default and prior behavior), **Show receipt, then ask to open drawer**, and **Stay on Sales**. The preference is read only after the server confirms a complete receipt. Recovery of the same confirmed checkout follows the same selected behavior; the receipt itself remains available in the durable checkout journal and Receipts page.

The drawer option opens the existing destination-specific confirmation only after the receipt dialog closes. No drawer pulse is sent without that confirmation. A local drawer still performs fresh POS Server authorization before the Windows RAW pulse; a server drawer uses the existing authorized endpoint. Invalid saved values fall back to Show receipt. The preference is local to Native on this Windows account, alongside printer settings.

This does not automatically print paper or queue a network PDF. Automatic physical output still needs an explicit duplicate/lost-response policy; current Print/PDF, network queue recovery and manual drawer controls remain available. Tests cover preference persistence/defaulting and prove that Stay/Show receipt never invoke drawer handling while the prompt mode invokes the existing guarded flow only after receipt display.

## Explicit manual cloud operations

Integrations → **Sync to cloud…** and **Pull from cloud…** use the effective running POS Server configuration. Preflight returns only host, port, database and primary backend; credentials and URLs are never returned. The server blocks an obvious same host/port/database primary target. The enable flag remains a scheduler setting and does not disable an explicitly confirmed one-shot action.

Both actions require a fresh administrator with `settings`/`edit_settings`; pull additionally requires `backup` and `restore`. The client and server require the exact typed phrase `SYNC TO CLOUD` or `PULL FROM CLOUD`. A single server OS lock serializes operations. Before pull, Native creates its own verified server snapshot; the existing pull service may also create its legacy backup. Upserts can overwrite matching IDs, and table-level commits mean a later failure can leave a partly completed cloud operation.

The request UUID is reserved before data transfer. A completed or failed response is stored and replayed without rerunning the transfer. If the server process stops after reservation but before recording the result, recovery returns **needs review** and does not rerun. If another worker still owns the lock, the client retains its recovery journal. Results/audit contain status, table/row counts and only a backup-created boolean; service exception text, credentials and absolute backup paths are suppressed. No scheduler is started.

Tests use mocked cloud/backup adapters and disposable databases. They cover masked preflight, same-target rejection, fresh permissions, server-side typed confirmation, success/failure audit, one-shot replay, safety backup, interrupted unknown outcome, API/OpenAPI wiring and absence of live cloud traffic.

## Phase 7 source completion and boundaries

Phase 7 source scope is complete. The separate Native app covers the required employee, settings, user/role, device, backup, reporting, integrations and activity workflows while the original KAY POS, POS Lite and Service Job Client remain available.

The following stay with an existing owner or require Phase 8 acceptance rather than another Native background owner:

1. The original KAY POS owns the live Telegram command listener and scheduled executive digests. Native edits configuration and tests connectivity but does not start a duplicate listener or send unsolicited messages.
2. The existing server/original-app cloud scheduler remains the single scheduler owner. Native provides explicit manual sync/pull with recovery and does not create a second loop.
3. Physical printing remains explicit. Native does not auto-repeat paper output or drawer pulses after an uncertain response. Remote Printer Agent drawer support requires an Agent protocol addition and hardware acceptance.
4. Database connection replacement, production restore and updater installation/restart remain maintenance/deployment operations. PostgreSQL test-database restore needs a separately provisioned disposable target. Native provides diagnostics, archive inspection and SQLite rehearsals without accepting destructive production credentials.
5. Arbitrary external/client-local paths cannot be safely inferred. Managed server folders are packaged and the manifest states coverage. The optional Native Service Jobs page is unnecessary because staff Start/Complete is owned by Service Job Client and collection remains in POS Lite.

Phase 8 acceptance must update/restart the real POS Server, exercise disposable PostgreSQL and physical ZKTeco/printer hardware, verify Telegram/cloud connectivity, test original POS/POS Lite/Service Client coexistence, confirm Windows DPI behavior, and build/sign/rehearse Native distribution and rollback. No such live transfer, message, hardware pulse, production restore or deployment was performed during source development.

## Validation

The following suite passes **195 tests** (20 Phase 7 core tests, 6 attachment tests, 5 local printing/after-sale tests, 10 network/drawer tests, 4 assistant-report tests, 3 local error-diagnostic tests, 3 saved-question tests, 3 sales-digest tests, 3 update-information tests, 3 backup-verification tests, 7 backup-package/rehearsal tests, 6 database-diagnostic tests, 8 Telegram configuration tests, 7 cloud configuration tests, 6 manual cloud-operation tests, 2 original environment-loader tests, 94 earlier Native/launcher tests and 5 original Burmese-parser tests):

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m unittest tests.test_native_pos_cloud_operations tests.test_native_pos_backup_package tests.test_native_pos_backup_verify tests.test_native_pos_updates tests.test_native_pos_sales_digest tests.test_native_pos_saved_questions tests.test_native_pos_error_diagnostics tests.test_native_pos_cloud_config tests.test_env_loader tests.test_native_pos_telegram tests.test_native_pos_database tests.test_native_pos_assistant_reports tests.test_native_pos_network_print tests.test_native_pos_printing tests.test_native_pos_files tests.test_native_pos_phase7 tests.test_native_pos_phase6 tests.test_native_pos_phase5 tests.test_native_pos_phase4 tests.test_native_pos_phase3 tests.test_native_pos_phase2 tests.test_native_pos_server tests.test_launcher tests.test_ai_burmese_normalizer
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

Preview artifacts: `employees-light.png`, `employees-dark.png`, `payroll-light.png`, `settings-light.png`, `users-light.png`, `employee-form.png`, `employee-photo.png`, `receipt-image.png`, `printer-settings.png`, `network-printer.png`, `assistant-reports.png`, `database-diagnostics.png`, `telegram-settings.png`, `cloud-settings.png`, `error-diagnostics.png`, `saved-questions.png`, `sales-digest.png`, `update-information.png`, `backup-verification.png`, `backup-package-rehearsal.png`, `cloud-operations.png`.
