# -*- coding: utf-8 -*-
import os
import json
import sys
from typing import Optional, Dict, Any, Union, List

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core.client import BaseNetSecClient
from profile.config import URL_USER_INFO
from security_utils import redact_text
from .config import (
    URL_RUN_POLICY,
    URL_INDOOR_POLICY,
    URL_GEO_FENCE,
    URL_SEMESTER_INFO,
    URL_SEMESTER_SUMMARY,
    URL_RUN_GOALS
)
from .models import RunRule, GeoFenceArea, SemesterInfo


class PolicyClient(BaseNetSecClient):
    """运动世界校园 7.3.92 跑步规则与地理围栏客户端"""

    def __init__(self,
                 uid: Optional[Union[int, str]] = None,
                 token: Optional[str] = None,
                 unid: Optional[Union[int, str]] = None,
                 device_config: Optional[Dict[str, Any]] = None):
        super().__init__(uid=uid, token=token, unid=unid, device_config=device_config)
        self.last_policy_error: Optional[str] = None
        self.last_geo_fence_error: Optional[str] = None

    def get_run_policy(self, run_mode: int = 1, unid: Optional[Union[int, str]] = None) -> Optional[RunRule]:
        """获取指定运动模式的跑步规则（配速、步频、单次/单日里程、有效时段等）"""
        self.last_policy_error = None
        url = URL_INDOOR_POLICY if run_mode == 5 else URL_RUN_POLICY
        try:
            unid_val = int(unid if unid is not None else self.unid or 0)
        except (TypeError, ValueError):
            self.last_policy_error = "学校 UNID 必须是正整数"
            return None
        if unid_val <= 0:
            profile = self.execute_request("GET", URL_USER_INFO)
            details = profile.get("data") if isinstance(profile, dict) else None
            try:
                if not isinstance(profile, dict) or profile.get("error") != 10000 or not isinstance(details, dict):
                    raise ValueError("profile unavailable")
                if int(details.get("uid", -1)) != int(self.uid):
                    raise ValueError("profile UID mismatch")
                unid_val = int(details.get("unid", 0))
                if unid_val <= 0:
                    raise ValueError("school missing")
            except (TypeError, ValueError):
                code = profile.get("error", -1) if isinstance(profile, dict) else -1
                self.last_policy_error = f"未取得账号学校 UNID（资料接口 code={code}），请传入登录返回的 --unid"
                return None
        self.unid = str(unid_val)
        body = {
            "runMode": run_mode,
            "ruleUpdateTime": 0,
            "geoFenceUpdateTime": 0,
            "selectUnid": unid_val,
            "operateType": 0
        }
        res = self.execute_request("POST", url, body_plain=body)
        if not isinstance(res, dict) or res.get("error") != 10000:
            code = res.get("error", -1) if isinstance(res, dict) else -1
            message = redact_text(res.get("message", "接口未提供错误说明")) if isinstance(res, dict) else "响应不是 JSON 对象"
            self.last_policy_error = f"规则接口 code={code} selectUnid={unid_val}: {message}"
            return None
        data = res.get("data")
        try:
            if isinstance(data, str):
                data = json.loads(data)
            if not isinstance(data, dict) or not isinstance(data.get("runRuleModel"), dict) or not data["runRuleModel"]:
                self.last_policy_error = f"规则接口 code=10000 selectUnid={unid_val}，但未返回 runRuleModel"
                return None
            return RunRule.from_api_data(data)
        except (TypeError, ValueError, KeyError, AttributeError):
            self.last_policy_error = f"规则接口 code=10000 selectUnid={unid_val}，规则数据格式无法解析"
            return None


    def get_geo_fence(self, update_time: int = 0) -> List[GeoFenceArea]:
        """拉取学校电子围栏边界多边形与随机打卡点集"""
        self.last_geo_fence_error = None
        res = self.execute_request("POST", URL_GEO_FENCE,
                                   body_plain={"geoFenceUpdateTime": update_time})
        if not isinstance(res, dict) or res.get("error") != 10000:
            code = res.get("error", -1) if isinstance(res, dict) else -1
            message = redact_text(res.get("message", "接口未提供错误说明")) if isinstance(res, dict) else "响应不是 JSON 对象"
            self.last_geo_fence_error = f"围栏接口 code={code}: {message}"
            return []
        try:
            data = res.get("data")
            if isinstance(data, str):
                data = json.loads(data)
            if not isinstance(data, dict) or not isinstance(data.get("geoFences"), list):
                self.last_geo_fence_error = "围栏接口 code=10000，但未返回 geoFences 数组"
                return []
            if not data["geoFences"]:
                self.last_geo_fence_error = "围栏接口 code=10000，返回的 geoFences 为空"
                return []
            fences = [GeoFenceArea.from_api_data(item) for item in data["geoFences"]]
            if not any(f.polygon_points for f in fences):
                self.last_geo_fence_error = "围栏接口返回了围栏，但没有有效边界点"
            return fences
        except (TypeError, ValueError, KeyError, AttributeError):
            self.last_geo_fence_error = "围栏数据格式无法解析；未丢弃错误点后继续提交"
            return []


    def get_semester_info(self, run_mode: int = 1) -> Optional[SemesterInfo]:
        """查询学生本学期已完成公里数与剩余目标"""
        body = {
            "runMode": run_mode
        }
        res = self.execute_request("POST", URL_SEMESTER_INFO, body_plain=body)
        if isinstance(res, dict) and res.get("error") == 10000 and "data" in res and res["data"]:
            return SemesterInfo.from_api_data(res["data"])
        return None

    def get_semester_summary(self, sid: int = 0) -> Dict[str, Any]:
        """查询学期总体结算汇总"""
        return self.execute_request("POST", URL_SEMESTER_SUMMARY, body_plain={"sid": sid})

    def get_run_goals(self) -> Dict[str, Any]:
        """查询本学期考核指标与目标"""
        return self.execute_request("POST", URL_RUN_GOALS, body_plain={})


    def get_distance_route_points(self, sport_type: int = 1, distance_m: int = 1000) -> dict:
        url = f"https://run.gxapp.iydsj.com/api/v560/get/{sport_type}/distance/{distance_m}"
        return self.execute_request("POST", url, body_plain={})

