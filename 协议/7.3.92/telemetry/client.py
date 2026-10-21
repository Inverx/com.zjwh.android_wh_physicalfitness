# -*- coding: utf-8 -*-
import json
import ssl
import time
import urllib.request
from typing import Optional, Dict, Any, List, Union

from core.security import open_https
from core.config import DEFAULT_DEVICE_CONFIG, load_customer_device
from .config import (
    URL_STARTUP_PV,
    URL_DATA_COLLECTION_PV,
    URL_AD_PV,
    URL_DEVICE_VERIFY,
    URL_CONTROL_MESSAGE,
    URL_BARRIER_FREE,
    URL_CHEAT_LIST,
    URL_RANK_LIST,
    URL_CREDIT_POPUP
)


class TelemetryClient:
    """运动世界校园 7.3.92 客户端行为特征、反作弊规则同步与数据埋点客户端"""

    def __init__(self, device_config: Optional[Dict[str, Any]] = None):
        self.device = load_customer_device()
        if device_config:
            self.device.update(device_config)
        self.ssl_ctx = ssl.create_default_context()

    def _post_json(self, url: str, payload: dict, custom_headers: Optional[dict] = None) -> dict:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "okhttp/4.12.0",
        }
        if custom_headers:
            headers.update(custom_headers)
        data_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        try:
            with open_https(req, context=self.ssl_ctx, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": -1, "message": str(e)}

    def send_startup_pv(self, uid: int, unid: int, gender: int = 0) -> dict:
        """冷启动初始化埋点 (对齐 7.3.92 抓包格式)"""
        body = {
            "uid": int(uid),
            "unid": int(unid),
            "appVersion": self.device.get("appVersion", "7.3.92"),
            "gender": int(gender),
            "caid": 2023,
            "osType": 0,
            "deviceId": self.device.get("DeviceId", "")
        }
        return self._post_json(URL_STARTUP_PV, body)

    def send_page_exposure(self, unid: int, items: Optional[List[str]] = None) -> dict:
        """页面曝光行为打点 (My_page_exposure 等)"""
        now_ms = int(time.time() * 1000)
        target_items = items or ["My_page_exposure", "Exposure_of_sports_page_banner/2064"]
        events = [{"createTime": now_ms, "itemId": it, "module": 10018} for it in target_items]
        body = {
            "androidId": "",
            "androidMac": "",
            "data": events,
            "sn": "",
            "unid": int(unid)
        }
        return self._post_json(URL_DATA_COLLECTION_PV, body)

    def send_device_verify(self, uid: int, unid: int) -> dict:
        """极验设备验证特征打点 (/api/v620/datacollection/geetest/deviceVerify)"""
        body = {
            "uid": int(uid),
            "unid": int(unid),
            "deviceId": self.device.get("DeviceId", "")
        }
        return self._post_json(URL_DEVICE_VERIFY, body)

    def check_control_message(self) -> dict:
        """心跳与控制信令检查 (control.gxapp.iydsj.com/getMessage)"""
        req = urllib.request.Request(URL_CONTROL_MESSAGE, headers={"User-Agent": "okhttp/4.12.0"}, method="GET")
        try:
            with open_https(req, context=self.ssl_ctx, timeout=5) as resp:
                return {"status": resp.status, "body": resp.read().decode("utf-8", errors="ignore")}
        except Exception as e:
            return {"error": -1, "message": str(e)}

    def get_barrier_free_policy(self, netsec_client) -> dict:
        """拉取服务端无障碍服务检测与反辅助策略 (/api/v1/barrierFree/getBarrierFree)"""
        return netsec_client.execute_request("GET", URL_BARRIER_FREE)

    def get_cheat_blacklist(self, netsec_client) -> dict:
        """拉取客户端黑名单应用与作弊工具包名特征库 (/api/v78/cheat/cheatlist)"""
        return netsec_client.execute_request("POST", URL_CHEAT_LIST, body_plain={})

    def get_rank_list(self, netsec_client, rank_type: int = 1) -> dict:
        """跑后排行榜查询 (/api/v41/rank)"""
        return netsec_client.execute_request("POST", URL_RANK_LIST, body_plain={"type": int(rank_type)})

    def get_credit_popup(self, netsec_client) -> dict:
        """信用分弹窗与风险审查 (/api/creditscore/v70390/popup)"""
        return netsec_client.execute_request("GET", URL_CREDIT_POPUP)
