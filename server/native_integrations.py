"""Read configuration health without starting listeners or sending messages."""
from server.native_admin import AdminRepository


class IntegrationAdapter:
    def status(self):
        from utils.telegram_service import load_telegram_config
        from services.cloud_sync_service import cloud_database_url, cloud_sync_enabled
        telegram = load_telegram_config()
        from models.database import connect_db
        conn = connect_db()
        try:
            cursor = conn.cursor(); cursor.execute("SELECT value FROM settings WHERE key='customer_display_youtube_url'"); row = cursor.fetchone()
            youtube_configured = bool(row and row[0])
            cursor.execute("SELECT value FROM settings WHERE key='performance_customer_display_youtube_enabled'"); row = cursor.fetchone()
            youtube_enabled = str(row[0] if row else '1') == '1'
        finally: conn.close()
        return [
            dict(service='Telegram', configured=bool(telegram.bot_token and telegram.chat_id), enabled=telegram.enabled,
                 detail='Listener configured: ' + str(telegram.listener_enabled) + '. Running-process state is not monitored. Administrators can edit the server file with Telegram server settings; environment overrides may take precedence.'),
            dict(service='Cloud sync', configured=bool(cloud_database_url()), enabled=cloud_sync_enabled(),
                 detail='The existing server/original application owns cloud sync. Administrators can edit its server file with Cloud server settings. Native starts no scheduler and does not run cloud pull.'),
            dict(service='YouTube', configured=youtube_configured, enabled=youtube_enabled,
                 detail='Shared customer-display URL is editable under Settings → YouTube. Playback remains with the existing customer display; Native has no WebEngine.'),
        ]

    def test(self, service):
        if service == 'Telegram':
            from utils.telegram_service import load_telegram_config, _telegram_bot_post
            config = load_telegram_config()
            if not config.bot_token: raise ValueError('Telegram bot token is not configured on the server')
            try:
                result = _telegram_bot_post('getMe', config)
                return dict(message='Telegram bot connection OK', account=result.get('username', ''))
            except Exception as exc: raise ValueError('Telegram connection failed. Check the server token and network.') from exc
        if service == 'Cloud sync':
            from services.cloud_sync_service import CloudSyncService
            try: result = CloudSyncService().test_connection()
            except Exception as exc: raise ValueError('Cloud connection failed. Check server configuration and network.') from exc
            if not result.ok: raise ValueError('Cloud connection failed. Check server configuration and network.')
            return dict(message='Cloud database connection OK')
        raise ValueError('Choose Telegram or Cloud sync')


class IntegrationRepository(AdminRepository):
    def __init__(self, service=None, adapter=None):
        super().__init__(service); self.adapter = adapter or IntegrationAdapter()

    def authorize_request(self, user, edit=False):
        conn = self.connect()
        try: self.authorize(conn.cursor(), user, ['settings', 'edit_settings'] if edit else ['settings'])
        finally: conn.rollback(); conn.close()

    def read(self, user):
        self.authorize_request(user); return dict(records=self.adapter.status())

    def test(self, user, service):
        self.authorize_request(user, True); return self.adapter.test(service)


def install_routes(app, current_user, repository=None):
    from fastapi import Depends, HTTPException
    from pydantic import BaseModel
    repo = repository or IntegrationRepository()
    class Test(BaseModel): service: str
    def run(action):
        try: return action()
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    @app.get('/api/native/integrations')
    def read(user=Depends(current_user)): return run(lambda: repo.read(user))
    @app.post('/api/native/integrations/test')
    def test(payload: Test, user=Depends(current_user)): return run(lambda: repo.test(user, payload.service))
