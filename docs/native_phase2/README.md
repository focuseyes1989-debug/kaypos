# KAY POS Native — Phase 2

Historical Phase 2 milestone. The current source now includes the [Phase 3 Sales pilot](../native_phase3/README.md); the no-business-writes descriptions below refer to the Phase 2 snapshot.

Implemented: separate native-widget preview application, POS Server API login (matching POS Lite), optional local read-only test adapters, permission-filtered shell, appearance preferences, launcher entry and separate build recipe.

Updated requirements: default server `https://192.168.110.112:8000`; minimum supported display **1366 × 768**. The window fits the monitor working area, accounting for the taskbar and title bar, rather than forcing a 1366 × 768 client area off-screen.

## Start from source

Double-click `kay_pos_native.pyw` in the project root, or open **KAY POS Native — Phase 2 Preview** from the launcher. For console diagnostics:

```powershell
python kay_pos_native.py
```

The existing **KAY POS**, POS Lite and other launcher entries keep their previous startup targets. Native uses `Global\KAY_POS_Native_SingleInstance_v1` and the Windows application ID `KAY.POSNative`. It can have its own process alongside the original app; simultaneous business writes are not enabled in Phase 2.

## Sign in with the existing POS Server

1. Open Native from the launcher or `kay_pos_native.pyw`.
2. Keep **Server** selected. Default URL: `https://192.168.110.112:8000`.
3. **Allow self-signed HTTPS certificate** defaults on, matching POS Lite's LAN server setup. Turn it off when using a trusted certificate.
4. Click **Test Connection**, then enter your existing POS Lite username/password and **Sign In**.

Native uses the existing `/health`, `/api/login` and `/api/me` endpoints through `LiteApiClient`. Login tokens remain in memory and are cleared/closed on logout or exit. No direct database file or PostgreSQL configuration is needed for normal use. This preview does not send sales or stock mutations.

Update and restart the POS Server from this source revision to return the additive `permissions` list from `verify_user`. Existing Lite response fields and routes are retained. Older servers still authenticate; non-admin accounts without permission metadata get no pages and a message to update the server, rather than guessed access. Admin navigation continues to work with older responses. The actual account login was not tested because no credentials were supplied.

The default IP's `/health` returned **HTTP 200** from this machine on 2026-09-04. This verifies reachability, not full authentication or business-operation compatibility.

## Optional local practice sign-in

1. Change **Connection** to **SQLite** (optional local development mode).
2. Enter a practice username and a new practice password (at least 8 characters).
3. Click **Create Practice File…** and choose a new `.db` file. An existing file is never overwritten, even after a file-picker overwrite confirmation.
4. Click **Test Connection**, then **Sign In** with those credentials.

This explicitly creates only a disposable `users` / `user_roles` authentication fixture with the corresponding legacy columns and password format. It is not a new production POS schema and is not suitable for sales. No built-in password is installed. User and role administration will arrive later.

Alternatively, use **Browse…** to select an existing compatible KAY test copy. It is opened with SQLite `mode=ro` and `query_only=ON`; no migration, recovery, last-login update or production initialization is run. The selected absolute target is displayed before and after login. A missing path produces an error rather than a new empty database.

## PostgreSQL adapter

An optional adapter supports an existing isolated schema ending in `_test`, for example `kay_native_test`. Its connection comes exclusively from `NATIVE_POS_TEST_DATABASE_URL`, inherited by the process. Use a test-only account and an existing test database/schema with compatible `users` and `user_roles` tables. Select **PostgreSQL** and enter the schema name in the login dialog. The adapter does not create a schema or copy data.

Connections explicitly request `default_transaction_read_only=on`, a five-second connect timeout and statement timeout, and a schema-specific search path. Connection credentials are not stored in preferences or displayed in error messages. Do not use the normal production database environment variable. Live PostgreSQL connectivity has not been exercised in this environment; connection-policy tests use a mock, and schema/env validation is tested locally.

## What works now

