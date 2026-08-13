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

The cloud URL uses real HTTPS from the host, so mobile camera barcode scanning
is more reliable than local self-signed HTTPS.

## Local Server PC

Keep using the local server when the shop LAN is available:

```powershell
python run_pos_server.py --host 0.0.0.0 --port 8443 --https
```

If the server PC is off, users can open the cloud URL instead.
