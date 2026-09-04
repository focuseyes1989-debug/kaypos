"""Native sales routes; the existing Lite/browser API remains compatible."""
from uuid import UUID

from fastapi import Depends, HTTPException
from pydantic import Field


def install_routes(app, current_user, sale_model):
    from server import cashier_service as service

    class NativeSaleRequest(sale_model):
        request_id: str = Field(default='', max_length=36)
        expected_total: float | None = None
        discount_percent: float = Field(default=0, ge=0, le=100)

    def authorize(user, credit=False):
        conn = service.connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute('''SELECT u.role, u.permissions, r.permissions, u.is_active,
                u.force_password_change FROM users u LEFT JOIN user_roles r ON r.name=u.role
                WHERE u.id=?''', (user.get('id'),))
            row = cursor.fetchone()
            if not row or not row[3] or row[4]:
                raise HTTPException(403, 'Account is inactive or needs a password change')
            permissions = {p.strip() for value in row[1:3] for p in str(value or '').split(',') if p.strip()}
            required = {'sales', 'create_sale'} | ({'credit_sale'} if credit else set())
            if str(row[0]).casefold() != 'admin' and not required.issubset(permissions):
                raise HTTPException(403, 'Sale permission required')
        finally:
            conn.close()

    def values(payload, user):
        data = payload.model_dump() if hasattr(payload, 'model_dump') else payload.dict()
        data['created_by'] = user['username']
        if data['allow_credit_over_limit']:
            raise HTTPException(400, 'Credit limit override is not enabled in Native')
        authorize(user, data['sale_mode'].lower() == 'credit' or data['payment_type'].lower() == 'credit')
        return data

    @app.get('/api/native/sales/capabilities')
    def capabilities(user=Depends(current_user)):
        authorize(user)
        return {'version': 1, 'quote': True, 'idempotent_checkout': True}

    @app.post('/api/native/sales/quote')
    def quote(payload: NativeSaleRequest, user=Depends(current_user)):
        data = values(payload, user)
        data.update(preview_only=True, request_id='', expected_total=None)
        try:
            return {'quote': service.create_sale(**data)}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post('/api/native/sales')
    def checkout(payload: NativeSaleRequest, user=Depends(current_user)):
        data = values(payload, user)
        try:
            UUID(data['request_id'])
            if data['expected_total'] is None:
                raise ValueError('Review the server total before checkout')
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        try:
            return {'receipt': service.create_sale(**data)}
        except ValueError as exc:
            # A known rollback is distinguishable from a lost commit response.
            return {'rejected': str(exc)}

    @app.post('/api/native/cashdrawer/open')
    def drawer(user=Depends(current_user)):
        authorize(user)
        try:
            return service.open_cash_drawer()
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
