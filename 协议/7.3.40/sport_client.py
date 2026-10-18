import base64
import collections
import json
import logging
import os
import subprocess
import tempfile
import time
from typing import Dict, Optional, Tuple, Union, Any, Callable, List
import uuid

import requests

from netsec_crypto import (
    SPORT_STATIC_SALT,
    compute_token_sign,
    NetSecSession,
    NetSecCrypto
)
from geetest_solver import GeeTestV4Solver, GEETEST_IDS, GeeTestResult
from running_protocol import (
    OutdoorRunRecordBuilder,
    IndoorRunRecordBuilder,
    generate_synthetic_gps_track,
    validate_outdoor_record_consistency,
)
from coordinate_utils import validate_coordinate
from rank_protocol import (
    RankType,
    RankSortType,
    RankGender,
    IndoorDateRange,
    LeaderboardRequestBuilder
)
from security_utils import install_redaction_filter

logger = logging.getLogger("sport_client")
install_redaction_filter(logger)

DEFAULT_HOST_RUN = "https://run.gxapp.iydsj.com"
DEFAULT_HOST_DISCOVERY = "https://discovery.gxapp.iydsj.com"


class SportClient:
    def __init__(self,
                 uid: Optional[Union[int, str]] = None,
                 token: Optional[str] = None,
                 unid: int = 0,
                 device_id: Optional[str] = None,
                 app_version: str = "7.3.90",     # App版本
                 os_version: str = "15",          # Android版本
                 device_name: str = "SM-A5460",    # 设备型号
                 proxy: Optional[str] = None,
                 adb_path: Optional[str] = None,
                 verify_response_signature: bool = False):
        self.uid = str(uid) if uid else None
        self.token = token
        self.unid = int(unid) if unid else 0
        self.device_id = device_id or "7a3f91c2d8e64b5fa104ce7392bd6e81"   #固定 32 位设备 ID
        self.app_version = app_version
        self.os_version = os_version
        self.device_name = device_name
        self.proxy = proxy
        self.adb_path = adb_path or os.path.join("D:", os.sep, "Android", "Sdk", "platform-tools", "adb.exe")
        # Current live response `s` values do not validate with the extracted key.
        # Opt-in verification is strict; normal operation still relies on TLS.
        self.verify_response_signature = verify_response_signature

        self.session = NetSecSession()
        self.crypto = NetSecCrypto()
        self.geetest_solver = GeeTestV4Solver()
        self.rank_builder = LeaderboardRequestBuilder(unid=self.unid, uid=int(self.uid) if self.uid else None)

    def set_credentials(self, uid: Union[int, str], token: str, unid: Optional[int] = None):
        self.uid = str(uid)
        self.token = token
        if unid is not None:
            self.unid = int(unid)
            self.rank_builder.unid = int(unid)
        if self.uid:
            self.rank_builder.uid = int(self.uid)

    def build_public_headers(self, custom_headers: Optional[Dict[str, str]] = None, sign_params: Optional[Dict[str, str]] = None) -> collections.OrderedDict:
        now_ms = int(time.time() * 1000)
        nonce = str(uuid.uuid4())

        headers = collections.OrderedDict([
            ("Accept", "application/json"),   # 接收 JSON
            ("Content-Type", "application/json"),    # 请求体为 JSON
            ("appVersion", self.app_version),    # App 版本
            ("physicPixel", "1080x2400"),   # 屏幕物理分辨率
            ("logicPixel", "393x873"),   # 屏幕逻辑分辨率
            ("isRoot", "0"),   # 是否 Root
            ("osType", "0"),     # 系统类型
        ])
        if self.uid:
            headers["uid"] = str(self.uid)   # 用户 ID

        headers.update([
            ("IMEI", ""),   # 手机 IMEI
            ("timeStamp", str(now_ms)),   # 当前时间戳
            ("blMac", ""),    # 蓝牙 MAC
            ("nonce", nonce),    # 蓝牙 MAC
        ])

        if self.token:
            headers["token"] = str(self.token)   # 登录 Token

        headers.update([
            ("cpuModel", "arm64-v8a"),   # CPU 架构
            ("deviceName", self.device_name),   # 手机型号
            ("appInstallTime", "1768017600000"),   # App 安装时间(2026-01-01 08:00:00（UTC+8）)
            ("androidId", ""),   # Android ID
            ("DeviceId", self.device_id),   # 设备 ID
            ("appUpdateTime", "1768017600000"),   # App 更新时间(2026-01-01 08:00:00（UTC+8）)
            ("wifiMac", ""),   # WiFi MAC
            ("CustomDeviceId", ""),   # 自定义设备 ID
            ("osVersion", self.os_version),   # Android 版本
            ("User-Agent", "okhttp/4.12.0")   # HTTP 客户端版本
        ])

        if custom_headers:
            headers.update(custom_headers)

        # Standard tokenSign calculation
        sign_dict = {
            "timeStamp": str(now_ms),
            "token": str(self.token or ""),
            "uid": str(self.uid or "")
        }
        if sign_params:
            sign_dict.update(sign_params)

        headers["tokenSign"] = compute_token_sign(sign_dict)
        return headers

    def build_header_sign(self, headers: Dict[str, str]) -> Dict[str, str]:
        headers_json = json.dumps(headers, separators=(",", ":"), ensure_ascii=False)
        return self.crypto.encrypt_request(headers_json.strip(), self.session)

    def execute_request(self,
                        method: str,
                        url: str,
                        body_plain: Optional[Union[dict, list]] = None,
                        custom_headers: Optional[Dict[str, str]] = None,
                        sign_params: Optional[Dict[str, str]] = None,
                        timeout: int = 25) -> Any:
        headers = self.build_public_headers(custom_headers, sign_params)
        h_sign = self.build_header_sign(headers)
        headers["headerSign"] = json.dumps(h_sign, separators=(",", ":"), ensure_ascii=False)

        encrypted_body = None
        if body_plain is not None:
            encrypted_body = self.crypto.encrypt_request(body_plain, self.session)

        # Prefer a connected phone so requests can use its unproxied mobile network.
        adb_connected = False
        if os.path.isfile(self.adb_path):
            try:
                state = subprocess.run(
                    [self.adb_path, "get-state"],
                    capture_output=True,
                    timeout=5,
                )
                adb_connected = state.returncode == 0 and state.stdout.strip() == b"device"
            except (OSError, subprocess.SubprocessError):
                adb_connected = False

        if adb_connected:
            request_id = uuid.uuid4().hex
            remote_body = f"/data/local/tmp/sport_body_{request_id}.json"
            remote_cfg = f"/data/local/tmp/sport_curl_{request_id}.cfg"
            remote_files = [remote_cfg]

            try:
                with tempfile.TemporaryDirectory(prefix="sport_client_") as temp_dir:
                    local_cfg = os.path.join(temp_dir, "curl.cfg")
                    cfg_lines = [
                        f'url = "{url}"',
                        f'request = "{method.upper()}"',
                        "silent",
                        "show-error",
                    ]
                    for key, value in headers.items():
                        safe_value = value.replace("\\", "\\\\").replace('"', '\\"')
                        cfg_lines.append(f'header = "{key}: {safe_value}"')

                    if encrypted_body is not None:
                        local_body = os.path.join(temp_dir, "body.json")
                        body_bytes = json.dumps(
                            encrypted_body,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        ).encode("utf-8")
                        with open(local_body, "wb") as body_file:
                            body_file.write(body_bytes)
                        push_body = subprocess.run(
                            [self.adb_path, "push", local_body, remote_body],
                            capture_output=True,
                            timeout=10,
                        )
                        if push_body.returncode != 0:
                            message = push_body.stderr.decode("utf-8", errors="ignore").strip()
                            return {"error": -1, "message": f"ADB push body failed: {message}"}
                        remote_files.append(remote_body)
                        cfg_lines.append('header = "Content-Type: application/json;charset=utf-8"')
                        cfg_lines.append(f'data-binary = "@{remote_body}"')

                    with open(local_cfg, "w", encoding="utf-8", newline="\n") as cfg_file:
                        cfg_file.write("\n".join(cfg_lines) + "\n")

                    push_cfg = subprocess.run(
                        [self.adb_path, "push", local_cfg, remote_cfg],
                        capture_output=True,
                        timeout=10,
                    )
                    if push_cfg.returncode != 0:
                        message = push_cfg.stderr.decode("utf-8", errors="ignore").strip()
                        return {"error": -1, "message": f"ADB push curl config failed: {message}"}

                    res = subprocess.run(
                        [self.adb_path, "shell", "curl", "-K", remote_cfg],
                        capture_output=True,
                        timeout=timeout,
                    )
                    raw = res.stdout.decode("utf-8", errors="ignore").strip()
                    if res.returncode != 0:
                        message = res.stderr.decode("utf-8", errors="ignore").strip()
                        return {"error": -1, "message": f"ADB curl failed: {message}", "raw": raw}
            except subprocess.TimeoutExpired:
                return {"error": -1, "message": f"ADB request timed out after {timeout} seconds"}
            finally:
                subprocess.run(
                    [self.adb_path, "shell", "rm", "-f", *remote_files],
                    capture_output=True,
                    timeout=5,
                )

            try:
                resp_obj = json.loads(raw)
            except json.JSONDecodeError:
                return {"error": -1, "message": "Device response is not JSON", "raw": raw}

            if resp_obj.get("v") in (101, "101"):
                try:
                    dec = self.crypto.decrypt_response(
                        resp_obj,
                        self.session,
                        verify_sig=self.verify_response_signature,
                    )
                    return json.loads(dec)
                except Exception as exc:
                    return {"error": -1, "message": f"Response decryption failed: {exc}"}
            return resp_obj

        # Direct PC network request
        req_kwargs = {
            "method": method.upper(),
            "url": url,
            "headers": headers,
            "timeout": timeout
        }
        if self.proxy:
            req_kwargs["proxies"] = {"http": self.proxy, "https": self.proxy}
        if encrypted_body is not None:
            req_kwargs["json"] = encrypted_body

        try:
            resp = requests.request(**req_kwargs)
        except requests.RequestException as exc:
            return {"error": -1, "message": f"Network request failed: {exc}"}
        if resp.status_code == 200:
            try:
                raw_json = resp.json()
            except requests.JSONDecodeError:
                return {"error": -1, "message": "Response is not JSON", "raw": resp.text}
            if raw_json.get("v") in (101, "101"):
                try:
                    dec_str = self.crypto.decrypt_response(
                        raw_json,
                        self.session,
                        verify_sig=self.verify_response_signature,
                    )
                    return json.loads(dec_str)
                except Exception as exc:
                    return {"error": -1, "message": f"Response decryption failed: {exc}"}
            return raw_json

        return {"error": resp.status_code, "raw": resp.text}

    def _put_presigned_json(self,
                            signed_url: str,
                            headers: Dict[str, str],
                            payload: dict,
                            timeout: int = 25) -> dict:
        payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        adb_connected = False
        if os.path.isfile(self.adb_path):
            try:
                state = subprocess.run(
                    [self.adb_path, "get-state"],
                    capture_output=True,
                    timeout=5,
                )
                adb_connected = state.returncode == 0 and state.stdout.strip() == b"device"
            except (OSError, subprocess.SubprocessError):
                adb_connected = False

        if adb_connected:
            request_id = uuid.uuid4().hex
            remote_body = f"/data/local/tmp/sport_obs_{request_id}.json"
            remote_cfg = f"/data/local/tmp/sport_obs_{request_id}.cfg"
            try:
                with tempfile.TemporaryDirectory(prefix="sport_obs_") as temp_dir:
                    local_body = os.path.join(temp_dir, "payload.json")
                    local_cfg = os.path.join(temp_dir, "curl.cfg")
                    with open(local_body, "wb") as body_file:
                        body_file.write(payload_bytes)

                    safe_url = signed_url.replace("\\", "\\\\").replace('"', '\\"')
                    cfg_lines = [
                        f'url = "{safe_url}"',
                        'request = "PUT"',
                        f'data-binary = "@{remote_body}"',
                    ]
                    for key, value in headers.items():
                        safe_value = str(value).replace("\\", "\\\\").replace('"', '\\"')
                        cfg_lines.append(f'header = "{key}: {safe_value}"')
                    with open(local_cfg, "w", encoding="utf-8", newline="\n") as cfg_file:
                        cfg_file.write("\n".join(cfg_lines) + "\n")

                    for local_path, remote_path in ((local_body, remote_body), (local_cfg, remote_cfg)):
                        pushed = subprocess.run(
                            [self.adb_path, "push", local_path, remote_path],
                            capture_output=True,
                            timeout=10,
                        )
                        if pushed.returncode != 0:
                            message = pushed.stderr.decode("utf-8", errors="ignore").strip()
                            return {"error": -1, "message": f"ADB push OBS payload failed: {message}"}

                    response = subprocess.run(
                        [
                            self.adb_path, "shell", "curl", "-sS", "-o", "/dev/null",
                            "-w", "%{http_code}", "-K", remote_cfg,
                        ],
                        capture_output=True,
                        timeout=timeout,
                    )
                    if response.returncode != 0:
                        message = response.stderr.decode("utf-8", errors="ignore").strip()
                        return {"error": -1, "message": f"ADB OBS upload failed: {message}"}
                    status_text = response.stdout.decode("ascii", errors="ignore").strip()
                    try:
                        status_code = int(status_text[-3:])
                    except ValueError:
                        return {"error": -1, "message": f"Invalid OBS HTTP status: {status_text!r}"}
            except subprocess.TimeoutExpired:
                return {"error": -1, "message": f"OBS upload timed out after {timeout} seconds"}
            finally:
                subprocess.run(
                    [self.adb_path, "shell", "rm", "-f", remote_body, remote_cfg],
                    capture_output=True,
                    timeout=5,
                )
        else:
            request_kwargs = {
                "url": signed_url,
                "headers": headers,
                "data": payload_bytes,
                "timeout": timeout,
            }
            if self.proxy:
                request_kwargs["proxies"] = {"http": self.proxy, "https": self.proxy}
            try:
                response = requests.put(**request_kwargs)
            except requests.RequestException as exc:
                return {"error": -1, "message": f"OBS upload failed: {exc}"}
            status_code = response.status_code

        if not 200 <= status_code < 300:
            return {"error": status_code, "message": f"OBS upload returned HTTP {status_code}"}
        return {"error": 10000, "message": "OBS upload succeeded"}

    def _upload_obs_payload(self, object_key: str, payload: dict) -> dict:
        presign_url = f"{DEFAULT_HOST_RUN}/api/obs/temporary/url"
        presign_body = {
            "bucketName": "iydsj-hbase-hot",
            "objectKey": object_key,
            "method": "Put",
            "contentType": "text/plain",
        }
        presign_result = self.execute_request("POST", presign_url, presign_body)
        if presign_result.get("error") != 10000:
            return {
                "error": presign_result.get("error", -1),
                "message": f"Failed to obtain OBS upload URL: {presign_result.get('message', presign_result)}",
            }

        temporary = presign_result.get("data")
        if isinstance(temporary, str):
            try:
                temporary = json.loads(temporary)
            except json.JSONDecodeError:
                return {"error": -1, "message": "Invalid OBS temporary URL response"}
        if not isinstance(temporary, dict) or not temporary.get("signedUrl"):
            return {"error": -1, "message": "OBS temporary URL response is incomplete"}

        signed_headers = temporary.get("actualSignedRequestHeaders") or {"Content-Type": "text/plain"}
        return self._put_presigned_json(temporary["signedUrl"], signed_headers, payload)

    # 1. Login Operations
    def login(self,
              username: str,
              password: str,
              progress_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        def log(msg: str):
            if progress_callback:
                progress_callback(msg)
            else:
                logger.info(msg)

        uuid_str = str(uuid.uuid4())
        log("正在检查登录状态...")

        chk_url = f"{DEFAULT_HOST_RUN}/api/v65/security/checkGeeUse"
        chk_body = {"username": username, "uuid": uuid_str, "unid": 0, "type": 2}
        chk_res = self.execute_request("POST", chk_url, chk_body)

        need_captcha = True
        if isinstance(chk_res, dict) and chk_res.get("data") is True:
            need_captcha = False

        if need_captcha:
            log("正在完成安全验证...")
            gt_res = self.geetest_solver.solve(GEETEST_IDS["LOGIN"], proxy=self.proxy)

            val_url = f"{DEFAULT_HOST_RUN}/api/v70270/security/geevalidate"
            val_body = gt_res.to_app_validate_payload(username=username, uuid_str=uuid_str)
            val_res = self.execute_request("POST", val_url, val_body)
            if val_res.get("error") != 10000:
                raise RuntimeError(f"安全验证失败: {val_res.get('message', val_res)}")
            log("安全验证通过")
        else:
            log("无需安全验证")

        log("正在提交登录...")
        login_url = f"{DEFAULT_HOST_RUN}/api/v70100/login"
        auth_raw = f"{username}:{password}".encode("utf-8")
        custom_headers = {
            "Authorization": "Basic " + base64.b64encode(auth_raw).decode("ascii")
        }
        login_body = {
            "loginType": 1,
            "device_model": self.device_name,
            "os_version": self.os_version,
            "uuid": uuid_str
        }
        login_res = self.execute_request("POST", login_url, login_body, custom_headers=custom_headers)
        if login_res.get("error") == 10000 and "data" in login_res:
            d = login_res["data"]
            self.set_credentials(uid=d.get("uid"), token=d.get("token"), unid=d.get("unid"))
        return login_res

    # 2. Running Policy & GeoFence
    def get_run_policy(self, run_mode: int = 1) -> dict:
        endpoint = "/api/v59/indoorRunModePolicy" if run_mode == 5 else "/api/v70103/runModePolicy"
        url = f"{DEFAULT_HOST_RUN}{endpoint}"
        body = {
            "runMode": run_mode,
            "ruleUpdateTime": 0,
            "geoFenceUpdateTime": 0,
            "selectUnid": self.unid,
            "operateType": 0
        }
        return self.execute_request("POST", url, body)

    def get_geo_fence(self, update_time: int = 0) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v1/getGeoFenceForRun"
        return self.execute_request("POST", url, {"geoFenceUpdateTime": update_time})

    def get_history_config(self) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v70100/run/getHistoryConfig"
        return self.execute_request("GET", url)

    # 3. Score & Progress Queries
    def get_semester_completed(self, sid: int = 0) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v55/runnings/recordssummary/semester"
        return self.execute_request("POST", url, {"sid": sid})

    def get_semester_info(self, run_mode: int = 1) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v41/running/getPersonalSemesterInfo"
        return self.execute_request("POST", url, {"runMode": run_mode})

    # 4. History Queries
    def get_run_history(self, page_num: int = 1, page_size: int = 20, sid: int = 0, sport_type: int = 1) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v70230/runnings/records"
        body = {
            "pageNum": page_num,
            "pageSize": page_size,
            "sid": sid,
            "type": sport_type,
        }
        return self.execute_request("POST", url, body)

    def get_run_detail(self, rrid: int) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v70320/runnings/get_one_record"
        return self.execute_request("POST", url, {"rrid": rrid})

    def get_indoor_history(self, page_num: int = 1, page_size: int = 20) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v74/runnings/indoor/findForPage"
        return self.execute_request("POST", url, {"pageNum": page_num, "pageSize": page_size})

    # 5. Leaderboard Queries
    def get_main_rank(self,
                      rank_type: int = RankType.PERSONAL,
                      sort_type: int = RankSortType.DAY,
                      gender: Optional[int] = RankGender.ALL,
                      date_str: Optional[str] = None) -> dict:
        url = f"{DEFAULT_HOST_DISCOVERY}/api/v41/rank"
        body = self.rank_builder.build_main_rank_body(
            unid=self.unid,
            rank_type=rank_type,
            sort_type=sort_type,
            gender=gender,
            date_str=date_str,
        )
        return self.execute_request("POST", url, body)

    def get_indoor_rank(self,
                        page_num: int = 1,
                        page_size: int = 20,
                        gender: int = RankGender.FEMALE,
                        date_range: int = IndoorDateRange.WEEK) -> dict:
        url = f"{DEFAULT_HOST_DISCOVERY}/api/v43/runnings/indoor/studentRank"
        body = self.rank_builder.build_indoor_rank_body(
            page_num=page_num,
            page_size=page_size,
            gender=gender,
            date_range=date_range
        )
        return self.execute_request("POST", url, body)

    def get_history_rank(self,
                         sort_type: int = RankSortType.DAY,
                         gender: int = RankGender.FEMALE,
                         page_num: int = 1,
                         page_size: int = 20) -> dict:
        url = f"{DEFAULT_HOST_DISCOVERY}/api/v41/historyRank"
        body = self.rank_builder.build_history_rank_body(
            unid=self.unid,
            sort_type=sort_type,
            gender=gender,
            page_num=page_num,
            page_size=page_size,
        )
        return self.execute_request("POST", url, body)

    def get_cheat_list(self, page_num: int = 1, page_size: int = 20) -> dict:
        url = f"{DEFAULT_HOST_DISCOVERY}/api/v78/cheat/cheatlist"
        body = self.rank_builder.build_cheat_list_body(unid=self.unid, page_num=page_num, page_size=page_size)
        return self.execute_request("POST", url, body)

    # 6. Run Submissions
    def submit_outdoor_run(self,
                       total_distance_m: float = 2360.0,   # 距离，米
                       total_time_sec: int = 845,          # 时长，秒
                       total_steps: int = 2487,            # 总步数
                       sport_type: int = 1,                # 运动类型
                       start_lat: Optional[float] = None,    # 起点纬度
                       start_lon: Optional[float] = None,    # 起点经度
                       dry_run: bool = False) -> dict:

        if start_lat is None or start_lon is None:
            raise ValueError(
                "start_lat and start_lon are required; pass the actual run anchor coordinates"
            )
        start_lat, start_lon = validate_coordinate(start_lat, start_lon)
        if total_distance_m <= 0:
            raise ValueError("total_distance_m must be positive")
        if total_time_sec <= 0:
            raise ValueError("total_time_sec must be positive")
        if total_steps < 0:
            raise ValueError("total_steps cannot be negative")

    # 当前时间作为结束时间
    
        stop_time_ms = int(time.time() * 1000)

    # 根据时长计算开始时间

        start_time_ms = stop_time_ms - (total_time_sec * 1000)

    # 生成模拟轨迹
        gps_points, five_points = generate_synthetic_gps_track(
            start_lat=start_lat,
            start_lon=start_lon,
            total_distance_m=total_distance_m,
            total_time_sec=total_time_sec,
            start_time_ms=start_time_ms,
        )

        builder = OutdoorRunRecordBuilder(
            uid=int(self.uid or 0),
            unid=self.unid,
            sport_type=sport_type,
            sel_distance_m=int(round(total_distance_m)),
            sel_run_time_s=total_time_sec,
        )
        endpoint, save_body, obs_payload = builder.build_record(
            total_distance_m=int(round(total_distance_m)),
            total_time_sec=total_time_sec,
            total_steps=total_steps,
            start_time_ms=start_time_ms,
            stop_time_ms=stop_time_ms,
            gps_points=gps_points,
            five_points=five_points,
        )
        consistency = validate_outdoor_record_consistency(save_body)
        if dry_run:
            return {
                "error": 10000,
                "message": "dry-run: record generated and validated; nothing uploaded",
                "dryRun": True,
                "data": {"uuid": builder.uuid_str, **consistency},
            }
        hour = time.strftime("%Y%m%d%H", time.localtime(start_time_ms / 1000))
        upload_result = self._upload_obs_payload(
            f"run_data/{hour}/{builder.uuid_str}.json",
            obs_payload,
        )
        if upload_result.get("error") != 10000:
            upload_result["stage"] = "obs_upload"
            return upload_result
        url = f"{DEFAULT_HOST_RUN}{endpoint}"
        return self.execute_request("POST", url, save_body)

    def submit_indoor_exercise(self,
                               total_time_sec: int = 1200,
                               total_steps: int = 2000,
                               calorie: int = 150) -> dict:
        builder = IndoorRunRecordBuilder(
            uid=int(self.uid or 0),
            unid=self.unid,
        )
        stop_time_ms = int(time.time() * 1000)
        start_time_ms = stop_time_ms - (total_time_sec * 1000)
        endpoint, save_body, obs_payload = builder.build_record(
            total_time_sec=total_time_sec,
            total_steps=total_steps,
            start_time_ms=start_time_ms,
            stop_time_ms=stop_time_ms,
            calorie=calorie,
        )
        hour = time.strftime("%Y%m%d%H", time.localtime(start_time_ms / 1000))
        upload_result = self._upload_obs_payload(
            f"indoor_json/{hour}/{builder.uuid_str}.json",
            obs_payload,
        )
        if upload_result.get("error") != 10000:
            upload_result["stage"] = "obs_upload"
            return upload_result
        url = f"{DEFAULT_HOST_RUN}{endpoint}"
        return self.execute_request("POST", url, save_body)
