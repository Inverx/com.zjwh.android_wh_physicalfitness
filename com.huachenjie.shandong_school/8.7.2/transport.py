"""网络传输底层模块。支持直连、ADB 转发与代理模式。"""
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time
import urllib.parse
from typing import Dict, Any, Optional

import requests

from crypto import get_sign, APP_VERSION, BUILD_VERSION, APP_CODE

def generate_device_id() -> str:
    """生成 16 位随机十六进制设备识别码。"""
    return secrets.token_hex(8)

class HttpTransport:
    DEFAULT_BASE_URL = "https://api.huachenjie.com/run-front"
    DEFAULT_MODEL = "Android|GenericDevice"
    DEFAULT_SYS_VER = "12"
    DEFAULT_PLATFORM = "2"
    DEFAULT_CHANNEL = "other"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        token: Optional[str] = None,
        satoken: Optional[str] = None,
        device_id: Optional[str] = None,
        model_name: Optional[str] = None,
        system_version: Optional[str] = None,
        transport_mode: str = "direct",
        proxy: Optional[str] = None,
        adb_path: Optional[str] = None,
        adb_device: Optional[str] = None,
        timeout: int = 15
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token or ""
        self.satoken = satoken or ""
        self.device_id = device_id or os.environ.get("SHANDONG_DEVICE_ID") or generate_device_id()
        self.model_name = model_name or os.environ.get("SHANDONG_MODEL") or self.DEFAULT_MODEL
        self.system_version = system_version or self.DEFAULT_SYS_VER
        self.app_version = APP_VERSION
        self.build_version = BUILD_VERSION
        self.app_code = APP_CODE
        self.platform = self.DEFAULT_PLATFORM
        self.channel = self.DEFAULT_CHANNEL
        self.transport_mode = transport_mode
        self.proxy = proxy or os.environ.get("SHANDONG_PROXY")
        self.timeout = timeout
        self.adb_device = adb_device or os.environ.get("ADB_DEVICE")

        self.adb_path = adb_path or os.environ.get("ADB_PATH") or shutil.which("adb")
        if not self.adb_path:
            sdk_adb = r"D:\Work\Tools\Android\Sdk\platform-toolsdb.exe"
            if os.path.exists(sdk_adb):
                self.adb_path = sdk_adb
            else:
                self.adb_path = r"D:\Work\Tools\Androidindb.cmd"

        self.session = requests.Session()
        if self.proxy and self.transport_mode == "proxy":
            self.session.proxies = {
                "http": self.proxy,
                "https": self.proxy,
            }

    def get_common_params(self) -> Dict[str, Any]:
        """组装客户端公共基础参数。"""
        return {
            "modelName": self.model_name,
            "appVersion": self.app_version,
            "buildVersion": self.build_version,
            "channel": self.channel,
            "appCode": self.app_code,
            "deviceId": self.device_id,
            "systemVersion": self.system_version,
            "platform": self.platform,
            "timestamp": str(int(time.time() * 1000)),
        }

    def _build_headers(self, raw_post_body: str, v: Optional[str] = None, api: Optional[str] = None) -> Dict[str, str]:
        """构建通用请求头并计算签名。"""
        brand = self.model_name.split("|")[0] if "|" in self.model_name else self.model_name
        headers = {
            "User-Agent": f"ShanDong/{self.app_version} ({brand};Android {self.system_version})",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, text/plain, */*",
            "timestamp": str(int(time.time() * 1000)),
        }
        if self.token:
            headers["Authorization"] = self.token
            headers["token"] = self.token
        if self.satoken:
            headers["satoken"] = self.satoken
        if v:
            headers["v"] = v
        if api:
            headers["api"] = api
        if raw_post_body:
            headers["sign"] = get_sign(raw_post_body)
        return headers

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None, add_common: bool = True, v: Optional[str] = None, api: Optional[str] = None) -> Dict[str, Any]:
        """发送 POST 请求。支持直连与 ADB 模式。"""
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        payload = {}
        if add_common:
            payload.update(self.get_common_params())
        if data:
            payload.update(data)

        raw_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        headers = self._build_headers(raw_body, v=v, api=api)

        if self.transport_mode == "adb":
            return self._post_via_adb(url, raw_body, headers)
        else:
            try:
                resp = self.session.post(url, data=raw_body.encode("utf-8"), headers=headers, timeout=self.timeout, verify=False)
                return resp.json()
            except Exception as e:
                return {"code": -1, "message": f"网络传输异常: {e}"}

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送 GET 请求。"""
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        headers = self._build_headers("")
        if self.transport_mode == "adb":
            return self._get_via_adb(url, params, headers)
        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout, verify=False)
            return resp.json()
        except Exception as e:
            return {"code": -1, "message": f"网络传输异常: {e}"}

    def _get_adb_target(self) -> Optional[str]:
        """获取目标 ADB 设备标识。"""
        if self.adb_device:
            return self.adb_device
        try:
            r = subprocess.run([self.adb_path, "devices"], capture_output=True, text=True, timeout=5)
            lines = [l for l in r.stdout.strip().splitlines() if "	device" in l]
            if lines:
                return lines[0].split("	")[0]
        except Exception:
            pass
        return None

    def _post_via_adb(self, url: str, raw_body: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """通过 ADB shell curl 发送 POST 请求。"""
        if not self.adb_path:
            return {"code": -2, "message": "未找到 ADB 执行文件路径"}
        dev = self._get_adb_target()
        dev_args = ["-s", dev] if dev else []

        remote_tmp = "/data/local/tmp/shandong_req.json"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
            tf.write(raw_body)
            local_tmp = tf.name

        try:
            push_cmd = [self.adb_path] + dev_args + ["push", local_tmp, remote_tmp]
            subprocess.run(push_cmd, capture_output=True, timeout=5, encoding="utf-8", errors="replace")

            header_args = []
            for hk, hv in headers.items():
                if not hv and hk != "k":
                    continue
                safe_v = str(hv).replace("'", "'\''")
                header_args.append(f"-H '{hk}: {safe_v}'")

            header_str = " ".join(header_args)
            curl_cmd = f"curl -s -k --compressed -X POST '{url}' {header_str} -d @{remote_tmp} --connect-timeout {self.timeout}"

            res = subprocess.run([self.adb_path] + dev_args + ["shell", curl_cmd], capture_output=True, encoding="utf-8", errors="replace", timeout=self.timeout + 10)
            out = res.stdout.strip()
            if not out:
                return {"code": -3, "message": f"ADB 请求无响应，错误: {res.stderr}"}
            try:
                return json.loads(out)
            except Exception:
                return {"code": -4, "message": "ADB 返回非 JSON", "raw": out}
        except Exception as e:
            return {"code": -1, "message": f"ADB 传输异常: {e}"}
        finally:
            if os.path.exists(local_tmp):
                try:
                    os.remove(local_tmp)
                except Exception:
                    pass
            subprocess.run([self.adb_path] + dev_args + ["shell", "rm", "-f", remote_tmp], capture_output=True)

    def _get_via_adb(self, url: str, params: Optional[Dict[str, Any]], headers: Dict[str, str]) -> Dict[str, Any]:
        """通过 ADB shell curl 发送 GET 请求。"""
        dev = self._get_adb_target()
        dev_args = ["-s", dev] if dev else []
        full_url = url
        if params:
            full_url += "?" + urllib.parse.urlencode(params)

        header_args = []
        for hk, hv in headers.items():
            if not hv: continue
            safe_v = str(hv).replace("'", "'\''")
            header_args.append(f"-H '{hk}: {safe_v}'")

        header_str = " ".join(header_args)
        curl_cmd = f"curl -s -k --compressed '{full_url}' {header_str} --connect-timeout {self.timeout}"
        res = subprocess.run([self.adb_path] + dev_args + ["shell", curl_cmd], capture_output=True, encoding="utf-8", errors="replace", timeout=self.timeout + 10)
        out = res.stdout.strip()
        if not out:
            return {"code": -3, "message": f"ADB GET 无响应: {res.stderr}"}
        try:
            return json.loads(out)
        except Exception:
            return {"code": -4, "message": "ADB 返回非 JSON", "raw": out}
