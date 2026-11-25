# -*- coding: utf-8 -*-
import datetime
import os
import sys
from typing import Optional, Dict, Any, Union, List

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core.client import BaseNetSecClient
from .config import (
    URL_GET_ONE_RECORD,
    URL_RUN_RECORDS,
    URL_INDOOR_RECORDS,
    URL_CALENDAR_LIST,
    URL_RUN_DATA_INDEX,
    URL_HISTORY_CONFIG
)
from .models import RunRecordDetail


class HistoryClient(BaseNetSecClient):
    """运动世界校园 7.3.92 历史成绩与回查客户端"""

    def __init__(self,
                 uid: Optional[Union[int, str]] = None,
                 token: Optional[str] = None,
                 unid: Optional[Union[int, str]] = None,
                 device_config: Optional[Dict[str, Any]] = None):
        super().__init__(uid=uid, token=token, unid=unid, device_config=device_config)

    def get_one_record(self, rrid: int) -> Optional[RunRecordDetail]:
        """单次运动结算详情回查 (/api/v70320/runnings/get_one_record)"""
        body = {"rrid": int(rrid)}
        res = self.execute_request("POST", URL_GET_ONE_RECORD, body_plain=body)
        if isinstance(res, dict) and res.get("error") == 10000 and "data" in res and res["data"]:
            return RunRecordDetail.from_api_data(res["data"])
        return None

    def get_run_records(self, page_num: int = 1, page_size: int = 20, sid: int = 0, sport_type: int = 1) -> dict:
        """分页查询跑步历史列表 (/api/v70230/runnings/records)"""
        body = {
            "pageNum": int(page_num),
            "pageSize": int(page_size),
            "sid": int(sid),
            "type": int(sport_type)
        }
        return self.execute_request("POST", URL_RUN_RECORDS, body_plain=body)

    def get_indoor_records(self, page_num: int = 1, page_size: int = 20, sid: int = 0) -> dict:
        """分页查询室内运动记录 (/api/v74/runnings/indoor/findForPage)"""
        body = {
            "pageNum": int(page_num),
            "pageSize": int(page_size),
            "sid": int(sid)
        }
        return self.execute_request("POST", URL_INDOOR_RECORDS, body_plain=body)

    def get_calendar_list(self, year: Optional[int] = None, month: Optional[int] = None) -> dict:
        """打卡日历列表查询 (/api/v70100/run/calendar/list)"""
        now = datetime.datetime.now()
        y = year or now.year
        m = month or now.month
        body = {"year": int(y), "month": int(m)}
        return self.execute_request("POST", URL_CALENDAR_LIST, body_plain=body)

    def get_history_config(self) -> dict:
        """历史记录配置项查询 (/api/v70100/run/getHistoryConfig)"""
        return self.execute_request("GET", URL_HISTORY_CONFIG)

    def get_data_index(self, sport_type: int = 1) -> dict:
        """数据索引看板查询 (/api/v70100/run/data/index)"""
        return self.execute_request("GET", f"{URL_RUN_DATA_INDEX}?type={sport_type}")
