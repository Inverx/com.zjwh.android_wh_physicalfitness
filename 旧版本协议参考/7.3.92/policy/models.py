# -*- coding: utf-8 -*-
import json
import math
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union


@dataclass
class FaceCheckConfig:
    """人脸抽检配置模型"""
    enable: bool = False
    check_point_min: int = 0
    check_point_max: int = 0
    check_run_valid_time: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_data(cls, data: Dict[str, Any]) -> "FaceCheckConfig":
        if not data:
            return cls()
        return cls(
            enable=bool(data.get("enable", False)),
            check_point_min=int(data.get("checkPointMin", 0)),
            check_point_max=int(data.get("checkPointMax", 0)),
            check_run_valid_time=int(data.get("checkRunValidTime", 0)),
            raw=data
        )


@dataclass
class RunRule:
    """单次与单日跑步规则模型"""
    day_goal: int
    min_distance: int
    speed_top: str
    speed_bottom: str
    step_top: Union[int, str]
    step_bottom: Union[int, str]
    valid_times: List[str]
    face_check: FaceCheckConfig
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_data(cls, data: Dict[str, Any]) -> "RunRule":
        rule = data.get("runRuleModel", {}) or {}
        face = data.get("runFaceCheckConfigDTO", {}) or {}
        
        v_times = []
        for vt in rule.get("validTime", []):
            st = vt.get("start", "")
            et = vt.get("end", "")
            if st and et:
                v_times.append(f"{st}~{et}")

        s_top = rule.get("stepTop", "-")
        s_bot = rule.get("stepBottom", "-")
        step_top_text = "不限" if s_top in (0, "0") else s_top
        step_bot_text = "不限" if s_bot in (0, "0") else s_bot

        return cls(
            day_goal=int(rule.get("dayGoal", 0)),
            min_distance=int(rule.get("minDistance", 0)),
            speed_top=str(rule.get("speedTop", "-")),
            speed_bottom=str(rule.get("speedBottom", "-")),
            step_top=step_top_text,
            step_bottom=step_bot_text,
            valid_times=v_times,
            face_check=FaceCheckConfig.from_api_data(face),
            raw=data
        )


@dataclass
class GeoPoint:
    """经纬度坐标点"""
    lat: float
    lng: float
    point_id: Optional[int] = None
    name: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_data(cls, data):
        if not isinstance(data, dict):
            raise ValueError("point must be an object")
        lat, lon = data.get("lat"), data.get("lng", data.get("lon"))
        if isinstance(lat, bool) or isinstance(lon, bool):
            raise ValueError("point coordinates must be numbers")
        lat, lon = float(lat), float(lon)
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("point coordinates are out of range")
        return cls(lat=lat, lng=lon, point_id=data.get("id"),
                   name=data.get("pointName", data.get("name")), raw=dict(data))

    def gcj_coordinates(self):
        lat = self.raw.get("glat", self.raw.get("gLat"))
        lon = self.raw.get("glon", self.raw.get("glng", self.raw.get("gLng")))
        if lat is None or lon is None or lat == -1 or lon == -1:
            raise ValueError("围栏未返回 GCJ 坐标，无法构造官方点位请求")
        point = GeoPoint.from_api_data({"lat": lat, "lon": lon})
        return point.lat, point.lng

    def as_checkpoint(self):
        values = dict(self.raw)
        values.update({"lat": self.lat, "lng": self.lng, "name": self.name})
        return values


@dataclass
class GeoFenceArea:
    """学校电子围栏与必经打卡点模型"""
    fence_id: int
    fence_name: str
    polygon_points: List[GeoPoint]
    check_points: List[GeoPoint]
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_data(cls, data: Dict[str, Any]) -> "GeoFenceArea":
        def parse(field_name):
            values = data.get(field_name) or []
            if isinstance(values, str):
                values = json.loads(values)
            if not isinstance(values, list):
                raise ValueError(f"{field_name} must be a list")
            return [GeoPoint.from_api_data(point) for point in values]

        poly = parse("points")
        # Legacy compatibility only: live checkpoints come from pointsResModels.
        checks = parse("passPoints")

        return cls(
            fence_id=int(data.get("id", 0)),
            fence_name=str(data.get("name", "未命名围栏")),
            polygon_points=poly,
            check_points=checks,
            raw=data
        )


@dataclass
class SemesterInfo:
    """学期跑步进度模型"""
    semester_name: str
    total_completed_distance: float
    valid_count: int
    target_distance: float
    remaining_distance: float
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_data(cls, data: Dict[str, Any]) -> "SemesterInfo":
        tot = float(data.get("totalDistance", 0.0))
        tar = float(data.get("targetDistance", 0.0) or data.get("goalDistance", 0.0))
        rem = max(0.0, tar - tot)
        return cls(
            semester_name=str(data.get("semesterName", "")),
            total_completed_distance=tot,
            valid_count=int(data.get("validCount", 0)),
            target_distance=tar,
            remaining_distance=rem,
            raw=data
        )
