"""Offline reproduction of missing-school rule requests and error reporting."""
import json
import socket
import types
import unittest
from unittest.mock import Mock, patch

from policy.client import PolicyClient
from sport_client import SportClient792


class PolicyDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)
        self.device = {'DeviceId': '1' * 32}
        self.good = {'error': 10000, 'data': {'runRuleModel': {'minDistance': 2000}}}

    def client(self, unid=None):
        return PolicyClient(uid=1, token='AUDIT_DUMMY', unid=unid, device_config=self.device)

    def test_missing_unid_resolves_profile_before_rule_request(self):
        client = self.client()
        client.execute_request = Mock(side_effect=[
            {'error': 10000, 'data': {'uid': 1, 'unid': 3304}}, self.good])
        self.assertEqual(client.get_run_policy().min_distance, 2000)
        self.assertEqual(client.unid, '3304')
        calls = client.execute_request.call_args_list
        self.assertEqual(calls[0].args[0], 'GET')
        self.assertEqual(calls[1].kwargs['body_plain']['selectUnid'], 3304)
        self.assertIsNone(client.last_policy_error)

    def test_explicit_unid_skips_profile_lookup(self):
        client = self.client(3304)
        client.execute_request = Mock(return_value=self.good)
        self.assertIsNotNone(client.get_run_policy())
        self.assertEqual(client.execute_request.call_count, 1)
        self.assertEqual(client.execute_request.call_args.kwargs['body_plain']['selectUnid'], 3304)

    def test_missing_school_never_sends_zero_to_policy(self):
        client = self.client()
        client.execute_request = Mock(return_value={'error': 10000, 'data': {'uid': 1}})
        self.assertIsNone(client.get_run_policy())
        self.assertEqual(client.execute_request.call_count, 1)
        self.assertIn('--unid', client.last_policy_error)

    def test_profile_for_another_uid_is_not_used(self):
        client = self.client()
        client.execute_request = Mock(return_value={'error': 10000, 'data': {'uid': 99, 'unid': 3304}})
        self.assertIsNone(client.get_run_policy())
        self.assertEqual(client.execute_request.call_count, 1)

    def test_server_error_is_preserved_but_diagnostics_redact_token(self):
        client = self.client(3304)
        client.execute_request = Mock(return_value={'error': 12345, 'message': 'invalid token=AUDIT_SECRET'})
        self.assertIsNone(client.get_run_policy())
        self.assertIn('12345', client.last_policy_error)
        self.assertIn('selectUnid=3304', client.last_policy_error)
        self.assertNotIn('AUDIT_SECRET', client.last_policy_error)

    def test_missing_or_invalid_rule_data_has_specific_error(self):
        for data in (None, {}, {'unexpected': 1}, {'runRuleModel': []}, 'invalid json'):
            client = self.client(3304)
            client.execute_request = Mock(return_value={'error': 10000, 'data': data})
            self.assertIsNone(client.get_run_policy())
            self.assertIn('code=10000', client.last_policy_error)

    def test_string_encoded_rule_payload_is_supported(self):
        client = self.client(3304)
        client.execute_request = Mock(return_value={'error': 10000, 'data': json.dumps(self.good['data'])})
        self.assertEqual(client.get_run_policy().min_distance, 2000)

    def test_error_state_cleared_after_successful_retry(self):
        client = self.client(3304)
        client.execute_request = Mock(side_effect=[{'error': -1}, self.good])
        self.assertIsNone(client.get_run_policy())
        self.assertIsNotNone(client.get_run_policy())
        self.assertIsNone(client.last_policy_error)

    def test_profile_query_updates_school_for_all_subclients(self):
        client = SportClient792(uid=1, token='AUDIT_DUMMY', device_config=self.device)
        client.profile.get_user_info = Mock(return_value=types.SimpleNamespace(uid=1, unid=3304))
        self.assertIsNotNone(client.get_user_profile())
        self.assertEqual(client.unid, '3304')
        for sub in (client.policy, client.running, client.history, client.running.policy):
            self.assertEqual(sub.unid, '3304')

    def test_resolved_policy_school_updates_facade(self):
        client = SportClient792(uid=1, token='AUDIT_DUMMY', device_config=self.device)
        client.policy.execute_request = Mock(side_effect=[
            {'error': 10000, 'data': {'uid': 1, 'unid': 3304}}, self.good])
        self.assertIsNotNone(client.get_run_policy())
        self.assertEqual(client.unid, '3304')
        self.assertEqual(client.running.unid, '3304')


if __name__ == '__main__':
    unittest.main()
