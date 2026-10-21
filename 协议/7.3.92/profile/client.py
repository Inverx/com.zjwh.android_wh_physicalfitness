# -*- coding: utf-8 -*-
import os
import sys
import time
from typing import Optional, Dict, Any, Union

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core.client import BaseNetSecClient
from .config import (
    URL_SERVER_TIME,
    URL_USER_INFO,
    URL_HOME_BASE_USER,
    URL_HOME_EXTENDED_USER
)
from .models import ServerTime, UserProfileDetails, HomeBaseUserInfo, HomeExtendedInfo


class ProfileClient(BaseNetSecClient):
    """运动世界校园 7.3.92 个人档案与时钟同步客户端"""

    def __init__(self,
                 uid: Optional[Union[int, str]] = None,
                 token: Optional[str] = None,
                 unid: Optional[Union[int, str]] = None,
                 device_config: Optional[Dict[str, Any]] = None):
        super().__init__(uid=uid, token=token, unid=unid, device_config=device_config)

    def get_server_time(self) -> ServerTime:
        """拉取服务端 GMT 时间戳并完成偏斜校准"""
        t0 = int(time.time() * 1000)
        res = self.execute_request("GET", URL_SERVER_TIME)
        if isinstance(res, dict) and res.get("error") == 10000 and "data" in res:
            try:
                value = res["data"]
                if isinstance(value, bool) or not isinstance(value, (str, int)):
                    raise ValueError("invalid server time")
                server_ms = int(value)
                if server_ms <= 0:
                    raise ValueError("invalid server time")
                return ServerTime.from_api(server_ms, t0)
            except (TypeError, ValueError, OverflowError, OSError):
                pass
        failure = ServerTime.from_api(t0, t0)
        failure.synchronized = False
        failure.error_message = "无法获取服务端时间"
        return failure

    def get_user_info(self) -> Optional[UserProfileDetails]:
        """拉取学生核心详细档案"""
        res = self.execute_request("GET", URL_USER_INFO)
        if isinstance(res, dict) and res.get("error") == 10000 and "data" in res:
            return UserProfileDetails.from_api_data(res["data"])
        return None

    def get_home_base_user_info(self, target_uid: Optional[Union[int, str]] = None) -> Optional[HomeBaseUserInfo]:
        """拉取首页头像、学号与学院基本资料"""
        uid_val = target_uid or self.uid
        if not uid_val:
            return None
        url = f"{URL_HOME_BASE_USER}?uid={uid_val}"
        res = self.execute_request("GET", url)
        if isinstance(res, dict) and res.get("error") == 10000 and "data" in res:
            return HomeBaseUserInfo.from_api_data(res["data"])
        return None

    def get_home_extended_info(self, target_uid: Optional[Union[int, str]] = None) -> Optional[HomeExtendedInfo]:
        """拉取信用分与跑步累计数据"""
        uid_val = target_uid or self.uid
        if not uid_val:
            return None
        url = f"{URL_HOME_EXTENDED_USER}?uid={uid_val}"
        res = self.execute_request("GET", url)
        if isinstance(res, dict) and res.get("error") == 10000 and "data" in res:
            return HomeExtendedInfo.from_api_data(res["data"])
        return None

    def get_home_page(self) -> dict:
        return self.execute_request('POST', 'https://run.gxapp.iydsj.com/api/v77/home/page', body_plain={})

    def get_home_config(self) -> dict:
        return self.execute_request('GET', 'https://discovery.gxapp.iydsj.com/api/v70250/home/config')

    def get_home_icon(self) -> dict:
        return self.execute_request('GET', 'https://discovery.gxapp.iydsj.com/api/v70310/home/icon')

    def get_homepage_bounce(self) -> dict:
        return self.execute_request('POST', 'https://discovery.gxapp.iydsj.com/api/v70340/homepage/bounce', body_plain={})

    def get_module(self) -> dict:
        return self.execute_request('POST', 'https://run.gxapp.iydsj.com/api/v70340/module', body_plain={})

    def warmup_dashboard_session(self) -> dict:
        return {
            'home_page': self.get_home_page(),
            'home_config': self.get_home_config(),
            'home_icon': self.get_home_icon(),
            'bounce': self.get_homepage_bounce(),
            'module': self.get_module()
        }
