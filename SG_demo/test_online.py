"""Local HTTP checks; no public tunnel or actual solver is required."""
import http.client
import json
import threading
import unittest
from unittest.mock import patch

from twin_server import TwinServer


class OnlineTests(unittest.TestCase):
    def setUp(self):
        self.server = TwinServer(('127.0.0.1', 0), ['https://sgdemo-theta.vercel.app'], 'test-code')
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()

    def request(self, method, path='/api/session', headers=None, body='{}'):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_cors_auth_and_busy(self):
        origin = 'https://sgdemo-theta.vercel.app'
        headers = {'Origin': origin, 'Content-Type': 'application/json'}
        status, reply, _ = self.request('OPTIONS', headers=headers)
        self.assertEqual(status, 204)
        self.assertEqual(reply['Access-Control-Allow-Origin'], origin)
        self.assertEqual(self.request('POST', headers=headers)[0], 401)
        headers['Authorization'] = 'Bearer test-code'
        with patch('twin_server.Twin') as twin:
            twin.return_value.snapshot.return_value = {'time': 0}
            status, _, body = self.request('POST', headers=headers)
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)['session'])
        self.server.compute_gate.acquire()
        try:
            self.assertEqual(self.request('POST', headers=headers)[0], 429)
        finally:
            self.server.compute_gate.release()
        headers['Origin'] = 'https://untrusted.example'
        self.assertEqual(self.request('POST', headers=headers)[0], 403)
        self.assertEqual(self.request('OPTIONS', headers=headers)[0], 403)
        self.assertEqual(self.request('GET', '/api/health')[0], 200)


if __name__ == '__main__':
    unittest.main()
