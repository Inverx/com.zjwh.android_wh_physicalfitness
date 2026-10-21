"""Offline regression tests for the protocol audit; no live credentials or services."""
import contextlib
import importlib
import importlib.util
import io
import pathlib
import socket
import subprocess
import sys
import types
import unittest
from decimal import Decimal
from unittest.mock import Mock, patch

from core.crypto import aes128_cbc_encrypt, aes128_cbc_decrypt, aes128_encrypt_block, key_expansion_128
from core.security import SameOriginRedirectHandler, open_https
from record_validation import time_buckets, validate_run
from security_utils import redact_text
from sport_client import SportClient792
from running.builder import RunningTrackBuilder
from running.client import RunningClient
from profile.client import ProfileClient
from profile.models import ServerTime
from ads.client import AdClient
import urllib.error
import urllib.request


class OfflineTest(unittest.TestCase):
    def setUp(self):
        self.guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden'))
        self.guard.start()
        self.addCleanup(self.guard.stop)


class SecurityTests(OfflineTest):
    def test_credentials_redacted_in_common_formats(self):
        for message in (
            'Authorization: Basic AUDIT_SECRET', 'authorization=Bearer AUDIT_SECRET',
            '{"token": "AUDIT_SECRET"}', "{'password': 'AUDIT_SECRET'}",
            'token=AUDIT_SECRET', '{"Authorization": "Basic AUDIT_SECRET"}',
        ):
            with self.subTest(message=message):
                self.assertNotIn('AUDIT_SECRET', redact_text(message))

    def test_cipher_known_vector(self):
        key = bytes.fromhex('000102030405060708090a0b0c0d0e0f')
        plain = bytes.fromhex('00112233445566778899aabbccddeeff')
        self.assertEqual(aes128_encrypt_block(plain, key_expansion_128(key)).hex(),
                         '69c4e0d86a7b0430d8cdb78070b4c55a')

    def test_both_crypto_modules_reject_bad_padding_and_lengths(self):
        for name in ('core.crypto', 'login.crypto'):
            crypto = importlib.import_module(name)
            key = bytes(16)
            invalid = crypto.aes128_cbc_encrypt(bytes(14) + b'\x01\x02', key)[:16]
            for wire in (b'', b'bad', invalid):
                with self.subTest(module=name, wire=wire), self.assertRaises(ValueError):
                    crypto.aes128_cbc_decrypt(wire, key)
            for size in (0, 1, 15, 16, 17, 32):
                plain = b'x' * size
                self.assertEqual(crypto.aes128_cbc_decrypt(
                    crypto.aes128_cbc_encrypt(plain, key), key), plain)

    def test_cross_origin_and_downgrade_redirects_blocked(self):
        handler = SameOriginRedirectHandler()
        req = urllib.request.Request('https://first.invalid/a', headers={'token': 'AUDIT_SECRET'})
        for target in ('https://second.invalid/b', 'http://first.invalid/b', 'https://first.invalid:444/b'):
            with self.subTest(target=target), self.assertRaises((ValueError, urllib.error.HTTPError)):
                handler.redirect_request(req, None, 302, 'Found', {}, target)
        redirected = handler.redirect_request(req, None, 302, 'Found', {}, 'https://first.invalid/b')
        self.assertEqual(redirected.full_url, 'https://first.invalid/b')

    def test_initial_http_url_rejected_before_opening(self):
        with patch('core.security.urllib.request.build_opener') as build:
            with self.assertRaises(ValueError):
                open_https(urllib.request.Request('http://first.invalid'), context=None, timeout=1)
            build.assert_not_called()

    def test_random_module_is_not_used_for_request_keys(self):
        for name in ('core.crypto', 'login.crypto'):
            module = importlib.import_module(name)
            with patch('random.choice', side_effect=AssertionError('insecure random')):
                wire, key = module.NetSecClient().encrypt_request({'test': 1})
            self.assertTrue(wire['k'])
            self.assertEqual(len(key), 16)


