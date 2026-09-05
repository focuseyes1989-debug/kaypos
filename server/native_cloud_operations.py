"""Serialized, replay-safe access to the existing one-shot cloud service."""
from datetime import datetime
import hashlib, json
from pathlib import Path
from uuid import UUID
from server.native_admin import AdminRepository
from server.native_file_lock import file_lock
from server.native_cloud_config import destination

class CloudAdapter:
    def effective(self):
        from services.cloud_sync_service import cloud_database_url, cloud_sync_enabled
        from utils.db_compat import database_url, is_postgres_backend
        return cloud_database_url(), cloud_sync_enabled(), database_url(), 'PostgreSQL' if is_postgres_backend() else 'SQLite'
    def run(self, operation):
        from services.cloud_sync_service import CloudSyncService
        service=CloudSyncService()
        return service.sync_once() if operation=='cloud.sync' else service.pull_once()

class CloudOperationsRepository(AdminRepository):
    def __init__(self, service=None, adapter=None, lock_path=None, backup_repository=None):
        super().__init__(service); self.adapter=adapter or CloudAdapter()
        if backup_repository is None:
            from server.native_backup import BackupRepository
            backup_repository=BackupRepository(service)
        self.backup_repository=backup_repository
        self.lock_path=Path(lock_path or Path(__file__).resolve().parents[1]/'database/native_backups/cloud-operation.lock')
    def authorize_operation(self,user,operation):
        required=['settings','edit_settings']+(['backup','restore'] if operation=='cloud.pull' else [])
        conn=self.connect()
        try:self.authorize(conn.cursor(),user,required)
        finally:conn.rollback();conn.close()
    def preflight(self,user):
        self.authorize_operation(user,'cloud.sync')
        cloud,enabled,primary,backend=self.adapter.effective()
        if not cloud:return dict(ready=False,destination='Not configured',enabled=enabled,backend=backend,message='Configure the effective cloud URL on the POS Server before running a manual operation.')
        host,port,database=destination(cloud);same=False
        if primary:
            try:same=destination(primary)==(host,port,database)
            except ValueError:pass
        return dict(ready=not same,destination=f'{host}:{port} / {database}',enabled=enabled,backend=backend,message=('Cloud and primary database resolve to the same configured host/port/database; manual operations are blocked.' if same else 'Manual operations use effective running-process configuration. The enable flag controls the scheduler, not these explicit buttons.'))
    def _reserve(self,user,request_id,operation,fingerprint):
        conn=self.connect();c=conn.cursor()
        try:
            self.prepare(conn)
            if not self.pg():c.execute('BEGIN IMMEDIATE')
            else:c.execute('LOCK TABLE native_admin_requests IN SHARE ROW EXCLUSIVE MODE')
            c.execute('SELECT user_id,operation,payload_hash,result_json FROM native_admin_requests WHERE request_id=?',(request_id,));row=c.fetchone()
            if row:
                if int(row[0])!=int(user['id']) or row[1]!=operation or row[2]!=fingerprint:raise ValueError('Request ID belongs to a different cloud operation')
                conn.rollback();return json.loads(row[3]) if row[3] else dict(status='needs_review',message='The earlier server process stopped before recording a result. Inspect local/cloud data and backups before starting a new operation.')
            c.execute('INSERT INTO native_admin_requests(request_id,user_id,operation,payload_hash,result_json,created_at) VALUES(?,?,?,?,?,?)',(request_id,user['id'],operation,fingerprint,'',datetime.now().isoformat()));conn.commit();return None
        except Exception:conn.rollback();raise
        finally:conn.close()
    def _finish(self,user,request_id,operation,fingerprint,result):
        conn=self.connect();c=conn.cursor()
        try:
            self.prepare(conn)
            if not self.pg():c.execute('BEGIN IMMEDIATE')
            else:c.execute('LOCK TABLE native_admin_requests IN SHARE ROW EXCLUSIVE MODE')
            c.execute('SELECT result_json FROM native_admin_requests WHERE request_id=? AND user_id=? AND operation=? AND payload_hash=?',(request_id,user['id'],operation,fingerprint));row=c.fetchone()
            if not row:raise ValueError('Cloud request reservation was lost; administrator review is required')
            if row[0]:conn.rollback();return json.loads(row[0])
            encoded=json.dumps(result,ensure_ascii=False,separators=(',',':'));c.execute('UPDATE native_admin_requests SET result_json=? WHERE request_id=?',(encoded,request_id))
            c.execute('SELECT username FROM users WHERE id=?',(user['id'],));username=c.fetchone()[0]
            self.insert(c,'user_activity_log',dict(user_id=user['id'],username=username,action=operation,details=f"status={result['status']}; tables={result['synced_tables']}; rows={result['synced_rows']}; backup_created={result['backup_created']}",created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')));conn.commit();return result
        except Exception:conn.rollback();raise
        finally:conn.close()
    def execute(self,user,request_id,operation):
        if operation not in ('cloud.sync','cloud.pull'):raise ValueError('Unknown cloud operation')
        request_id=str(UUID(request_id));self.authorize_operation(user,operation);state=self.preflight(user)
        if not state['ready']:raise ValueError(state['message'])
        fingerprint=hashlib.sha256(operation.encode()).hexdigest();self.lock_path.parent.mkdir(parents=True,exist_ok=True)
        with file_lock(self.lock_path):
            replay=self._reserve(user,request_id,operation,fingerprint)
            if replay is not None:return replay
            safety_backup=False
            try:
                if operation=='cloud.pull':
                    self.backup_repository.create(user,request_id);safety_backup=True
                raw=self.adapter.run(operation)
            except Exception:raw=None
            ok=bool(raw and raw.ok)
            result=dict(status='completed' if ok else 'failed',operation=operation,synced_tables=max(0,int(getattr(raw,'synced_tables',0) or 0)),synced_rows=max(0,int(getattr(raw,'synced_rows',0) or 0)),backup_created=safety_backup or bool(getattr(raw,'backup_path','')),message=('Cloud operation completed.' if ok else 'Cloud operation failed or was only partly completed. Inspect both databases and backups before retrying.'))
            return self._finish(user,request_id,operation,fingerprint,result)

def install_routes(app,current_user,repository=None):
    from fastapi import Depends,HTTPException
    from pydantic import BaseModel,Field
    repo=repository or CloudOperationsRepository()
    class Command(BaseModel):
        request_id:str=Field(min_length=36,max_length=36)
        operation:str
        values:dict=Field(default_factory=dict)
    def run(action):
        try:return action()
        except PermissionError as exc:raise HTTPException(403,str(exc)) from exc
        except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    @app.get('/api/native/cloud_operations')
    def preflight(user=Depends(current_user)):return run(lambda:repo.preflight(user))
    @app.post('/api/native/cloud_operations/commands')
    def command(payload:Command,user=Depends(current_user)):
        expected='SYNC TO CLOUD' if payload.operation=='cloud.sync' else 'PULL FROM CLOUD' if payload.operation=='cloud.pull' else ''
        if payload.values.get('confirmation')!=expected:raise HTTPException(400,'Typed cloud-operation confirmation does not match')
        return run(lambda:{'result':dict(repo.execute(user,payload.request_id,payload.operation),request_id=payload.request_id)})
