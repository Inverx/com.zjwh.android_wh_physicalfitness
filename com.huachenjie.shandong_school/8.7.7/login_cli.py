"""登录与凭证管理命令行工具。"""
import argparse
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from client import ShanDongClient
from logger import log_status, log_fields, log_error, log_detail
import captcha_solver
import crypto

def main():
    parser = argparse.ArgumentParser(description="闪动校园登录与凭证管理")
    parser.add_argument("-u", "--mobile", help="登录手机号")
    parser.add_argument("-p", "--password", help="登录密码")
    parser.add_argument("--token", help="直接注入 Token 凭证")
    parser.add_argument("--satoken", help="直接注入 SaToken 凭证")
    parser.add_argument("--device-id", help="设备识别码")
    parser.add_argument("--model", help="机型标识")
    parser.add_argument("--clear", action="store_true", help="清除本地保存的会话")
    parser.add_argument("--transport", default="direct", choices=["direct", "adb", "proxy"], help="网络传输模式")
    parser.add_argument("--proxy", help="代理服务器地址")
    parser.add_argument("--adb-path", help="ADB 命令路径")
    parser.add_argument("--adb-device", help="ADB 目标设备编号")
    args = parser.parse_args()

    client = ShanDongClient(
        transport_mode=args.transport,
        proxy=args.proxy,
        adb_path=args.adb_path,
        adb_device=args.adb_device
    )

    if args.clear:
        client.clear_saved_session()
        log_status("清除本地会话", ok=True)
        return

    # 直接注入 Token 模式
    if args.token:
        client.transport.token = args.token
        if args.satoken:
            client.transport.satoken = args.satoken
        if args.device_id:
            client.transport.device_id = args.device_id
        if args.model:
            client.transport.model_name = args.model
        client._save_current_session()
        log_status("注入凭证", ok=True)
        log_fields(Token=args.token[:12] + "...", 状态="已持久化")

        info_res = client.query_common_user_info()
        if info_res.get("code") == 0 and info_res.get("data"):
            udata = info_res["data"]
            client.user_id = udata.get("userId")
            client.school_code = udata.get("schoolCode")
            client._save_current_session()
            log_status("凭证核验", ok=True)
            log_fields(
                用户ID=udata.get("userId"),
                姓名=crypto.decrypt_field(udata.get("userName", "")),
                手机号=crypto.decrypt_field(udata.get("phone", "")),
                学校=crypto.decrypt_field(udata.get("schoolName", "")),
                学号=crypto.decrypt_field(udata.get("studentNumber", ""))
            )
        else:
            log_status("凭证核验", ok=False)
            log_error(info_res.get("message", "核验失败"))
            log_detail(info_res)
        return

    if not args.mobile or not args.password:
        if client.transport.token:
            log_status("已存会话", ok=True)
            log_fields(
                Token=client.transport.token[:16] + "...",
                SaToken=client.transport.satoken[:16] + "..." if client.transport.satoken else "无",
                设备=client.transport.model_name,
                用户ID=client.user_id or "未记录"
            )
        else:
            parser.print_help()
        return

    log_status("账号登录", ok=True, status_text="开始")
    log_fields(账号=args.mobile, 模式="密码与滑块验证")

    # 1. 登录前置检查
    chk_res = client.login_check(args.mobile)
    if chk_res.get("code") != 0:
        log_status("前置检查", ok=False)
        log_error(chk_res.get("message", "前置检查失败"))
        log_detail(chk_res)
        return

    log_status("前置检查", ok=True)

    # 2. 初次密码请求
    l_res = client.login_by_password(args.mobile, args.password)
    
    # 3. 滑块人机验证处理
    if l_res.get("code") == 1600:
        log_status("人机校验", ok=True, status_text="触发滑块")
        c_res = client.get_slider_captcha()
        if c_res.get("code") != 0 or not c_res.get("data"):
            log_status("拉取验证码", ok=False)
            log_error(c_res.get("message", "拉取失败"))
            log_detail(c_res)
            return

        cdata = c_res["data"]
        token = cdata.get("token")
        bg_url = cdata.get("originalImageUrl")
        tmpl_url = cdata.get("jigsawImageUrl")

        log_fields(验证码Token=token[:10] + "...")

        try:
            import requests
            bg_bytes = requests.get(bg_url, timeout=10, verify=False).content
            tmpl_bytes = requests.get(tmpl_url, timeout=10, verify=False).content
            raw_x = captcha_solver.solve_slider_notch(bg_bytes, tmpl_bytes)
            log_status("识别缺口", ok=True)
            log_fields(偏移量=f"{raw_x:.2f}px")
        except Exception as e:
            log_status("识别缺口", ok=False)
            log_error(str(e))
            raw_x = 120.0

        v_res, enc_point = client.verify_slider_captcha(token, raw_x)
        if v_res.get("code") != 0:
            log_status("校验滑块", ok=False)
            log_error(v_res.get("message", "校验被拒绝"))
            log_detail(v_res)
            return

        log_status("校验滑块", ok=True)
        l_res = client.login_by_password(args.mobile, args.password, captcha_point=enc_point)

    if l_res.get("code") == 0 and l_res.get("data"):
        data = l_res["data"]
        log_status("账号登录", ok=True)
        log_fields(
            用户ID=data.get("userId"),
            Token=data.get("token")[:16] + "...",
            SaToken=data.get("satoken")[:16] + "...",
            学校代码=data.get("schoolCode")
        )
        if data.get("alertTip"):
            tip = data["alertTip"]
            log_fields(提示=f"{tip.get('title')}: {tip.get('content')}")
    else:
        log_status("账号登录", ok=False)
        log_error(l_res.get("message", "登录失败"))
        log_detail(l_res)

if __name__ == "__main__":
    main()
