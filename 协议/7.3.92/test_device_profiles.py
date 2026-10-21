"""Device identity persistence tests; all files live in temporary directories."""
import contextlib
import importlib
import importlib.util
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from core.devices import DeviceStore, DEVICE_TEMPLATES
from login.client import LoginClient
from profile.client import ProfileClient
from sport_client import SportClient792


class DeviceStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = DeviceStore(self.temp.name)
        guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_same_account_survives_reopening_and_phone_normalization(self):
        first = self.store.for_account('10000000000')
        again = DeviceStore(self.temp.name).for_account('+86 10000000000')
        self.assertEqual(first, again)
        self.assertEqual(first, self.store.for_account('008610000000000'))

    def test_distinct_accounts_have_distinct_ids_and_coherent_models(self):
        devices = [self.store.for_account('audit-account-' + str(i)) for i in range(8)]
        self.assertEqual(len({d['DeviceId'] for d in devices}), 8)
        self.assertEqual(len({d['deviceName'] for d in devices[:4]}), 4)
        for device in devices:
            template = next(t for t in DEVICE_TEMPLATES if t['deviceName'] == device['deviceName'])
            self.assertEqual(device['physicPixel'], template['physicPixel'])
            self.assertEqual(device['logicPixel'], template['logicPixel'])
            self.assertIn(device['osVersion'], template['osVersions'])

    def test_uid_mapping_reuses_account_profile(self):
        device = self.store.for_account('audit-account')
        self.store.bind_uid('audit-account', 42)
        self.assertEqual(device, DeviceStore(self.temp.name).for_uid('42'))

    def test_uid_collision_does_not_rebind_other_accounts(self):
        first = self.store.for_account('first-audit-account')
        self.store.for_account('second-audit-account')
        self.store.bind_uid('first-audit-account', 42)
        with self.assertRaises(ValueError):
            self.store.bind_uid('second-audit-account', 42)
        self.assertEqual(self.store.for_uid(42), first)

    def test_unknown_uid_does_not_generate_new_identity(self):
        with self.assertRaisesRegex(ValueError, 'first log in'):
            self.store.for_uid(99)
        self.assertFalse(self.store.path.exists())

    def test_store_does_not_contain_plaintext_account_or_credentials(self):
        self.store.for_account('private-audit-account')
        self.store.bind_uid('private-audit-account', 42)
        text = self.store.path.read_text(encoding='utf-8')
        self.assertNotIn('private-audit-account', text)
        self.assertNotIn('password', text.lower())
        self.assertNotIn('token', text.lower())
        self.assertEqual(set(json.loads(text)), {'version', 'accounts', 'uids'})

    def test_corrupt_file_is_preserved_and_never_regenerated(self):
        self.store.path.write_text('broken json', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'refusing to replace'):
            self.store.for_account('audit-account')
        self.assertEqual(self.store.path.read_text(), 'broken json')
        self.assertFalse((Path(self.temp.name) / 'devices.lock').exists())

    def test_incomplete_saved_profile_is_not_silently_reset(self):
        self.store.for_account('audit-account')
        data = json.loads(self.store.path.read_text(encoding='utf-8'))
        next(iter(data['accounts'].values())).pop('DeviceId')
        self.store.path.write_text(json.dumps(data), encoding='utf-8')
        before = self.store.path.read_bytes()
        with self.assertRaises(ValueError):
            self.store.for_account('audit-account')
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_atomic_write_failure_preserves_previous_file(self):
        self.store.for_account('first-audit-account')
        before = self.store.path.read_bytes()
        with patch('core.devices.os.replace', side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                self.store.for_account('second-audit-account')
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertFalse(list(Path(self.temp.name).glob('*.tmp')))

    def test_concurrent_creators_reuse_one_profile_and_preserve_other_accounts(self):
        def same(_):
            return DeviceStore(self.temp.name).for_account('shared-audit-account')
        with ThreadPoolExecutor(max_workers=8) as pool:
            devices = list(pool.map(same, range(8)))
        self.assertTrue(all(d == devices[0] for d in devices))
        def different(i):
            return DeviceStore(self.temp.name).for_account('audit-account-' + str(i))
        with ThreadPoolExecutor(max_workers=8) as pool:
            devices = list(pool.map(different, range(8)))
        data = json.loads(self.store.path.read_text(encoding='utf-8'))
        self.assertEqual(len(data['accounts']), 9)
        self.assertEqual(len({d['DeviceId'] for d in devices}), 8)

    def test_profile_survives_a_separate_python_process(self):
        device = self.store.for_account('audit-account')
        script = ('from core.devices import DeviceStore; import sys,json; '
                  'print(json.dumps(DeviceStore(sys.argv[1]).for_account("audit-account")))')
        result = subprocess.run([sys.executable, '-B', '-c', script, self.temp.name],
                                cwd=Path(__file__).resolve().parent, capture_output=True,
                                text=True, check=True, timeout=10)
        self.assertEqual(json.loads(result.stdout), device)

    def test_store_location_is_independent_of_working_directory(self):
        self.assertTrue(DeviceStore().directory.is_absolute())
        self.assertEqual(DeviceStore().directory.name, '.device_profiles')

    def mock_login(self, client, uid=42, success=True):
        client.check_gee_use = Mock(return_value={'error': 10000, 'data': True})
        client.submit_login = Mock(return_value=(
            {'error': 10000, 'data': {'uid': uid, 'unid': 2, 'token': 'AUDIT_DUMMY'}}
            if success else {'error': -1, 'message': 'mock failure'}))

    def test_standalone_login_saves_device_before_first_request_and_binds_uid(self):
        client = LoginClient(device_dir=self.temp.name)
        self.mock_login(client)
        def initial_check(*args):
            self.assertEqual(client.device_config['DeviceId'], self.store.for_account('audit-account')['DeviceId'])
            return {'error': 10000, 'data': True}
        client.check_gee_use.side_effect = initial_check
        self.assertTrue(client.login('audit-account', 'AUDIT_PASSWORD').success)
        saved = self.store.for_uid(42)
        self.assertEqual(client.device_config['DeviceId'], saved['DeviceId'])
        self.assertEqual(client.device_config['deviceName'], saved['deviceName'])

    def test_failed_login_keeps_device_but_does_not_bind_uid(self):
        client = LoginClient(device_dir=self.temp.name)
        self.mock_login(client, success=False)
        self.assertFalse(client.login('audit-account', 'AUDIT_PASSWORD').success)
        self.assertTrue(self.store.path.exists())
        with self.assertRaises(ValueError):
            self.store.for_uid(42)

    def test_facade_propagates_saved_identity_to_every_subclient(self):
        client = SportClient792(account='audit-account', device_dir=self.temp.name)
        self.mock_login(client.login_client)
        self.assertTrue(client.login('audit-account', 'AUDIT_PASSWORD').success)
        expected = self.store.for_uid(42)['DeviceId']
        for sub in (client.login_client, client.profile, client.policy, client.running,
                    client.history, client.ads, client.running.profile, client.running.policy,
                    client.running.history):
            self.assertEqual(sub.device_config['DeviceId'], expected)
        self.assertEqual(client.telemetry.device['DeviceId'], expected)
        self.assertEqual(client.running.telemetry.device['DeviceId'], expected)
        reused = SportClient792(uid=42, token='AUDIT_DUMMY', device_dir=self.temp.name)
        self.assertEqual(reused.device_config, client.device_config)

    def test_facade_login_selects_account_even_without_constructor_account(self):
        client = SportClient792(device_dir=self.temp.name)
        # login() may rebuild clients when it switches from an anonymous profile.
        with patch('sport_client.LoginClient') as factory:
            factory.return_value.login.return_value = types.SimpleNamespace(
                success=True, user=types.SimpleNamespace(uid=42, token='AUDIT_DUMMY', unid=2))
            self.assertTrue(client.login('audit-account', 'AUDIT_PASSWORD').success)
        self.assertEqual(client.device_config, self.store.for_uid(42))

    def test_direct_query_client_reuses_uid_mapping(self):
        device = self.store.for_account('audit-account')
        self.store.bind_uid('audit-account', 42)
        with patch.dict('os.environ', {'SPORT_DEVICE_DIR': self.temp.name}):
            query = ProfileClient(uid=42, token='AUDIT_DUMMY')
        self.assertEqual(query.device_config, device)

    def test_setting_query_credentials_later_also_reuses_device(self):
        device = self.store.for_account('audit-account')
        self.store.bind_uid('audit-account', 42)
        with patch.dict('os.environ', {'SPORT_DEVICE_DIR': self.temp.name}):
            query = ProfileClient()
            query.set_credentials(42, 'AUDIT_DUMMY')
        self.assertEqual(query.device_config, device)

    def test_setting_facade_credentials_later_propagates_saved_device(self):
        device = self.store.for_account('audit-account')
        self.store.bind_uid('audit-account', 42)
        client = SportClient792(device_dir=self.temp.name)
        client.set_credentials(42, 'AUDIT_DUMMY', 2)
        self.assertEqual(client.device_config, device)
        self.assertEqual(client.running.device_config, device)
        self.assertEqual(client.running.telemetry.device['DeviceId'], device['DeviceId'])

    def test_cli_passes_account_and_device_directory(self):
        spec = importlib.util.spec_from_file_location('audit_main_cli', Path(__file__).with_name('cli.py'))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        fake = Mock()
        fake.login.return_value = types.SimpleNamespace(success=False, error_code=-1, message='mock')
        with patch.object(sys, 'argv', ['cli.py', '-u', 'audit-account', '-p', 'dummy',
                                      '--device-dir', self.temp.name]), \
                patch.object(cli, 'SportClient792', return_value=fake) as factory, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(), 1)
        self.assertEqual(factory.call_args.kwargs['account'], 'audit-account')
        self.assertEqual(factory.call_args.kwargs['device_dir'], self.temp.name)


if __name__ == '__main__':
    unittest.main()
