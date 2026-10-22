"""Offline coverage for the Android five-point request and runtime integration."""
import base64
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
import types
import unittest
from unittest.mock import Mock, patch

from policy.client import PolicyClient
from policy.models import GeoFenceArea, GeoPoint
from running.builder import RunningTrackBuilder
from running.client import RunningClient


def official_points():
    return [{'lat':30+i*.0003, 'lon':120+i*.0002,
             'glat':30+i*.0003-.006, 'glon':120+i*.0002-.006,
             'pointName':f'Campus {i}', 'isFixed':i%2} for i in range(5)]


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        guard=patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def client(self, response=None):
        client=PolicyClient(uid=1,token='DUMMY',unid=2,device_config={'DeviceId':'1'*32})
        client.execute_request=Mock(return_value=response or {'error':10000,'data':{
            'pointsResModels':official_points(),'sportStartTime':1700000000000}})
        return client

    def fence(self):
        return GeoFenceArea.from_api_data({'id':3,'name':'test','points':[
            {'lat':30,'lon':120,'glat':29.994,'glon':119.994}]})

    def test_full_request_body_and_fixed_path_key(self):
        client=self.client()
        points=client.get_run_checkpoints(2000,29.994,119.994,uuid_str='session-id')
        self.assertEqual(len(points),5)
        args=client.execute_request.call_args
        url='https://run.gxapp.iydsj.com/api/v560/get/1/distance/2000'
        self.assertEqual(args.args,('POST',url))
        body=args.kwargs['body_plain']
        self.assertEqual(set(body),{'longitude','latitude','selectedUnid','uuid','runec','runAreaId','sign'})
        self.assertEqual(body['selectedUnid'],2)
        self.assertEqual(body['uuid'],'session-id')
        self.assertEqual(body['runAreaId'],-1)
        self.assertEqual(body['runec'],'')
        expected=hashlib.md5(b'http://run.gxapp.iydsj.com/api/v560/get/1/distance/2000' +
                             b'2slhe02lsfiwowlcixisla_sls-_slaor').hexdigest()
        self.assertEqual(body['sign'],expected)
        self.assertEqual(client.last_checkpoint_start_time,1700000000000)

    def test_payload_shapes_and_metadata_preserved(self):
        for data in ({'pointsResModels':official_points()},json.dumps({'pointsResModels':official_points()})):
            client=self.client({'error':10000,'data':data})
            points=client.get_run_checkpoints(2000,30,120)
            self.assertEqual(points[1].name,'Campus 1')
            self.assertEqual(points[1].raw['isFixed'],1)
            self.assertEqual(points[0].gcj_coordinates(),(29.994,119.994))
            self.assertIsNone(client.last_checkpoint_error)

    def test_error_empty_and_bad_coordinates_not_success(self):
        responses=[{'error':-10000,'message':'ERROR'},
                   {'error':10000,'data':{'pointsResModels':[]}},
                   {'error':10000,'data':{'passPoints':official_points()}},
                   {'error':10000,'data':{'pointsResModels':[{'lat':30}]}},
                   {'error':10000,'data':'{broken'}]
        for response in responses:
            with self.subTest(response=response):
                client=self.client(response)
                self.assertEqual(client.get_run_checkpoints(2000,30,120),[])
                self.assertTrue(client.last_checkpoint_error)
                self.assertIsNone(client.last_checkpoint_start_time)

    def test_missing_anchor_and_invalid_distance_prevent_network(self):
        for kwargs in ({},{'latitude':float('nan'),'longitude':120},
                       {'latitude':30,'longitude':181},{'latitude':30,'longitude':120,'distance_m':0}):
            client=self.client()
            self.assertEqual(client.get_run_checkpoints(**({'distance_m':2000,'latitude':None,'longitude':None}|kwargs)),[])
            client.execute_request.assert_not_called()

    def test_geofence_lon_and_lng_preserve_gcj_anchor(self):
        for key in ('lon','lng'):
            fence=GeoFenceArea.from_api_data({'id':3,'points':[
                {'lat':30,key:120,'glat':29.994,'glng':119.994}]})
            self.assertEqual(fence.polygon_points[0].lng,120)
            self.assertEqual(fence.polygon_points[0].gcj_coordinates(),(29.994,119.994))
            self.assertEqual(fence.check_points,[])
        for raw in ({'lat':30,'lon':120},{'lat':30,'lon':120,'glat':-1,'glon':-1}):
            with self.assertRaises(ValueError):GeoPoint.from_api_data(raw).gcj_coordinates()

    def test_policy_minimum_distance_and_selected_area(self):
        client=self.client()
        client.get_run_policy=Mock(return_value=types.SimpleNamespace(min_distance=2000,raw={
            'runAreaModels':[{'id':8,'valid':True,'select':True,'fenceIds':[3]}]}))
        self.assertEqual(len(client.get_checkpoints_for_run(self.fence(),'shared-uuid')),5)
        call=client.execute_request.call_args
        self.assertIn('/distance/2000',call.args[1])
        self.assertEqual(call.kwargs['body_plain']['runAreaId'],8)
        self.assertEqual(call.kwargs['body_plain']['latitude'],29.994)
        self.assertEqual(call.kwargs['body_plain']['uuid'],'shared-uuid')

    def test_ambiguous_area_and_missing_rule_prevent_point_request(self):
        for rule in (None,types.SimpleNamespace(min_distance=2000,raw={'runAreaModels':[
                {'id':1,'valid':True,'fenceIds':[3]},{'id':2,'valid':True,'fenceIds':[3]}]})):
            client=self.client()
            client.get_run_policy=Mock(return_value=rule)
            self.assertEqual(client.get_checkpoints_for_run(self.fence()),[])
            client.execute_request.assert_not_called()
            self.assertTrue(client.last_checkpoint_error)

    def test_official_metadata_survives_builder_and_obs(self):
        checkpoints=[GeoPoint.from_api_data(point).as_checkpoint() for point in official_points()]
        builder=RunningTrackBuilder(1,2,1)
        track,fixed=builder.generate_track_around_points(30,120,checkpoints,2150,760,0)
        body,obs,_=builder.build_submission_payload(2150,760,2900,0,760000,track,fixed)
        serialized=json.loads(body['fivePointJson'])
        for actual,source in zip(serialized,official_points()):
            for key in ('lat','lon','glat','glon','pointName','isFixed'):
                self.assertEqual(actual[key],source[key])
        self.assertEqual(serialized,json.loads(gzip.decompress(base64.b64decode(obs['fixed_point_json']))))

    def test_counted_run_fetches_official_points_and_reuses_uuid(self):
        client=RunningClient(uid=1,token='DUMMY',unid=2,device_config={'DeviceId':'1'*32})
        client.profile.get_server_time=Mock(return_value=types.SimpleNamespace(
            server_timestamp_ms=1700000760000,offset_seconds=0))
        client.telemetry.send_startup_pv=Mock()
        client.telemetry.send_page_exposure=Mock()
        client.policy.get_geo_fence=Mock(return_value=[self.fence()])
        client.policy.get_checkpoints_for_run=Mock(return_value=[GeoPoint.from_api_data(p) for p in official_points()])
        client.request_obs_upload_url=Mock(return_value={'error':10000,'data':{'signedUrl':'https://obs.invalid/a'}})
        client.upload_to_obs=Mock(return_value={'error':10000})
        client.submit_record=Mock(return_value={'error':-10000,'message':'mock failure'})
        messages=[]
        result=client.execute_full_run(2150,760,1,messages.append)
        self.assertFalse(result.success)
        body=client.submit_record.call_args.args[0]
        request_uuid=client.policy.get_checkpoints_for_run.call_args.kwargs['uuid_str']
        self.assertEqual(request_uuid,body['uuid'])
        self.assertEqual(json.loads(body['fivePointJson'])[0]['pointName'],'Campus 0')
        self.assertTrue(any('来源=pointsResModels' in message for message in messages))

    def test_query_only_cli_never_submits(self):
        spec=importlib.util.spec_from_file_location('checkpoint_cli',Path(__file__).with_name('cli.py'))
        cli=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        client=Mock()
        client.get_geo_fences.return_value=[self.fence()]
        client.policy.get_checkpoints_for_run.return_value=[GeoPoint.from_api_data(p) for p in official_points()]
        with patch.object(sys,'argv',['cli.py','-t','DUMMY','--uid','1','--unid','2','--checkpoints']), \
                patch.object(cli,'SportClient792',return_value=client), \
                patch('sys.stdout',new_callable=io.StringIO) as output:
            cli.main()
        self.assertIn('点数=5',output.getvalue())
        client.run.assert_not_called()
        client.running.submit_record.assert_not_called()


if __name__=='__main__':unittest.main()
