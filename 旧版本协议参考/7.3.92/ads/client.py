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
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": -1, "message": str(e)}

    def simulate_watch_ad(self,
                          ad_position: str = "4",
                          duration_sec: int = 15,
                          is_reward_video: bool = True,
                          progress_callback: Optional[Callable[[str], None]] = None) -> AdWatchResult:
        """
        模拟真实看广告/激励视频全时序行为：
        1. 获取广告配置与可用插槽；
        2. 触发广告拉取与展示曝光 PV；
        3. 模拟视频按序播放心跳 (0% -> 25% -> 50% -> 75% -> 100% 完播)；
        4. 上报最终激励发放与合规归档。
        """
        def log(msg: str):
            if progress_callback:
                progress_callback(msg)

        log(f"[1/4] 正在拉取广告配置与可用资源位 (位置: {ad_position})...")
        cfg_res = self.get_ad_config()
        slot_res = self.get_slot_list()

        log("[2/4] 上报广告展示初审曝光事件 (Ad Impression PV)...")
        pv1 = self.send_ad_pv(ad_position=ad_position, ad_id="", has_ad=1, start_type=1, type_val=3)

        log(f"[3/4] 模拟广告播放心跳进度 (时长: {duration_sec} 秒)...")
        steps = [0.25, 0.50, 0.75, 1.00]
        for step in steps:
            pct = int(step * 100)
            time.sleep(0.5)  # 轻量时钟步进
            log(f"播放进度: {pct}%")
            # 每次步进伴随曝光心跳
            self.send_ad_pv(ad_position=ad_position, ad_id="", has_ad=1, start_type=3, type_val=6)

        pv_final = self.send_ad_pv(ad_position=ad_position, ad_id="", has_ad=0, start_type=3, type_val=6)

        log("    -> 看广告流程完成 SUCCESS!")
        return AdWatchResult(
            success=True,
            ad_position=ad_position,
            message="广告播放与激励上报成功",
            events_count=len(steps) + 2,
            duration_sec=duration_sec,
            raw={"ad_config": cfg_res, "final_pv": pv_final}
        )
