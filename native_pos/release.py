"""Native release metadata and distribution verification."""
import hashlib
import json
from pathlib import Path


def metadata(path=None):
    target = Path(path or Path(__file__).resolve().parents[1] / 'native_version.json')
    try: value = json.loads(target.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError) as exc: raise ValueError('Native release metadata is missing or invalid') from exc
    required = {'product': 'KAY POS Native', 'release_channel': 'phase8-preview', 'minimum_display': '1366x768', 'server_api': 'native-v1'}
    if any(value.get(key) != expected for key, expected in required.items()): raise ValueError('Native release identity does not match this build')
    parts = str(value.get('version', '')).split('.')
    if len(parts) != 3 or any(not part.isdigit() for part in parts): raise ValueError('Native version must use major.minor.patch')
    return value


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): digest.update(block)
    return digest.hexdigest()


def distribution_manifest(directory, source_revision='unknown', source_dirty=True):
    directory = Path(directory); executable = directory / 'KAY_POS_Native.exe'
    version_file = directory / '_internal' / 'native_version.json'
    icon = directory / '_internal' / 'assets' / 'kay' / 'kay_multi.ico'
    missing = [str(path.relative_to(directory)) for path in (executable, version_file, icon) if not path.is_file()]
    if missing: raise ValueError('Native distribution is incomplete: ' + ', '.join(missing))
    info = metadata(version_file)
    result = dict(product=info['product'], version=info['version'], release_channel=info['release_channel'],
                  minimum_display=info['minimum_display'], server_api=info['server_api'], executable='KAY_POS_Native.exe',
                  executable_size=executable.stat().st_size, executable_sha256=sha256(executable),
                  source_revision=str(source_revision or 'unknown'), source_dirty=bool(source_dirty), smoke_test='pending')
    return result
