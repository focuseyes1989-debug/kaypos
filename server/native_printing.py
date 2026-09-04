"""Fresh POS permission check before a Native client submits a printer job."""
from server.native_catalog import CatalogRepository


def install_routes(app, current_user, repository=None):
    from fastapi import Depends, HTTPException
    repo = repository or CatalogRepository()
    @app.get('/api/native/printing/authorize')
    def authorize(user=Depends(current_user)):
        conn = repo.connect()
        try:
            repo.authorize(conn.cursor(), user, ['print_receipt'])
            return {'allowed': True}
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        finally: conn.rollback(); conn.close()
