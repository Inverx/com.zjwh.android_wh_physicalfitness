# -*- coding: utf-8 -*-
import os
import sys
import json
import uuid
import hashlib
from typing import Optional, Dict, Any, Union, List

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core.client import BaseNetSecClient
from .config import (
    URL_RUN_POLICY,
    URL_INDOOR_POLICY,
    URL_GEO_FENCE,
    URL_SEMESTER_INFO,
    URL_SEMESTER_SUMMARY,
    URL_RUN_GOALS
)
from .models import RunRule, GeoFenceArea, GeoPoint, SemesterInfo
from core.config import HOST_RUN


class PolicyClient(BaseNetSecClient):
    """运动世界校园 7.3.92 跑步规则与地理围栏客户端"""

    def __init__(self,
                 uid: Optional[Union[int, str]] = None,
                 token: Optional[str] = None,
                 unid: Optional[Union[int, str]] = None,
                 device_config: Optional[Dict[str, Any]] = None):
        super().__init__(uid=uid, token=token, unid=unid, device_config=device_config)
        self.last_checkpoint_error: Optional[str] = None
        self.last_checkpoint_start_time: Optional[int] = None

    def get_run_policy(self, run_mode: int = 1, unid: Optional[Union[int, str]] = None) -> Optional[RunRule]:
        """获取指定运动模式的跑步规则（配速、步频、单次/单日里程、有效时段等）"""
        url = URL_INDOOR_POLICY if run_mode == 5 else URL_RUN_POLICY
        unid_val = int(unid or self.unid or 0)
        body = {
            "runMode": run_mode,
            "ruleUpdateTime": 0,
            "geoFenceUpdateTime": 0,
            "selectUnid": unid_val,
            "operateType": 0
        }
        res = self.execute_request("POST", url, body_plain=body)
        if isinstance(res, dict) and res.get("error") == 10000 and "data" in res and res["data"]:
            return RunRule.from_api_data(res["data"])
        return None

    def get_geo_fence(self, update_time: int = 0) -> List[GeoFenceArea]:
        """拉取学校围栏边界；实时点位由 get_run_checkpoints 单独获取。"""
        body = {
            "geoFenceUpdateTime": update_time
        }
        res = self.execute_request("POST", URL_GEO_FENCE, body_plain=body)
        fences = []
        if isinstance(res, dict) and res.get("error") == 10000 and "data" in res and res["data"]:
            d = res["data"]
            raw_list = d.get("geoFences", []) or []
            for item in raw_list:
                fences.append(GeoFenceArea.from_api_data(item))
        return fences

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


    def get_distance_route_points(self, sport_type: int = 1, distance_m: int = 1000,
                                  latitude: Optional[float] = None,
                                  longitude: Optional[float] = None,
                                  run_area_id: int = -1,
                                  uuid_str: Optional[str] = None,
                                  runec: str = "") -> dict:
        """Query point issuance with a GCJ anchor, not fence boundary points.

        Android requestFivePoint fixes the path key to 1. Source:
        Coaixy/android_wh_physicalfitness_analyse @ 91dc299a, classes
        CommonApiManager$requestFivePoint$1 and Utils.atlasSign.
        """
        if sport_type != 1:
            raise ValueError("点位查询仅支持计分跑，路径 key 固定为 1")
        if isinstance(distance_m, bool) or not isinstance(distance_m, int) or distance_m <= 0:
            raise ValueError("点位查询距离必须是正整数")
        anchor = GeoPoint.from_api_data({"lat": latitude, "lon": longitude})
        if not self.uid or not self.token or int(self.unid or 0) <= 0:
            raise ValueError("点位查询需要有效 UID、Token 和学校 UNID")
        if isinstance(run_area_id, bool) or not isinstance(run_area_id, int) or run_area_id < -1:
            raise ValueError("runAreaId 必须为 -1 或非负整数")
        if not isinstance(runec, str):
            raise ValueError("runec must be a string")
        url = f"{HOST_RUN}/api/v560/get/1/distance/{distance_m}"
        salt = "2slhe02lsfiwowlcixisla_sls-_slaor"
        sign = hashlib.md5((url.replace("https://", "http://", 1)+salt).encode("utf-8")).hexdigest()
        body = {"longitude": anchor.lng, "latitude": anchor.lat,
                "selectedUnid": int(self.unid), "uuid": uuid_str or str(uuid.uuid4()),
                "runec": runec, "runAreaId": run_area_id, "sign": sign}
        return self.execute_request("POST", url, body_plain=body)

    def get_checkpoints_for_run(self, fence: GeoFenceArea,
                                uuid_str: Optional[str] = None) -> List[GeoPoint]:
        """Use the school minimum distance and selected area, as RunStartViewModel does."""
        self.last_checkpoint_error = None
        self.last_checkpoint_start_time = None
        try:
            rule = self.get_run_policy(run_mode=1)
            if rule is None or rule.min_distance <= 0:
                raise ValueError("未取得有效学校规则，无法确认点位查询距离")
            area_id = -1
            areas = rule.raw.get("runAreaModels")
            if areas:
                valid = [area for area in areas if area.get("valid")]
                selected = [area for area in valid if area.get("select")]
                if len(selected) == 1:
                    area = selected[0]
                elif len(valid) == 1:
                    area = valid[0]
                else:
                    raise ValueError("学校有多个跑步区域，尚未明确选择区域")
                if fence.fence_id not in area.get("fenceIds", []):
                    raise ValueError("当前围栏不属于选定跑步区域")
                area_id = int(area["id"])
            if not fence.polygon_points:
                raise ValueError("围栏没有有效锚点")
            latitude, longitude = fence.polygon_points[0].gcj_coordinates()
            return self.get_run_checkpoints(
                rule.min_distance, latitude, longitude, area_id, uuid_str)
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            self.last_checkpoint_error = f"五点查询未完成: {exc}"
            return []

    def get_run_checkpoints(self, distance_m: int, latitude: float, longitude: float,
                            run_area_id: int = -1, uuid_str: Optional[str] = None,
                            runec: str = "") -> List[GeoPoint]:
        self.last_checkpoint_error = None
        self.last_checkpoint_start_time = None
        try:
            result = self.get_distance_route_points(
                distance_m=distance_m, latitude=latitude, longitude=longitude,
                run_area_id=run_area_id, uuid_str=uuid_str, runec=runec)
            if not isinstance(result, dict) or result.get("error") != 10000:
                code = result.get("error", -1) if isinstance(result, dict) else -1
                message = result.get("message", "无错误说明") if isinstance(result, dict) else "响应不是对象"
                self.last_checkpoint_error = f"五点接口 code={code}: {message}"
                return []
            data = result.get("data", result)
            if isinstance(data, str):
                data = json.loads(data)
            if not isinstance(data, dict) or not isinstance(data.get("pointsResModels"), list):
                raise ValueError("五点响应缺少 pointsResModels 数组")
            values = data["pointsResModels"]
            if not values:
                raise ValueError("五点接口返回的 pointsResModels 为空")
            points = [GeoPoint.from_api_data(point) for point in values]
            self.last_checkpoint_start_time = data.get("sportStartTime")
            return points
        except (TypeError, ValueError, KeyError) as exc:
            self.last_checkpoint_error = f"五点请求或响应无法解析: {exc}"
            return []

