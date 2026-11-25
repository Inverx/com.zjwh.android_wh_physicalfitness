"""人脸识别与底图认证管理命令行工具。"""
import argparse
import json
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from client import ShanDongClient
from logger import log_status, log_fields, log_error, log_detail

def main():
    parser = argparse.ArgumentParser(description="人脸识别与底图认证管理")
    parser.add_argument("--bind", help="首次绑定人脸底图 (传入已上传 OSS 的图片 URL)")
    parser.add_argument("--update", help="更新已有人脸底图 (传入新图片 OSS URL)")
    parser.add_argument("--close", action="store_true", help="关闭账号人脸识别功能")
    parser.add_argument("--token-oss", action="store_true", help="拉取阿里云 OSS 临时 STS 鉴权令牌")
    parser.add_argument("--token", help="临时传入 Token 凭证")
    parser.add_argument("--transport", default="direct", choices=["direct", "adb", "proxy"], help="网络传输模式")
    parser.add_argument("--proxy", help="代理服务器地址")
    parser.add_argument("--adb-path", help="ADB 命令路径")
    parser.add_argument("--adb-device", help="ADB 目标设备编号")
    args = parser.parse_args()

    client = ShanDongClient(
        token=args.token,
        transport_mode=args.transport,
        proxy=args.proxy,
        adb_path=args.adb_path,
        adb_device=args.adb_device
    )
    if not client.transport.token:
        log_status("载入会话", ok=False)
        log_error("未检测到有效会话，请先执行 login_cli.py 进行验证")
        return

    log_status("载入会话", ok=True)
    log_fields(Token=client.transport.token[:12] + "...", 设备=client.transport.model_name)

    # 1. 获取 OSS STS 凭证
    if args.token_oss:
        log_status("获取上传凭证", ok=True)
        oss_res = client.get_oss_token()
        if oss_res.get("code") == 0 and oss_res.get("data"):
            od = oss_res["data"]
            log_fields(
                AccessKeyId=od.get("accessKeyId"),
                Expiration=od.get("expiration"),
                Token长度=len(od.get("securityToken", "")),
                状态="有效"
            )
        else:
            log_status("获取上传凭证", ok=False)
            log_error(oss_res.get("message", "获取失败"))
            log_detail(oss_res)
        return

    # 2. 首次绑定人脸底图
    if args.bind:
        log_status("首次认证绑定", ok=True, status_text="提交")
        log_fields(底图URL=args.bind)
        b_res = client.bind_user_face(args.bind)
        if b_res.get("code") == 0:
            log_status("首次认证绑定", ok=True)
            log_fields(结果="已通过认证")
        else:
            log_status("首次认证绑定", ok=False)
            log_error(b_res.get("message", "绑定失败"))
            log_detail(b_res)
        return

    # 3. 更新人脸底图
    if args.update:
        log_status("更新人脸底图", ok=True, status_text="提交")
        log_fields(新底图URL=args.update)
        u_res = client.update_user_face(args.update)
        if u_res.get("code") == 0:
            log_status("更新人脸底图", ok=True)
            log_fields(结果="已替换底图")
        else:
            log_status("更新人脸底图", ok=False)
            log_error(u_res.get("message", "更新失败"))
            log_detail(u_res)
        return

    # 4. 关闭人脸识别功能
    if args.close:
        log_status("关闭人脸认证", ok=True, status_text="提交")
        c_res = client.close_user_face()
        if c_res.get("code") == 0:
            log_status("关闭人脸认证", ok=True)
        else:
            log_status("关闭人脸认证", ok=False)
            log_error(c_res.get("message", "关闭失败"))
            log_detail(c_res)
        return

    # 5. 默认查询人脸认证状态
    log_status("查询人脸认证状态", ok=True)
    res = client.get_user_face_img()
    if res.get("code") == 0 and res.get("data"):
        data = res["data"]
        auth_status = "已认证" if data.get("faceAuth") else "未认证"
        enabled_status = "启用" if data.get("faceEnabled") == 1 else "关闭"
        model_str = "本地模型" if data.get("faceModelType") == 2 else f"模式{data.get('faceModelType')}"
        img_url = data.get("faceImg")

        log_fields(
            认证状态=auth_status,
            功能状态=enabled_status,
            相似度阈值=f"{data.get('similarityValue', 0)}%",
            算法引擎=model_str,
            底图在库="是" if img_url else "否",
            底图地址=img_url or "无"
        )
    else:
        log_status("查询人脸认证状态", ok=False)
        log_error(res.get("message", "查询异常"))
        log_detail(res)

if __name__ == "__main__":
    main()
