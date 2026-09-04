"""Native-only preferences. Passwords and PostgreSQL connection strings are never saved."""
import json
import os
from pathlib import Path

DEFAULTS = dict(style='System', palette='System', font_family='', font_size=10,
                backend='Server', database='', schema='kay_native_test',
                server_url='https://192.168.110.112:8000', insecure_tls=True,
                username='', width=1366, height=768,
                receipt_printer='', receipt_paper='A4', receipt_dpi=300, drawer_target='server',
                print_server_url='', print_agent='', print_remote_name='', print_verify_tls=True, print_key_protected='')

def config_path():
    return Path(os.getenv('APPDATA') or Path.home()) / 'KAY' / 'POSNative' / 'config.json'

def load_config(path=None):
    try:
        data = json.loads(Path(path or config_path()).read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    result = {key: data.get(key, value) for key, value in DEFAULTS.items()}
    for key in ('style','palette','font_family','backend','database','schema','username','server_url','receipt_printer'):
        result[key] = str(result[key] or DEFAULTS[key])
    # Upgrade the initial local-only preview to the user's server-first setup.
    if 'server_url' not in data:
        result['backend'] = 'Server'
    result['insecure_tls'] = bool(result['insecure_tls'])
    if result['drawer_target'] not in ('server', 'local'): result['drawer_target'] = 'server'
    if result['receipt_paper'] not in ('58mm', '80mm', 'A4'): result['receipt_paper'] = 'A4'
    if result['receipt_dpi'] not in (203, 300, 600): result['receipt_dpi'] = 300
    for key, minimum, maximum in (('font_size',8,20),('width',1366,3840),('height',768,2160)):
        try:
            result[key] = max(minimum, min(maximum, int(result[key])))
        except (TypeError,ValueError):
            result[key] = DEFAULTS[key]
    return result

def save_config(values, path=None):
    target = Path(path or config_path())
    data = load_config(target)
    data.update({key: values[key] for key in DEFAULTS if key in values})
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    temporary.replace(target)
    return data
