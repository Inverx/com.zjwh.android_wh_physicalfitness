import argparse
import json
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from sport_client import SportClient


def main():
    print("运动世界校园 / 学期成绩")
    print()

    parser = argparse.ArgumentParser(description="查询学期成绩")
    parser.add_argument("-t", "--token", help="登录 Token")
    parser.add_argument("-u", "--uid", help="用户 UID")
    parser.add_argument("--unid", default="0", help="学校 UNID（默认 0）")
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

    client = SportClient(uid=uid, token=token, unid=int(args.unid or 0), proxy=args.proxy)

    print("正在查询学期成绩...")
    res_completed = client.get_semester_completed()
    res_config = client.get_history_config()

    if res_completed.get("error") == 10000:
        d = res_completed.get("data", {})
        print("\n查询结果")
        print(f"学期: {d.get('sname', '当前学期') or '当前学期'}")
        print(f"总里程: {d.get('semesterDis', 0)} 米")
        print(f"有效里程: {d.get('semesterValidDis', 0)} 米")
        print(f"跑步次数: {d.get('semesterCount', 0)} 次")
        print(f"有效次数: {d.get('semesterValidCount', 0)} 次")

        if res_config.get("error") == 10000 and "data" in res_config and res_config["data"]:
            cfg = res_config["data"][0].get("campusConfigModel", {})
            if cfg:
                print("\n学校标准")
                print(f"单日上限: 男 {cfg.get('maleDayUpper', '-')} 米 / 女 {cfg.get('femaleDayUpper', '-')} 米")
                print(f"单次最低: 男 {cfg.get('maleMinSingleDis', '-')} 米 / 女 {cfg.get('femaleMinSingleDis', '-')} 米")
                valid_t = cfg.get("randomValidTimes", [])
                if valid_t:
                    t_range = ", ".join([f"{x.get('startTime')}~{x.get('endTime')}" for x in valid_t])
                    print(f"有效时段: {t_range}")

        print()
    else:
        print("\n查询失败")
        print(json.dumps(res_completed, ensure_ascii=False, indent=2))
        print()


if __name__ == "__main__":
    main()