class ValidationTests(OfflineTest):
    def test_buckets_preserve_time_steps_and_distance(self):
        for duration in (1, 9, 10, 11, 761, 1200):
            with self.subTest(duration=duration):
                buckets = list(time_buckets(duration, 2917, 0, duration * 1000, 2100.17))
                self.assertEqual(sum(b[2] for b in buckets), 2917)
                self.assertEqual(sum(Decimal(str(b[3])) for b in buckets), Decimal('2100.17'))
                self.assertEqual(buckets[0][0], 0)
                self.assertEqual(buckets[-1][1], duration * 1000)
                self.assertTrue(all(a[1] == b[0] for a, b in zip(buckets, buckets[1:])))

    def test_invalid_input_rejected(self):
        for duration in (0, -1, 7201, 1.5, True):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                validate_run(duration, 0, 0, int(duration * 1000))
        for distance in (-1, 0, float('nan'), float('inf'), True):
            with self.subTest(distance=distance), self.assertRaises(ValueError):
                validate_run(1, 0, 0, 1000, distance)
        with self.assertRaises(ValueError):
            validate_run(1, 0, 0, 999)

    def test_counted_run_restores_original_circular_five_point_fallback(self):
        _, fixed = RunningTrackBuilder(1, 2).generate_track_around_points(30, 120)
        self.assertEqual(len(fixed), 5)
        for index, point in enumerate(fixed):
            self.assertEqual(point.pointName, f'CheckPoint_{index + 1}')
            self.assertAlmostEqual(((point.lat - 30) ** 2 + (point.lon - 120) ** 2) ** .5,
                                   .00135, places=6)

    def test_selected_duration_is_not_interpreted_as_school_minimum(self):
        builder = RunningTrackBuilder(1, 2, sport_type=6)
        points, fixed = builder.generate_track_around_points(
            30, 120, total_time_sec=760, start_time_ms=0)
        body, _, _ = builder.build_submission_payload(
            2100, 760, 2917, 0, 760000, points, fixed, sel_run_time_s=1200)
        self.assertEqual(body['totalTime'], 760)
        self.assertEqual(body['selRunTime'], 1200)
        self.assertTrue(body['complete'])

    def test_empty_track_rejected(self):
        with self.assertRaises(ValueError):
            RunningTrackBuilder(1, 2).build_submission_payload(2000, 1200, 2000, 0, 1200000, [], [])


