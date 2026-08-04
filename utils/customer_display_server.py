"""LAN customer display server for Android/tablet clients."""

import json
import socket
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from loguru import logger


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _default_state():
    return {
        "version": 1,
        "updated_at": _now_iso(),
        "status": "idle",
        "shop": {
            "name": "ZAY POS",
            "phone": "",
            "address": "",
            "footer": "",
        },
        "customer": {
            "id": None,
            "name": "",
        },
        "currency_symbol": "",
        "items": [],
        "item_count": 0,
        "subtotal": 0.0,
        "discount": 0.0,
        "tax": 0.0,
        "grand_total": 0.0,
        "payment": 0.0,
        "change": 0.0,
        "payment_type": "",
    }


def _local_ipv4_addresses():
    ips = set()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        if ip and not ip.startswith("127."):
            ips.add(ip)
    except OSError:
        pass
    finally:
        sock.close()

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass

    return sorted(ips)


def _customer_display_html():
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ZAY POS Customer Display</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #202225;
      --panel: #2f3136;
      --panel-alt: #36393f;
      --text: #dcddde;
      --muted: #b9bbbe;
      --accent: #5865f2;
      --success: #3ba55d;
      --warn: #faa61a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: "Myanmar Text", "Noto Sans Myanmar", "Segoe UI", Arial, sans-serif;
    }
    .shell { padding: 20px; max-width: 1120px; margin: 0 auto; }
    header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      padding: 18px 20px;
      background: var(--panel-alt);
      border-bottom: 3px solid var(--accent);
      border-radius: 8px;
    }
    h1 { margin: 0; font-size: 26px; }
    .muted { color: var(--muted); }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(300px, 0.8fr);
      gap: 16px;
      margin-top: 16px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid #1b1d21;
      border-radius: 8px;
      padding: 16px;
    }
    .item {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      padding: 12px 0;
      border-bottom: 1px solid #40444b;
    }
    .item:last-child { border-bottom: 0; }
    .item strong { display: block; font-size: 18px; color: #fff; }
    .item .total { color: var(--success); font-weight: 800; }
    .total-card {
      background: #1f2227;
      border: 2px solid var(--accent);
      border-radius: 8px;
      padding: 18px;
      text-align: center;
    }
    .grand { font-size: 42px; font-weight: 900; color: var(--success); margin-top: 8px; }
    .row { display: flex; justify-content: space-between; gap: 16px; padding: 9px 0; border-bottom: 1px solid #40444b; }
    .row:last-child { border-bottom: 0; }
    .discount { color: var(--warn); }
    @media (max-width: 760px) {
      .shell { padding: 12px; }
      header, .grid { grid-template-columns: 1fr; display: grid; }
      .grand { font-size: 34px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <h1 id="shopName">ZAY POS</h1>
        <div class="muted" id="shopInfo"></div>
      </div>
      <div class="muted" id="status">Connecting...</div>
    </header>
    <main class="grid">
      <section class="panel">
        <h2>Your Cart</h2>
        <div id="customer" class="muted"></div>
        <div id="items"></div>
      </section>
      <aside>
        <section class="total-card">
          <div class="muted">Grand Total</div>
          <div class="grand" id="grandTotal">0</div>
        </section>
        <section class="panel" style="margin-top:16px">
          <div class="row"><span>Subtotal</span><strong id="subtotal">0</strong></div>
          <div class="row discount"><span>Discount</span><strong id="discount">0</strong></div>
          <div class="row"><span>Tax</span><strong id="tax">0</strong></div>
          <div class="row"><span>Payment</span><strong id="payment">0</strong></div>
          <div class="row"><span>Change</span><strong id="change">0</strong></div>
        </section>
      </aside>
    </main>
  </div>
  <script>
    const fmt = (value, symbol) => `${symbol ? symbol + " " : ""}${Number(value || 0).toLocaleString(undefined, {maximumFractionDigits: 2})}`;
    async function refresh() {
      try {
        const res = await fetch("/state", {cache: "no-store"});
        const data = await res.json();
        const shop = data.shop || {};
        const symbol = data.currency_symbol || "";
        document.getElementById("shopName").textContent = shop.name || "ZAY POS";
        document.getElementById("shopInfo").textContent = [shop.phone, shop.address].filter(Boolean).join(" | ");
        document.getElementById("status").textContent = `Updated ${data.updated_at || ""}`;
        document.getElementById("customer").textContent = data.customer && data.customer.name ? `Customer: ${data.customer.name}` : "";
        const items = document.getElementById("items");
        items.innerHTML = "";
        (data.items || []).forEach(item => {
          const row = document.createElement("div");
          row.className = "item";
          row.innerHTML = `<div><strong></strong><span class="muted"></span></div><div class="total"></div>`;
          row.querySelector("strong").textContent = item.name || "";
          row.querySelector(".muted").textContent = `${item.qty || 0} x ${fmt(item.price, symbol)}`;
          row.querySelector(".total").textContent = fmt(item.total, symbol);
          items.appendChild(row);
        });
        if (!items.children.length) {
          items.innerHTML = '<div class="muted">Waiting for cart items...</div>';
        }
        document.getElementById("grandTotal").textContent = fmt(data.grand_total, symbol);
        document.getElementById("subtotal").textContent = fmt(data.subtotal, symbol);
        document.getElementById("discount").textContent = fmt(data.discount, symbol);
        document.getElementById("tax").textContent = fmt(data.tax, symbol);
        document.getElementById("payment").textContent = fmt(data.payment, symbol);
        document.getElementById("change").textContent = fmt(data.change, symbol);
      } catch (error) {
        document.getElementById("status").textContent = "Offline";
      }
    }
    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>"""


class _CustomerDisplayHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, request_handler_class, service):
        self.service = service
        super().__init__(server_address, request_handler_class)


class _CustomerDisplayHandler(BaseHTTPRequestHandler):
    server_version = "ZayPosCustomerDisplay/1.0"

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/state":
            self._send_json(self.server.service.get_state())
        elif path == "/health":
            self._send_json(self.server.service.status())
        elif path in ("", "/"):
            html = _customer_display_html().encode("utf-8")
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        else:
            self._send_json({"error": "not_found"}, status=404)

    def _send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        try:
            message = fmt % args
        except TypeError:
            message = fmt
        logger.debug(f"Customer display HTTP: {message}")


class CustomerDisplayServer:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self._lock = threading.RLock()
        self._state = _default_state()
        self._server = None
        self._thread = None
        self._last_error = ""

    def start(self):
        if self.is_running:
            return self
        try:
            self._server = _CustomerDisplayHTTPServer(
                (self.host, self.port),
                _CustomerDisplayHandler,
                self,
            )
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                name="CustomerDisplayServer",
                daemon=True,
            )
            self._thread.start()
            self._last_error = ""
            logger.info(f"Customer display server started on {self.host}:{self.port}")
        except OSError as exc:
            self._server = None
            self._thread = None
            self._last_error = str(exc)
            logger.warning(f"Customer display server could not start: {exc}")
        return self

    def stop(self):
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server:
            try:
                server.shutdown()
                server.server_close()
            except Exception as exc:
                logger.warning(f"Customer display server stop failed: {exc}")
        if thread and thread.is_alive():
            thread.join(timeout=2)
        logger.info("Customer display server stopped")

    @property
    def is_running(self):
        return self._server is not None and self._thread is not None and self._thread.is_alive()

    def set_state(self, state):
        next_state = dict(_default_state())
        next_state.update(state or {})
        next_state["updated_at"] = _now_iso()
        with self._lock:
            self._state = json.loads(json.dumps(next_state, ensure_ascii=False, default=str))

    def get_state(self):
        with self._lock:
            return json.loads(json.dumps(self._state, ensure_ascii=False, default=str))

    def status(self):
        ips = _local_ipv4_addresses()
        urls = [f"http://{ip}:{self.port}" for ip in ips]
        if not urls:
            urls = [f"http://127.0.0.1:{self.port}"]
        return {
            "running": self.is_running,
            "host": self.host,
            "port": self.port,
            "urls": urls,
            "last_error": self._last_error,
        }


_server = CustomerDisplayServer()


def start_customer_display_server():
    return _server.start()


def stop_customer_display_server():
    _server.stop()


def set_customer_display_state(state):
    _server.set_state(state)


def get_customer_display_server_status():
    return _server.status()