- Native QMainWindow, menus, toolbar, splitter, list navigation, forms and dialogs; no legacy global stylesheet or custom widget painting.
- The 12 stable route IDs from the main app, shown according to account permissions. Pages are clearly marked with their planned delivery phase. The shell does not pretend that sales/stock/report functionality is implemented.
- PBKDF2-HMAC-SHA256 legacy password verification with the same 100,000 iterations and user salt. Admin grants all routes; other roles combine role and user permission strings. Inactive accounts are denied.
- Accounts requiring password change (including old unsalted accounts) cannot bypass it: change the password in the existing KAY POS and update the test copy before using Native. Phase 2 does not write password changes.
- Direct route navigation enforces the same session permission check as the visible menu. **Refresh access (F5)** signs out and requests reauthentication so permissions are not silently reused indefinitely across refresh.
- Sign out clears the session and password and returns to login. Worker results are ignored after closing; a pending read finishes before the thread/application is destroyed.
- **Appearance → Style, palette and font…** enumerates styles actually installed in Qt. System uses the startup platform style/palette. Explicit Light/Dark uses Fusion for consistent palette rendering. Font and window dimensions are saved under the Native profile only.

Native preferences live at `%APPDATA%\KAY\POSNative\config.json` (home-directory fallback if APPDATA is absent). Passwords, bearer tokens and PostgreSQL DSNs are excluded from saved fields. Server URL and certificate preference are Native-only settings. Existing local-only preview settings migrate to Server mode once; users may subsequently select an optional local adapter explicitly. Existing KAY POS/Lite theme preferences are not modified.

## Service ownership and adapter boundary

`native_pos/data.py` contains an explicit `Target`, immutable `Session`, `SessionProvider` protocol, a POS Lite-compatible `ServerStore` and optional `ReadOnlyStore`. Server mode is the default and uses the same backend business data as POS Lite. Full Native feature coverage will require API additions where existing endpoints lack main-app parity. It intentionally does not import `models.database`, `app.application`, or legacy UI: those modules can initialize databases or background services during startup. The auth SQL/schema and permission semantics match the inspected KAY implementation. Future write adapters must preserve legacy caller behavior and add transaction parity tests before use.

Backup, cloud sync, Telegram, printer listeners, customer-display servers, employee schema creation, database auto-repair and update polling are not started by Native. Existing KAY applications retain ownership. There is no second scheduler or port binding in this preview. Full service ownership/coexistence is a later integration gate before enabling those features.

## Files

- `kay_pos_native.py`, `kay_pos_native.pyw`: console/windowed entry points.
- `native_pos/window.py`: login, appearance dialog, native shell, session lifecycle.
- `native_pos/routes.py`: explicit route registry.
- `native_pos/data.py`: read-only authentication and opt-in practice fixture.
- `native_pos/config.py`, `theme.py`, `tasks.py`: isolated preferences, standard styles and safe worker completion.
- `build_native_pos.py`, `requirements-pos-native.txt`: separate Windows packaging recipe/dependencies.
- `tests/test_native_pos_phase2.py`: focused adapter/lifecycle/permission/launcher tests.

Optional packaging command:

```powershell
python build_native_pos.py
```

Output: `dist/KAY_POS_Native/KAY_POS_Native.exe`. Build work goes to `build/native` and its spec to `build/native_spec`. This recipe does not delete old KAY build outputs. The executable was not built in this phase because source execution is the current workflow.

## Verification and remaining gates

Automated result: **27 tests passed** (`python -m unittest tests.test_native_pos_phase2 tests.test_native_pos_server tests.test_launcher`). Verified using disposable SQLite fixtures and offscreen Qt: login success/failure, inactive and forced-change accounts, permission union, route restrictions, no-overwrite fixture creation, unchanged database bytes/read-only writes rejected, config whitelist/corruption handling, no legacy UI/database imports, light/dark styles, graceful close during a pending worker, original/native launcher target resolution, and the existing launcher regression suite.

Visual inspection: [login](login.png), [light shell](light.png), [dark shell](dark.png). These previews use synthetic session data; no production login or customer records. The offscreen Windows font was explicitly registered for preview rendering; normal source startup uses the platform fonts.

Pending deployment checks: live isolated PostgreSQL, packaged Windows execution, actual monitor/keyboard/screen-reader testing, Myanmar font shaping on target machines, and physical 100/125/150/200% DPI behavior. A 1366×768 display layout was rendered with a reserved taskbar/title-bar area; minimum client dimensions are clamped to the actual monitor working area. Larger monitors retain saved window dimensions. No performance improvement claim is made yet. No production database was opened directly for verification; only the configured server health endpoint was contacted. Server login/permissions/token cleanup tests use mocked HTTP responses and disposable SQLite auth fixtures.

Next: **Phase 3 — Sales and Cashier pilot**, including checkout-service extraction, barcode/cart/payment UI, pricing and credit parity, receipt/drawer behavior, and rollback tests. Phase 2 placeholders must be replaced incrementally; they are not feature-complete screens.
