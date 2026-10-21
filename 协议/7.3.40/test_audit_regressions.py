"""Offline regression coverage for the archived 7.3.40 implementation."""
import unittest
import base64
import json
import socket
import sys
import types
from unittest.mock import Mock, patch
from decimal import Decimal
from record_validation import time_buckets
from security_utils import redact_text
from running_protocol import IndoorRunRecordBuilder, OutdoorRunRecordBuilder, generate_synthetic_gps_track


class AuditRegressionTests(unittest.TestCase):
    def test_header_and_json_credentials_redacted(self):
        for message in ('Authorization: Basic AUDIT_SECRET', 'Authorization: Bearer AUDIT_SECRET',
                        '{"token": "AUDIT_SECRET"}', "{'password': 'AUDIT_SECRET'}"):
            with self.subTest(message=message):
                self.assertNotIn('AUDIT_SECRET', redact_text(message))

    def test_outdoor_buckets_preserve_totals(self):
        points, fixed = generate_synthetic_gps_track(30, 120, 2100, 761, 0)
        _, record, _ = OutdoorRunRecordBuilder(1, 2).build_record(
            2100, 761, 2917, 0, 761000, points, fixed)
        self.assertEqual(sum(b['stepsNum'] for b in record['stepsPerTenSec']), 2917)
        self.assertEqual(sum(Decimal(str(b['distance'])) for b in record['speedPerTenSec']), Decimal('2100'))
        self.assertEqual(record['stepsPerTenSec'][-1]['endTime'], 761000)

    def test_indoor_buckets_preserve_steps_and_end(self):
        _, record, _ = IndoorRunRecordBuilder(1, 2).build_record(761, 2917, 0, 761000)
        self.assertEqual(sum(b['stepsNum'] for b in record['stepsPerTenSec']), 2917)
        self.assertEqual(record['stepsPerTenSec'][-1]['endTime'], 761000)

    def test_invalid_indoor_values_rejected(self):
        for duration, steps, stop in ((-1, 1, -1000), (0, 1, 0), (1, -1, 1000), (1, 1, 999)):
            with self.subTest(duration=duration, steps=steps), self.assertRaises(ValueError):
                IndoorRunRecordBuilder(1, 2).build_record(duration, steps, 0, stop)

    def test_partial_and_exact_buckets(self):
        for duration in (1, 9, 10, 11, 761, 1200):
            buckets = list(time_buckets(duration, 2917, 0, duration * 1000, 2000))
            self.assertEqual(sum(b[2] for b in buckets), 2917)
            self.assertEqual(buckets[-1][1], duration * 1000)


try:
    import Crypto
    import requests
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


@unittest.skipUnless(CRYPTO_AVAILABLE, 'requires declared pycryptodome and requests dependencies')
class CryptoTransportTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden'))
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def test_crypto_rejects_bad_padding(self):
        from Crypto.Cipher import AES
        from netsec_crypto import NetSecCrypto, NetSecSession
        session = NetSecSession()
        wire = AES.new(session.response_aes_key, AES.MODE_CBC, iv=bytes(16)).encrypt(bytes(14) + b'\x01\x02')
        response = {'v': 101, 'r': base64.b64encode(wire).decode(), 's': ''}
        with self.assertRaises(ValueError):
            NetSecCrypto().decrypt_response(response, session, verify_sig=False)

    def test_crypto_uses_secure_random_source(self):
        from netsec_crypto import NetSecCrypto, NetSecSession
        with patch('random.choice', side_effect=AssertionError('insecure random')):
            wire = NetSecCrypto().encrypt_request({'test': 1}, NetSecSession())
        self.assertTrue(wire['k'])

    def client(self):
        # Browser/captcha dependencies are unrelated to the HTTP transport tests.
        bridge = types.ModuleType('geetest_solver')
        bridge.GeeTestV4Solver = Mock()
        bridge.GEETEST_IDS = {}
        bridge.GeeTestResult = Mock()
        with patch.dict(sys.modules, {'geetest_solver': bridge}):
            import sport_client
        return sport_client.SportClient(uid=1, token='AUDIT_DUMMY', unid=2, adb_path='missing-audit-adb')

    def test_api_requests_do_not_follow_redirects(self):
        client = self.client()
        response = Mock(status_code=302, text='redirect')
        with patch('requests.request', return_value=response) as request:
            client.execute_request('GET', 'https://example.invalid/a')
        self.assertIs(request.call_args.kwargs['allow_redirects'], False)

    def test_obs_put_does_not_follow_redirects(self):
        client = self.client()
        with patch('requests.put', return_value=Mock(status_code=302)) as request:
            result = client._put_presigned_json('https://example.invalid/a', {}, {})
        self.assertIs(request.call_args.kwargs['allow_redirects'], False)
        self.assertNotEqual(result['error'], 10000)

    def test_invalid_indoor_input_never_uploads(self):
        client = self.client()
        client._upload_obs_payload = Mock()
        with self.assertRaises(ValueError):
            client.submit_indoor_exercise(total_time_sec=-1)
        client._upload_obs_payload.assert_not_called()


if __name__ == '__main__':
    unittest.main()
