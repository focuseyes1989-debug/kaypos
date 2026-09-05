"""Server-local snapshots and isolated restore rehearsals; no live DB replacement.

SQLite uses the online backup API (includes committed WAL content). PostgreSQL
uses pg_dump against the actual connected database, with credentials in the
child environment, never command arguments or API responses.
"""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
from uuid import UUID

from server.native_admin import AdminRepository


class BackupRepository(AdminRepository):
    def __init__(self, service=None, directory=None, asset_root=None):
        super().__init__(service)
        from utils.paths import get_db_dir
        self.asset_root = Path(asset_root or get_db_dir()).resolve()
        self.directory = Path(directory or Path(__file__).resolve().parents[1] / 'database' / 'native_backups').resolve()

    def permitted(self, user, permission):
        conn = self.connect()
        try: self.authorize(conn.cursor(), user, [permission])
        finally: conn.rollback(); conn.close()

    def metadata(self, path):
        checksum = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''): checksum.update(block)
        return dict(name=path.name, size=path.stat().st_size, sha256=checksum.hexdigest(),
                    created_at=datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds'))

    def read(self, user):
        self.permitted(user, 'backup')
        files = sorted(self.directory.glob('native-*.*'), key=lambda p: p.stat().st_mtime, reverse=True) if self.directory.exists() else []
        return dict(records=[self.metadata(p) for p in [p for p in files if p.suffix in ('.db', '.dump', '.zip')][:100]],
                    backend='PostgreSQL' if self.pg() else 'SQLite',
                    message='Backups stay on the POS Server. Choose database-only or database + managed files. Packages include listed server asset folders; arbitrary external/client paths need separate backup. Restore-copy supports SQLite snapshots. No Native backup scheduler runs.')

    def path(self, name):
        if not re.fullmatch(r'native-[0-9a-f-]{36}\.(db|dump|zip)', name): raise ValueError('Invalid backup name')
        path = (self.directory / name).resolve()
        if path.parent != self.directory or not path.is_file(): raise ValueError('Backup not found')
        return path

    def create(self, user, request_id):
        self.permitted(user, 'backup'); request_id = str(UUID(request_id))
        self.directory.mkdir(parents=True, exist_ok=True)
        final = self.directory / f"native-{request_id}{'.dump' if self.pg() else '.db'}"
        # The OS lock coordinates all server workers and prevents concurrent retry
        # from replacing an already confirmed snapshot with newer database state.
        from server.native_file_lock import file_lock
        with file_lock(self.directory / (request_id + '.lock')):
            if not final.exists():
                temp = final.with_suffix(final.suffix + '.partial'); conn = self.connect()
                try:
                    self.authorize(conn.cursor(), user, ['backup']); conn.rollback()
                    if self.pg():
                        executable = shutil.which('pg_dump')
                        if not executable: raise ValueError('Install matching PostgreSQL client tools (pg_dump) on the POS Server')
                        info = conn.info; env = os.environ.copy()
                        for key, attr in [('PGHOST', 'host'), ('PGPORT', 'port'), ('PGDATABASE', 'dbname'), ('PGUSER', 'user'), ('PGPASSWORD', 'password')]:
                            env[key] = str(getattr(info, attr) or '')
                        env['PGCONNECT_TIMEOUT'] = '15'
                        result = subprocess.run([executable, '--format=custom', '--no-password', '--file', str(temp)], env=env,
                            capture_output=True, timeout=600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                        if result.returncode: raise ValueError('PostgreSQL backup failed. Check server client-tool version and database access.')
                    else:
                        dest = sqlite3.connect(temp)
                        try:
                            conn.backup(dest)
                            if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('Snapshot integrity check failed')
                        finally: dest.close()
                    temp.replace(final)
                finally:
                    conn.close(); temp.unlink(missing_ok=True)
            self.audit(user, 'backup.create', request_id, final.name)
            return dict(message='Server snapshot created', **self.metadata(final))

    def rehearse(self, user, name, checksum):
        self.permitted(user, 'restore'); path = self.path(name)
        if self.metadata(path)['sha256'] != checksum: raise ValueError('Backup changed; refresh before restoring a copy')
        if path.suffix == '.zip':
            from server.native_backup_package import rehearse_package
            from server.native_file_lock import file_lock
            directory = self.directory / 'package_rehearsals'; directory.mkdir(exist_ok=True)
            target = directory / path.stem
            with file_lock(directory / (path.name + '.lock')):
                result = rehearse_package(path, target, checksum)
            self.audit(user, 'backup.package_rehearse', path.stem.removeprefix('native-'), name)
            return dict(result, copy_name='package_rehearsals/' + path.stem)
        if path.suffix != '.db': raise ValueError('PostgreSQL restore rehearsal requires a separate PostgreSQL test database and pg_restore; arrange this on the server')
        directory = self.directory / 'restore_rehearsals'; directory.mkdir(exist_ok=True)
        target = directory / name
        from server.native_file_lock import file_lock
        with file_lock(directory / (name + '.lock')):
            source = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
            temp = target.with_suffix('.partial')
            try:
                if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('Backup integrity check failed')
                destination = sqlite3.connect(temp)
                try:
                    source.backup(destination)
                    if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('Restored copy integrity check failed')
                    tables = destination.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
                    counts = {name: destination.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0] for (name,) in tables}
                finally: destination.close()
                temp.replace(target)
            finally: source.close(); temp.unlink(missing_ok=True)
            self.audit(user, 'backup.rehearse', path.stem.removeprefix('native-'), name)
            return dict(message='Restored separate SQLite copy; integrity check OK', tables=counts, copy_name='restore_rehearsals/' + name)

    def package(self, user, request_id):
        from server.native_file_lock import file_lock
        from server.native_backup_package import build_package, verify_package
        self.permitted(user, 'backup'); request_id = str(UUID(request_id))
        self.directory.mkdir(parents=True, exist_ok=True)
        final = self.directory / f'native-{request_id}.zip'
        with file_lock(self.directory / (request_id + '.package.lock')):
            if not final.exists():
                snapshot = self.create(user, request_id)
                temporary = final.with_suffix('.zip.partial')
                try:
                    build_package(self.path(snapshot['name']), self.asset_root, temporary)
                    verify_package(temporary)
                    temporary.replace(final)
                finally: temporary.unlink(missing_ok=True)
            self.audit(user, 'backup.package', request_id, final.name)
            return dict(message='Database and managed-file package created. Review manifest coverage before restoring.', **self.metadata(final))

    def verify(self, user, name, checksum):
        """Read the selected artifact without restoring or touching business data."""
        import time
        self.permitted(user, 'backup')
        path = self.path(name)
        metadata = self.metadata(path)
        if metadata['sha256'] != checksum: raise ValueError('Backup changed; refresh before verifying')
        if path.suffix == '.zip':
            from server.native_backup_package import verify_package
            import zipfile
            try: count = verify_package(path)
            except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc: raise ValueError('Backup package verification failed') from exc
            message = f'Package manifest and {count} file checksums verified. Database restore compatibility and external path mappings still require a separate rehearsal.'
        elif path.suffix == '.db':
            source = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)
            deadline = time.monotonic() + 30
            try:
                source.execute('PRAGMA query_only=ON')
                source.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
                checks = source.execute('PRAGMA quick_check(20)').fetchall()
                if checks != [('ok',)]: raise ValueError('SQLite snapshot quick check failed; retain the file for administrator review')
                count = source.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
            except sqlite3.Error as exc: raise ValueError('SQLite snapshot verification failed or timed out') from exc
            finally: source.close()
            message = f'SQLite quick check passed; {count} user tables. This is not a full restore or application compatibility test.'
        else:
            executable = shutil.which('pg_restore')
            if not executable: raise ValueError('Install matching PostgreSQL client tools (pg_restore) on the POS Server')
            try:
                result = subprocess.run([executable, '--list', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except (OSError, subprocess.TimeoutExpired) as exc: raise ValueError('PostgreSQL archive inspection failed or timed out') from exc
            if result.returncode: raise ValueError('PostgreSQL archive index could not be read; check client version and backup file')
            message = 'PostgreSQL archive index is readable. Data blocks and restore compatibility are not verified; a separate test-database restore is still required.'
        if self.metadata(path)['sha256'] != checksum: raise ValueError('Backup changed during verification; refresh and try again')
        return dict(message=message, name=name, sha256=checksum, checked_at=datetime.now().isoformat(timespec='seconds'))

    def audit(self, user, operation, request_id, name):
        conn = self.connect(); c = conn.cursor()
        try:
            self.prepare(conn)
            if not self.pg(): c.execute('BEGIN IMMEDIATE')
            if self.pg(): c.execute('LOCK TABLE native_admin_requests IN SHARE ROW EXCLUSIVE MODE')
            audit_id = f'{request_id}:{operation}'
            c.execute('SELECT user_id FROM native_admin_requests WHERE request_id=?', (audit_id,))
            row = c.fetchone()
            if row:
                conn.rollback(); return
            c.execute('SELECT username FROM users WHERE id=?', (user['id'],)); username = c.fetchone()[0]
            self.insert(c, 'user_activity_log', dict(user_id=user['id'], username=username, action=operation, details=name,
                                                   created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            c.execute('INSERT INTO native_admin_requests(request_id,user_id,operation,payload_hash,result_json,created_at) VALUES(?,?,?,?,?,?)',
                      (audit_id, user['id'], operation, name, '{}', datetime.now().isoformat()))
            conn.commit()
        except Exception: conn.rollback(); raise
        finally: conn.close()


def install_routes(app, current_user, repository=None):
    from fastapi import Depends, HTTPException
    from fastapi.responses import FileResponse
    from pydantic import BaseModel, Field
    repo = repository or BackupRepository()
    class Command(BaseModel):
        request_id: str = Field(min_length=36, max_length=36)
        name: str = ''
        sha256: str = ''
    class RecoverableCommand(BaseModel):
        request_id: str = Field(min_length=36, max_length=36)
        operation: str
        values: dict
    def run(action):
        try: return action()
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    @app.get('/api/native/backups')
    def read(user=Depends(current_user)): return run(lambda: repo.read(user))
    @app.get('/api/native/backups/verify/{name}')
    def verify(name: str, sha256: str, user=Depends(current_user)):
        return run(lambda: repo.verify(user, name, sha256))
    @app.post('/api/native/backups/commands')
    def command(payload: RecoverableCommand, user=Depends(current_user)):
        def execute():
            if payload.operation == 'backup.create': result = repo.create(user, payload.request_id)
            elif payload.operation == 'backup.package': result = repo.package(user, payload.request_id)
            elif payload.operation == 'backup.rehearse': result = repo.rehearse(user, payload.values['name'], payload.values['sha256'])
            else: raise ValueError('Unknown backup operation')
            return {'result': dict(result, request_id=payload.request_id, operation=payload.operation)}
        return run(execute)
    @app.post('/api/native/backups/create')
    def create(payload: Command, user=Depends(current_user)): return run(lambda: repo.create(user, payload.request_id))
    @app.post('/api/native/backups/rehearse')
    def rehearse(payload: Command, user=Depends(current_user)): return run(lambda: repo.rehearse(user, payload.name, payload.sha256))
    @app.get('/api/native/backups/download/{name}')
    def download(name: str, user=Depends(current_user)):
        def response():
            repo.permitted(user, 'backup'); path = repo.path(name)
            return FileResponse(path, filename=path.name, media_type='application/octet-stream')
        return run(response)
