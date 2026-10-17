# -*- coding: utf-8 -*-
import json
import os
import sys
import time
import urllib.request
import random
from typing import Optional, Dict, Any, Union, List, Callable

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core.client import BaseNetSecClient
from profile.client import ProfileClient
from policy.client import PolicyClient
from history.client import HistoryClient
from telemetry.client import TelemetryClient
from .config import (
    URL_OBS_TEMPORARY_URL,
    URL_SAVE_RECORD,
    URL_RUN_DETAIL_CONFIG,
    OBS_BUCKET_NAME
)
from .models import RunningSubmissionResult
from .builder import RunningTrackBuilder


class RunningClient(BaseNetSecClient):
    """运动世界校园 7.3.92 跑步提交与 OBS 上传客户端"""

    def __init__(self,
                 uid: Optional[Union[int, str]] = None,
                 token: Optional[str] = None,
                 unid: Optional[Union[int, str]] = None,
                 device_config: Optional[Dict[str, Any]] = None):
        super().__init__(uid=uid, token=token, unid=unid, device_config=device_config)
        self.telemetry = TelemetryClient(device_config=self.device_config)
        self.profile = ProfileClient(uid=uid, token=token, unid=unid, device_config=self.device_config)
        self.policy = PolicyClient(uid=uid, token=token, unid=unid, device_config=self.device_config)
        self.history = HistoryClient(uid=uid, token=token, unid=unid, device_config=self.device_config)

    def set_credentials(self, uid: Optional[Union[int, str]], token: Optional[str], unid: Optional[Union[int, str]] = None):
        super().set_credentials(uid, token, unid)
        self.profile.set_credentials(uid, token, unid)
        self.policy.set_credentials(uid, token, unid)
        self.history.set_credentials(uid, token, unid)

    def request_obs_upload_url(self, object_key: str) -> dict:
        """向网关申请华为云 OBS 预签名上传地址 (/api/obs/temporary/url)"""
        body = {
            "bucketName": OBS_BUCKET_NAME,
            "objectKey": object_key,
            "method": "Put",
            "contentType": "text/plain"
        }
        res = self.execute_request("POST", URL_OBS_TEMPORARY_URL, body_plain=body)
        if isinstance(res, dict) and res.get("error") == 10000 and "data" in res:
            data = res["data"]
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    pass
            return {"error": 10000, "data": data}
        return res if isinstance(res, dict) else {"error": -1, "message": str(res)}

    def upload_to_obs(self, signed_url: str, signed_headers: dict, payload: dict) -> dict:
        """直接以 PUT 请求向华为云 OBS 存储桶异步推送轨迹与步频载荷"""
        data_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers = dict(signed_headers or {"Content-Type": "text/plain"})
        req = urllib.request.Request(signed_url, data=data_bytes, headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=30) as resp:
                if 200 <= resp.status < 300:
                    return {"error": 10000, "message": "OBS 上传成功"}
                return {"error": resp.status, "message": f"OBS HTTP {resp.status}"}
        except urllib.error.HTTPError as e:
            return {"error": e.code, "message": f"OBS 上传失败: {e.reason}"}
        except Exception as e:
            return {"error": -1, "message": f"OBS 网络异常: {e}"}

    def submit_record(self, save_body: dict) -> dict:
        """核心跑步记录结算上报 (/api/v70260/runnings/save/record)"""
        return self.execute_request("POST", URL_SAVE_RECORD, body_plain=save_body)

    def get_rundetail_config(self, sport_type: int = 1) -> dict:
        """拉取跑步详情页配置 (/api/v70340/activity/rundetail/config)"""
        return self.execute_request("GET", f"{URL_RUN_DETAIL_CONFIG}?sportType={sport_type}")

    def execute_full_run(self,
                         target_distance_m: int = 2100,
                         target_time_sec: int = 780,
                         sport_type: int = 1,
                         progress_callback: Optional[Callable[[str], None]] = None) -> RunningSubmissionResult:
        """按照 7.3.92 实机抓包全时序规范执行拟人跑步结算全流程"""
        def log(msg: str):
            if progress_callback:
                progress_callback(msg)

        if not self.uid or not self.token:
            return RunningSubmissionResult(success=False, message="缺少鉴权凭据 (uid/token)")

        # 1. 冷启动时间校准与行为埋点
        log("[1/6] 服务端 GMT 时间校准与冷启动埋点上报...")
        st1 = self.profile.get_server_time()
        t_now_ms = st1.server_timestamp_ms
        if self.unid:
            self.telemetry.send_startup_pv(uid=int(self.uid), unid=int(self.unid))
            self.telemetry.send_page_exposure(unid=int(self.unid))

        # 2. 拉取电子围栏与打卡点
        fences = self.policy.get_geo_fence()
        checkpoints = []
        center_lat, center_lng = 0.0, 0.0  # 默认通用占位坐标
        if fences and len(fences) > 0:
            f = fences[0]
            checkpoints = [{"lat": cp.lat, "lng": cp.lng, "name": cp.name} for cp in f.check_points]
            if f.polygon_points:
                center_lat = f.polygon_points[0].lat
                center_lng = f.polygon_points[0].lng
            log(f"    -> 成功关联围栏: {f.fence_name} (包含 {len(checkpoints)} 个目标打卡点)")
        else:
            log("    [!] 未查询到专属围栏，启用运动学环形合规轨迹兜底")

        # 3. 拟人运动学轨迹生成
        stop_time_ms = t_now_ms
        start_time_ms = stop_time_ms - (target_time_sec * 1000)
        total_steps = int((target_distance_m / 0.72) * random.uniform(0.96, 1.04))

        builder = RunningTrackBuilder(uid=int(self.uid), unid=int(self.unid or 0), sport_type=sport_type)
        gps_pts, five_pts = builder.generate_track_around_points(
            center_lat=center_lat,
            center_lng=center_lng,
            checkpoints=checkpoints,
            total_distance_m=target_distance_m,
            total_time_sec=target_time_sec,
            start_time_ms=start_time_ms
        )

        save_record, obs_payload, obj_key = builder.build_submission_payload(
            total_distance_m=target_distance_m,
            total_time_sec=target_time_sec,
            total_steps=total_steps,
            start_time_ms=start_time_ms,
            stop_time_ms=stop_time_ms,
            gps_points=gps_pts,
            five_points=five_pts,
            sel_distance_m=2000,
            sel_run_time_s=1200
        )
        log(f"轨迹合成: 成功 距离={target_distance_m}m 耗时={target_time_sec}s 点数={len(gps_pts)} 步数={total_steps} 配速={save_record["speed"]}")

        # 4. 华为云 OBS 预签名上传
        log("[4/6] 申请 OBS 异步大对象存储地址并上传轨迹数据...")
        obs_res = self.request_obs_upload_url(object_key=obj_key)
        if obs_res.get("error") != 10000 or not obs_res.get("data"):
            err = obs_res.get("message", "OBS 凭证申请失败")
            return RunningSubmissionResult(success=False, message=f"申请 OBS 上传凭证失败: {err}", raw=obs_res)

        obs_info = obs_res["data"]
        signed_url = obs_info.get("signedUrl")
        signed_headers = obs_info.get("actualSignedRequestHeaders") or {"Content-Type": "text/plain"}
        put_res = self.upload_to_obs(signed_url, signed_headers, obs_payload)
        if put_res.get("error") != 10000:
            return RunningSubmissionResult(success=False, message=f"推送到 OBS 失败: {put_res.get("message")}", raw=put_res)
        log("    -> OBS 轨迹点阵推送完成 SUCCESS!")

        # 5. 核心跑步结算上报 (save/record)
        log("[5/6] 提交最终跑步成绩结算 (/api/v70260/runnings/save/record)...")
        sub_res = self.submit_record(save_record)
        if not isinstance(sub_res, dict) or sub_res.get("error") != 10000:
            code = sub_res.get("error", -1) if isinstance(sub_res, dict) else -1
            msg = sub_res.get("message", "结算上报失败") if isinstance(sub_res, dict) else str(sub_res)
            return RunningSubmissionResult(success=False, error_code=code, message=msg, raw=sub_res)

        data = sub_res.get("data") or {}
        rrid = data.get("rrid") or data.get("id")
        log(f"    -> 成绩结算成功！获得运动流水号 RRID={rrid}")

        # 6. 跑后实时成绩与状态回查
        time.sleep(0.5)
        record_detail = self.history.get_one_record(rrid=rrid) if rrid else None
        is_valid = record_detail.is_valid if record_detail else True
        
        # 跑后触发详情配置与看盘回刷
        self.get_rundetail_config(sport_type=sport_type)
        if self.unid:
            self.telemetry.send_page_exposure(unid=int(self.unid))

        log(f"    -> 最终判定结果: {"达标通过 PASS" if is_valid else "未达标"}")
        return RunningSubmissionResult(
            success=True,
            rrid=rrid,
            error_code=10000,
            message="跑步提交与结算完成",
            total_distance=float(target_distance_m),
            total_time=int(target_time_sec),
            is_valid=is_valid,
            raw=sub_res
        )
