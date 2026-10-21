"""Regression coverage for observed fence field shapes, using synthetic coordinates."""
import json
import socket
import unittest
from unittest.mock import Mock, patch
from policy.client import PolicyClient
from policy.models import GeoFenceArea, RunRule


class GeofenceParsingTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_lon_from_fence_endpoint_and_lng_from_policy_both_parse(self):
        for longitude in ('lon', 'lng'):
            fence = GeoFenceArea.from_api_data({'id': 1, 'points': [
                {'lat': 30.0, longitude: 120.0, 'glat': 30.1, 'glon': 120.1}]})
            self.assertEqual(len(fence.polygon_points), 1)
            self.assertEqual(fence.polygon_points[0].lng, 120.0)

    def test_ten_boundary_points_are_not_silently_lost(self):
        fence = GeoFenceArea.from_api_data({'points': [
            {'lat': 30 + i * .001, 'lon': 120 + i * .001, 'pointsNumber': i}
            for i in range(10)]})
        self.assertEqual(len(fence.polygon_points), 10)
        self.assertEqual(fence.check_points, [])

    def test_zero_coordinate_is_valid(self):
        fence = GeoFenceArea.from_api_data({'points': [{'lat': 0, 'lon': 0}]})
        self.assertEqual(fence.polygon_points[0].lng, 0)

    def test_invalid_points_are_errors_instead_of_being_discarded(self):
        for point in ({'lat': 30}, {'lat': 30, 'lon': float('nan')}, {'lat': 91, 'lon': 120}):
            with self.assertRaises(ValueError):
                GeoFenceArea.from_api_data({'points': [point]})

    def test_missing_checkpoint_field_does_not_fabricate_points(self):
        fence = GeoFenceArea.from_api_data({'points': [{'lat': 30, 'lon': 120}]})
        self.assertEqual(fence.check_points, [])

    def client(self):
        return PolicyClient(uid=1, token='AUDIT_DUMMY', unid=2,
                            device_config={'DeviceId': '1' * 32})

    def test_api_error_retains_code_but_redacts_credentials(self):
        client = self.client()
        client.execute_request = Mock(return_value={'error': 12345, 'message': 'token=AUDIT_SECRET'})
        self.assertEqual(client.get_geo_fence(), [])
        self.assertIn('12345', client.last_geo_fence_error)
        self.assertNotIn('AUDIT_SECRET', client.last_geo_fence_error)

    def test_empty_and_malformed_geofence_payloads_have_diagnostics(self):
        for data in ({}, {'geoFences': []}, {'geoFences': [{'points': [{'lat': 30}]}]}):
            client = self.client()
            client.execute_request = Mock(return_value={'error': 10000, 'data': data})
            self.assertEqual(client.get_geo_fence(), [])
            self.assertTrue(client.last_geo_fence_error)

    def test_json_encoded_payload_and_error_reset(self):
        client = self.client()
        payload = {'geoFences': [{'points': [{'lat': 30, 'lon': 120}]}]}
        client.execute_request = Mock(side_effect=[{'error': -1}, {'error': 10000, 'data': json.dumps(payload)}])
        self.assertEqual(client.get_geo_fence(), [])
        self.assertEqual(len(client.get_geo_fence()[0].polygon_points), 1)
        self.assertIsNone(client.last_geo_fence_error)

    def test_school_minimum_runtime_is_read_from_explicit_field(self):
        rule = RunRule.from_api_data({'runRuleModel': {'minDistance': 2000, 'minRunTime': 300}})
        self.assertEqual(rule.min_run_time_sec, 300)
        self.assertIsNone(RunRule.from_api_data({'runRuleModel': {'minDistance': 2000}}).min_run_time_sec)
        with self.assertRaises(ValueError):
            RunRule.from_api_data({'runRuleModel': {'minRunTime': -1}})


if __name__ == '__main__':
    unittest.main()
