# KAY POS Lite

KAY POS Lite is the low-end Windows client for the existing KAY POS Server and PostgreSQL database. It does not open the database directly.

## Start in source mode

1. Start PostgreSQL and the POS Server from Server Manager.
2. Run `py kay_pos_lite.py`, or open **KAY POS Lite** from Launcher.
3. Use the server URL `https://SERVER-IP:8000` and enable self-signed HTTPS when using the Server Manager certificate.

## Low-end operating profile

- Target display: 1366×768 or larger.
- Product and customer requests are capped at 100 rows; sales history uses 50-row pages.
- Images, charts, WebEngine and Matplotlib are not loaded.
- HTTP connections are pooled for the authenticated session.
- All network and PostgreSQL work runs outside the Qt UI thread.

## Deployment note

No executable build is required. Copy/update the project source and dependencies, then launch `kay_pos_lite.py`. Restart the POS Server after server API updates.
