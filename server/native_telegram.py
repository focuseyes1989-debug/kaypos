"""Recoverable server .env edits; never start a listener or send a message."""
from datetime import datetime
import json
import os
import re
from uuid import UUID
from pathlib import Path
from server.native_admin import AdminRepository
from server.native_catalog import digest as payload_digest
from server.native_file_lock import file_lock, FileOperationBusy
from utils import telegram_config_store as store


def enabled(value): return str(value or '').lower() in ('1', 'true', 'yes', 'on')


class TelegramRepository(AdminRepository):
    label = 'Telegram'
    operation = 'telegram.save'
    def __init__(self, service=None, path=None, environment=None):
        super().__init__(service); self.path = Path(path) if path else store.env_path()
        self.environment = os.environ if environment is None else environment

    def authorize_config(self, c, user):
        self.authorize(c, user, ['settings', 'edit_settings'])
        c.execute('SELECT role FROM users WHERE id=?', (user['id'],))
        if str(c.fetchone()[0]).lower() != 'admin': raise PermissionError(f'Administrator access is required for server {self.label} configuration')

    def read(self, user):
        conn = self.connect()
        try:
            self.authorize_config(conn.cursor(), user)
            raw = store.read(self.path); values = store.parse(raw)
            return dict(revision=store.digest(raw), enabled=enabled(values.get(store.KEYS[0])),
                        listener_enabled=enabled(values.get(store.KEYS[1])), chat_id=values.get(store.KEYS[3], ''),
                        token_configured=bool(values.get(store.KEYS[2])),
                        environment_overrides=[key for key in store.KEYS if key in self.environment],
                        pending=store.marker_path(self.path).exists(),
                        message='Edits change the server .env file. Restart the existing server/listener owner to apply them; process/system environment values take precedence. Saving does not start a listener or send messages.')
        finally: conn.rollback(); conn.close()

    def updated(self, raw, values):
        old = store.parse(raw)
        for key in ('enabled', 'listener_enabled', 'clear_token'):
            if values.get(key, False) not in (True, False): raise ValueError('Invalid checkbox value')
        token = str(values.get('bot_token') or '').strip()
        if token and values.get('clear_token'): raise ValueError('Choose either replacement token or clear token')
        if token and not re.fullmatch(r'\d{5,20}:[A-Za-z0-9_-]{20,200}', token): raise ValueError('Invalid Telegram bot token format')
        token = '' if values.get('clear_token') else token or old.get(store.KEYS[2], '')
        chat = str(values.get('chat_id') or '').strip()
        if chat and not re.fullmatch(r'-?\d{1,20}|@[A-Za-z0-9_]{5,64}', chat): raise ValueError('Enter a numeric chat ID or @channel_name')
        if values.get('listener_enabled') and not values.get('enabled'): raise ValueError('Enable Telegram before enabling its listener')
        if values.get('enabled') and (not token or not chat): raise ValueError('Bot token and chat ID are required when Telegram is enabled')
        return store.render(raw, dict(zip(store.KEYS, ('1' if values.get('enabled') else '0', '1' if values.get('listener_enabled') else '0', token, chat))))

    def command(self, user, request_id, operation, values):
        request_id = str(UUID(request_id))
        if operation != self.operation: raise ValueError('Unknown configuration operation')
        fingerprint = payload_digest([operation, values]); conn = self.connect(); c = conn.cursor()
        try:
            self.authorize_config(c, user); self.prepare(conn)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with file_lock(store.lock_path(self.path)):
                if self.pg(): c.execute('LOCK TABLE users,user_roles,native_admin_requests IN SHARE ROW EXCLUSIVE MODE')
                else: c.execute('BEGIN IMMEDIATE')
                self.authorize_config(c, user)
                marker_path = store.marker_path(self.path)
                c.execute('SELECT user_id,payload_hash,result_json FROM native_admin_requests WHERE request_id=?', (request_id,))
                prior = c.fetchone()
                if prior:
                    if prior[0] != user['id'] or prior[1] != fingerprint: raise ValueError('Request ID belongs to another change')
                    if prior[2]:
                        result = json.loads(prior[2]); conn.rollback()
                        if marker_path.exists():
                            marker = json.loads(marker_path.read_text())
                            if marker['request_id'] == request_id: marker_path.unlink()
                        return result
                raw = store.read(self.path); current = store.digest(raw)
                if marker_path.exists():
                    marker = json.loads(marker_path.read_text())
                    if marker['request_id'] != request_id: raise ValueError('Another Telegram/cloud configuration change needs recovery before editing')
                    if marker['user_id'] != user['id'] or marker['fingerprint'] != fingerprint: raise ValueError('Pending request belongs to another change')
                    if current not in (marker['before'], marker['after']):
                        raise RuntimeError('The server .env changed outside this pending request. Administrator review is required before recovery.')
                    output = self.updated(raw, values) if current == marker['before'] else None
                    if output is not None and store.digest(output) != marker['after']:
                        raise RuntimeError('Pending server settings no longer match. Administrator review is required.')
                else:
                    if values.get('revision') != current: raise ValueError('Server configuration changed. Refresh before saving.')
                    output = self.updated(raw, values)
                    marker = dict(request_id=request_id, user_id=user['id'], fingerprint=fingerprint, before=current, after=store.digest(output))
                    store.atomic_write(marker_path, json.dumps(marker).encode())
                # From this point, failures are unknown outcomes: retain the marker
                # and encrypted client request, then recover the same UUID.
                if output is not None: store.atomic_write(self.path, output)
                result = dict(request_id=request_id, operation=operation, message=f'{self.label} server file saved. Apply through the existing server/service owner; environment overrides may still take precedence. No service or transfer was started.')
                c.execute('SELECT username FROM users WHERE id=?', (user['id'],)); actor = c.fetchone()[0]
                self.insert(c, 'user_activity_log', dict(user_id=user['id'], username=actor, action=operation,
                    details=json.dumps(dict(request_id=request_id, message=f'Server {self.label} configuration saved; no service/transfer started')), created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                c.execute('''INSERT INTO native_admin_requests(request_id,user_id,operation,payload_hash,result_json,created_at)
                    VALUES(?,?,?,?,?,?)''', (request_id, user['id'], operation, fingerprint, json.dumps(result), datetime.now().isoformat()))
                conn.commit(); marker_path.unlink(); return result
        finally: conn.rollback(); conn.close()


def install_routes(app, current_user, repository=None, namespace='telegram'):
    from fastapi import Depends, HTTPException
    from pydantic import BaseModel, Field
    repo = repository or TelegramRepository()
    class Command(BaseModel):
        request_id: str = Field(min_length=36, max_length=36)
        operation: str
        values: dict
    @app.get(f'/api/native/{namespace}')
    def read(user=Depends(current_user)):
        try: return repo.read(user)
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except Exception as exc: raise HTTPException(503, f'Cannot read the server {repo.label} settings file') from exc
    @app.post(f'/api/native/{namespace}/commands')
    def command(payload: Command, user=Depends(current_user)):
        try: return {'result': repo.command(user, payload.request_id, payload.operation, payload.values)}
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except FileOperationBusy as exc: raise HTTPException(503, 'Server configuration save is already running. Recover the same request after it finishes.') from exc
        except ValueError as exc:
            # Never clear recovery after the filesystem transaction started.
            if store.marker_path(repo.path).exists():
                raise HTTPException(503, 'Server configuration save needs recovery or administrator review. Retry the same request.') from exc
            return {'rejected': str(exc)}
        except Exception as exc:
            raise HTTPException(503, 'Server configuration save was not confirmed. Recover the same request; check server file/database access if it remains unresolved.') from exc
