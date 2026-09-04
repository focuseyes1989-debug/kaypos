"""Portable employee attachments and shared receipt images, with atomic audit."""
import base64
import binascii
import hashlib
import io
from pathlib import PurePosixPath
import warnings

from server.native_admin import AdminRepository, constraint_error
from server.native_catalog import digest, number

MAX_BYTES = 8 * 1024 * 1024
IMAGE_KEYS = {'logo': ('shop_logo', 'shop_logo_image'), 'qr': ('shop_qr_code', 'shop_qr_code_image')}


def decode(value):
    if not isinstance(value, str) or len(value) > (MAX_BYTES + 2) // 3 * 4:
        raise ValueError('File must be at most 8 MB')
    try: data = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc: raise ValueError('Invalid file encoding') from exc
    if not data or len(data) > MAX_BYTES: raise ValueError('Choose a non-empty file of at most 8 MB')
    return data


def filename(value):
    name = PurePosixPath(str(value or '').replace('\\', '/')).name
    name = ''.join(c for c in name if c.isprintable() and c not in '<>:"/\\|?*').strip(' .')[:120]
    if not name: raise ValueError('Filename is required')
    return name


def image_png(data):
    from PIL import Image, ImageOps
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in ('PNG', 'JPEG', 'WEBP'): raise ValueError('Choose PNG, JPEG or WebP')
                if source.width * source.height > 16000000: raise ValueError('Image must contain at most 16 million pixels')
                source.load(); normalized = ImageOps.exif_transpose(source).convert('RGBA')
                normalized.thumbnail((1600, 1600))
                output = io.BytesIO(); normalized.save(output, 'PNG')
                if output.tell() > MAX_BYTES: raise ValueError('Normalized image exceeds 8 MB; choose a smaller image')
                return output.getvalue()
    except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Invalid or oversized image') from exc


