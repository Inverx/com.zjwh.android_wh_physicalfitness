# -*- coding: utf-8 -*-
import argparse
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from history.client import HistoryClient


def main():
    parser = argparse.ArgumentParser(description="运动世界 7.3.92 历史记录与成绩回查终端")
    parser.add_argument("-t", "--token", required=True, help="登录 Token")
    parser.add_argument("-u", "--uid", required=True, help="用户 UID")
    parser.add_argument("--unid", help="学校 UNID")
    parser.add_argument("-r", "--rrid", type=int, help="指定回查的单次跑步记录 RRID")
    parser.add_argument("-p", "--page", type=int, default=1, help="页码")
    args = parser.parse_args()

    client = HistoryClient(uid=args.uid, token=args.token, unid=args.unid)

    if args.rrid:
        detail = client.get_one_record(args.rrid)
        if detail:
            valid_str = "达标" if detail.is_valid else "未达标"
            print(f"记录回查: rrid={args.rrid} 状态={valid_str} 里程={detail.total_distance:.2f}m 有效里程={detail.valid_distance:.2f}m 耗时={detail.total_time}s 配速={detail.avg_speed} 步频={detail.avg_step_freq}步/分 热量={detail.calorie}kcal")
        else:
            print(f"记录回查: 失败 rrid={args.rrid} 原因=未找到记录")
        return

    records_res = client.get_run_records(page_num=args.page)
    if isinstance(records_res, dict) and records_res.get("error") == 10000 and "data" in records_res:
        items = records_res["data"].get("recordList", []) or []
        print(f"历史记录: 页码={args.page} 条数={len(items)}")
        for it in items[:5]:
            status_str = "达标" if it.get("status") == 1 or it.get("isValid") else f"状态码={it.get('status')}"
            print(f"记录明细: rrid={it.get('rrid')} 里程={it.get('totalDis')}m 耗时={it.get('totalTime')}s 状态={status_str}")
    else:
        err_msg = records_res.get("message") if isinstance(records_res, dict) else "网络异常"
        print(f"历史记录: 失败 页码={args.page} 原因={err_msg}")

    cal_res = client.get_calendar_list()
    if isinstance(cal_res, dict) and cal_res.get("error") == 10000:
        print("打卡日历: 成功")
    else:
        cal_err = cal_res.get("message") if isinstance(cal_res, dict) else "网络异常"
        print(f"打卡日历: 失败 原因={cal_err}")


if __name__ == "__main__":
    main()
