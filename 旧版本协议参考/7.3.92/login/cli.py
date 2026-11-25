# -*- coding: utf-8 -*-
import argparse
import os
import sys
import time

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from .client import LoginClient
    from .models import UserProfile, LoginResult
except (ImportError, ValueError):
    from client import LoginClient
    from models import UserProfile, LoginResult


def main():
    parser = argparse.ArgumentParser(description="运动世界校园 7.3.92 纯协议登录终端")
    parser.add_argument("-u", "--username", required=True, help="登录账号 (手机号/学号)")
    parser.add_argument("-p", "--password", required=True, help="登录密码")
    args = parser.parse_args()

    client = LoginClient()

    def on_progress(msg: str):
        print(msg)

    start_time = time.time()
    result = client.login(args.username, args.password, progress_callback=on_progress)
    elapsed = time.time() - start_time

    if result.success and result.user:
        u = result.user
        print(f"登录结果: 成功 姓名={u.name} 性别={u.sex} 学校={u.campus_name} 学院={u.depart} 班级={u.grade_class} 学号={u.campus_id} uid={u.uid} unid={u.unid} token={u.token} 耗时={elapsed:.2f}s")
    else:
        print(f"登录结果: 失败 code={result.error_code} 原因={result.message} 耗时={elapsed:.2f}s")


if __name__ == "__main__":
    main()
