# Car Management on the KAY POS server

Starting `run_pos_server.py` now also starts the LAN Car Management TCP service.
The existing Car Management client protocol remains available on port `12345`.

## Mobile owner print page

Open `https://SERVER-IP:8000/car` (or `/car/kiosk`) on a phone. Owners can use
their existing QR link, scan it directly with the phone's rear camera, or search
by car number, driver name, or phone number,
select the privacy-limited matching record, choose an online Car Print Agent
printer, and request the normal form print sequence. Search results never expose
NRC, phone, address, engine, frame, database IDs, or permanent QR tokens. Each
selection receives a one-use print grant that expires after 10 minutes; search
and print endpoints are rate limited per client address.

The in-page camera scanner requires a trusted HTTPS connection and browser
camera permission. Manual QR link/token entry remains available when camera
access is unavailable or denied.

## Defaults

- Bind address: `0.0.0.0`
- TCP port: `12345`
- Database: the same local database configured for KAY POS
- Internet/Aiven: not required

Optional environment settings:

```text
ZAY_CAR_SERVER_ENABLED=1
ZAY_CAR_SERVER_HOST=0.0.0.0
ZAY_CAR_SERVER_PORT=12345
```

Set `ZAY_CAR_SERVER_ENABLED=0` to disable the integrated service. Allow inbound
TCP port `12345` in Windows Firewall on the server PC so clients on the same
LAN/Wi-Fi can connect.

## Legacy SQLite migration

Validate the old database without writing:

```powershell
py -3 tools/migrate_car_sqlite.py "F:\ZAY CAR MANAGEMENT\ZAY CAR MANAGEMENT\car_data.db" --dry-run
```

Import records into the configured KAY POS database:

```powershell
py -3 tools/migrate_car_sqlite.py "F:\ZAY CAR MANAGEMENT\ZAY CAR MANAGEMENT\car_data.db"
```

The import preserves record IDs and skips IDs that already exist. It does not
clear or overwrite the destination table. Keep a backup of the legacy database
until the imported records have been checked from a Car Management client.
