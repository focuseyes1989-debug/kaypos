"""Phase W1 route, responsive shell and safe PWA-cache tests."""
import json
import unittest
from pathlib import Path

from server import api


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'server' / 'static' / 'touch_pos'


class TouchPosPhaseW1Tests(unittest.TestCase):
    def test_touch_pos_routes_serve_separate_shell_and_worker(self):
        page = api.touch_pos_home()
        worker = api.touch_pos_service_worker()
        self.assertEqual(Path(page.path), STATIC / 'index.html')
        self.assertEqual(page.headers['cache-control'], 'no-store')
        self.assertEqual(Path(worker.path), STATIC / 'service-worker.js')
        self.assertEqual(worker.headers['service-worker-allowed'], '/touch-pos/')
        paths = {route.path for route in api.app.routes}
        self.assertIn('/touch-pos', paths)
        self.assertIn('/touch-pos/', paths)

    def test_manifest_has_standalone_landscape_identity(self):
        value = json.loads((STATIC / 'manifest.webmanifest').read_text(encoding='utf-8'))
        self.assertEqual(value['name'], 'KAY POS Touch')
        self.assertEqual(value['start_url'], '/touch-pos/')
        self.assertEqual(value['scope'], '/touch-pos/')
        self.assertEqual(value['display'], 'standalone')
        self.assertEqual(value['orientation'], 'landscape')

    def test_shell_has_three_touch_work_areas_and_no_live_sale_controls(self):
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        for marker in ('categories panel', 'catalog panel', 'cart panel', 'id="connection"', 'id="fullscreen"'):
            self.assertIn(marker, html)
        self.assertIn('class="pay" type="button" disabled', html)
        self.assertNotIn('/api/sales', html)

    def test_layout_targets_desktop_and_tablet_without_page_scroll(self):
        css = (STATIC / 'touch-pos.css').read_text(encoding='utf-8')
        self.assertIn('overflow:hidden', css)
        self.assertIn('grid-template-columns:170px minmax(450px,1fr) 350px', css)
        self.assertIn('@media(max-width:1099px)', css)
        self.assertIn('@media(max-width:760px)', css)
        self.assertIn('min-height:48px', css)

    def test_client_only_checks_health_and_registers_scoped_worker(self):
        script = (STATIC / 'touch-pos.js').read_text(encoding='utf-8')
        self.assertIn("fetch('/health'", script)
        self.assertIn("register('/touch-pos/service-worker.js', {scope: '/touch-pos/'})", script)
        self.assertNotIn('/api/login', script)
        self.assertNotIn('/api/sales', script)

    def test_service_worker_never_intercepts_api_or_health(self):
        worker = (STATIC / 'service-worker.js').read_text(encoding='utf-8')
        self.assertIn("url.pathname.startsWith('/api/')", worker)
        self.assertIn("url.pathname === '/health'", worker)
        self.assertNotIn("'/api/", worker.split('const SHELL', 1)[1].split('];', 1)[0])


if __name__ == '__main__':
    unittest.main()
