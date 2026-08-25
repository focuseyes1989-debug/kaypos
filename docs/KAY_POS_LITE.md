# KAY POS Lite

KAY POS Lite is the low-end Windows client for the existing KAY POS Server and PostgreSQL database. It does not open the database directly.

## Start in source mode

1. Start PostgreSQL and the POS Server from Server Manager.
2. Run `py kay_pos_lite.py`, or open **KAY POS Lite** from Launcher.
3. Use the server URL `https://SERVER-IP:8000` and enable self-signed HTTPS when using the Server Manager certificate.

## Low-end operating profile

- Target display: 1366×768 or larger.
- Product and customer requests are capped at 100 rows; sales history uses 50-row pages.
- Product and expense tables initially load 50 rows and fetch the next 50 near the bottom of the scroll range.
- Point of Sale loads thumbnails only for visible product rows and keeps a bounded 200-image memory cache.
- Images, charts, WebEngine and Matplotlib are not loaded.
- HTTP connections are pooled for the authenticated session.
- All network and PostgreSQL work runs outside the Qt UI thread.

## Receipt and cash drawer shortcuts

- `Ctrl+P`: print the latest completed or viewed receipt.
- `Ctrl+Shift+D`: open the cash drawer through the receipt printer installed on the POS Lite client PC.
- `Ctrl+Shift+P`: select the local receipt printer used for receipt printing and the cash drawer.

## Expenses

Open **Expenses** from the Lite sidebar to search by date or text, review the filtered total, and add an expense with category, amount, payment method, reference and notes. Expense writes go through the authenticated POS Server API into the shared PostgreSQL database.

## Deployment note

No executable build is required. Copy/update the project source and dependencies, then launch `kay_pos_lite.py`. Restart the POS Server after server API updates.