class ClientTests(OfflineTest):
    def run_client(self):
        client = RunningClient(uid=1, token='AUDIT_DUMMY', unid=2, device_config={'DeviceId': '1' * 32})
        client.profile.get_server_time = Mock(return_value=ServerTime.from_api(1800000000000, 1800000000000))
        rule = types.SimpleNamespace(min_distance=2000, face_check=types.SimpleNamespace(enable=False))
        client.policy.get_run_policy = Mock(return_value=rule)
        points = [types.SimpleNamespace(lat=30.0, lng=120.0, name='test')]
        fence = types.SimpleNamespace(polygon_points=points, check_points=points, fence_name='test')
        client.policy.get_geo_fence = Mock(return_value=[fence])
        client.telemetry.send_startup_pv = Mock(return_value={'error': 10000})
        client.telemetry.send_page_exposure = Mock(return_value={'error': 10000})
        client.request_obs_upload_url = Mock(return_value={'error': 10000, 'data': {'signedUrl': 'https://obs.invalid/a'}})
        client.upload_to_obs = Mock(return_value={'error': 10000})
        client.submit_record = Mock(return_value={'error': 10000, 'data': {'rrid': 42}})
        client.history.get_one_record = Mock(return_value=types.SimpleNamespace(rrid=42, is_valid=True))
        client.get_rundetail_config = Mock(return_value={'error': 10000})
        return client

    def execute(self, client, **kwargs):
        with patch('running.client.time.sleep'):
            return client.execute_full_run(**kwargs)

    def test_absent_clock_stops_before_upload(self):
        client = self.run_client()
        clock = client.profile.get_server_time.return_value
        clock.synchronized = False
        clock.error_message = 'offline'
        result = self.execute(client)
        self.assertFalse(result.success)
        client.request_obs_upload_url.assert_not_called()

    def test_missing_rule_or_fence_stops_before_upload(self):
        for attribute in ('rule', 'fence'):
            with self.subTest(attribute=attribute):
                client = self.run_client()
                if attribute == 'rule': client.policy.get_run_policy.return_value = None
                else: client.policy.get_geo_fence.return_value = []
                self.assertFalse(self.execute(client).success)
                client.upload_to_obs.assert_not_called()
                client.submit_record.assert_not_called()

    def test_invalid_run_stops_before_upload(self):
        for seconds in (-1, 0):
            with self.subTest(seconds=seconds):
                client = self.run_client()
                self.assertFalse(self.execute(client, target_time_sec=seconds).success)
                client.upload_to_obs.assert_not_called()

    def test_760_second_run_preserves_duration_without_local_minimum(self):
        client = self.run_client()
        result = self.execute(client, target_time_sec=760)
        self.assertTrue(result.success)
        body = client.submit_record.call_args.args[0]
        self.assertEqual(body['totalTime'], 760)
        self.assertEqual(body['selRunTime'], 760)
        self.assertEqual(body['stopTime'] - body['startTime'], 760000)
        self.assertTrue(body['complete'])

    def test_distance_below_school_minimum_still_stops_before_upload(self):
        client = self.run_client()
        result = self.execute(client, target_distance_m=1999, target_time_sec=760)
        self.assertFalse(result.success)
        self.assertIn('2000', result.message)
        client.upload_to_obs.assert_not_called()

    def test_only_explicit_server_minimum_time_is_enforced(self):
        for duration, permitted in ((299, False), (760, True)):
            client = self.run_client()
            client.policy.get_run_policy.return_value.min_run_time_sec = 300
            result = self.execute(client, target_time_sec=duration)
            self.assertEqual(result.success, permitted)
            if not permitted:
                self.assertIn('minRunTime=300', result.message)
                client.upload_to_obs.assert_not_called()

    def test_missing_checkpoints_uses_fallback_and_logs_source(self):
        client = self.run_client()
        fence = client.policy.get_geo_fence.return_value[0]
        fence.check_points = []
        messages = []
        result = self.execute(client, progress_callback=messages.append)
        self.assertTrue(result.success)
        self.assertTrue(any('圆形生成 5 个本地点' in message for message in messages))
        client.upload_to_obs.assert_called_once()

    def test_required_face_verification_stops_submission(self):
        client = self.run_client()
        client.policy.get_run_policy.return_value.face_check.enable = True
        self.assertFalse(self.execute(client).success)
        client.submit_record.assert_not_called()

    def test_missing_record_id_never_valid(self):
        client = self.run_client()
        client.submit_record.return_value = {'error': 10000, 'data': {}}
        result = self.execute(client)
        self.assertFalse(result.success)
        self.assertIsNone(result.is_valid)
        client.history.get_one_record.assert_not_called()

    def test_missing_or_mismatched_detail_remains_unknown(self):
        for detail in (None, types.SimpleNamespace(rrid=99, is_valid=True)):
            client = self.run_client()
            client.history.get_one_record.return_value = detail
            result = self.execute(client)
            self.assertFalse(result.success)
            self.assertEqual(result.rrid, 42)
            self.assertIsNone(result.is_valid)

    def test_valid_and_invalid_verified_results_preserved(self):
        for valid in (False, True):
            client = self.run_client()
            client.history.get_one_record.return_value.is_valid = valid
            result = self.execute(client)
            self.assertTrue(result.success)
            self.assertIs(result.is_valid, valid)

    def test_malformed_obs_response_never_uploaded(self):
        client = self.run_client()
        client.request_obs_upload_url.return_value = {'error': 10000, 'data': 'bad'}
        self.assertFalse(self.execute(client).success)
        client.upload_to_obs.assert_not_called()

    def test_clock_failure_marked_explicitly(self):
        client = ProfileClient()
        client.execute_request = Mock(return_value={'error': -1})
        self.assertFalse(client.get_server_time().synchronized)

    def test_malformed_clock_payload_never_succeeds(self):
        for value in ('bad', None, True, -1, 1.5, 10**30):
            client = ProfileClient()
            client.execute_request = Mock(return_value={'error': 10000, 'data': value})
            self.assertFalse(client.get_server_time().synchronized)

    def test_facade_uses_authenticated_transport(self):
        client = SportClient792(uid=1, token='AUDIT_DUMMY', unid=2, device_config={'DeviceId': '1' * 32})
        client.profile.execute_request = Mock(return_value={'error': 10000})
        for name in ('get_cheat_blacklist', 'get_barrier_free_policy', 'get_ranks', 'get_credit_popup'):
            self.assertEqual(getattr(client, name)(), {'error': 10000})
        self.assertEqual(client.profile.execute_request.call_count, 4)

    def test_ads_do_not_claim_playback_or_send_fake_events(self):
        client = AdClient()
        client.get_ad_config = Mock()
        client.send_ad_pv = Mock()
        result = client.simulate_watch_ad(duration_sec=120)
        self.assertFalse(result.success)
        self.assertEqual(result.duration_sec, 0)
        self.assertEqual(result.events_count, 0)
        client.get_ad_config.assert_not_called()
        client.send_ad_pv.assert_not_called()


