"""Small psycopg adapter for the app's existing SQLite-style query calls."""

from datetime import date, datetime
from decimal import Decimal
import re

from utils.db_compat import adapt_sql_placeholders


AUTO_ID_TABLES = {
    "categories",
    "category_groups",
    "app_metadata",
    "cash_drawer",
    "category_activity_log",
    "customers",
    "credit_adjustments",
    "credit_payments",
    "credit_sales",
    "credit_transactions",
    "expenses",
    "expense_alerts_log",
    "expense_attachments",
    "expense_budgets",
    "expense_categories",
    "expense_notification_settings",
    "expiry_alerts_log",
    "held_sales",
    "locations",
    "migration_history",
    "migrations",
    "payment_types",
    "payments",
    "products",
    "product_discounts",
    "product_locations",
    "product_variants",
    "purchase_order_items",
    "purchase_orders",
    "restaurant_kitchen_ticket_items",
    "restaurant_kitchen_tickets",
    "restaurant_order_items",
    "restaurant_order_modifiers",
    "restaurant_orders",
    "restaurant_tables",
    "sale_items",
    "sales",
    "stock_movements",
    "supplier_payments",
    "suppliers",
    "user_activity_log",
    "user_roles",
    "users",
    "customer_points_log",
}
_INSERT_TABLE_RE = re.compile(r"^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_INSERT_OR_IGNORE_RE = re.compile(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+", re.IGNORECASE)
_PRAGMA_TABLE_INFO_RE = re.compile(
    r"^\s*PRAGMA\s+table_info\s*\(\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*\)\s*;?\s*$",
    re.IGNORECASE,
)
_BEGIN_IMMEDIATE_RE = re.compile(r"^\s*BEGIN\s+IMMEDIATE\s*;?\s*$", re.IGNORECASE)
_SQLITE_MASTER_EXISTS_RE = re.compile(
    r"^\s*SELECT\s+name\s+FROM\s+sqlite_master\s+WHERE\s+type\s*=\s*['\"]table['\"]\s+AND\s+name\s*=\s*\?\s*;?\s*$",
    re.IGNORECASE,
)
_SQLITE_MASTER_TABLE_LIMIT_RE = re.compile(
    r"^\s*SELECT\s+name\s+FROM\s+sqlite_master\s+WHERE\s+type\s*=\s*['\"]table['\"]\s+LIMIT\s+1\s*;?\s*$",
    re.IGNORECASE,
)
_SQLITE_MASTER_TABLE_COUNT_RE = re.compile(
    r"^\s*SELECT\s+COUNT\s*\(\s*\*\s*\)\s+FROM\s+sqlite_master\s+WHERE\s+type\s*=\s*['\"]table['\"]\s*;?\s*$",
    re.IGNORECASE,
)
_SQLITE_MASTER_TABLE_LIST_RE = re.compile(
    r"^\s*SELECT\s+name\s+FROM\s+sqlite_master\s+WHERE\s+type\s*=\s*['\"]table['\"]\s*;?\s*$",
    re.IGNORECASE,
)
_SQLITE_MASTER_INDEX_EXISTS_RE = re.compile(
    r"^\s*SELECT\s+name\s+FROM\s+sqlite_master\s+WHERE\s+type\s*=\s*['\"]index['\"]\s+AND\s+name\s*=\s*\?\s*;?\s*$",
    re.IGNORECASE,
)
_SQLITE_MASTER_INDEX_LIST_RE = re.compile(
    r"^\s*SELECT\s+name\s+FROM\s+sqlite_master\s+WHERE\s+type\s*=\s*['\"]index['\"]\s+AND\s+name\s+NOT\s+LIKE\s+['\"]sqlite_%['\"]\s*;?\s*$",
    re.IGNORECASE,
)
_SETTINGS_OR_REPLACE_RE = re.compile(
    r"^\s*INSERT\s+OR\s+REPLACE\s+INTO\s+settings\s*\(\s*key\s*,\s*value\s*\)\s*VALUES\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)\s*;?\s*$",
    re.IGNORECASE | re.DOTALL,
)
_DATE_NOW_REPLACEMENTS = (
    ("date('now', 'start of month', '-1 month')", "(date_trunc('month', CURRENT_DATE)::date - INTERVAL '1 month')::date"),
    ("date('now', 'start of month')", "date_trunc('month', CURRENT_DATE)::date"),
    ("date('now', 'weekday 0', '-14 days')", "(CURRENT_DATE - INTERVAL '14 days')::date"),
    ("date('now', 'weekday 0', '-7 days')", "(CURRENT_DATE - INTERVAL '7 days')::date"),
    ("date('now', 'weekday 0')", "CURRENT_DATE"),
    ("date('now', '-30 days')", "(CURRENT_DATE - INTERVAL '30 days')::date"),
    ("date('now', '-14 days')", "(CURRENT_DATE - INTERVAL '14 days')::date"),
    ("date('now', '-7 days')", "(CURRENT_DATE - INTERVAL '7 days')::date"),
    ("date('now', '-1 day')", "(CURRENT_DATE - INTERVAL '1 day')::date"),
    ("date('now', '+30 days')", "(CURRENT_DATE + INTERVAL '30 days')::date"),
    ("date('now', '+14 days')", "(CURRENT_DATE + INTERVAL '14 days')::date"),
    ("date('now', '+7 days')", "(CURRENT_DATE + INTERVAL '7 days')::date"),
    ("date('now')", "CURRENT_DATE"),
)


