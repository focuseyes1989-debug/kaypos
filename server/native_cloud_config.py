"""Cloud config only: reuses the recoverable .env writer, never runs sync/pull."""
import re
from urllib.parse import urlsplit, parse_qs, unquote
from server.native_telegram import TelegramRepository, enabled, install_routes as install_config_routes
from utils import telegram_config_store as store

KEYS = ('ZAY_POS_CLOUD_SYNC_ENABLED', 'ZAY_POS_CLOUD_DATABASE_URL', 'ZAY_POS_CLOUD_SYNC_INTERVAL_SECONDS')


def destination(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ('postgres', 'postgresql') or not parsed.hostname or not parsed.path.strip('/') or parsed.fragment:
            raise ValueError()
        if not re.fullmatch(r'[A-Za-z0-9._:-]{1,253}', parsed.hostname): raise ValueError()
        if any(key.lower() in ('host', 'hostaddr', 'port', 'dbname', 'database', 'user', 'password', 'service', 'servicefile', 'passfile') for key in parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)):
            raise ValueError()
        if any(c.isspace() or c in '\x00\r\n\"\'' for c in value): raise ValueError()
        if parsed.port == 0: raise ValueError()
        return parsed.hostname.lower(), parsed.port or 5432, unquote(parsed.path.lstrip('/'))
    except (TypeError, ValueError) as exc:
        raise ValueError('Use a PostgreSQL URL with host and database, percent-encoded credentials, and no target/credential overrides in query parameters') from exc


class CloudConfigRepository(TelegramRepository):
    label = 'Cloud sync'
    operation = 'cloud.save'

    def __init__(self, service=None, path=None, environment=None):
        from utils.env_loader import project_env_path
        super().__init__(service, path if path is not None else project_env_path(), environment)

    def read(self, user):
        conn = self.connect()
        try:
            self.authorize_config(conn.cursor(), user)
            raw = store.read(self.path); values = store.parse(raw, KEYS)
            url = values.get(KEYS[1], '')
            target = 'Not configured'
            if url:
                try:
                    host, port, database = destination(url); target = f'{host}:{port} / {database}'
                except ValueError: target = 'Configured; URL format needs review'
            interval_note = ''
            try:
                interval = int(values.get(KEYS[2], '300'))
                if not 60 <= interval <= 86400: raise ValueError()
            except ValueError:
                interval = 300; interval_note = ' Stored interval is not supported by this editor; it suggests 300 seconds. Save to change it.'
            return dict(revision=store.digest(raw), enabled=enabled(values.get(KEYS[0])), interval_seconds=interval,
                        url_configured=bool(url), destination=target, pending=store.marker_path(self.path).exists(),
                        environment_overrides=[key for key in KEYS if key in self.environment],
                        message='These are server-file settings. The existing cloud sync owner applies them; restart/reconfigure that owner as needed. Running process/environment values may take precedence. Saving never starts sync, pulls data or starts another scheduler.' + interval_note)
        finally: conn.rollback(); conn.close()

    def updated(self, raw, values):
        old = store.parse(raw, KEYS)
        for key in ('enabled', 'clear_url'):
            if values.get(key, False) not in (True, False): raise ValueError('Invalid checkbox value')
        replacement = str(values.get('cloud_url') or '').strip()
        if replacement and values.get('clear_url'): raise ValueError('Choose either replacement URL or clear URL')
        url = '' if values.get('clear_url') else replacement or old.get(KEYS[1], '')
        if len(url) > 4096: raise ValueError('Cloud URL exceeds 4096 characters')
        if values.get('enabled') and not url: raise ValueError('Cloud database URL is required when enabled')
        if url and (replacement or values.get('enabled')):
            target = destination(url)
            source_keys = ('ZAY_POS_DATABASE_URL', 'DATABASE_URL')
            source = store.parse(raw, source_keys)
            primary = self.environment.get(source_keys[0]) or self.environment.get(source_keys[1]) or source.get(source_keys[0]) or source.get(source_keys[1])
            if primary:
                try: same = target == destination(primary)
                except ValueError: same = False
                if same and values.get('enabled'): raise ValueError('Cloud destination must differ from the configured primary database')
        try:
            interval = int(values.get('interval_seconds', 300))
            if str(interval) != str(values.get('interval_seconds', 300)) or not 60 <= interval <= 86400: raise ValueError()
        except (TypeError, ValueError) as exc: raise ValueError('Sync interval must be a whole number from 60 to 86400 seconds') from exc
        return store.render(raw, dict(zip(KEYS, ('1' if values.get('enabled') else '0', url, str(interval)))), KEYS)


def install_routes(app, current_user, repository=None):
    install_config_routes(app, current_user, repository or CloudConfigRepository(), namespace='cloud_config')
