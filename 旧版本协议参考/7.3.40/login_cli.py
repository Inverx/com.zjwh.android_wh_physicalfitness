import argparse
import json
import os
import sys
import time

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from sport_client import SportClient
from security_utils import mask_secret, redact_data


def print_banner():
    print("运动世界校园 / 登录")
    print()


def format_login_success(data: dict):
    sex = {1: "男", 2: "女"}.get(data.get("sex"), "未设置")
    print()
    print("登录成功")
    print(f"姓名: {data.get('name', '未设置')}")
    print(f"学号/工号: {mask_secret(data.get('campusId', '未设置'))}")
    print(f"学校: {data.get('campusName', '未设置')}")
    print(f"院系: {data.get('depart', '未设置')}")
    print(f"班级: {data.get('gradeClass', '未设置')}")
    print(f"UID: {mask_secret(data.get('uid', '-'))}")
    print(f"UNID: {data.get('unid', '-')}")
    print(f"性别: {sex}")
    print(f"Token: {mask_secret(data.get('token', '-'))}")
    print()


def format_login_error(res: dict):
    print()
    print("登录失败")
    code = res.get("error", res.get("code", "未知"))
    msg = res.get("message", res.get("errorMsg", "未知错误"))
    print(f"错误码: {code}")
    print(f"原因: {msg}")
    if code in (10003, 10004):
        print("建议: 检查账号和密码")
    elif code == 18001:
        print("建议: 先在手机 App 完成设备绑定")
    elif code == 18002:
        print("建议: 在手机 App 确认切换设备")
    else:
        print("响应:", json.dumps(redact_data(res), ensure_ascii=False))
    print()


def main():
    print_banner()

    parser = argparse.ArgumentParser(description="登录运动世界校园")
    parser.add_argument("-u", "--username", help="登录账号（手机号或学号）")
    parser.add_argument("-p", "--password", help="登录密码")
    parser.add_argument("--proxy", help="代理地址，例如 http://127.0.0.1:7890")
    args = parser.parse_args()

    username = args.username
    if not username:
        try:
            username = input("登录账号或学号: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            print("操作已取消")
            return

    if not username:
        print("错误: 账号不能为空")
        return

    password = args.password
    if not password:
        try:
            password = input("登录密码: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            print("操作已取消")
            return

    if not password:
        print("错误: 密码不能为空")
        return

    proxy = args.proxy
    if proxy:
        print(f"代理: {proxy}")

    client = SportClient(proxy=proxy)

    def progress_callback(msg: str):
        print(msg)

    start_time = time.time()
    try:
        resp = client.login(username=username, password=password, progress_callback=progress_callback)
        elapsed = time.time() - start_time
        print(f"耗时: {elapsed:.2f} 秒")

        if resp.get("error") == 10000 and "data" in resp and isinstance(resp["data"], dict):
            format_login_success(resp["data"])
        else:
            format_login_error(resp)

    except Exception as e:
        print()
        print(f"登录异常: {e}")


if __name__ == "__main__":
    main()
