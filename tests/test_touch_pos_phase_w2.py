"""Phase W2 staff authentication, permission and session tests."""
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from fastapi import HTTPException
from server import api


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'server' / 'static' / 'touch_pos'


class TouchPosPhaseW2Tests(unittest.TestCase):
    def test_existing_login_token_enters_touch_session_then_revokes(self):
        user = {'id': 7, 'username': 'cashier', 'full_name': 'Test Cashier', 'role': 'Cashier', 'permissions': ['create_sale']}
        with patch('server.api.cashier_service.verify_user', return_value=user):
            login = api.login(api.LoginRequest(username='cashier', password='test-password'))
        authorization = f"Bearer {login['token']}"
        try:
            self.assertEqual(api.touch_pos_session(api.current_user(authorization))['user'], user)
            self.assertEqual(api.touch_pos_logout(authorization), {'ok': True})
            with self.assertRaises(HTTPException): api.current_user(authorization)
        finally:
            api._TOKENS.pop(login['token'], None)

    def test_admin_and_create_sale_permission_have_touch_access(self):
        self.assertTrue(api._touch_pos_user({'role': 'Admin', 'permissions': []})['can_sell'])
        self.assertTrue(api._touch_pos_user({'role': 'Cashier', 'permissions': ['create_sale']})['can_sell'])
        self.assertFalse(api._touch_pos_user({'role': 'Viewer', 'permissions': ['sales']})['can_sell'])

    def test_session_rejects_account_without_create_sale(self):
        with self.assertRaises(HTTPException) as caught:
            api.touch_pos_session({'role': 'Viewer', 'permissions': ['sales']})
        self.assertEqual(caught.exception.status_code, 403)
        self.assertIn('create sales', caught.exception.detail)

    def test_logout_revokes_only_current_bearer_token(self):
        token, other = uuid4().hex, uuid4().hex
        api._TOKENS[token] = {'id': 1}; api._TOKENS[other] = {'id': 2}
        try:
            self.assertEqual(api.touch_pos_logout(f'Bearer {token}'), {'ok': True})
            self.assertNotIn(token, api._TOKENS)
            self.assertIn(other, api._TOKENS)
            with self.assertRaises(HTTPException): api.current_user(f'Bearer {token}')
        finally:
            api._TOKENS.pop(token, None); api._TOKENS.pop(other, None)

    def test_login_form_uses_password_manager_fields(self):
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        self.assertIn('autocomplete="username"', html)
        self.assertIn('autocomplete="current-password"', html)
        self.assertIn('id="loginStatus"', html)
        self.assertIn('id="signOut"', html)

    def test_client_keeps_token_in_tab_session_and_never_password(self):
        script = (STATIC / 'touch-pos.js').read_text(encoding='utf-8')
        self.assertIn("sessionStorage.getItem(TOKEN_KEY)", script)
        self.assertIn("sessionStorage.setItem(TOKEN_KEY, token)", script)
        self.assertNotIn('localStorage', script)
        self.assertNotIn('setItem(\'password', script)
        self.assertIn("api('/api/touch-pos/session')", script)
        self.assertIn("api('/api/touch-pos/logout'", script)

    def test_password_is_cleared_after_success_failure_and_sign_out(self):
        script = (STATIC / 'touch-pos.js').read_text(encoding='utf-8')
        self.assertGreaterEqual(script.count("password.value = ''"), 3)
        self.assertIn("showLogin('Session expired. Please sign in again.')", script)


if __name__ == '__main__':
    unittest.main()
