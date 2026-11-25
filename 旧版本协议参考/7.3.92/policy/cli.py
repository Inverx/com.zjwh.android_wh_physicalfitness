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

from policy.client import PolicyClient


def main():
    parser = argparse.ArgumentParser(description="运动世界 7.3.92 跑步规则与地理围栏终端")
    parser.add_argument("-t", "--token", help="登录 Token")
    parser.add_argument("-u", "--uid", help="用户 UID")
    parser.add_argument("--unid", help="学校 UNID")
    parser.add_argument("-m", "--mode", type=int, default=1, choices=[1, 2, 3, 5, 6], help="模式: 1计分跑 6自由跑")
    args = parser.parse_args()

    if not args.token or not args.uid:
        print("跑步规则: 失败 原因=缺少Token或UID")
        return

    client = PolicyClient(uid=args.uid, token=args.token, unid=args.unid)
    mode_name = "计分跑" if args.mode == 1 else "自由跑"

    # 1. 跑步规则
    rule = client.get_run_policy(run_mode=args.mode)
    if rule:
        face_str = f"已开启({rule.face_check.check_point_min}~{rule.face_check.check_point_max}次)" if rule.face_check.enable else "未开启"
        valid_time_str = ",".join(rule.valid_times) if rule.valid_times else "全天"
        print(f"跑步规则: 模式={mode_name} 单日上限={rule.day_goal}m 单次最低={rule.min_distance}m 配速={rule.speed_top}~{rule.speed_bottom}分/km 步频={rule.step_top}~{rule.step_bottom}步/分 人脸抽检={face_str} 时段={valid_time_str}")
    else:
        print(f"跑步规则: 失败 模式={mode_name} 原因=规则查询为空")

    # 2. 地理围栏
    fences = client.get_geo_fence()
    print(f"地理围栏: 围栏数={len(fences)}")
    for idx, f in enumerate(fences, 1):
        print(f"围栏明细: 序号={idx} id={f.fence_id} 名称={f.fence_name} 边界点数={len(f.polygon_points)} 打卡点数={len(f.check_points)}")

    # 3. 学期进度
    sem = client.get_semester_info(run_mode=args.mode)
    if sem:
        print(f"学期进度: 学期={sem.semester_name} 已完成={sem.total_completed_distance}km 目标={sem.target_distance}km 剩余={sem.remaining_distance}km 有效次数={sem.valid_count}")
    else:
        print(f"学期进度: 失败 模式={mode_name} 原因=查询为空")


if __name__ == "__main__":
    main()
