import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from local_print_bridge import JobLedger, handler_factory, normalize_origin, validate_job


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = JobLedger(Path(self.tmp.name)/'jobs.db')
        self.calls = []
        def dispatch(path, payload):
            self.calls.append(path)
            return {'printers': ['Test local printer']} if path == '/printers' else {'status': 'sent'}
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_factory('https://pos.example', 'test-pair-key', dispatch, self.ledger))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.tmp.cleanup()
    def request(self, method='GET', path='/printers', body=None, **headers):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=2)
        values = {'Origin': 'https://pos.example', 'X-Kay-Bridge-Key': 'test-pair-key', 'Content-Type': 'application/json', **headers}
        conn.request(method, path, json.dumps(body) if body is not None else None, values)
        response = conn.getresponse()
        result = response.status, response.read(), dict(response.getheaders())
        conn.close()
        return result
    def test_local_discovery_requires_pairing_and_origin(self):
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.request(**{'Origin':'https://other.example'})[0], 403)
        self.assertEqual(self.request(**{'X-Kay-Bridge-Key':''})[0], 401)
        self.assertEqual(self.request(**{'Host':'evil.example'})[0], 403)
        self.assertEqual(self.calls, ['/printers'])
    def test_preflight_is_scoped(self):
        status, _, headers = self.request('OPTIONS')
        self.assertEqual(status, 204)
        self.assertEqual(headers['Access-Control-Allow-Origin'], 'https://pos.example')
        self.assertEqual(headers['Access-Control-Allow-Private-Network'], 'true')
        self.assertEqual(self.request('OPTIONS', **{'Origin':'null'})[0], 403)
    def test_idempotency_and_payload_validation(self):
        body={'printer':'Test local printer','request_key':'sale:12345'}
        self.assertEqual(self.request('POST','/drawer',body)[0], 200)
        self.assertEqual(self.request('POST','/drawer',body)[0], 200)
        self.assertEqual(self.calls, ['/drawer'])
        self.assertEqual(self.request('POST','/drawer',{**body,'printer':'Other'})[0], 400)
        self.assertEqual(self.request('POST','/raw',body)[0], 400)
        self.assertEqual(self.request('POST','/print',{**body,'receipt':{'items':[]},'paper':'bad'})[0], 400)
        self.assertEqual(self.calls, ['/drawer'])
    def test_uncertain_job_not_replayed_after_restart(self):
        payload={'printer':'Test local printer','request_key':'sale:67890'}
        def fail(*_):
            raise RuntimeError('Printer offline')
        with self.assertRaises(RuntimeError):
            self.ledger.run('https://pos.example','/drawer',payload,fail)
        restarted=JobLedger(self.ledger.path)
        with self.assertRaisesRegex(ValueError,'uncertain or failed'):
            restarted.run('https://pos.example','/drawer',payload,lambda *_:self.fail('Replayed'))
    def test_origin(self):
        self.assertEqual(normalize_origin('https://pos.example/touch-pos/'),'https://pos.example')
        for value in ('null','file:///tmp','http://pos.example','https://user:pass@pos.example'):
            with self.assertRaises(ValueError):normalize_origin(value)


if __name__ == '__main__':
    unittest.main()
