"""Database compatibility helpers for new service modules.

The application currently runs on SQLite. Keeping small SQL differences in one
place makes the restaurant workflow easier to migrate to PostgreSQL later.
"""

import os
import re


SQLITE_BACKEND = "sqlite"
POSTGRES_BACKEND = "postgres"
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def get_db_backend():
    backend = os.getenv("ZAY_POS_DB_BACKEND", SQLITE_BACKEND).strip().lower() or SQLITE_BACKEND
    if backend in {"postgresql", "psql", "pg"}:
        return POSTGRES_BACKEND
    return backend


def is_sqlite_backend():
    return get_db_backend() == SQLITE_BACKEND


def is_postgres_backend():
    return get_db_backend() == POSTGRES_BACKEND


def placeholder():
    if is_sqlite_backend():
        return "?"
    return "%s"


def placeholders(count):
    return ",".join(placeholder() for _ in range(int(count or 0)))


def database_url():
    return os.getenv("ZAY_POS_DATABASE_URL") or os.getenv("DATABASE_URL") or ""


def adapt_sql_placeholders(sql):
    """Convert qmark placeholders to pyformat placeholders outside strings.

    Most existing app queries use SQLite's `?` placeholders. psycopg expects
    `%s`, so PostgreSQL connections run statements through this adapter.
    """
    if not is_postgres_backend() or "?" not in str(sql):
        return sql

    result = []
    in_single = False
    in_double = False
    index = 0
    text = str(sql)
    while index < len(text):
        char = text[index]
        if char == "'" and not in_double:
            result.append(char)
            if in_single and index + 1 < len(text) and text[index + 1] == "'":
                result.append(text[index + 1])
                index += 2
                continue
            in_single = not in_single
        elif char == '"' and not in_single:
            result.append(char)
            in_double = not in_double
        elif char == "?" and not in_single and not in_double:
            result.append("%s")
        else:
            result.append(char)
        index += 1
    return "".join(result)


def current_timestamp_sql():
    return "CURRENT_TIMESTAMP"


def integer_primary_key_sql():
    if is_sqlite_backend():
        return "INTEGER PRIMARY KEY AUTOINCREMENT"
    return "SERIAL PRIMARY KEY"


def begin_transaction_sql(immediate=False):
    if is_sqlite_backend() and immediate:
        return "BEGIN IMMEDIATE"
    return "BEGIN"


def quote_identifier(name):
    if not _IDENTIFIER_RE.match(str(name or "")):
        raise ValueError(f"Unsafe database identifier: {name!r}")
    return name


def table_columns(cursor, table_name):
    table_name = quote_identifier(table_name)
    if is_sqlite_backend():
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {row[1] for row in cursor.fetchall()}
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = CURRENT_SCHEMA()
          AND table_name = %s
    """, (table_name,))
    return {row[0] for row in cursor.fetchall()}


def table_exists(cursor, table_name):
    table_name = quote_identifier(table_name)
    if is_sqlite_backend():
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
    else:
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = CURRENT_SCHEMA()
              AND table_name = %s
        """, (table_name,))
    return cursor.fetchone() is not None


def ensure_column(cursor, table_name, column_name, column_definition):
    table_name = quote_identifier(table_name)
    column_name = quote_identifier(column_name)
    if column_name not in table_columns(cursor, table_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
