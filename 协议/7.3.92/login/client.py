# -*- coding: utf-8 -*-
import base64
import json
import os
import ssl
import sys
import time
import urllib.request
import uuid
from typing import Dict, Any, Optional, Callable

# 兼容包引用与单文件直跑
cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core.security import open_https
from security_utils import redact_text
try:
    from .config import (
        URL_CHECK_GEE_USE,
        URL_GEE_VALIDATE,
        URL_LOGIN,
        LOGIN_CAPTCHA_ID,
        DEFAULT_DEVICE_CONFIG,
    )
    from .models import LoginResult, UserProfile, GeetestResult
    from .captcha import GeetestV4Solver
except (ImportError, ValueError):
    from config import (
        URL_CHECK_GEE_USE,
        URL_GEE_VALIDATE,
        URL_LOGIN,
        LOGIN_CAPTCHA_ID,
        DEFAULT_DEVICE_CONFIG,
    )
    from models import LoginResult, UserProfile, GeetestResult
    from captcha import GeetestV4Solver

try:
    from .crypto import NetSecClient, compute_token_sign, aes128_cbc_decrypt
except (ImportError, ValueError):
    from crypto import NetSecClient, compute_token_sign, aes128_cbc_decrypt


class LoginClient:
    """运动世界校园 7.3.92 独立登录客户端"""

    def __init__(self,
                 device_config: Optional[Dict[str, Any]] = None,
                 solver: Optional[GeetestV4Solver] = None):
        self.device_config = dict(DEFAULT_DEVICE_CONFIG)
        if device_config:
            self.device_config.update(device_config)

        self.solver = solver or GeetestV4Solver()
        self.crypto = NetSecClient()
        self.ssl_ctx = ssl.create_default_context()

    def execute_request(self,
                        url: str,
                        body: Any,
                        custom_headers: Optional[Dict[str, str]] = None) -> Any:
        """底层标准加解密请求管道"""
        now_ms = int(time.time() * 1000)
        nonce = str(uuid.uuid4())

        headers = dict(self.device_config)
        headers["timeStamp"] = str(now_ms)
        headers["nonce"] = nonce

        if custom_headers:
            headers.update(custom_headers)

        # 1. 对全部 Header 生成 headerSign
        h_wire, h_resp_key = self.crypto.encrypt_request(
            json.dumps(headers, separators=(",", ":"), ensure_ascii=False)
        )
        headers["headerSign"] = json.dumps(h_wire, separators=(",", ":"))

        # 2. 对 Body 执行 NetSec 加密
        b_wire, _ = self.crypto.encrypt_request(body)
        b_bytes = json.dumps(b_wire).encode("utf-8")

        # 3. 发送请求
        req = urllib.request.Request(url, data=b_bytes, headers=headers, method="POST")
        with open_https(req, context=self.ssl_ctx, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            resp_obj = json.loads(raw)
            if "r" in resp_obj:
                r_bytes = base64.b64decode(resp_obj["r"])
                dec_h = aes128_cbc_decrypt(r_bytes, h_resp_key)
                inner = json.loads(dec_h.decode("utf-8"))
                if "data" in inner:
                    biz_b64 = inner["data"]
                    biz_bytes = base64.b64decode(biz_b64)
                    try:
                        return json.loads(biz_bytes.decode("utf-8"))
                    except Exception:
                        return biz_bytes.decode("utf-8")
                return inner
            return resp_obj

    def check_gee_use(self, username: str, session_uuid: str) -> Dict[str, Any]:
        """发起安全初审"""
        body = {"username": username, "uuid": session_uuid, "unid": 0, "type": 2}
        return self.execute_request(URL_CHECK_GEE_USE, body)

    def gee_validate(self, gt_res: GeetestResult, session_uuid: str, username: str) -> Dict[str, Any]:
        """向服务端上报极验凭据并进行二次绑定校验"""
        payload = gt_res.to_validate_payload(session_uuid=session_uuid, username=username)
        return self.execute_request(URL_GEE_VALIDATE, payload)

    def submit_login(self, username: str, password: str, session_uuid: str) -> Dict[str, Any]:
        """提交基础认证凭据与设备信息"""
        auth_raw = f"{username}:{password}".encode("utf-8")
        custom_headers = {
            "Authorization": "Basic " + base64.b64encode(auth_raw).decode("ascii")
        }
        login_body = {
            "loginType": 1,
            "device_model": self.device_config.get("deviceName", "Android Device"),
            "os_version": self.device_config.get("osVersion", "13"),
            "username": username,
            "uuid": session_uuid
        }
        return self.execute_request(URL_LOGIN, login_body, custom_headers=custom_headers)

    def login(self,
              username: str,
              password: str,
              progress_callback: Optional[Callable[[str], None]] = None) -> LoginResult:
        """端到端登录流程 (checkGeeUse -> solve_captcha -> geevalidate -> login)"""
        def log(msg: str):
            if progress_callback:
                progress_callback(redact_text(msg))

        session_uuid = str(uuid.uuid4())

        # 1. checkGeeUse
        log("[1/3] 发起账号安全初审 (checkGeeUse)...")
        chk_res = self.check_gee_use(username, session_uuid)

        need_captcha = True
        if isinstance(chk_res, dict) and chk_res.get("data") is True:
            need_captcha = False

        # 2. 极验滑块与二次验证 (带自动重试)
        if need_captcha:
            max_val_retries = 3
            val_passed = False
            for val_attempt in range(1, max_val_retries + 1):
                log(f"[2/3] 极验人机校验 (第 {val_attempt}/{max_val_retries} 次尝试)...")
                gt_res = self.solver.solve(captcha_id=LOGIN_CAPTCHA_ID)
                log(f"    -> 滑块识别验证完成 (lot_number: {gt_res.lot_number[:16]}...)")

                log("[2.1/3] 上报极验凭据至服务端进行会话绑定 (geevalidate)...")
                val_res = self.gee_validate(gt_res, session_uuid, username)
                log(f"    -> geevalidate 状态: {val_res.get('error', -1) if isinstance(val_res, dict) else -1}")
                if isinstance(val_res, dict) and val_res.get("error") == 10000:
                    val_passed = True
                    log("    -> 二次校验通过 PASS!")
                    break
                else:
                    log(f"    [!] 第 {val_attempt} 次凭据核验未通过，准备重试...")
                    time.sleep(1.0)

            if not val_passed:
                err_msg = val_res.get("message", "geevalidate 校验失败") if isinstance(val_res, dict) else str(val_res)
                return LoginResult(
                    success=False,
                    error_code=val_res.get("error", -1) if isinstance(val_res, dict) else -1,
                    message=f"极验二次校验失败: {err_msg}",
                    raw=val_res
                )
        else:
            log("[2/3] 当前设备/会话处于白名单，免验证码直接跳过！")

        # 3. 正式登录
        log("[3/3] 提交正式鉴权凭据 (login)...")
        login_res = self.submit_login(username, password, session_uuid)

        if isinstance(login_res, dict) and login_res.get("error") == 10000 and "data" in login_res:
            if (not isinstance(login_res["data"], dict) or not login_res["data"].get("token")
                    or int(login_res["data"].get("uid", -1)) <= 0):
                return LoginResult(success=False, error_code=-1, message="登录响应缺少有效凭据")
            user_prof = UserProfile.from_api_data(login_res["data"])
            log("登录成功")
            return LoginResult(
                success=True,
                error_code=10000,
                message="登录成功",
                user=user_prof,
                raw=login_res
            )
        else:
            code = login_res.get("error", -1) if isinstance(login_res, dict) else -1
            msg = login_res.get("message", "未知错误") if isinstance(login_res, dict) else str(login_res)
            return LoginResult(
                success=False,
                error_code=code,
                message=msg,
                raw=login_res
            )


