"""Explicit server-owned device operations. No background workers are started."""
from services.employee_transaction import transaction
from server.native_admin import AdminRepository, constraint_error
from server.native_catalog import digest, number, flag
from contextvars import ContextVar
import json
from uuid import UUID

_device_read = ContextVar('native_device_read', default=None)


DEVICE_FIELDS = ('id', 'device_no', 'name', 'ip_address', 'port', 'serial_no', 'last_sync_at', 'is_active')
MAPPING_FIELDS = ('id', 'device_id', 'employee_id', 'device_user_id')


class OperationsRepository(AdminRepository):
    def __init__(self, service=None, employee=None, device=None):
        super().__init__(service, employee); self._device = device

    @property
    def device(self):
        if self._device is None:
            from services import zkteco_service
            self._device = zkteco_service
        return self._device

    def prepare(self, conn, employee=False):
        super().prepare(conn, employee=True)
        with transaction(conn): self.device.ensure_zkteco_schema()
        conn.commit()

    def lock_tables(self, operation):
        return 'users,user_roles,employees,shifts,employee_shifts,employee_leave,attendance,zkteco_devices,zkteco_employee_mappings,zkteco_attendance_logs'

    def mappings(self, c, device_id):
        return self.rows(c, '''SELECT m.device_user_id,e.employee_no FROM zkteco_employee_mappings m
            JOIN employees e ON e.id=m.employee_id WHERE m.device_id=? AND e.employment_status='Active' ORDER BY e.id''', (device_id,))

    def command(self, user, request_id, operation, values):
        if operation not in ('device.test', 'device.sync'): return super().command(user, request_id, operation, values)
        request_id = str(UUID(request_id)); conn = self.connect(); c = conn.cursor()
        try:
            self.authorize(c, user, self.required(operation, values)); self.prepare(conn)
            c.execute('SELECT user_id,payload_hash,result_json FROM native_admin_requests WHERE request_id=?', (request_id,))
            prior = c.fetchone()
            if prior:
                if prior[0] != user['id'] or prior[1] != digest([operation, values]): raise ValueError('Request ID belongs to another change')
                if prior[2]: return json.loads(prior[2])
            old = self.checked_record(c, 'zkteco_devices', values, DEVICE_FIELDS)
            c.execute('SELECT comm_key FROM zkteco_devices WHERE id=?', (old['id'],)); key = c.fetchone()[0]
            mappings = self.mappings(c, old['id']) if operation == 'device.sync' else []
            if operation == 'device.sync' and (not old['is_active'] or not mappings): raise ValueError('Enable the device and configure active employee mappings first')
        finally: conn.rollback(); conn.close()
        # Network access occurs with no open database connection or write lock.
        data = self.device.test_device(old['ip_address'], old['port'], key) if operation == 'device.test' else self.device.read_device_data(old['ip_address'], old['port'], key)
        token = _device_read.set(dict(data=data, mappings=digest(mappings)))
        try: return super().command(user, request_id, operation, values)
        finally: _device_read.reset(token)

    def required(self, operation, v):
        if operation in ('device.save', 'mapping.save', 'mapping.delete'): return ['settings', 'edit_settings', 'employees', 'manage_employees']
        if operation == 'device.sync': return ['settings', 'employees', 'manage_attendance', 'manage_employees']
        if operation == 'device.test': return ['settings', 'edit_settings']
        raise ValueError('Unknown device action')

    def read(self, user):
        conn = self.connect(); c = conn.cursor()
        try:
            self.authorize(c, user, ['settings', 'employees'])
            self.prepare(conn)
            devices = self.rows(c, "SELECT " + ','.join(DEVICE_FIELDS) + ' FROM zkteco_devices ORDER BY device_no')
            mappings = self.rows(c, 'SELECT ' + ','.join(MAPPING_FIELDS) + ' FROM zkteco_employee_mappings ORDER BY id')
            for row in devices + mappings: row['revision'] = digest(row)
            employees = self.rows(c, 'SELECT id,employee_no,full_name FROM employees ORDER BY full_name')
            return dict(devices=devices, mappings=mappings, employees=employees, version=1)
        finally: conn.rollback(); conn.close()

    def apply(self, conn, c, operation, v, actor):
        with transaction(conn):
            if operation == 'device.save':
                old = self.checked_record(c, 'zkteco_devices', v, DEVICE_FIELDS) if v.get('id') else None
                data = dict(device_no=number(v.get('device_no'), True, minimum=1, maximum=9999), name=str(v.get('name') or '')[:100],
                            ip_address=str(v.get('ip_address') or '').strip(), port=number(v.get('port', 4370), True, minimum=1, maximum=65535), is_active=flag(v.get('is_active', True)))
                # Device addresses are configuration restricted to settings managers.
                import ipaddress
                ipaddress.ip_address(data['ip_address'])
                if old and v.get('comm_key') in (None, ''):
                    c.execute('SELECT comm_key FROM zkteco_devices WHERE id=?', (old['id'],)); data['comm_key'] = c.fetchone()[0]
                else: data['comm_key'] = number(v.get('comm_key'), True, maximum=2147483647)
                record_id = self.device.save_device(data, old['id'] if old else None)
                return dict(id=record_id, message='Device configuration saved')
            if operation in ('mapping.save', 'mapping.delete'):
                old = self.checked_record(c, 'zkteco_employee_mappings', v, MAPPING_FIELDS) if v.get('id') else None
                if operation == 'mapping.delete':
                    if not old: raise ValueError('Select a mapping')
                    self.device.delete_mapping(old['id'])
                else:
                    device_id = number(v.get('device_id'), True, minimum=1); employee_id = number(v.get('employee_id'), True, minimum=1)
                    for table, record_id in [('zkteco_devices', device_id), ('employees', employee_id)]:
                        c.execute(f'SELECT id FROM {table} WHERE id=?', (record_id,))
                        if not c.fetchone(): raise ValueError('Select an existing device and employee')
                    if old and (old['device_id'] != device_id or old['employee_id'] != employee_id): raise ValueError('Delete this mapping and create a new one to change its employee/device')
                    if not old:
                        c.execute('SELECT id FROM zkteco_employee_mappings WHERE device_id=? AND employee_id=?', (device_id, employee_id))
                        if c.fetchone(): raise ValueError('Mapping already exists; refresh and edit it')
                    user_id = str(v.get('device_user_id') or '').strip()
                    if not user_id or len(user_id) > 30: raise ValueError('Device user ID is required (maximum 30 characters)')
                    self.device.save_mapping(device_id, employee_id, user_id)
                return dict(message='Device mapping saved')
            old = self.checked_record(c, 'zkteco_devices', v, DEVICE_FIELDS)
            c.execute('SELECT comm_key FROM zkteco_devices WHERE id=?', (old['id'],)); key = c.fetchone()[0]
            if operation == 'device.test':
                result = _device_read.get()['data']
                return dict(message='Device connection OK', details=result)
            if operation == 'device.sync':
                if not old['is_active']: raise ValueError('Device is inactive')
                mappings = self.mappings(c, old['id'])
                if not mappings: raise ValueError('No active employee mappings for this device')
                snapshot = _device_read.get()
                if not snapshot or digest(mappings) != snapshot['mappings']: raise ValueError('Employee mappings changed while reading the device. Refresh and sync again.')
                results = [self.device.sync_employee(old['device_no'], old['ip_address'], old['port'], key, r['device_user_id'], r['employee_no'], snapshot=snapshot['data'], initialize_schema=False) for r in mappings]
                return dict(message=f"Attendance imported: {sum(r['inserted'] for r in results)} new punches, {sum(r['duplicates'] for r in results)} duplicates", details=results)
            raise ValueError('Unsupported device action')


def install_routes(app, current_user, repository=None):
    from fastapi import Depends, HTTPException
    from pydantic import BaseModel, Field
    repo = repository or OperationsRepository()

    class Command(BaseModel):
        request_id: str = Field(min_length=36, max_length=36)
        operation: str = Field(max_length=60)
        values: dict

    @app.get('/api/native/operations')
    def read(user=Depends(current_user)):
        try: return repo.read(user)
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc

    @app.post('/api/native/operations/commands')
    def command(payload: Command, user=Depends(current_user)):
        try: return {'result': repo.command(user, payload.request_id, payload.operation, payload.values)}
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc: return {'rejected': str(exc)}
        except Exception as exc:
            if constraint_error(exc): return {'rejected': 'Device number or employee mapping already exists. Refresh and edit the existing record.'}
            # Network exceptions may include device details. Do not expose credentials.
            raise HTTPException(503, 'Device operation failed. Check the device connection and recover the pending command.') from exc