def import_postgres_driver():
    try:
        import psycopg

        return "psycopg", psycopg
    except ImportError:
        try:
            import psycopg2

            return "psycopg2", psycopg2
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL backend requires psycopg or psycopg2. "
                "Install one of them before setting ZAY_POS_DB_BACKEND=postgres."
            ) from exc


def connect_postgres(database_url):
    driver_name, driver = import_postgres_driver()
    if driver_name == "psycopg":
        conn = driver.connect(database_url)
    else:
        conn = driver.connect(database_url)
    return PostgresConnectionAdapter(conn)


class PostgresConnectionAdapter:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args, **kwargs):
        return PostgresCursorAdapter(self._conn.cursor(*args, **kwargs))

    def execute(self, sql, params=None):
        cursor = self.cursor()
        cursor.execute(sql, params)
        return cursor

    def executemany(self, sql, seq_of_params):
        cursor = self.cursor()
        cursor.executemany(sql, seq_of_params)
        return cursor

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        self._conn.__enter__()
        return self

    def __exit__(self, *args):
        return self._conn.__exit__(*args)


class PostgresCursorAdapter:
    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = None

    def execute(self, sql, params=None):
        self.lastrowid = None
        metadata_sql = _adapt_sqlite_metadata_query(sql)
        if metadata_sql:
            self._cursor.execute(adapt_sql_placeholders(metadata_sql), params)
            return self
        if _BEGIN_IMMEDIATE_RE.match(str(sql or "")):
            self._cursor.execute("BEGIN")
            return self
        pragma_table = _match_pragma_table_info(sql)
        if pragma_table:
            self._execute_table_info(pragma_table)
            return self
        adapted_sql = _adapt_sqlite_conflict_syntax(sql)
        adapted_sql = adapt_sql_placeholders(adapted_sql)
        returning_id = _should_add_returning_id(adapted_sql)
        if returning_id:
            adapted_sql = f"{adapted_sql.rstrip().rstrip(';')} RETURNING id"
        self._cursor.execute(adapted_sql, params)
        if returning_id:
            row = self._cursor.fetchone()
            self.lastrowid = row[0] if row else None
        return self

    def executemany(self, sql, seq_of_params):
        self.lastrowid = None
        adapted_sql = _adapt_sqlite_conflict_syntax(sql)
        self._cursor.executemany(adapt_sql_placeholders(adapted_sql), seq_of_params)
        return self

    def fetchone(self):
        return _normalize_row(self._cursor.fetchone())

    def fetchall(self):
        return [_normalize_row(row) for row in self._cursor.fetchall()]

    def fetchmany(self, size=None):
        if size is None:
            rows = self._cursor.fetchmany()
        else:
            rows = self._cursor.fetchmany(size)
        return [_normalize_row(row) for row in rows]

    def _execute_table_info(self, table_name):
        self._cursor.execute("""
            SELECT
                ordinal_position - 1 AS cid,
                column_name AS name,
                data_type AS type,
                CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END AS notnull,
                column_default AS dflt_value,
                CASE WHEN column_name = ANY (
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND tc.table_schema = CURRENT_SCHEMA()
                      AND tc.table_name = %s
                ) THEN 1 ELSE 0 END AS pk
            FROM information_schema.columns
            WHERE table_schema = CURRENT_SCHEMA()
              AND table_name = %s
            ORDER BY ordinal_position
        """, (table_name, table_name))

    def __iter__(self):
        for row in self._cursor:
            yield _normalize_row(row)

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def __enter__(self):
        self._cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self._cursor.__exit__(*args)


def _should_add_returning_id(sql):
    text = str(sql or "")
    if " RETURNING " in text.upper() or " ON CONFLICT " in text.upper():
        return False
    match = _INSERT_TABLE_RE.match(text)
    if not match:
        return False
    return match.group(1).lower() in AUTO_ID_TABLES


