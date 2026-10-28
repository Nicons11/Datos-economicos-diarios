import hashlib
import hmac
import json
import subprocess
import unittest
from unittest.mock import Mock, patch
import actualizar_apps_script as app

URL = 'https://script.google.com/macros/s/example123/exec'
KEY = 'a' * 64

class Bridge(unittest.TestCase):
    def test_signed_request_and_rejected_response(self):
        response = Mock()
        response.json.return_value = {'ok': False, 'error': 'Solicitud no autorizada'}
        with patch.object(app.requests, 'post', return_value=response) as post:
            with self.assertRaisesRegex(RuntimeError, 'no autorizada'):
                app.exchange(URL, KEY, 'read')
        sent = post.call_args.kwargs['json']
        expected = hmac.new(KEY.encode(), sent['payload'].encode(), hashlib.sha256).hexdigest()
        self.assertEqual(sent['signature'], expected)
        self.assertEqual(json.loads(sent['payload'])['action'], 'read')
        self.assertNotIn(KEY, sent['payload'])

    def test_query_failure_never_uploads(self):
        with patch.dict(app.os.environ, APPS_SCRIPT_URL=URL, APPS_SCRIPT_KEY=KEY), \
             patch.object(app, 'exchange', return_value={'ok': True, 'content': None, 'version': None}) as exchange, \
             patch.object(app.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'consulta')):
            with self.assertRaises(subprocess.CalledProcessError):
                app.main()
        exchange.assert_called_once_with(URL, KEY, 'read')

    def test_invalid_endpoint_does_not_send_key(self):
        with patch.object(app.requests, 'post') as post:
            with self.assertRaises(ValueError):
                app.exchange('https://example.com/exec', KEY, 'read')
        post.assert_not_called()

if __name__ == '__main__':
    unittest.main()
