"""One HTTP boundary for production providers; all transport is dummy/stubbed."""
import ast
import io
import itertools
from pathlib import Path
import unittest
from unittest.mock import patch

import requests

from risk_engine.sources import common


class Reply(requests.Response):
    closed = False

    def close(self):
        self.closed = True
        super().close()


def response(payload=b'{}', status=200, headers=None):
    result = Reply()
    result.status_code = status
    result.raw = io.BytesIO(payload)
    result.headers.update(headers or {})
    result.encoding = 'utf-8'
    return result


class ProviderHttpTests(unittest.TestCase):
    def test_valid_json_text_and_release_of_transport(self):
        for loader, body, expected in [
            (common.safe_get_json, b'{"data": [1]}', {'data': [1]}),
            (common.safe_get_json, b'[1, 2]', [1, 2]),
            (common.safe_get_text, b'Date,Value\n2026-01-01,1', 'Date,Value\n2026-01-01,1'),
        ]:
            stream = io.BytesIO(body)
            reply = response(); reply.raw = stream
            with patch.object(common.requests, 'get', return_value=reply) as get:
                self.assertEqual(loader('https://provider.example/data', 20), expected)
                self.assertTrue(reply.closed)
                self.assertEqual(get.call_args.kwargs['allow_redirects'], False)
                self.assertEqual(get.call_args.kwargs['stream'], True)
                self.assertLessEqual(get.call_args.kwargs['timeout'], 10)

    def test_redirect_does_not_send_custom_key_to_second_origin(self):
        # Exercise real Requests redirect behavior through a mocked adapter, not a server.
        seen = []
        replies = []
        reads = []
        class UnreadableRedirect(io.BytesIO):
            def read(self, *args, **kwargs):
                reads.append(args)
                raise AssertionError("redirect body must never be buffered")
        def send(_adapter, request, **_kwargs):
            seen.append(request)
            reply = response(status=302, headers={'Location': 'https://other.example/collect'})
            reply.raw = UnreadableRedirect(b'body-must-not-be-read')
            replies.append(reply)
            return reply
        with patch.object(requests.adapters.HTTPAdapter, 'send', send):
            self.assertIsNone(common.safe_get_json('https://provider.example/data', 1,
                                                  headers={'X-Goog-Api-Key': 'dummy-key'}))
        self.assertEqual(len(seen), 1)
        self.assertTrue(replies[0].closed)
        self.assertTrue(replies[0].raw.closed)
        self.assertEqual(reads, [], "a caught read error must not hide body consumption")
        self.assertEqual(seen[0].url, 'https://provider.example/data')
        self.assertEqual(seen[0].headers['X-Goog-Api-Key'], 'dummy-key')

    def test_rejects_declared_and_decoded_byte_overflow_and_malformed_data(self):
        for body, headers in [
            (b'{}', {'Content-Length': '5'}),
            (b'12345', {}),  # no declared length, or expanded by transport
            (b'{}', {'Content-Length': '-1'}),
            (b'{}', {'Content-Length': 'invalid'}),
            (b'no', {}),
        ]:
            stream = io.BytesIO(body); reply = response(headers=headers); reply.raw = stream
            with self.subTest(body=body, headers=headers), patch.object(common, 'MAX_RESPONSE_BYTES', 4), \
                    patch.object(common.requests, 'get', return_value=reply):
                self.assertIsNone(common.safe_get_json('https://provider.example', 1))
                self.assertTrue(reply.closed)
        with patch.object(common, 'MAX_RESPONSE_BYTES', 2), \
                patch.object(common.requests, 'get', return_value=response(b'{}')):
            self.assertEqual(common.safe_get_json('https://provider.example', 1), {})

    def test_elapsed_check_and_unacceptable_schemes_withhold_results(self):
        with patch.object(common.requests, 'get', return_value=response()), \
                patch.object(common.time, 'monotonic', side_effect=itertools.chain([0], itertools.repeat(61))):
            with self.assertRaisesRegex(TimeoutError, 'elapsed budget'):
                common.request_json('https://provider.example', 1)
        for url in ['http://provider.example', 'file:///secret', 'https://user:secret@provider.example']:
            with patch.object(common.requests, 'get') as get:
                self.assertIsNone(common.safe_get_text(url, 1))
                get.assert_not_called()
        for timeout in [0, -1, float('nan'), float('inf')]:
            with patch.object(common.requests, 'get') as get:
                self.assertIsNone(common.safe_get_json('https://provider.example', timeout))
                get.assert_not_called()

    def test_production_transport_calls_cannot_bypass_common_boundary(self):
        root = Path(__file__).resolve().parents[1] / 'risk_engine'
        # Research collectors have separate fixed-host/process/byte controls and
        # live outside risk_engine. Every production transport import is centralized.
        forbidden_roots = {'requests', 'urllib3', 'urllib', 'http', 'httpx', 'aiohttp', 'socket'}
        violations = []
        for path in root.rglob('*.py'):
            if path == root / 'sources/common.py':
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                modules = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                           else [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
                # urllib.parse is pure URL handling, not transport.
                violations.extend(f'{path.relative_to(root)}:{node.lineno}:{module}'
                                  for module in modules if module.split('.')[0] in forbidden_roots
                                  and module != 'urllib.parse')
        self.assertEqual(violations, [])


if __name__ == '__main__':
    unittest.main()
