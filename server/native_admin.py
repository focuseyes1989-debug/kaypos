"""Native employee and administration API; fresh authorization and atomic audit.

Employee operations reuse the original service inside one request-local outer
transaction. No original window, scheduler, listener or printer is constructed.
"""
from datetime import date, datetime
import json
import hashlib
import os
import re
from uuid import UUID

from native_pos.admin_schema import EMPLOYEE_SECTIONS, SETTINGS
from server.native_business import BusinessRepository, day, money
from server.native_catalog import digest, number, flag
from services.employee_transaction import transaction


def constraint_error(error):
    import sqlite3
    return isinstance(error, sqlite3.IntegrityError) or str(getattr(error, 'sqlstate', '') or '').startswith('23')


class AdminRepository(BusinessRepository):
    def __init__(self, service=None, employee=None):
        super().__init__(service)
        self._employee = employee

    @property
    def employee(self):
        if self._employee is None:
            from services import employee_service
            self._employee = employee_service
        return self._employee

    def prepare(self, conn, employee=False):
        c = conn.cursor()
        if employee:
            with transaction(conn):
                self.employee.ensure_employee_schema(grant_permissions=False)
        c.execute('''CREATE TABLE IF NOT EXISTS native_admin_requests (
            request_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, operation TEXT NOT NULL,
            payload_hash TEXT NOT NULL, result_json TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)''')
        # Existing installations already have this table; no history is replaced.
        pk = 'SERIAL PRIMARY KEY' if self.pg() else 'INTEGER PRIMARY KEY AUTOINCREMENT'
        c.execute(f'''CREATE TABLE IF NOT EXISTS user_activity_log (
            id {pk}, user_id INTEGER, username TEXT, action TEXT, details TEXT,
            ip_address TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

    def read(self, user, section, start='', end='', query='', offset=0):
        conn = self.connect(); c = conn.cursor()
        try:
            if section in EMPLOYEE_SECTIONS:
                title, permission, table, manage, fields = EMPLOYEE_SECTIONS[section]
                self.authorize(c, user, ['employees', permission])
                self.prepare(conn, employee=True)
                self.authorize(c, user, ['employees', permission])
                start = day(start or date.today().replace(day=1)); end = day(end or date.today())
                if end < start: raise ValueError('End date must be on or after start date')
                if section == 'performance':
                    with transaction(conn): records = self.employee.performance_report(start, end)
                else:
                    columns = sorted(set(self.columns(c, table)) - {'photo_data'})
                    where, args = '', []
                    date_field = {'attendance': 'attendance_date', 'leave': 'start_date', 'advances': 'advance_date'}.get(section)
                    if date_field:
                        where = f' WHERE {date_field}>=? AND {date_field}<=?'; args = [start, end]
                    elif section == 'payroll':
                        where = ' WHERE period_month>=? AND period_month<=?'; args = [start[:7], end[:7]]
                    # Do not silently truncate employee/financial records.
                    records = self.rows(c, f"SELECT {','.join(columns)} FROM {table}{where} ORDER BY id DESC LIMIT 10001", args)
                    if len(records) > 10000: raise ValueError('More than 10,000 records; narrow the date range')
                    for record in records: record['revision'] = digest(record)
                employees = self.rows(c, 'SELECT id,employee_no,full_name,employment_status FROM employees ORDER BY full_name')
                names = {r['id']: r['full_name'] for r in employees}
                for record in records:
                    if 'employee_id' in record: record['employee_name'] = names.get(record['employee_id'], '')
                # Only employees managers receive account linkage choices.
                try:
                    self.authorize(c, user, ['manage_employees'])
                    users = self.rows(c, 'SELECT id,username,full_name FROM users WHERE is_active=1 ORDER BY username')
                except PermissionError: users = []
                shifts = self.rows(c, 'SELECT id,name FROM shifts WHERE is_active=1 ORDER BY name') if section in ('shifts', 'assignments') else []
                return dict(records=records, employees=employees, users=users, shifts=shifts, version=1)
            if section in SETTINGS:
                self.authorize(c, user, ['settings'])
                fields = SETTINGS[section]; keys = [f[0] for f in fields]
                existing = dict(c.execute('SELECT key,value FROM settings WHERE key IN (' + ','.join('?' for _ in keys) + ')', keys).fetchall())
                values = {}
                for key, label, kind, default in fields:
                    raw = existing.get(key, default)
                    values[key] = str(raw).lower() in ('1', 'true') if kind == 'bool' else raw
                return dict(values=values, revision=digest(existing), version=1)
            if section == 'activity':
                self.authorize(c, user, ['users', 'settings'])
                start = day(start or date.today()); end = day(end or date.today())
                rows = self.rows(c, '''SELECT id,created_at,username,action,details,ip_address FROM user_activity_log
                    WHERE DATE(created_at)>=? AND DATE(created_at)<=?
                    AND (LOWER(COALESCE(username,'')) LIKE ? OR LOWER(COALESCE(action,'')) LIKE ?)
                    ORDER BY id DESC LIMIT 100 OFFSET ?''', (start, end, '%' + query.lower() + '%', '%' + query.lower() + '%', number(offset, True)))
                return dict(records=rows, version=1)
            if section == 'roles':
                self.authorize(c, user, ['users'])
                rows = self.rows(c, 'SELECT id,name,description,permissions,is_system FROM user_roles ORDER BY name')
                for row in rows: row['revision'] = digest(row)
                return dict(records=rows, version=1)
            if section == 'users':
                self.authorize(c, user, ['users'])
                rows = self.rows(c, 'SELECT id,username,full_name,role,is_active,permissions FROM users ORDER BY username')
                for row in rows: row['revision'] = digest(row)
                return dict(records=rows, roles=[r['name'] for r in self.rows(c, 'SELECT name FROM user_roles ORDER BY name')], version=1)
            raise ValueError('Unknown administration page')
        finally:
            conn.rollback(); conn.close()

    def required(self, operation, v):
        if operation.startswith('employee.'):
            section = operation.split('.')[1]
            if section not in EMPLOYEE_SECTIONS: raise ValueError('Unknown employee action')
            _, permission, _, manage, _ = EMPLOYEE_SECTIONS[section]
            if not manage: raise ValueError('This page is read-only')
            return ['employees', permission, manage]
        if operation == 'settings.save': return ['settings', 'edit_settings']
        if operation == 'role.save': return ['users', 'edit_user']
        if operation == 'user.save': return ['users', 'edit_user' if v.get('id') else 'add_user']
        raise ValueError('Unknown administration action')

    def command(self, user, request_id, operation, values):
        request_id = str(UUID(request_id)); required = self.required(operation, values)
        fingerprint = digest([operation, values]); conn = self.connect(); c = conn.cursor()
        try:
            self.authorize(c, user, required)
            self.prepare(conn, operation.startswith('employee.'))
            if not self.pg(): c.execute('BEGIN IMMEDIATE')
            else:
                # Includes absent-row checks, legacy writes, salary expenses and auth edits.
                tables = self.lock_tables(operation)
                c.execute(f'LOCK TABLE {tables} IN SHARE ROW EXCLUSIVE MODE')
            self.authorize(c, user, required)
            c.execute('''INSERT INTO native_admin_requests(request_id,user_id,operation,payload_hash,created_at)
                VALUES(?,?,?,?,?) ON CONFLICT(request_id) DO NOTHING''',
                (request_id, user['id'], operation, fingerprint, datetime.now().isoformat()))
            c.execute('SELECT user_id,payload_hash,result_json FROM native_admin_requests WHERE request_id=?', (request_id,))
            owner, prior, result = c.fetchone()
            if owner != user['id'] or prior != fingerprint: raise ValueError('Request ID belongs to another change')
            if result: conn.rollback(); return json.loads(result)
            c.execute('SELECT username FROM users WHERE id=?', (user['id'],))
            actor = dict(user, username=c.fetchone()[0])
            result = self.apply(conn, c, operation, values, actor)
            result = dict(result, request_id=request_id, operation=operation)
            # Audit identifiers and outcome, never passwords, tokens or employee personal fields.
            self.insert(c, 'user_activity_log', dict(user_id=actor['id'], username=actor['username'],
                action=operation, details=json.dumps(dict(request_id=request_id, record_id=result.get('id'), message=result.get('message')), ensure_ascii=False),
                created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            c.execute('UPDATE native_admin_requests SET result_json=? WHERE request_id=?', (json.dumps(result, default=str), request_id))
            conn.commit(); return result
        except Exception:
            conn.rollback(); raise
        finally: conn.close()

    def apply(self, conn, c, operation, values, actor):
        if operation.startswith('employee.'):
            with transaction(conn): return self.change_employee(c, operation, values, actor)
        if operation == 'settings.save': return self.change_settings(c, values)
        if operation == 'role.save': return self.change_role(c, values, actor)
        return self.change_user(c, values, actor)

    def lock_tables(self, operation):
        tables = 'users, user_roles, settings'
        if operation.startswith('employee.'):
            tables += ',employees,shifts,employee_shifts,attendance,payrolls,employee_leave,employee_documents,salary_advances,commission_rules,cash_sessions,expenses,sales'
        return tables

    def checked_record(self, c, table, v, columns=None):
        columns = columns or sorted(set(self.columns(c, table)) - {'photo_data'})
        rows = self.rows(c, f"SELECT {','.join(columns)} FROM {table} WHERE id=?", (number(v.get('id'), True, minimum=1),))
        if not rows: raise ValueError('Record no longer exists')
        old = rows[0]
        if digest(old) != v.get('revision'): raise ValueError('Record changed. Refresh before editing.')
        return old

    def validated(self, fields, values):
        result = {}
        for key, label, kind, default in fields:
            value = values.get(key, default)
            if kind == 'bool': value = flag(value)
            elif kind == 'int': value = number(value, True)
            elif kind == 'money': value = money(value)
            elif kind == 'date': value = day(value)
            elif kind in ('employee', 'shift', 'user'): value = number(value, True, minimum=1) if value else None
            else:
                value = str(value or '').strip()
                if len(value) > 4000: raise ValueError(label + ' is too long')
                if isinstance(kind, tuple) and value not in kind: raise ValueError('Invalid ' + label)
            result[key] = value
        return result

    def change_employee(self, c, operation, v, actor):
        _, section, action = operation.split('.')
        _, _, table, _, fields = EMPLOYEE_SECTIONS[section]
        old = self.checked_record(c, table, v) if v.get('id') else None
        data = self.validated(fields, v) if action == 'save' else {}
        if data.get('employee_id'):
            c.execute('SELECT id FROM employees WHERE id=?', (data['employee_id'],))
            if not c.fetchone(): raise ValueError('Select an existing employee')
        elif any(f[0] == 'employee_id' for f in fields) and action == 'save':
            raise ValueError('Select an employee')
        service = self.employee; record_id = old['id'] if old else None
        if section == 'employees' and action == 'save':
            if not data['employee_no'] or not data['full_name']: raise ValueError('Employee number and full name are required')
            if data['date_of_birth']: day(data['date_of_birth'])
            # Preserve photo blob/path and biometric mapping when editing ordinary fields.
            preserved = self.rows(c, 'SELECT * FROM employees WHERE id=?', (record_id,))[0] if old else {}
            record_id = service.save_employee(dict(preserved, **data), record_id)
        elif section == 'shifts' and action == 'save':
            if not data['name']: raise ValueError('Shift name is required')
            for key in ('start_time', 'end_time'): self.clock_value(data[key], required=True)
            if data['break_minutes'] > 1440: raise ValueError('Break cannot exceed 24 hours')
            if old:
                self.update(c, table, old['id'], data)
                service.recalculate_attendance_categories()
            else: service.save_shift(data['name'], data['start_time'], data['end_time'], data['break_minutes'], data['is_overnight'])
        elif section == 'assignments' and action in ('save', 'delete'):
            if action == 'delete':
                if not old: raise ValueError('Select an assignment')
                affected = service.delete_shift_assignment(old['id']); service.recalculate_attendance_categories(affected)
            else:
                if not data['shift_id']: raise ValueError('Select a shift')
                c.execute('SELECT id FROM shifts WHERE id=? AND is_active=1', (data['shift_id'],))
                if not c.fetchone(): raise ValueError('Select an active shift')
                if data['effective_to'] and day(data['effective_to']) < data['effective_from']: raise ValueError('Invalid effective date range')
                if data['weekly_off_days'] and not re.fullmatch(r'[0-6](,[0-6])*', data['weekly_off_days']): raise ValueError('Weekly off days must be comma-separated numbers 0 to 6')
                if old:
                    affected = service.update_shift_assignment(old['id'], **data)
                    service.recalculate_attendance_categories(affected)
                else:
                    c.execute('SELECT id FROM employee_shifts WHERE employee_id=? AND effective_from=?', (data['employee_id'], data['effective_from']))
                    if c.fetchone(): raise ValueError('Assignment already exists; edit it after refreshing')
                    record_id = service.assign_shift(data['employee_id'], data['shift_id'], data['effective_from'], data['weekly_off_days'])
                    if data['effective_to']: self.update(c, table, record_id, {'effective_to': data['effective_to']})
                service.recalculate_attendance_categories(data['employee_id'])
        elif section == 'attendance' and action == 'save':
            if not data['correction_reason']: raise ValueError('Correction reason is required')
            for key in ('check_in', 'check_out'): self.clock_value(data[key])
            if old and (old['employee_id'] != data['employee_id'] or str(old['attendance_date']) != data['attendance_date']):
                raise ValueError('Employee/date cannot change on an attendance correction')
            if not old:
                c.execute('SELECT id FROM attendance WHERE employee_id=? AND attendance_date=?', (data['employee_id'], data['attendance_date']))
                if c.fetchone(): raise ValueError('Attendance exists. Refresh and edit the existing record.')
            service.save_attendance(data['employee_id'], data['attendance_date'], data['check_in'], data['check_out'], data['status'], data['notes'], actor['id'], data['correction_reason'])
            # Manual edits store an explicit status, but late minutes must not
            # retain a prior device-import value after the time is corrected.
            c.execute('''SELECT s.start_time FROM employee_shifts es JOIN shifts s ON s.id=es.shift_id
                WHERE es.employee_id=? AND es.effective_from<=? AND (es.effective_to IS NULL OR es.effective_to>=?)
                ORDER BY es.effective_from DESC,es.id DESC LIMIT 1''', (data['employee_id'], data['attendance_date'], data['attendance_date']))
            shift = c.fetchone(); late = 0
            if shift and data['check_in'] and data['status'] == 'Late':
                h, m = map(int, str(shift[0])[:5].split(':')); ih, im = map(int, data['check_in'].split(':')); late = max(0, ih * 60 + im - h * 60 - m)
            c.execute('UPDATE attendance SET late_minutes=? WHERE employee_id=? AND attendance_date=?', (late, data['employee_id'], data['attendance_date']))
        elif section == 'leave' and action == 'save' and not old:
            if not data['leave_type'] or data['days'] <= 0: raise ValueError('Leave type and positive days are required')
            if data['end_date'] < data['start_date']: raise ValueError('Invalid leave date range')
            if data['days'] > (date.fromisoformat(data['end_date']) - date.fromisoformat(data['start_date'])).days + 1: raise ValueError('Leave days exceed date range')
            service.create_leave(data['employee_id'], data['leave_type'], data['start_date'], data['end_date'], data['days'], data['reason'])
        elif section == 'leave' and action == 'review' and old:
            status = v.get('status')
            if old['status'] not in ('Pending', 'Approved') or (old['status'] == 'Approved' and status != 'Cancelled'): raise ValueError('Leave has already been reviewed')
            service.review_leave(old['id'], status, actor['id'], str(v.get('review_notes') or '')[:4000])
            service.recalculate_attendance_categories(old['employee_id'])
        elif section == 'payroll' and action == 'save' and not old:
            if not re.fullmatch(r'\d{4}-\d{2}', data['period_month']): raise ValueError('Payroll period must be YYYY-MM')
            day(data['period_month'] + '-01')
            net = sum(data[k] for k in ('basic_salary', 'allowance', 'overtime_amount', 'bonus')) - sum(data[k] for k in ('late_deduction', 'absence_deduction', 'advance_deduction', 'other_deduction'))
            if net < 0: raise ValueError('Deductions exceed salary')
            service.save_payroll(data, actor['id'])
        elif section == 'payroll' and action == 'pay' and old:
            if old['status'] != 'Draft': raise ValueError('Only draft payroll can be paid')
            method = str(v.get('payment_method') or '').strip()
            if not method: raise ValueError('Payment method is required')
            service.pay_payroll(old['id'], day(v['paid_date']), method[:100], actor['username'])
        elif section == 'documents' and action == 'save' and not old:
            if not data['document_type']: raise ValueError('Document type is required')
            for key in ('issued_date', 'expiry_date'):
                if data[key]: day(data[key])
            if data['issued_date'] and data['expiry_date'] and data['expiry_date'] < data['issued_date']: raise ValueError('Expiry precedes issue date')
            service.add_document(data)
        elif section == 'advances' and action == 'save' and not old:
            service.add_advance(data['employee_id'], data['advance_date'], data['amount'], data['notes'], actor['id'])
        elif section == 'advances' and action == 'repay' and old:
            amount = money(v['amount'], minimum=.01)
            if amount > round(float(old['amount']) - float(old['repaid_amount'] or 0), 2): raise ValueError('Repayment exceeds outstanding advance')
            service.repay_advance(old['id'], amount)
        elif section == 'commission' and action == 'save':
            if data['rate_percent'] > 100: raise ValueError('Commission rate cannot exceed 100%')
            if old and old['employee_id'] != data['employee_id']: raise ValueError('Employee cannot change on a commission rule')
            if not old:
                c.execute('SELECT id FROM commission_rules WHERE employee_id=?', (data['employee_id'],))
                if c.fetchone(): raise ValueError('Rule exists. Refresh and edit it.')
            service.save_commission_rule(data['employee_id'], data['rate_percent'], data['target_amount'])
        elif section == 'cash' and action == 'save' and not old:
            service.open_cash_session(data['employee_id'], data['opening_cash'], actor['id'], data['notes'])
        elif section == 'cash' and action == 'close' and old:
            if old['status'] != 'Open': raise ValueError('Cash session is already closed')
            service.close_cash_session(old['id'], money(v['actual_cash']), actor['id'])
        else: raise ValueError('Unsupported employee action')
        if not record_id and action == 'save':
            # Commands serialize their tables, so the inserted record is stable.
            # Employee creation already returns its ID directly.
            if 'employee_id' in data:
                c.execute(f'SELECT id FROM {table} WHERE employee_id=? ORDER BY id DESC LIMIT 1', (data['employee_id'],))
            elif section == 'shifts': c.execute('SELECT id FROM shifts WHERE name=?', (data['name'],))
            found = c.fetchone(); record_id = found[0] if found else None
        return dict(id=record_id, message='Employee change saved')

    @staticmethod
    def clock_value(value, required=False):
        if (required or value) and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', str(value)):
            raise ValueError('Time must be HH:MM (24 hour)')

    def change_settings(self, c, v):
        section = v.get('section')
        if section not in SETTINGS: raise ValueError('Unknown settings section')
        fields = SETTINGS[section]; keys = [f[0] for f in fields]
        existing = dict(c.execute('SELECT key,value FROM settings WHERE key IN (' + ','.join('?' for _ in keys) + ')', keys).fetchall())
        if digest(existing) != v.get('revision'): raise ValueError('Settings changed. Refresh before saving.')
        data = self.validated(fields, v)
        if 'tax_rate' in data and data['tax_rate'] > 100: raise ValueError('Tax rate cannot exceed 100%')
        if data.get('discount_type') == 'percentage' and data['discount_value'] > 100: raise ValueError('Discount cannot exceed 100%')
        for key, value in data.items():
            c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(value)))
        return dict(message=section.title() + ' settings saved. Reopen affected pages in other clients.')

    def admin_only(self, c, actor):
        c.execute('SELECT role FROM users WHERE id=?', (actor['id'],))
        if str(c.fetchone()[0]).lower() != 'admin': raise PermissionError('Only an Admin may change account access or roles')

    def change_role(self, c, v, actor):
        self.admin_only(c, actor)
        old = self.checked_record(c, 'user_roles', v, ['id', 'name', 'description', 'permissions', 'is_system']) if v.get('id') else None
        name = str(v.get('name') or '').strip()
        if not name or len(name) > 80: raise ValueError('Role name is required (maximum 80 characters)')
        if name.lower() in ('admin', 'manager', 'cashier', 'viewer') or (old and old.get('is_system')):
            raise ValueError('Built-in roles are maintained by the original POS. Create a custom role to customize permissions.')
        if old and old['name'] != name: raise ValueError('Role name cannot change; create a new role instead')
        permissions = sorted({p.strip() for p in str(v.get('permissions') or '').split(',') if p.strip()})
        if any(not re.fullmatch('[a-z_]{1,60}', p) for p in permissions): raise ValueError('Invalid permission key')
        data = dict(name=name, description=str(v.get('description') or '')[:1000], permissions=','.join(permissions))
        if old: self.update(c, 'user_roles', old['id'], data); record_id = old['id']
        else: record_id = self.insert(c, 'user_roles', dict(data, is_system=0))
        return dict(id=record_id, message='Role saved; sign in again to refresh client navigation')

    def change_user(self, c, v, actor):
        self.admin_only(c, actor)
        old = self.checked_record(c, 'users', v, ['id', 'username', 'full_name', 'role', 'is_active', 'permissions']) if v.get('id') else None
        role = str(v.get('role') or '')
        c.execute('SELECT name FROM user_roles WHERE name=?', (role,))
        if not c.fetchone(): raise ValueError('Select an existing role')
        active = flag(v.get('is_active', True))
        if old and old['id'] == actor['id'] and (not active or role.lower() != 'admin'): raise ValueError('You cannot remove your own administrator access')
        if old and str(old['role']).lower() == 'admin' and (not active or role.lower() != 'admin'):
            c.execute("SELECT COUNT(*) FROM users WHERE LOWER(role)='admin' AND is_active=1 AND id<>?", (old['id'],))
            if not c.fetchone()[0]: raise ValueError('The last active administrator must remain active')
        fields = dict(full_name=str(v.get('full_name') or '')[:200], role=role, is_active=active)
        password = str(v.get('password') or '')
        if not old and not password: raise ValueError('A new account requires a password')
        if password:
            if len(password) < 8 or len(password) > 256: raise ValueError('Use a password of 8 to 256 characters')
            if not {'salt', 'password_hash'}.issubset(self.columns(c, 'users')): raise ValueError('Update the server account schema before setting passwords')
            salt = os.urandom(32).hex()
            fields.update(salt=salt, password_hash=hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 100000).hex(), force_password_change=0)
        if old:
            self.update(c, 'users', old['id'], fields); record_id = old['id']
        else:
            username = str(v.get('username') or '').strip()
            if not username or len(username) > 100: raise ValueError('Username is required (maximum 100 characters)')
            c.execute('SELECT id FROM users WHERE LOWER(username)=?', (username.lower(),))
            if c.fetchone(): raise ValueError('Username already exists')
            record_id = self.insert(c, 'users', dict(fields, username=username, permissions=''))
        return dict(id=record_id, message='Account saved; affected user should sign in again')


def install_routes(app, current_user, repository=None):
    from fastapi import Depends, HTTPException, Query
    from pydantic import BaseModel, Field
    repo = repository or AdminRepository()

    class Command(BaseModel):
        request_id: str = Field(min_length=36, max_length=36)
        operation: str = Field(max_length=60)
        values: dict

    @app.get('/api/native/admin')
    def read(section: str, start: str = '', end: str = '', query: str = '', offset: int = Query(default=0, ge=0), user=Depends(current_user)):
        try: return repo.read(user, section, start, end, query, offset)
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc: raise HTTPException(400, str(exc)) from exc

    @app.post('/api/native/admin/commands')
    def command(payload: Command, user=Depends(current_user)):
        try: return {'result': repo.command(user, payload.request_id, payload.operation, payload.values)}
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc: return {'rejected': str(exc)}
        except Exception as exc:
            if constraint_error(exc): return {'rejected': 'A duplicate or referenced record prevents this change. Refresh and check the selected records.'}
            raise
