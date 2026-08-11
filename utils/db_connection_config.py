"""Local database connection configuration for client PCs."""

import os
from pathlib import Path
from urllib.parse import quote, urlparse

from utils.env_loader import _candidate_env_paths, load_project_env


DEFAULT_DB_NAME = "zay_pos"
DEFAULT_DB_USER = "zay_pos_user"
DEFAULT_DB_PORT = 5432


def get_writable_env_path():
    for candidate in _candidate_env_paths():
        if candidate.exists():
            return candidate
    return Path.cwd() / ".env"


def parse_database_url(url):
    parsed = urlparse(url or "")
    return {
        "host": parsed.hostname or "",
        "port": parsed.port or DEFAULT_DB_PORT,
        "database": (parsed.path or "").lstrip("/") or DEFAULT_DB_NAME,
        "username": parsed.username or DEFAULT_DB_USER,
        "password": parsed.password or "",
    }


def build_database_url(host, port=DEFAULT_DB_PORT, database=DEFAULT_DB_NAME, username=DEFAULT_DB_USER, password=""):
    host = str(host or "").strip()
    database = str(database or DEFAULT_DB_NAME).strip()
    username = quote(str(username or DEFAULT_DB_USER).strip(), safe="")
    password = quote(str(password or "").strip(), safe="")
    port = int(port or DEFAULT_DB_PORT)
    auth = username if not password else f"{username}:{password}"
    return f"postgresql://{auth}@{host}:{port}/{database}"


def load_database_config():
    load_project_env()
    return parse_database_url(os.getenv("ZAY_POS_DATABASE_URL") or os.getenv("DATABASE_URL") or "")


def save_database_config(host, port, database, username, password):
    env_path = get_writable_env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    values = {
        "ZAY_POS_DB_BACKEND": "postgres",
        "ZAY_POS_DATABASE_URL": build_database_url(host, port, database, username, password),
    }
    existing = []
    if env_path.exists():
        existing = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    seen = set()
    output = []
    for line in existing:
        stripped = line.strip()
        if "=" not in stripped or stripped.startswith("#"):
            output.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in values:
            output.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            output.append(line)

    for key, value in values.items():
        if key not in seen:
            if output and output[-1].strip():
                output.append("")
            output.append(f"{key}={value}")

    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    os.environ.update(values)
    return env_path


def test_database_connection(host, port, database, username, password):
    url = build_database_url(host, port, database, username, password)
    try:
        from models.database.postgres_adapter import connect_postgres

        conn = connect_postgres(url)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        conn.close()
        return True, f"Connected. Products: {product_count}, Users: {user_count}"
    except Exception as exc:
        return False, str(exc)
