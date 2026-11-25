"""Offline regression tests for measured distance, timestamps and bucket totals."""
import base64
import copy
import gzip
import json
import math
import socket
import types
import unittest
from unittest.mock import Mock, patch

from running.builder import RunningTrackBuilder
from running.client import RunningClient
from running.consistency import time_buckets
from running.models import GpsPoint


def measured_length(points):
    # Independent spherical-law-of-cosines measurement, not the production helper.
    result = 0.0
    for first, last in zip(points, points[1:]):
        la1, la2 = math.radians(first.lat), math.radians(last.lat)
        delta = math.radians(last.lon-first.lon)
        cosine = math.sin(la1)*math.sin(la2) + math.cos(la1)*math.cos(la2)*math.cos(delta)
        result += 6371000*math.acos(max(-1.0, min(1.0, cosine)))
    return result


class RunConsistencyTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def build(self, seconds=760, meters=2150, steps=2900, mode=1, checkpoints=None):
        builder = RunningTrackBuilder(1, 2, mode, uuid_str='offline-consistency-test')
        points, fixed = builder.generate_track_around_points(
            30, 120, checkpoints, meters, seconds, 1700000000000)
        body, obs, key = builder.build_submission_payload(
            meters, seconds, steps, 1700000000000, 1700000000000+seconds*1000,
            points, fixed)
        return builder, points, fixed, body, obs

    def test_reported_2150m_760s_2900step_case(self):
        _, points, fixed, body, obs = self.build()
        self.assertAlmostEqual(measured_length(points), 2150, delta=.1)
        self.assertEqual(len(fixed), 5)
        self.assertEqual(sum(row['stepsNum'] for row in body['stepsPerTenSec']), 2900)
        self.assertAlmostEqual(sum(row['distance'] for row in body['speedPerTenSec']), 2150)
        self.assertEqual(points[-1].time-points[0].time, 760000)
        self.assertTrue(all(a.time < b.time for a,b in zip(points,points[1:])))
        # OBS and settlement must carry the same data, including bucket remainders.
        for field, obs_field in [('allLocJson','run_data'), ('fivePointJson','fixed_point_json')]:
            self.assertEqual(body[field], gzip.decompress(base64.b64decode(obs[obs_field])).decode())
        for field, obs_field in [('stepsPerTenSec','step_freq_json'), ('speedPerTenSec','speed_json')]:
            decoded=json.loads(gzip.decompress(base64.b64decode(obs[obs_field])))
            self.assertEqual(body[field], decoded)

    def test_partial_last_bucket_is_contiguous_and_lossless(self):
        for seconds in (1, 7, 10, 11, 31, 761):
            with self.subTest(seconds=seconds):
                rows=list(time_buckets(seconds, 2903, 1000, 1000+seconds*1000, 2153))
                self.assertEqual(rows[0][0],1000)
                self.assertEqual(rows[-1][1],1000+seconds*1000)
                self.assertTrue(all(a[1]==b[0] for a,b in zip(rows,rows[1:])))
                self.assertTrue(all(0 < end-begin <= 10000 for begin,end,_,_ in rows))
                self.assertEqual(sum(row[2] for row in rows),2903)
                self.assertAlmostEqual(sum(row[3] for row in rows),2153)

    def test_real_checkpoint_coordinates_preserved_and_visited(self):
        targets=[{'lat':30.0+i*.0002,'lng':120.0+i*.0003,'name':str(i)} for i in range(5)]
        _,points,fixed,_,_=self.build(checkpoints=targets)
        self.assertEqual([(p.lat,p.lon) for p in fixed],[(p['lat'],p['lng']) for p in targets])
        for point in fixed:
            self.assertTrue(any(p.lat==point.lat and p.lon==point.lon for p in points))
        self.assertAlmostEqual(measured_length(points),2150,delta=.1)

    def test_zero_checkpoint_coordinate_is_not_replaced_by_center(self):
        targets=[{'lat':0.0,'lng':120.0}, {'lat':.0005,'lng':120.0005}]
        _,points,fixed,_,_=self.build(checkpoints=targets)
        self.assertEqual(fixed[0].lat,0.0)
        self.assertEqual(points[0].lat,0.0)
        self.assertAlmostEqual(measured_length(points),2150,delta=.1)

    def test_route_too_short_for_supplied_points_is_rejected(self):
        targets=[{'lat':30.0,'lng':120.0},{'lat':31.0,'lng':121.0}]
        with self.assertRaisesRegex(ValueError,'too short'):
            self.build(checkpoints=targets)

    def test_partial_duration_and_shorter_template_repeated_laps(self):
        _,points,_,body,_=self.build(seconds=761,meters=5037,steps=6103)
        self.assertAlmostEqual(measured_length(points),5037,delta=.1)
        self.assertEqual(sum(x['stepsNum'] for x in body['stepsPerTenSec']),6103)
        self.assertEqual(body['stepsPerTenSec'][-1]['endTime']-body['stepsPerTenSec'][-1]['beginTime'],1000)

    def test_short_free_run_does_not_require_full_template_loop(self):
        _,points,fixed,_,_=self.build(meters=100,seconds=45,steps=120,mode=6)
        self.assertEqual(fixed,[])
        self.assertAlmostEqual(measured_length(points),100,delta=.1)

    def test_invalid_input_rejected(self):
        for seconds,steps,meters in [(0,1,100),(-1,1,100),(760,-1,2150),(760,1,float('nan'))]:
            with self.subTest(seconds=seconds,steps=steps,meters=meters),self.assertRaises(ValueError):
                self.build(seconds,meters,steps)

    def test_inconsistent_track_cannot_be_packaged(self):
        builder,points,fixed,_,_=self.build()
        for mutate in ('distance','timestamp','checkpoint'):
            bad=copy.deepcopy(points)
            if mutate=='distance': bad[1].lat += .01
            elif mutate=='timestamp': bad[-1].time-=1
            else: fixed=[types.SimpleNamespace(lat=31,lon=121)]
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                builder.build_submission_payload(2150,760,2900,1700000000000,
                                                 1700000760000,bad,fixed)

    def test_validation_failure_prevents_obs_and_settlement(self):
        client=RunningClient(uid=1,token='DUMMY',unid=2,device_config={'DeviceId':'1'*32})
        client.profile.get_server_time=Mock(return_value=types.SimpleNamespace(
            server_timestamp_ms=1700000000000,offset_seconds=0))
        client.telemetry.send_startup_pv=Mock()
        client.telemetry.send_page_exposure=Mock()
        client.policy.get_run_policy=Mock(return_value=types.SimpleNamespace(
            min_distance=2000,raw={'runRuleModel':{'minRunTime':300},'policy':1}))
        client.policy.get_geo_fence=Mock(return_value=[])
        client.request_obs_upload_url=Mock()
        client.submit_record=Mock()
        with patch('running.client.RunningTrackBuilder.generate_track_around_points',side_effect=ValueError('mismatch')):
            result=client.execute_full_run()
        self.assertFalse(result.success)
        self.assertIn('mismatch',result.message)
        client.request_obs_upload_url.assert_not_called()
        client.submit_record.assert_not_called()


if __name__=='__main__':
    unittest.main()
