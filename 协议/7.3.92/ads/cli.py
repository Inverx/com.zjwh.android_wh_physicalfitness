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

from ads.client import AdClient


def main():
    parser = argparse.ArgumentParser(description="运动世界 7.3.92 广告与激励视频模拟终端")
    parser.add_argument("-t", "--token", required=True, help="登录 Token")
    parser.add_argument("-u", "--uid", required=True, help="用户 UID")
    parser.add_argument("--unid", default=None, help="学校 UNID")
    parser.add_argument("-pos", "--position", default="4", choices=["1", "2", "4"], help="广告位: 1Banner 2弹窗 4激励视频")
    parser.add_argument("-d", "--duration", type=int, default=15, help="观看时长 (秒)")
    args = parser.parse_args()

    client = AdClient(uid=args.uid, token=args.token, unid=args.unid)
    res = client.simulate_watch_ad(
        ad_position=args.position,
        duration_sec=args.duration,
        progress_callback=print
    )

    if res.success:
        print(f"广告模拟: 成功 位置={res.ad_position} 心跳数={res.events_count} 耗时={args.duration}s")
    else:
        print(f"广告模拟: 失败 位置={args.position} 原因={res.message}")

    return 0 if res.success else 1


if __name__ == "__main__":
    sys.exit(main())
