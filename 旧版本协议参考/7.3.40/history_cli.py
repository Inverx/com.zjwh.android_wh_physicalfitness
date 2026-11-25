import argparse
import datetime
import json
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from sport_client import SportClient


def format_ts(ts_ms):
    if not ts_ms:
        return "-"
    try:
        dt = datetime.datetime.fromtimestamp(ts_ms / 1000.0)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts_ms)


def format_pace(seconds, meters):
    if not meters or meters <= 0 or not seconds or seconds <= 0:
        return "-"
    km = meters / 1000.0
    sec_per_km = seconds / km
    m = int(sec_per_km // 60)
    s = int(sec_per_km % 60)
    return f"{m}'{s:02d}\""


def main():
    print("运动世界校园 / 运动记录")
    print()

    parser = argparse.ArgumentParser(description="查询运动记录")
    parser.add_argument("-t", "--token", help="登录 Token")
    parser.add_argument("-u", "--uid", help="用户 UID")
    parser.add_argument("-p", "--page", default=1, type=int, help="页码（默认 1）")
    parser.add_argument("-s", "--size", default=10, type=int, help="每页条数（默认 10）")
    parser.add_argument("--type", default="outdoor", choices=["outdoor", "indoor"], help="记录类型：outdoor 室外，indoor 室内")
    parser.add_argument("--proxy", help="代理地址")
    args = parser.parse_args()

    token = args.token
    if not token:
        try:
            token = input("登录 Token: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            print("操作已取消")
            return

    if not token:
        print("错误: Token 不能为空")
        return

    uid = args.uid
    if not uid:
        try:
            uid = input("用户 UID: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            print("操作已取消")
            return

    if not uid:
        print("错误: UID 不能为空")
        return

    client = SportClient(uid=uid, token=token, proxy=args.proxy)

    if args.type == "outdoor":
        print(f"正在查询室外记录（第 {args.page} 页）...")
        res = client.get_run_history(page_num=args.page, page_size=args.size, sid=0, sport_type=1)
    else:
        print(f"正在查询室内记录（第 {args.page} 页）...")
        res = client.get_indoor_history(page_num=args.page, page_size=args.size)

    if res.get("error") == 10000 and "data" in res:
        records = res["data"]
        print(f"\n第 {args.page} 页")
        if isinstance(records, list) and records:
            for idx, r in enumerate(records, start=1):
                t_str = format_ts(r.get("startTime", r.get("sportDate", 0)))
                dis = float(r.get("totalDis", r.get("validDis", 0.0)))
                dur = int(r.get("totalTime", r.get("validTime", 0)))
                pace = format_pace(dur, dis)
                pace_text = f"{pace}/公里" if pace != "-" else "-"
                steps = r.get("avgStepFreq", "-")
                status = "达标" if r.get("complete", True) else "未达标"
                dur_min = f"{dur//60}分{dur%60}秒"
                print(f"{idx}. {t_str} | {dis:.1f} 米 | {dur_min} | {pace_text} | 步频 {steps} | {status}")
        else:
            print("暂无记录")
        print()
    else:
        print("\n查询失败")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        print()


if __name__ == "__main__":
    main()
