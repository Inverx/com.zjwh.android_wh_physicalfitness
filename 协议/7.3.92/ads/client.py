# -*- coding: utf-8 -*-
import json
import os
import sys
import time
import urllib.request
from typing import Optional, Dict, Any, Union, Callable

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core.security import open_https
from core.client import BaseNetSecClient
from .config import (
    URL_AD_CONFIG,
    URL_SLOT_LIST,
    URL_AD_PV,
    URL_ADSC,
    URL_BATCH_UPLOAD
)
from .models import AdWatchResult


class AdClient(BaseNetSecClient):
    """运动世界校园 7.3.92 广告系统与激励视频客户端"""

    def __init__(self,
                 uid: Optional[Union[int, str]] = None,
                 token: Optional[str] = None,
                 unid: Optional[Union[int, str]] = None,
                 device_config: Optional[Dict[str, Any]] = None):
        super().__init__(uid=uid, token=token, unid=unid, device_config=device_config)

    def get_ad_config(self) -> dict:
        """拉取广告位全局配置 (/api/v70360/ad/config)"""
        return self.execute_request("GET", URL_AD_CONFIG)

    def get_slot_list(self) -> dict:
        """拉取广告位插槽列表 (/api/v70340/resource/slot/list)"""
        return self.execute_request("POST", URL_SLOT_LIST, body_plain={})

    def send_ad_pv(self,
                   ad_position: str = "2",
                   ad_id: str = "",
                   has_ad: int = 1,
                   start_type: int = 3,
                   type_val: int = -1) -> dict:
        """向官方数据中心上报广告曝光 PV (/api/v70260/datacollection/ad/pv)"""
        now_ms = int(time.time() * 1000)
        body = {
            "adId": str(ad_id),
            "adPosition": str(ad_position),
            "barrierState": "0",
            "createdTime": now_ms,
            "crowdId": 0,
            "hasAd": int(has_ad),
            "matchSourceType": 2,
            "platformType": 0,
            "startType": int(start_type),
            "strategyId": 0,
            "type": int(type_val),
            "unid": int(self.unid or 0)
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "okhttp/4.12.0",
        }
        data_bytes = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(URL_AD_PV, data=data_bytes, headers=headers, method="POST")
        try:
            with open_https(req, context=self.ssl_ctx, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": -1, "message": str(e)}

    def simulate_watch_ad(self,
                          ad_position: str = "4",
                          duration_sec: int = 15,
                          is_reward_video: bool = True,
                          progress_callback: Optional[Callable[[str], None]] = None) -> AdWatchResult:
        """Return an explicit unsupported result until playback can be verified."""
        if ad_position not in ("1", "2", "4") or not isinstance(duration_sec, int) or duration_sec <= 0:
            message = "广告位置或时长无效"
        else:
            message = "尚未实现真实广告播放和奖励到账验证，已停止模拟上报"
        if progress_callback:
            progress_callback(message)
        return AdWatchResult(success=False, ad_position=ad_position,
                             message=message, events_count=0, duration_sec=0)
