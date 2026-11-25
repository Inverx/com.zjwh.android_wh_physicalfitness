"""Offline regressions for current and legacy history response formats."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from history.models import parse_history_records, history_record_status

class HistoryCliTests(unittest.TestCase):
    def test_list_and_legacy_envelope(self):
        rows=[{'rrid':1,'totalDis':2150,'totalTime':760,'status':1,'complete':True}]
        for data in (rows,{'recordList':rows},json.dumps(rows),json.dumps({'recordList':rows})):
            self.assertEqual(parse_history_records(data),rows)
        for data in (None,[],{'recordList':None},{'recordList':[]}):
            self.assertEqual(parse_history_records(data),[])

    def test_malformed_response_is_not_silently_empty(self):
        for data in ({},1,{'recordList':{}},['invalid'],'{broken'):
            with self.assertRaises(ValueError):parse_history_records(data)

    def test_normal_status_does_not_override_incomplete_flag(self):
        self.assertEqual(history_record_status({'status':1,'complete':False}),'未达标')
        self.assertEqual(history_record_status({'status':1,'complete':True}),'达标')
        self.assertNotEqual(history_record_status({'status':1}),'达标')

    def test_history_cli_formats_rows_and_handles_bad_payload(self):
        spec=importlib.util.spec_from_file_location('history_test_cli',Path(__file__).with_name('cli.py'))
        cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
        for data in ([{'rrid':1,'totalDis':2150,'totalTime':760,'status':1,'complete':True}],
                     {'recordList':[]},['invalid']):
            client=Mock();client.token='DUMMY';client.uid=1
            client.get_history_records.return_value={'error':10000,'data':data}
            with patch.object(cli,'SportClient792',return_value=client), \
                 patch.object(sys,'argv',['cli.py','-t','DUMMY','--uid','1','--history']), \
                 patch('sys.stdout',new_callable=io.StringIO) as output:
                cli.main()
            text=output.getvalue()
            if data==['invalid']:self.assertIn('响应解析失败',text)
            else:self.assertIn('历史记录: 条数=',text)
            client.execute_run.assert_not_called()

if __name__=='__main__':unittest.main()
