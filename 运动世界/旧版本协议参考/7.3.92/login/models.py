# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class GeetestResult:
    """极验 v4 求解结果模型"""
    captcha_id: str
    lot_number: str
    pass_token: str
    gen_time: str
    captcha_output: str

    def to_validate_payload(self, session_uuid: str, username: str) -> Dict[str, Any]:
        """生成发送至 /api/v70270/security/geevalidate 的载荷"""
        return {
            "lotNumber": self.lot_number,
            "captchaOutput": self.captcha_output,
            "passToken": self.pass_token,
            "genTime": self.gen_time,
            "isOffline": False,
            "osType": 0,
            "businessType": 0,
            "uuid": session_uuid,
            "username": username
        }


@dataclass
class UserProfile:
    """登录成功后的学生基础资料与核心 Token"""
    uid: int
    unid: int
    name: str
    username: str
    campus_name: str
    campus_id: str
    depart: str
    grade_class: str
    sex: str
    token: str
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_data(cls, data: Dict[str, Any]) -> "UserProfile":
        sex_map = {1: "男", 2: "女"}
        return cls(
            uid=data.get("uid", -1),
            unid=data.get("unid", -1),
            name=data.get("name", ""),
            username=data.get("username", ""),
            campus_name=data.get("campusName", ""),
            campus_id=data.get("campusId", ""),
            depart=data.get("depart", ""),
            grade_class=data.get("gradeClass", ""),
            sex=sex_map.get(data.get("sex"), "未知"),
            token=data.get("token", ""),
            raw=data
        )


@dataclass
class LoginResult:
    """登录结果包装对象"""
    success: bool
    error_code: int
    message: str
    user: Optional[UserProfile] = None
    raw: Optional[Dict[str, Any]] = None

