"""Bounded backup packaging of a snapshot and managed server assets."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import shutil
import sqlite3
import zipfile

FOLDERS = ('images', 'logos', 'product_images', 'network_print_assets')
MAX_BYTES = 2 * 1024 ** 3
MAX_FILES = 10000


def inventory(root):
    root = Path(root).resolve(); files = []
    def visit(path):
        info = path.lstat()
        if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Managed assets contain a link/reparse point; package was not created')
        if not path.resolve().is_relative_to(root): raise ValueError('Asset path escapes managed storage')
        if stat.S_ISDIR(info.st_mode):
            for child in sorted(path.iterdir()): visit(child)
        elif stat.S_ISREG(info.st_mode):
            files.append((path, path.relative_to(root).as_posix(), info.st_size, info.st_mtime_ns))
            if len(files) > MAX_FILES: raise ValueError('Package exceeds 10,000 managed files')
        else: raise ValueError('Unsupported managed asset file type')
    for name in FOLDERS:
        path = root / name
        if path.exists() or path.is_symlink(): visit(path)
    return files


def build_package(snapshot, root, output):
    assets = inventory(root)
    entries = [(Path(snapshot), 'snapshot' + Path(snapshot).suffix, Path(snapshot).stat().st_size, Path(snapshot).stat().st_mtime_ns)]
    entries += [(path, 'database/' + name, size, modified) for path, name, size, modified in assets]
    if sum(item[2] for item in entries) > MAX_BYTES: raise ValueError('Package exceeds 2 GiB of source data')
    manifest = dict(version=1, managed_folders=list(FOLDERS), files=[], notes=[
        'Database snapshot and filesystem assets are captured separately. Pause asset edits while creating a package.',
        'Only listed managed server folders are included. Arbitrary external/client paths, .env, credentials, certificates and other backups are excluded.',
        'Embedded employee documents/photos and receipt image data are inside the database snapshot.',
        'Restore into a separate directory first. Absolute legacy paths may require administrator remapping. No automatic production restore is provided.'])
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for path, name, expected, modified in entries:
            digest = hashlib.sha256(); size = 0
            with path.open('rb') as source, archive.open(name, 'w', force_zip64=True) as target:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    size += len(block)
                    if size > expected: raise ValueError('Source file changed during packaging; retry after edits stop')
                    digest.update(block); target.write(block)
            info = path.stat()
            if size != expected or info.st_size != expected or info.st_mtime_ns != modified:
                raise ValueError('Source file changed during packaging; retry after edits stop')
            manifest['files'].append(dict(path=name, size=size, sha256=digest.hexdigest()))
        if assets != inventory(root): raise ValueError('Managed assets changed during packaging; retry after edits stop')
        archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def verify_package(path):
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_FILES + 2 or sum(i.file_size for i in infos) > MAX_BYTES + 4 * 1024 ** 2:
            raise ValueError('Package exceeds verification limits')
        if archive.getinfo('manifest.json').file_size > 4 * 1024 ** 2: raise ValueError('Package manifest too large')
        if any(info.flag_bits & 1 or ((info.external_attr >> 16) & 0o170000) == 0o120000 for info in infos):
            raise ValueError('Encrypted or linked package members are not supported')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('version') != 1: raise ValueError('Unsupported package manifest version')
        records = manifest['files']
        if not isinstance(records, list) or len(records) > MAX_FILES + 1 or any(
                not isinstance(row, dict) or not isinstance(row.get('path'), str)
                or not isinstance(row.get('size'), int) or isinstance(row.get('size'), bool) or row['size'] < 0
                or not isinstance(row.get('sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', row['sha256'])
                for row in records): raise ValueError('Invalid package manifest records')
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or set(names) != {'manifest.json', *(r['path'] for r in records)}:
            raise ValueError('Package file list does not match manifest')
        if len(records) != len(names) - 1: raise ValueError('Duplicate package manifest entry')
        for record in records:
            name = record['path']
            if name not in ('snapshot.db', 'snapshot.dump'):
                parts = name.split('/')
                if len(parts) < 3 or parts[0] != 'database' or parts[1] not in FOLDERS or any(p in ('', '.', '..') or '\\' in p or ':' in p for p in parts):
                    raise ValueError('Unsafe package member name')
            digest = hashlib.sha256(); size = 0
            with archive.open(name) as source:
                for block in iter(lambda: source.read(1024 * 1024), b''): digest.update(block); size += len(block)
            if size != record['size'] or digest.hexdigest() != record['sha256']: raise ValueError('Package member checksum mismatch')
        if sum(r['path'] in ('snapshot.db', 'snapshot.dump') for r in records) != 1: raise ValueError('Package must contain one database snapshot')
    return len(records)


def rehearse_package(path, destination, source_sha256):
    """Extract a verified SQLite package into a new isolated directory."""
    verify_package(path)
    destination = Path(destination).resolve(); destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.with_name(destination.name + '.partial').resolve()
    if stage.parent != destination.parent or destination.parent == destination:
        raise ValueError('Invalid rehearsal destination')
    if destination.exists():
        marker = destination / 'rehearsal.json'
        try: result = json.loads(marker.read_text(encoding='utf-8'))
        except (OSError, ValueError, TypeError) as exc: raise ValueError('Existing rehearsal directory needs administrator review') from exc
        if result.get('source_sha256') != source_sha256: raise ValueError('Existing rehearsal belongs to a different package')
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read('manifest.json'))
        for row in manifest['files']:
            extracted = (destination / row['path']).resolve()
            if not extracted.is_relative_to(destination) or not extracted.is_file() or extracted.is_symlink():
                raise ValueError('Existing rehearsal files changed; administrator review is required')
            digest = hashlib.sha256(); size = 0
            with extracted.open('rb') as source:
                for block in iter(lambda: source.read(1024 * 1024), b''): digest.update(block); size += len(block)
            if size != row['size'] or digest.hexdigest() != row['sha256']:
                raise ValueError('Existing rehearsal files changed; administrator review is required')
        return result
    if stage.exists():
        if stage.parent != destination.parent or not stage.name.endswith('.partial'): raise ValueError('Unsafe rehearsal cleanup path')
        shutil.rmtree(stage)
    stage.mkdir()
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            if not any(row['path'] == 'snapshot.db' for row in manifest['files']):
                raise ValueError('PostgreSQL package rehearsal requires a separate test database and pg_restore')
            for row in manifest['files']:
                target = (stage / row['path']).resolve()
                if not target.is_relative_to(stage): raise ValueError('Unsafe package member name')
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256(); size = 0
                with archive.open(row['path']) as source, target.open('xb') as output:
                    for block in iter(lambda: source.read(1024 * 1024), b''):
                        size += len(block)
                        if size > row['size']: raise ValueError('Package member exceeds manifest size')
                        digest.update(block); output.write(block)
                    output.flush(); os.fsync(output.fileno())
                if size != row['size'] or digest.hexdigest() != row['sha256']:
                    raise ValueError('Extracted package member checksum mismatch')
        database = sqlite3.connect(stage / 'snapshot.db')
        try:
            if database.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('Rehearsed SQLite snapshot integrity check failed')
            tables = database.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
            counts = {name: database.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0] for (name,) in tables}
        finally: database.close()
        result = dict(source_sha256=source_sha256, files=len(manifest['files']), tables=counts,
                      message='Package extracted to a separate rehearsal directory; SQLite integrity and member checksums passed. Production files were not changed.')
        (stage / 'rehearsal.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        stage.replace(destination)
        return result
    except Exception:
        if stage.exists() and stage.parent == destination.parent and stage.name.endswith('.partial'): shutil.rmtree(stage)
        raise
