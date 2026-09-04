"""Read-only, bounded database diagnostics. No schema preparation or repair."""
from datetime import datetime, timezone
import time
from server.native_catalog import CatalogRepository


# Deliberately a readiness subset, not a promise of full migration parity.
TABLES = {
    'users': (True, ('id', 'username', 'role', 'permissions', 'is_active', 'force_password_change')),
    'user_roles': (True, ('name', 'permissions')),
    'settings': (True, ('key', 'value')),
    'products': (True, ('id', 'name', 'price')),
    'sales': (True, ('id', 'invoice_no', 'created_at', 'status', 'total')),
    'sale_items': (True, ('id', 'sale_id', 'product_id', 'qty', 'price')),
    'customers': (True, ('id', 'name')),
    'expenses': (True, ('id', 'amount')),
    'employees': (False, ('id', 'employee_no', 'full_name', 'photo_data')),
    'employee_documents': (False, ('id', 'employee_id', 'file_path')),
    'native_employee_documents': (False, ('document_id', 'filename', 'mime', 'content', 'sha256')),
    'native_admin_requests': (False, ('request_id', 'user_id', 'operation', 'payload_hash', 'result_json')),
    'network_print_jobs': (False, ('job_id', 'request_key', 'target_agent_id', 'status')),
}


class DatabaseRepository(CatalogRepository):
    def read(self, user, integrity=False):
        conn = self.connect(); c = conn.cursor(); pg = self.pg(); progress = None
        deadline = time.monotonic() + 10
        try:
            if pg:
                c.execute('SET TRANSACTION READ ONLY')
                c.execute("SET LOCAL statement_timeout = '10000ms'")
            else:
                c.execute('PRAGMA query_only=ON')
                c.execute('PRAGMA busy_timeout=3000')
                progress = getattr(conn, 'set_progress_handler', None)
                if progress: progress(lambda: int(time.monotonic() >= deadline), 5000)
                c.execute('BEGIN')
            self.authorize(c, user, ['settings', 'edit_settings'])
            c.execute('SELECT 1'); c.fetchone()
            if pg:
                c.execute("SELECT current_setting('server_version')"); version = c.fetchone()[0]
                c.execute('SELECT table_name,column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name IN (' + ','.join('?' for _ in TABLES) + ')', tuple(TABLES))
                columns = {}
                for table, column in c.fetchall(): columns.setdefault(table, set()).add(column)
                mode = 'Server managed'
            else:
                c.execute('SELECT sqlite_version()'); version = c.fetchone()[0]
                c.execute('PRAGMA journal_mode'); mode = str(c.fetchone()[0]).upper()
                columns = {}
                for table in TABLES:
                    c.execute(f'PRAGMA table_info("{table}")')
                    names = {row[1] for row in c.fetchall()}
                    if names: columns[table] = names
            records = []
            for table, (required, expected) in TABLES.items():
                actual = columns.get(table, set()); missing = sorted(set(expected) - actual)
                status = 'Ready' if not missing else 'Needs attention' if required or actual else 'Not initialized'
                records.append(dict(table=table, scope='Core' if required else 'Feature', status=status,
                                    missing_columns=', '.join(missing), columns_found=len(actual)))
            health = dict(status='Not run', details=['Select the integrity check to run SQLite quick_check.'])
            if pg:
                health = dict(status='Not supported', details=['PostgreSQL connection and schema metadata were checked. Physical integrity and restore validation require PostgreSQL maintenance tools and a separate restore database.'])
            elif integrity:
                if not progress: raise ValueError('This SQLite connection cannot enforce the diagnostic scan time budget')
                c.execute('PRAGMA quick_check(20)'); messages = [str(row[0]) for row in c.fetchall()]
                health = dict(status='OK' if messages == ['ok'] else 'Needs attention', details=messages)
            return dict(backend='PostgreSQL' if pg else 'SQLite', version=str(version), journal_mode=mode,
                        checked_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                        schema_status='Needs attention' if any(r['status'] == 'Needs attention' for r in records) else 'Ready',
                        records=records, integrity=health,
                        notes=['Checks are read-only and inspect a defined subset of Native schema requirements. No tables, values, settings or migrations are changed.',
                               'Not initialized means the optional feature has not provisioned its tables; open that feature after updating the server if you need it.',
                               'No row contents, credentials, database paths or connection strings are included. This report does not certify backup restore or full application compatibility.',
                               'SQLite quick_check reports at most 20 problems; it does not check foreign keys or perform full index consistency verification. Scans have a 10-second execution budget; large databases may require an offline maintenance check.'])
        finally:
            if progress: progress(None, 0)
            conn.rollback(); conn.close()


def install_routes(app, current_user, repository=None):
    from fastapi import Depends, HTTPException
    repo = repository or DatabaseRepository()
    @app.get('/api/native/database/diagnostics')
    def read(integrity: bool = False, user=Depends(current_user)):
        try: return repo.read(user, integrity)
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(503, 'Database diagnostics did not complete. Check server access/schema and retry; large SQLite scans may need an offline maintenance check.') from exc
