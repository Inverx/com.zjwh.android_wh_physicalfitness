# -*- coding: utf-8 -*-
import argparse
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from running.client import RunningClient


def main():
    parser = argparse.ArgumentParser(description="运动世界 7.3.92 跑步提交与 OBS 归档终端")
    parser.add_argument("-t", "--token", required=True, help="登录 Token")
    parser.add_argument("-u", "--uid", required=True, help="用户 UID")
    parser.add_argument("--unid", help="学校 UNID")
    parser.add_argument("-d", "--distance", type=int, default=2150, help="跑步目标距离 (米)")
    parser.add_argument("-s", "--seconds", type=int, default=760, help="跑步总耗时 (秒)")
    parser.add_argument("-m", "--mode", type=int, default=1, choices=[1, 6], help="运动类型: 1计分跑 6自由跑")
    args = parser.parse_args()

    client = RunningClient(uid=args.uid, token=args.token, unid=args.unid)
    res = client.execute_full_run(
        target_distance_m=args.distance,
        target_time_sec=args.seconds,
        sport_type=args.mode,
        progress_callback=print
    )

    mode_name = "计分跑" if args.mode == 1 else "自由跑"
    if res.success:
        valid_str = "达标" if res.is_valid is True else ("未达标" if res.is_valid is False else "待核验")
        print(f"跑步提交: 成功 模式={mode_name} rrid={res.rrid} 里程={res.total_distance}m 耗时={res.total_time}s 状态={valid_str}")
    else:
        print(f"跑步提交: 失败 模式={mode_name} code={res.error_code} 原因={res.message}")

    return 0 if res.success and res.is_valid is True else 1


if __name__ == "__main__":
    sys.exit(main())