class CliTests(OfflineTest):
    def test_missing_credentials_exit_nonzero(self):
        entry = pathlib.Path(__file__).with_name('cli.py')
        proc = subprocess.run([sys.executable, '-B', str(entry), '--run'], capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 1)

    def test_login_prints_reusable_credentials(self):
        spec = importlib.util.spec_from_file_location('audit_main_cli', pathlib.Path(__file__).with_name('cli.py'))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        fake = Mock()
        fake.token = 'AUDIT_FULL_TOKEN_SECRET'
        fake.uid = '123456789'
        fake.unid = '2'
        fake.login.return_value = types.SimpleNamespace(success=True)
        fake.sync_server_time.return_value = ServerTime.from_api(1800000000000)
        output = io.StringIO()
        with patch.object(sys, 'argv', ['cli.py', '-u', 'audit', '-p', 'dummy']), \
                patch.object(cli, 'SportClient792', return_value=fake), contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(), 0)
        self.assertIn('token=' + fake.token, output.getvalue())
        self.assertIn('uid=' + fake.uid, output.getvalue())
        self.assertIn('unid=' + fake.unid, output.getvalue())

    def test_standalone_login_prints_reusable_credentials(self):
        cli = importlib.import_module('login.cli')
        fake = Mock()
        user = types.SimpleNamespace(name='audit', uid=123456789, unid=2,
                                     token='AUDIT_FULL_TOKEN_SECRET')
        fake.login.return_value = types.SimpleNamespace(success=True, user=user)
        output = io.StringIO()
        with patch.object(sys, 'argv', ['login/cli.py', '-u', 'audit', '-p', 'dummy']), \
                patch.object(cli, 'LoginClient', return_value=fake), contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(), 0)
        self.assertIn('token=' + user.token, output.getvalue())
        self.assertIn('uid=' + str(user.uid), output.getvalue())
        self.assertIn('unid=' + str(user.unid), output.getvalue())

    def test_failed_sync_exit_nonzero(self):
        spec = importlib.util.spec_from_file_location('audit_main_cli', pathlib.Path(__file__).with_name('cli.py'))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        fake = Mock()
        clock = ServerTime.from_api(1800000000000)
        clock.synchronized = False
        clock.error_message = 'offline'
        fake.sync_server_time.return_value = clock
        with patch.object(sys, 'argv', ['cli.py', '--sync-time']), \
                patch.object(cli, 'SportClient792', return_value=fake), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(), 1)


if __name__ == '__main__':
    unittest.main()
