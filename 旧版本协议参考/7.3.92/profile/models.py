# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import datetime
import time


@dataclass
class ServerTime:
    """服务器时间校准模型"""
    server_timestamp_ms: int
    local_timestamp_ms: int
    offset_seconds: float
    server_datetime: str

    @classmethod
    def from_api(cls, server_ms: int, local_ms: Optional[int] = None) -> "ServerTime":
        if local_ms is None:
            local_ms = int(time.time() * 1000)
        offset = (server_ms - local_ms) / 1000.0
        dt = datetime.datetime.fromtimestamp(server_ms / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
        return cls(
            server_timestamp_ms=server_ms,
            local_timestamp_ms=local_ms,
            offset_seconds=offset,
            server_datetime=dt
        )


@dataclass
class UserProfileDetails:
    """用户全量档案模型 (/api/v70390/user/info)"""
    uid: int
    unid: int
    name: str
    username: str
    student_id: str
    campus_name: str
    campus_id: str
    depart: str
    grade_class: str
    major: str
    sex: str
    phone: str
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_data(cls, data: Dict[str, Any]) -> "UserProfileDetails":
        sex_map = {1: "男", 2: "女"}
        return cls(
            uid=data.get("uid", -1),
            unid=data.get("unid", -1),
            name=data.get("name", ""),
            username=data.get("username", ""),
            student_id=data.get("studentId", "") or data.get("studentNo", ""),
            campus_name=data.get("campusName", "") or data.get("universityName", ""),
            campus_id=str(data.get("campusId", "")),
            depart=data.get("depart", "") or data.get("department", ""),
            grade_class=data.get("gradeClass", "") or data.get("className", ""),
            major=data.get("major", ""),
            sex=sex_map.get(data.get("sex"), "未知"),
            phone=data.get("phone", "") or data.get("mobile", ""),
            raw=data
        )


@dataclass
class HomeBaseUserInfo:
    """首页基础用户信息 (/api/v76/user/homePageBaseUserInfo)"""
    uid: int
    name: str
    avatar_url: str
    student_no: str
    department_name: str
    university_name: str
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_data(cls, data: Dict[str, Any]) -> "HomeBaseUserInfo":
        return cls(
            uid=data.get("uid", -1),
            name=data.get("name", ""),
            avatar_url=data.get("avatar", "") or data.get("icon", ""),
            student_no=data.get("studentNo", "") or data.get("studentId", ""),
            department_name=data.get("departmentName", "") or data.get("depart", ""),
            university_name=data.get("universityName", "") or data.get("campusName", ""),
            raw=data
        )


@dataclass
class HomeExtendedInfo:
    """首页扩展用户信息 (/api/v70370/user/homePageExtendedInfo)"""
    uid: int
    credit_score: int
    run_count: int
    total_distance: float
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_data(cls, data: Dict[str, Any]) -> "HomeExtendedInfo":
        return cls(
            uid=data.get("uid", -1),
            credit_score=data.get("creditScore", 0) or data.get("score", 0),
            run_count=data.get("runCount", 0) or data.get("count", 0),
            total_distance=float(data.get("totalDistance", 0.0)),
            raw=data
        )
