# -*- coding: utf-8 -*-
import argparse
import getpass
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

cur_dir = os.path.dirname(os.path.abspath(__file__))
if cur_dir not in sys.path:
    sys.path.insert(0, cur_dir)

from sport_client import SportClient792
from security_utils import mask_secret, redact_text
from history.models import RunRecordDetail


def main():
    parser = argparse.ArgumentParser(description="运动世界校园 7.3.92 纯协议套件")
    parser.add_argument("-u", "--username", help="登录账号 (手机号)")
    parser.add_argument("-p", "--password", help="登录密码")
    parser.add_argument("-t", "--token", help="已有登录 Token")
    parser.add_argument("--uid", help="已有用户 UID")
    parser.add_argument("--unid", help="已有学校 UNID")
    parser.add_argument("--sync-time", action="store_true", help="执行服务端时间对齐")
    parser.add_argument("--rules", action="store_true", help="查询跑步规则与电子围栏")
    parser.add_argument("--profile", action="store_true", help="查询学生个人档案")
    parser.add_argument("--history", action="store_true", help="查询最近历史记录与打卡日历")

    # 跑步相关选项
    parser.add_argument("--run", action="store_true", help="触发一键全时序跑步与结算")
    parser.add_argument("--mode", type=int, default=1, choices=[1, 6], help="运动类型: 1计分跑 6自由跑")
    parser.add_argument("--distance", type=int, default=2150, help="跑步目标距离 (米，默认 2150)")
    parser.add_argument("--time-sec", type=int, default=760, help="跑步耗时 (秒，默认 760)")

    # 广告相关选项
    parser.add_argument("--watch-ad", action="store_true", help="模拟看广告与激励视频曝光链路")
    parser.add_argument("--ad-pos", default="4", choices=["1", "2", "4"], help="广告位: 1Banner 2弹窗 4激励视频(默认)")
    parser.add_argument("--ad-duration", type=int, default=15, help="广告观看耗时 (秒，默认 15)")

    parser.add_argument("--device-dir", help="设备配置保存目录（默认当前版本的 .device_profiles）")
    args = parser.parse_args()
    failed = False
    if args.password and not args.username:
        parser.error("密码参数需要同时提供账号")
    if args.username and args.password is None:
        args.password = getpass.getpass("登录密码: ")
    if args.username and not args.password:
        parser.error("密码不能为空")

    client = SportClient792(uid=args.uid, token=args.token, unid=args.unid,
                            account=args.username, device_dir=args.device_dir)

    # 1. 登录认证
    if args.username and args.password:
        res = client.login(args.username, args.password, progress_callback=lambda msg: print(redact_text(msg)))
        if not res.success:
            print(f"登录失败: code={res.error_code} 原因={res.message}")
            return 1
        print(f"登录成功: token={client.token} uid={client.uid} unid={client.unid}")

    # 2. 时钟对齐
    if args.sync_time or (not args.rules and not args.profile and not args.history and not args.run and not args.watch_ad):
        st = client.sync_server_time()
        if not st.synchronized:
            failed = True
            print(f"时钟同步: 失败 原因={st.error_message}")
        else:
            print(f"时钟同步: 服务端时间={st.server_datetime} 偏斜={st.offset_seconds:+.3f}s")

    # 3. 个人档案
    if args.profile:
        if not client.token:
            failed = True
            print("个人档案: 失败 原因=缺少Token")
        else:
            prof = client.get_user_profile()
            if prof:
                print(f"个人档案: 姓名={mask_secret(prof.name, keep=1)} 性别={prof.sex} 学校={prof.campus_name} 学院={prof.depart} 班级={prof.grade_class} 学号={mask_secret(prof.student_id)}")
            else:
                failed = True
                print("个人档案: 失败 原因=查询为空")

    # 4. 跑步规则与围栏
    if args.rules:
        if not client.token or not client.uid:
            failed = True
            print("跑步规则: 失败 原因=缺少Token或UID")
        else:
            rule = client.get_run_policy(run_mode=args.mode)
            fences = client.get_geo_fences() if rule else []
            mode_name = "计分跑" if args.mode == 1 else "自由跑"
            if rule:
                print(f"跑步规则: 模式={mode_name} 单日上限={rule.day_goal}m 单次最低={rule.min_distance}m 学校最短时长={rule.min_run_time_sec if rule.min_run_time_sec is not None else '未返回'}秒 配速={rule.speed_top}~{rule.speed_bottom}分/km 步频={rule.step_top}~{rule.step_bottom}步/分 围栏数={len(fences)}")
            else:
                failed = True
                reason = client.policy.last_policy_error or "规则查询为空"
                print(f"跑步规则: 失败 模式={mode_name} 原因={redact_text(reason)}")

    # 5. 广告模拟
    if args.watch_ad:
        ad_res = client.watch_ad(
            ad_position=args.ad_pos,
            duration_sec=args.ad_duration,
            progress_callback=lambda msg: print(redact_text(msg))
        )
        if ad_res.success:
            print(f"广告模拟: 成功 位置={args.ad_pos} 事件数={ad_res.events_count} 耗时={args.ad_duration}s")
        else:
            failed = True
            print(f"广告模拟: 失败 位置={args.ad_pos} 原因={ad_res.message}")

    # 6. 历史记录
    if args.history:
        if not client.token or not client.uid:
            failed = True
            print("历史记录: 失败 原因=缺少Token或UID")
        else:
            h_res = client.get_history_records(page_num=1, page_size=5)
            if isinstance(h_res, dict) and h_res.get("error") == 10000:
                recs = (h_res.get("data") or {}).get("recordList", []) or []
                print(f"历史记录: 条数={len(recs)}")
                for r in recs:
                    status_str = "达标" if RunRecordDetail.from_api_data(r).is_valid else "未达标或待核验"
                    print(f"记录明细: rrid={r.get('rrid')} 里程={r.get('totalDis')}m 耗时={r.get('totalTime')}s 状态={status_str}")
            else:
                err_msg = h_res.get("message") if isinstance(h_res, dict) else "网络异常"
                failed = True
                print(f"历史记录: 失败 原因={err_msg}")

    # 7. 拟人跑步提交
    if args.run:
        if not client.token or not client.uid:
            failed = True
            print("跑步提交: 失败 原因=缺少Token或UID")
        else:
            mode_name = "计分跑" if args.mode == 1 else "自由跑"
            run_res = client.execute_run(
                target_distance_m=args.distance,
                target_time_sec=args.time_sec,
                sport_type=args.mode,
                progress_callback=lambda msg: print(redact_text(msg))
            )
            if run_res.success:
                valid_str = "达标" if run_res.is_valid is True else ("未达标" if run_res.is_valid is False else "待核验")
                failed = failed or run_res.is_valid is not True
                print(f"跑步提交: 成功 模式={mode_name} rrid={run_res.rrid} 里程={run_res.total_distance}m 耗时={run_res.total_time}s 状态={valid_str}")
            else:
                failed = True
                print(f"跑步提交: 失败 模式={mode_name} code={run_res.error_code} 原因={run_res.message}")

    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"执行失败: {redact_text(exc)}")
        sys.exit(1)
