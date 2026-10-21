# -*- coding: utf-8 -*-
import argparse
import getpass
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

from security_utils import mask_secret, redact_text

try:
    from .client import LoginClient
    from .models import UserProfile, LoginResult
except (ImportError, ValueError):
    from client import LoginClient
    from models import UserProfile, LoginResult


def main():
    parser = argparse.ArgumentParser(description="运动世界校园 7.3.92 纯协议登录终端")
    parser.add_argument("-u", "--username", required=True, help="登录账号 (手机号/学号)")
    parser.add_argument("-p", "--password", required=False, help="登录密码")
    args = parser.parse_args()

    if args.password is None:
        args.password = getpass.getpass("登录密码: ")
    if not args.password:
        parser.error("密码不能为空")

    client = LoginClient()

    def on_progress(msg: str):
        print(redact_text(msg))

    start_time = time.time()
    result = client.login(args.username, args.password, progress_callback=on_progress)
    elapsed = time.time() - start_time

    if result.success and result.user:
        u = result.user
        print(f"登录结果: 成功 姓名={mask_secret(u.name, keep=1)} uid={mask_secret(u.uid)} token=[REDACTED] 耗时={elapsed:.2f}s")
        return 0
    else:
        print(f"登录结果: 失败 code={result.error_code} 原因={result.message} 耗时={elapsed:.2f}s")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"登录失败: {redact_text(exc)}")
        sys.exit(1)
