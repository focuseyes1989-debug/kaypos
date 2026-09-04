"""Explicit read-only authentication adapter over the existing KAY users/roles schema.
Does not import models.database: that module has production initialization side effects.
Future write adapters must be introduced with transaction/parity tests, not via this reader.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import hmac
import os
from pathlib import Path
import re
import sqlite3
from typing import Protocol

@dataclass(frozen=True)
class Session:
    user_id: int
    username: str
    full_name: str
    role: str
    permissions: frozenset[str]

    def can(self, permission):
        return self.role.strip().casefold() == 'admin' or permission in self.permissions

class SessionProvider(Protocol):
    def diagnose(self) -> str: ...
    def authenticate(self, username: str, password: str) -> Session: ...

@dataclass(frozen=True)
class Target:
    backend: str = 'SQLite'
    database: str = ''
    schema: str = 'kay_native_test'
    server_url: str = ''
    insecure_tls: bool = True

    @property
    def label(self):
        if self.backend == 'Server':
            return self.server_url
        if self.backend == 'PostgreSQL':
            return f'PostgreSQL / {self.schema} (NATIVE_POS_TEST_DATABASE_URL)'
        return str(Path(self.database).expanduser().resolve()) if self.database else 'No database selected'

class ServerStore:
    """Use the same login and bearer-token API as POS Lite, not direct SQL."""
    def __init__(self, target):
        from lite_pos.api import LiteApiClient
        self.client = LiteApiClient(target.server_url, target.insecure_tls)
        self.target = Target('Server', server_url=self.client.server_url, insecure_tls=target.insecure_tls)

    def diagnose(self):
        self.client.health()
        return f'Server connected: {self.target.label}'

    def authenticate(self, username, password):
        if not username.strip() or not password:
            raise ValueError('Username and password are required.')
        user = self.client.login(username, password)
        confirmed = self.client.current_user()
        user = dict(user, **confirmed)
        permissions = user.get('permissions') or []
        if isinstance(permissions, str):
            permissions = permissions.split(',')
        return Session(int(user['id']), str(user['username']), str(user.get('full_name') or user['username']),
                       str(user.get('role') or ''), frozenset(str(p).strip() for p in permissions if str(p).strip()))

    def close(self):
        self.client.close()

def open_store(target):
    return ServerStore(target) if target.backend == 'Server' else ReadOnlyStore(target)

class ReadOnlyStore:
    def __init__(self, target: Target):
        self.target = target

    @contextmanager
    def connection(self):
        if self.target.backend == 'SQLite':
            if not self.target.database:
                raise ValueError('Select an existing practice database or create a new practice file.')
            path = Path(self.target.database).expanduser().resolve()
            if not path.is_file():
                raise ValueError('Database file not found. No database was created.')
            conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)
            conn.execute('PRAGMA query_only=ON')
        elif self.target.backend == 'PostgreSQL':
            if not re.fullmatch(r'[a-z][a-z0-9_]*_test', self.target.schema):
                raise ValueError('Use an existing isolated schema ending in _test (for example kay_native_test).')
            dsn = os.getenv('NATIVE_POS_TEST_DATABASE_URL')
            if not dsn:
                raise ValueError('Set NATIVE_POS_TEST_DATABASE_URL for the isolated PostgreSQL test database.')
            try:
                import psycopg
                conn = psycopg.connect(dsn, connect_timeout=5,
                    options=f'-c default_transaction_read_only=on -c statement_timeout=5000 -c search_path={self.target.schema}')
            except Exception:
                raise ValueError('PostgreSQL connection failed. Check the test connection environment variable, server and driver.') from None
        else:
            raise ValueError('Unsupported database backend.')
        try:
            yield conn
        finally:
            conn.close()

    def _query(self, conn, sql, values=()):
        if self.target.backend == 'PostgreSQL':
            sql = sql.replace('?', '%s')
        cursor = conn.cursor()
        try:
            cursor.execute(sql, values)
            columns = [item[0] for item in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def diagnose(self):
        try:
            with self.connection() as conn:
                self._query(conn, 'SELECT id, username, password_hash, role, full_name, salt, force_password_change, permissions FROM users WHERE 1=0')
                self._query(conn, 'SELECT name, permissions FROM user_roles WHERE 1=0')
        except ValueError:
            raise
        except Exception:
            raise ValueError('Cannot read the KAY users/roles schema. Select a compatible test copy; no migration was run.') from None
        return f'Connected read-only: {self.target.label}'

    def authenticate(self, username, password):
        if not username.strip() or not password:
            raise ValueError('Username and password are required.')
        self.diagnose()
        try:
            with self.connection() as conn:
                rows = self._query(conn, 'SELECT * FROM users WHERE username=?', (username.strip(),))
                user = rows[0] if rows else None
                salt = bytes.fromhex(user['salt']) if user and user.get('salt') else b'salt_123'
                candidate = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000).hex()
                if not user or not hmac.compare_digest(candidate, str(user.get('password_hash') or '')):
                    raise ValueError('Invalid username or password.')
                if user.get('is_active') in (0, False, '0'):
                    raise ValueError('This account is inactive.')
                if not user.get('salt') or user.get('force_password_change') in (1, True, '1'):
                    raise ValueError('Password change is required. Change it in KAY POS, then refresh your test copy.')
                roles = self._query(conn, 'SELECT permissions FROM user_roles WHERE name=?', (user['role'],))
                combined = str(user.get('permissions') or '') + ',' + str(roles[0].get('permissions') or '' if roles else '')
                return Session(int(user['id']), str(user['username']), str(user.get('full_name') or user['username']),
                               str(user['role']), frozenset(p.strip() for p in combined.split(',') if p.strip()))
        except ValueError:
            raise
        except Exception:
            raise ValueError('Could not authenticate against this test schema. Check the account and database format.') from None

def create_practice_database(path, username, password):
    """Explicit, no-overwrite auth fixture, matching legacy users/user_roles columns.
    Not a complete POS schema and never suitable as a production database.
    """
    if not username.strip() or len(password) < 8:
        raise ValueError('Enter a username and a practice password of at least 8 characters.')
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with sqlite3.connect(path) as conn:
            conn.executescript('''
                CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'cashier', full_name TEXT,
                    salt TEXT, force_password_change INTEGER DEFAULT 0, permissions TEXT, last_login TIMESTAMP,
                    is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE user_roles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
                    description TEXT, permissions TEXT, is_system INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            ''')
            salt = os.urandom(16)
            hashed = hashlib.pbkdf2_hmac('sha256',password.encode(),salt,100000).hex()
            conn.execute('INSERT INTO user_roles (name,permissions) VALUES (?,?)', ('Admin',''))
            conn.execute('INSERT INTO users (username,password_hash,role,full_name,salt) VALUES (?,?,?,?,?)',
                         (username.strip(),hashed,'Admin','Practice administrator',salt.hex()))
        conn.close()
    except Exception:
        # Only this invocation owns this newly created file.
        try:
            conn.close()
        except UnboundLocalError:
            pass
        path.unlink(missing_ok=True)
        raise
    return str(path)
