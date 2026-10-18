import argparse
import datetime
import json
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from sport_client import SportClient
from rank_protocol import RankType


def main():
    print("运动世界校园 / 排行榜")
    print()

    parser = argparse.ArgumentParser(description="查询校园排行榜")
    parser.add_argument("-t", "--token", help="登录 Token")
    parser.add_argument("-u", "--uid", help="用户 UID")
    parser.add_argument("--unid", help="学校 UNID")
    parser.add_argument("--type", default="1", choices=["1", "2", "3", "4", "5", "6"], help="榜单：1 个人，2 班级，3 院系，4 室内，5 历史，6 违规")
    parser.add_argument("--sort", default="1", choices=["1", "2"], help="周期：1 日榜，2 月榜")
    parser.add_argument("--gender", default="0", choices=["0", "1"], help="性别：0 女，1 男")
    parser.add_argument("--date", help="日期或月份（YYYY-MM-DD / YYYY-MM）")
    parser.add_argument("--range", default="2", choices=["1", "2", "3"], help="室内周期：1 日榜，2 周榜，3 月榜")
    parser.add_argument("--page", default=1, type=int, help="页码（默认 1）")
    parser.add_argument("--size", default=20, type=int, help="每页条数（默认 20）")
    parser.add_argument("--proxy", help="代理地址")
    args = parser.parse_args()

    token = args.token
    if not token:
        try:
            token = input("登录 Token: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return

    if not token:
        print("错误: Token 不能为空")
        return

    uid = args.uid
    if not uid:
        try:
            uid = input("用户 UID: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return

    if not uid:
        print("错误: UID 不能为空")
        return

    unid = args.unid
    if not unid:
        try:
            unid = input("学校 UNID（可留空）: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return

    client = SportClient(uid=uid, token=token, unid=int(unid or 0), proxy=args.proxy)
    choice = int(args.type)
    period_name = "日榜" if args.sort == "1" else "月榜"

    if choice == 1:
        gender_name = "女" if args.gender == "0" else "男"
        print(f"正在查询个人{period_name}（{gender_name}）...")
        res = client.get_main_rank(
            rank_type=RankType.PERSONAL,
            sort_type=int(args.sort),
            gender=int(args.gender),
            date_str=args.date,
        )
    elif choice == 2:
        print(f"正在查询班级{period_name}...")
        res = client.get_main_rank(
            rank_type=RankType.CLASS,
            sort_type=int(args.sort),
            date_str=args.date,
        )
    elif choice == 3:
        print(f"正在查询院系{period_name}...")
        res = client.get_main_rank(
            rank_type=RankType.DEPARTMENT,
            sort_type=int(args.sort),
            date_str=args.date,
        )
    elif choice == 4:
        range_name = {"1": "日榜", "2": "周榜", "3": "月榜"}[args.range]
        print(f"正在查询室内锻炼{range_name}...")
        res = client.get_indoor_rank(
            page_num=args.page,
            page_size=args.size,
            gender=int(args.gender),
            date_range=int(args.range),
        )
    elif choice == 5:
        print("正在查询历史排名...")
        res = client.get_history_rank(
            sort_type=int(args.sort),
            gender=int(args.gender),
            page_num=args.page,
            page_size=args.size,
        )
    elif choice == 6:
        print("正在查询违规通报...")
        res = client.get_cheat_list(page_num=args.page, page_size=args.size)

    if res.get("error") == 10000 and "data" in res:
        d = res["data"]
        print("\n查询结果")
        rank_list = d if isinstance(d, list) else d.get("rankList", d.get("list", []))
        if isinstance(rank_list, list) and rank_list:
            for idx, item in enumerate(rank_list[:args.size], start=1):
                if choice == 4:
                    order = item.get("order", idx)
                    name = item.get("name", "-")
                    print(f"{order}. {name} | {item.get('totalStep', 0)} 步")
                elif choice == 5:
                    ts_ms = item.get("date", 0)
                    date_str = datetime.datetime.fromtimestamp(ts_ms / 1000.0).strftime("%Y-%m-%d") if ts_ms else "-"
                    rank = item.get("rank", 0)
                    rank_text = f"第 {rank} 名" if rank > 0 else "未上榜"
                    print(f"{date_str} | {item.get('length', 0)} 米 | {rank_text}")
                elif choice == 6:
                    name = item.get("name", "-")
                    print(f"{idx}. {name} | {item.get('count', 0)} 次")
                else:
                    order = item.get("order", item.get("sort", idx))
                    name = item.get("name", "-")
                    print(f"{order}. {name} | {item.get('length', 0)} 米 | {item.get('num', 0)} 次")
        else:
            print("暂无数据")
        print()
    else:
        print("\n查询失败")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        print()


if __name__ == "__main__":
    main()
