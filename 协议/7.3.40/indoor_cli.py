import argparse
import json
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from sport_client import SportClient


def main():
    print("运动世界校园 / 室内锻炼")
    print()

    parser = argparse.ArgumentParser(description="提交室内锻炼记录")
    parser.add_argument("-t", "--token", help="登录 Token")
    parser.add_argument("-u", "--uid", help="用户 UID")
    parser.add_argument("--unid", default="0", help="学校 UNID（默认 0）")
    parser.add_argument("--time", type=int, help="锻炼时长，单位秒（默认 1200）")
    parser.add_argument("--steps", type=int, help="动作步数（默认 2000）")
    parser.add_argument("--calorie", type=int, help="消耗热量，单位千卡（默认 150）")
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

    duration = args.time
    if not duration:
        try:
            time_str = input("锻炼时长（秒，默认 1200）: ").strip()
            duration = int(time_str) if time_str else 1200
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return
        except ValueError:
            duration = 1200

    steps = args.steps
    if not steps:
        try:
            step_str = input("动作步数（默认 2000）: ").strip()
            steps = int(step_str) if step_str else 2000
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return
        except ValueError:
            steps = 2000

    calorie = args.calorie
    if not calorie:
        try:
            cal_str = input("消耗热量（千卡，默认 150）: ").strip()
            calorie = int(cal_str) if cal_str else 150
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return
        except ValueError:
            calorie = 150

    print("\n本次锻炼")
    print(f"时长: {duration} 秒")
    print(f"步数: {steps}")
    print(f"热量: {calorie} 千卡")

    client = SportClient(uid=uid, token=token, unid=int(args.unid), proxy=args.proxy)

    print("\n正在生成并提交记录...")

    res = client.submit_indoor_exercise(
        total_time_sec=duration,
        total_steps=steps,
        calorie=calorie
    )

    if res.get("error") == 10000 or res.get("code") == 0:
        print("\n提交成功")
    else:
        print("\n提交失败")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print()


if __name__ == "__main__":
    main()
