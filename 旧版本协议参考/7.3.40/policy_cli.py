import argparse
import json
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from sport_client import SportClient


def main():
    print("运动世界校园 / 跑步规则")
    print()

    parser = argparse.ArgumentParser(description="查询跑步规则和电子围栏")
    parser.add_argument("-t", "--token", help="登录 Token")
    parser.add_argument("-u", "--uid", help="用户 UID")
    parser.add_argument("--unid", help="学校 UNID")
    parser.add_argument("-m", "--mode", default="1", choices=["1", "2", "3", "5"], help="运动模式：1 计分跑，2 自由跑，5 室内锻炼")
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

    unid = args.unid
    if not unid:
        try:
            unid_str = input("学校 UNID（可留空）: ").strip()
            unid = int(unid_str) if unid_str else 0
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return
        except ValueError:
            unid = 0
    else:
        unid = int(unid)

    mode = int(args.mode)
    client = SportClient(uid=uid, token=token, unid=unid, proxy=args.proxy)

    print(f"正在查询模式 {mode} 的跑步规则...")
    res = client.get_run_policy(run_mode=mode)
    res_fence = client.get_geo_fence()

    if res.get("error") == 10000 and "data" in res and res["data"]:
        d = res["data"]
        rule = d.get("runRuleModel", {})
        face = d.get("runFaceCheckConfigDTO", {})
        step_top = rule.get("stepTop", "-")
        step_bottom = rule.get("stepBottom", "-")
        step_top_text = "不限" if step_top in (0, "0") else f"{step_top} 步/分钟"
        step_bottom_text = "不限" if step_bottom in (0, "0") else f"{step_bottom} 步/分钟"

        print("\n查询结果")
        print(f"单日上限: {rule.get('dayGoal', '-')} 米")
        print(f"单次最低: {rule.get('minDistance', '-')} 米")
        print(f"最高配速: {rule.get('speedTop', '-')} 分钟/公里")
        print(f"最低配速: {rule.get('speedBottom', '-')} 分钟/公里")
        print(f"最高步频: {step_top_text}")
        print(f"最低步频: {step_bottom_text}")

        valid_times = rule.get("validTime", [])
        if valid_times:
            time_str = ", ".join([f"{t.get('start', '')}~{t.get('end', '')}" for t in valid_times])
            print(f"有效时段: {time_str}")

        print()
        print(f"人脸抽检: {'开启' if face.get('enable') else '关闭'}")
        if face.get("enable"):
            print(f"抽检距离: {face.get('checkPointMin', 0)}~{face.get('checkPointMax', 0)} 米")
            print(f"检测时长: {face.get('checkRunValidTime', 0)} 秒")

        if res_fence.get("error") == 10000 and "data" in res_fence:
            geo_list = res_fence["data"].get("geoFences", []) or []
            print(f"电子围栏: {len(geo_list)} 个")

        print()
    else:
        print("\n查询失败")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        print()


if __name__ == "__main__":
    main()