def _match_pragma_table_info(sql):
    match = _PRAGMA_TABLE_INFO_RE.match(str(sql or ""))
    return match.group(1) if match else None


def _adapt_sqlite_metadata_query(sql):
    text = str(sql or "")
    if _SQLITE_MASTER_EXISTS_RE.match(text):
        return """
            SELECT table_name AS name
            FROM information_schema.tables
            WHERE table_schema = CURRENT_SCHEMA()
              AND table_name = ?
        """
    if _SQLITE_MASTER_TABLE_LIMIT_RE.match(text):
        return """
            SELECT table_name AS name
            FROM information_schema.tables
            WHERE table_schema = CURRENT_SCHEMA()
            LIMIT 1
        """
    if _SQLITE_MASTER_TABLE_COUNT_RE.match(text):
        return """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = CURRENT_SCHEMA()
        """
    if _SQLITE_MASTER_TABLE_LIST_RE.match(text):
        return """
            SELECT table_name AS name
            FROM information_schema.tables
            WHERE table_schema = CURRENT_SCHEMA()
            ORDER BY table_name
        """
    if _SQLITE_MASTER_INDEX_EXISTS_RE.match(text):
        return """
            SELECT indexname AS name
            FROM pg_indexes
            WHERE schemaname = CURRENT_SCHEMA()
              AND indexname = ?
        """
    if _SQLITE_MASTER_INDEX_LIST_RE.match(text):
        return """
            SELECT indexname AS name
            FROM pg_indexes
            WHERE schemaname = CURRENT_SCHEMA()
            ORDER BY indexname
        """
    return None


def _adapt_sqlite_conflict_syntax(sql):
    text = str(sql or "")
    settings_match = _SETTINGS_OR_REPLACE_RE.match(text)
    if settings_match:
        key_expr, value_expr = settings_match.groups()
        return (
            "INSERT INTO settings (key, value) "
            f"VALUES ({key_expr}, {value_expr}) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
        )

    if _INSERT_OR_IGNORE_RE.match(text):
        text = _INSERT_OR_IGNORE_RE.sub("INSERT INTO ", text).rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

    for sqlite_expr, postgres_expr in _DATE_NOW_REPLACEMENTS:
        text = text.replace(sqlite_expr, postgres_expr)

    text = re.sub(
        r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
        "SERIAL PRIMARY KEY",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+COLLATE\s+NOCASE\b", "", text, flags=re.IGNORECASE)
    text = _adapt_sqlite_date_now(text)
    text = _adapt_sqlite_strftime(text)
    text = _adapt_sqlite_group_concat(text)
    text = re.sub(r"\bdate\s*\(\s*([A-Za-z_][A-Za-z0-9_\.]*)\s*\)", r"DATE(\1)", text, flags=re.IGNORECASE)
    return text


def _adapt_sqlite_group_concat(sql):
    return re.sub(
        r"GROUP_CONCAT\s*\(\s*(.+?)\s*,\s*'([^']*)'\s*\)",
        lambda match: f"string_agg(({match.group(1)})::text, '{match.group(2)}')",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _adapt_sqlite_date_now(sql):
    text = re.sub(
        r"\bdate\s*\(\s*['\"]now['\"]\s*,\s*['\"]([+-]\d+\s+days?)['\"]\s*\)",
        lambda match: f"(CURRENT_DATE + INTERVAL '{match.group(1)}')::date",
        sql,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bdate\s*\(\s*['\"]now['\"]\s*,\s*\?\s*\)",
        "(CURRENT_DATE + ?::interval)::date",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _adapt_sqlite_strftime(sql):
    def replace(match):
        fmt = match.group(1)
        expr = match.group(2).strip()
        pg_fmt = {
            "%Y-%m": "YYYY-MM",
            "%Y-%m-%d": "YYYY-MM-DD",
            "%Y-%m-%d %H:%M": "YYYY-MM-DD HH24:MI",
            "%Y-%m-%d %H:%M:%S": "YYYY-MM-DD HH24:MI:SS",
            "%Y": "YYYY",
            "%m": "MM",
            "%d": "DD",
            "%H": "HH24",
            "%M": "MI",
            "%S": "SS",
        }.get(fmt)
        if not pg_fmt:
            return match.group(0)
        return f"to_char({expr}::timestamp, '{pg_fmt}')"

    return re.sub(
        r"strftime\s*\(\s*'([^']+)'\s*,\s*([^)]+?)\s*\)",
        replace,
        sql,
        flags=re.IGNORECASE,
    )


def _normalize_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _normalize_row(row):
    if row is None:
        return None
    if isinstance(row, tuple):
        return tuple(_normalize_value(value) for value in row)
    return row