class FilesRepository(AdminRepository):
    def prepare(self, conn, employee=False):
        super().prepare(conn, employee=True)
        blob = 'BYTEA' if self.pg() else 'BLOB'
        conn.cursor().execute(f'''CREATE TABLE IF NOT EXISTS native_employee_documents (
            document_id INTEGER PRIMARY KEY REFERENCES employee_documents(id) ON DELETE CASCADE,
            filename TEXT NOT NULL, mime TEXT NOT NULL, content {blob} NOT NULL,
            sha256 TEXT NOT NULL)''')
        conn.commit()

    def lock_tables(self, operation):
        return 'users,user_roles,settings,employees,employee_documents,native_employee_documents'

    def required(self, operation, values):
        if operation == 'photo.save': return ['employees', 'manage_employees']
        if operation == 'document.save': return ['employees', 'employee_documents', 'manage_employees']
        if operation == 'receipt_image.save': return ['settings', 'edit_settings']
        raise ValueError('Unknown attachment operation')

    def asset(self, c, kind, record_id):
        if kind in IMAGE_KEYS:
            path_key, data_key = IMAGE_KEYS[kind]
            c.execute('SELECT key,value FROM settings WHERE key IN (?,?)', (path_key, data_key))
            values = dict(c.fetchall()); url = values.get(data_key) or ''
            try: data = base64.b64decode(url.split(',', 1)[1], validate=True) if url else b''
            except (IndexError, ValueError, binascii.Error): data = b''
            return dict(data=data, name=kind + '.png', mime='image/png', revision=digest(values), reference=values.get(path_key) or '')
        record_id = number(record_id, True, minimum=1)
        if kind == 'photo':
            c.execute('SELECT photo_data,photo_path FROM employees WHERE id=?', (record_id,)); row = c.fetchone()
            if not row: raise ValueError('Employee no longer exists')
            data = bytes(row[0] or b'')
            return dict(data=data, name='employee-photo.png', mime='image/png', revision=digest([hashlib.sha256(data).hexdigest(), row[1]]), reference=row[1] or '')
        if kind == 'document':
            c.execute('SELECT file_path FROM employee_documents WHERE id=?', (record_id,)); document = c.fetchone()
            if not document: raise ValueError('Document no longer exists')
            c.execute('SELECT filename,mime,content,sha256 FROM native_employee_documents WHERE document_id=?', (record_id,)); row = c.fetchone()
            return dict(data=bytes(row[2]) if row else b'', name=row[0] if row else '', mime=row[1] if row else '',
                        revision=digest([document[0], row[3] if row else None]), reference=document[0] or '')
        raise ValueError('Unknown attachment type')

    def read(self, user, kind, record_id=0):
        conn = self.connect(); c = conn.cursor()
        try:
            required = ['settings'] if kind in IMAGE_KEYS else ['employees', 'employee_documents'] if kind == 'document' else ['employees']
            self.authorize(c, user, required); self.prepare(conn)
            self.authorize(c, user, required)
            asset = self.asset(c, kind, record_id); data = asset.pop('data')
            if data and kind != 'document':
                data = image_png(data)
            # No local/server path is opened on behalf of a supplied filename.
            if len(data) > MAX_BYTES: raise ValueError('Stored file exceeds the Native download limit')
            return dict(asset, size=len(data), content=base64.b64encode(data).decode(), sha256=hashlib.sha256(data).hexdigest())
        finally: conn.rollback(); conn.close()

    def apply(self, conn, c, operation, values, actor):
        kind = values.get('kind'); record_id = values.get('id', 0)
        expected_kind = {'photo.save': ('photo',), 'document.save': ('document',), 'receipt_image.save': ('logo', 'qr')}[operation]
        if kind not in expected_kind: raise ValueError('Attachment kind does not match the operation')
        old = self.asset(c, kind, record_id)
        if values.get('revision') != old['revision']: raise ValueError('Attachment changed. Refresh before replacing it.')
        remove = values.get('remove', False)
        if remove not in (True, False): raise ValueError('Invalid remove flag')
        data = b'' if remove else decode(values.get('content'))
        name = '' if remove else filename(values.get('filename'))
        if kind != 'document' and data: data = image_png(data)
        if kind == 'photo':
            self.update(c, 'employees', record_id, dict(photo_data=data or None, photo_path='employee-photo.png' if data else None))
        elif kind == 'document':
            if data:
                suffix = PurePosixPath(name).suffix.lower()
                if suffix == '.pdf':
                    if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-2048:]: raise ValueError('Invalid PDF file')
                    mime = 'application/pdf'
                elif suffix in ('.png', '.jpg', '.jpeg', '.webp'):
                    data = image_png(data); name = PurePosixPath(name).stem + '.png'; mime = 'image/png'
                else: raise ValueError('Documents must be PDF, PNG, JPEG or WebP')
                c.execute('''INSERT INTO native_employee_documents(document_id,filename,mime,content,sha256) VALUES(?,?,?,?,?)
                    ON CONFLICT(document_id) DO UPDATE SET filename=excluded.filename,mime=excluded.mime,
                    content=excluded.content,sha256=excluded.sha256''', (record_id, name, mime, data, hashlib.sha256(data).hexdigest()))
                self.update(c, 'employee_documents', record_id, dict(file_path=name))
            else:
                c.execute('DELETE FROM native_employee_documents WHERE document_id=?', (record_id,))
                self.update(c, 'employee_documents', record_id, dict(file_path=None))
        else:
            path_key, data_key = IMAGE_KEYS[kind]
            # Empty path makes legacy receipt helpers restore the new DB image,
            # rather than reuse an older client-local file at the old path.
            for key, value in [(path_key, ''), (data_key, 'data:image/png;base64,' + base64.b64encode(data).decode() if data else '')]:
                c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))
        return dict(id=record_id, message='Attachment removed' if remove else 'Attachment saved', size=len(data))


def install_routes(app, current_user, repository=None):
    from fastapi import Depends, HTTPException
    from pydantic import BaseModel, Field
    repo = repository or FilesRepository()
    class Command(BaseModel):
        request_id: str = Field(min_length=36, max_length=36)
        operation: str
        values: dict
    @app.get('/api/native/files')
    def read(kind: str, record_id: int = 0, user=Depends(current_user)):
        try: return repo.read(user, kind, record_id)
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    @app.post('/api/native/files/commands')
    def command(payload: Command, user=Depends(current_user)):
        try: return {'result': repo.command(user, payload.request_id, payload.operation, payload.values)}
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc: return {'rejected': str(exc)}
        except Exception as exc:
            if constraint_error(exc): return {'rejected': 'The referenced record changed. Refresh and try again.'}
            raise
