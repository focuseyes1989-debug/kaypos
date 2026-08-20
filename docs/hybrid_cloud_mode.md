# KAY POS Hybrid Cloud Mode

Hybrid mode keeps the current LAN server workflow and adds a hosted cloud POS
backend for phones, tablets, and remote clients.

## How It Works

- Local/LAN mode: server PC runs `run_pos_server.py`; clients use the server PC IP.
- Cloud mode: hosted FastAPI runs `server.cloud_app:app`; clients use the cloud HTTPS URL.
- Cloud database: hosted app uses Aiven PostgreSQL through `ZAY_POS_DATABASE_URL`.

## Cloud Environment

Set these environment variables on the hosting provider:

```text
ZAY_POS_DB_BACKEND=postgres
ZAY_POS_AUTO_INIT_DB=1
ZAY_POS_DATABASE_URL=postgres://avnadmin:YOUR_PASSWORD@YOUR_AIVEN_HOST:16365/defaultdb?sslmode=require
```

Do not commit the real database URL or password.

## Start Command

```bash
uvicorn server.cloud_app:app --host 0.0.0.0 --port $PORT
```

If the host does not provide `$PORT`, use:

```bash
uvicorn server.cloud_app:app --host 0.0.0.0 --port 8000
```

## Build Command

Use the cloud-only dependency file so the host does not install desktop PyQt
packages:

```bash
pip install -r requirements-cloud.txt
```

## Client URLs

After deployment, use:

```text
https://YOUR-CLOUD-DOMAIN/mobile/products
https://YOUR-CLOUD-DOMAIN/
```

## Car Management Hybrid Mode

Set a strong shared API key on the hosted service. Keep it outside source
control:

```text
ZAY_CAR_API_KEY=GENERATE_A_LONG_RANDOM_SECRET
```

In the Car Management client, open **Server Connection** and configure:

```text
Server IP / port: the shop LAN server (primary)
Cloud HTTPS URL: https://YOUR-CLOUD-DOMAIN
Cloud API key: the same ZAY_CAR_API_KEY value
Allow local offline use: enabled
```

The client tries LAN first and Cloud HTTPS second. If neither is reachable,
writes are saved to the current Windows user's local offline database. Pending
operations are replayed automatically before the next successful read or write.
Do not expose the raw LAN TCP port `12345` to the public internet.

The cloud URL uses real HTTPS from the host, so mobile camera barcode scanning
is more reliable than local self-signed HTTPS.

## Local Server PC

Keep using the local server when the shop LAN is available:

```powershell
python run_pos_server.py --host 0.0.0.0 --port 8443 --https
```

If the server PC is off, users can open the cloud URL instead.

## Desktop Client PC Failover

Desktop client PCs can keep the local PostgreSQL server as the primary
database and use Aiven PostgreSQL as a fallback when the local server is
offline.

In the app:

```text
Settings > Database
```

Set the local PostgreSQL server fields, then fill the Aiven fields and enable:

```text
Use this cloud database if the local PostgreSQL server is offline
```

The app writes these values to `.env`:

```text
ZAY_POS_DATABASE_FAILOVER_ENABLED=1
ZAY_POS_DATABASE_FALLBACK_URL=postgres://avnadmin:YOUR_PASSWORD@YOUR_AIVEN_HOST:16365/defaultdb?sslmode=require
```

Restart the client app after saving. On startup, it tries the primary local
PostgreSQL database first; if that connection fails, it connects to the cloud
fallback database.

## Server PC Recovery After Cloud Use

When the server PC was down and users continued on Aiven/cloud mode, the cloud
database becomes the latest source of truth. When the server PC is repaired:

1. Start the server PC app, but do not switch clients back to local mode yet.
2. Open `Settings > Database`.
3. Confirm the Aiven fields are correct.
4. Click `Pull from Cloud`.
5. Wait for the success message and note the backup path.
6. Restart the server PC app.
7. Switch client PCs back to local PostgreSQL/server PC mode.

`Pull from Cloud` copies cloud rows into the local POS database. Cloud rows win
when a matching local row has the same ID. For SQLite local databases, the app
creates a backup under:

```text
database/cloud_pull_backups/
```

The same operation is available from the command line:

```bash
python scripts/cloud_sync_once.py --pull
```

Safety notes:

- The primary database must be the repaired local/server database before
  pulling.
- Pull is refused when the primary database URL is the same as the cloud URL.
- Cloud failover is temporarily disabled during pull so a broken local server
  does not accidentally write back into the cloud database.
