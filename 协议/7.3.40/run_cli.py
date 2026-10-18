import argparse
import json
import os
import sys
import time

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from coordinate_utils import validate_coordinate
from security_utils import redact_data
from running_protocol import (
    OutdoorRunRecordBuilder,
    generate_synthetic_gps_track,
    validate_outdoor_record_consistency,
)


def main():
    print("运动世界校园 / 室外跑")
    print()

    parser = argparse.ArgumentParser(description="提交室外跑记录")
    parser.add_argument("-t", "--token", help="登录 Token")
    parser.add_argument("-u", "--uid", help="用户 UID")
    parser.add_argument("--unid", default="0", help="学校 UNID（默认 0）")
    parser.add_argument("-d", "--distance", type=float, help="跑步距离，单位米")
    parser.add_argument("--time", type=int, help="跑步用时，单位秒")
    parser.add_argument("--steps", type=int, help="跑步步数")
    parser.add_argument("--latitude", "--lat", dest="latitude", type=float,
                        help="跑步起点纬度（必须与设备定位锚点一致）")
    parser.add_argument("--longitude", "--lon", dest="longitude", type=float,
                        help="跑步起点经度（必须与设备定位锚点一致）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只生成并校验记录，不上传到服务器")
    parser.add_argument("--type", type=int, default=1, choices=[1, 4], help="类型：1 计分跑，4 自由跑（默认 1）")
    parser.add_argument("--proxy", help="代理地址")
    args = parser.parse_args()

    token = args.token
    if not token and not args.dry_run:
        try:
            token = input("登录 Token: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return

    if not token and not args.dry_run:
        print("错误: Token 不能为空")
        return

    uid = args.uid
    if not uid and not args.dry_run:
        try:
            uid = input("用户 UID: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return

    if not uid and not args.dry_run:
        print("错误: UID 不能为空")
        return

    distance = args.distance
    if distance is None:
        try:
            dist_str = input("跑步距离（米，默认 2000）: ").strip()
            distance = float(dist_str) if dist_str else 2000.0
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return
        except ValueError:
            distance = 2000.0

    duration = args.time
    if duration is None:
        try:
            time_str = input("跑步用时（秒，默认 720）: ").strip()
            duration = int(time_str) if time_str else 720
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return
        except ValueError:
            duration = 720

    steps = args.steps
    if steps is None:
        try:
            step_str = input("步数（默认按距离计算）: ").strip()
            steps = int(step_str) if step_str else int(distance * 1.05)
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return
        except ValueError:
            steps = int(distance * 1.05)

    latitude = args.latitude
    if latitude is None:
        try:
            value = input("跑步起点纬度（例如 39.9042）: ").strip()
            latitude = float(value)
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return
        except ValueError:
            print("错误: 纬度必须是数字")
            return

    longitude = args.longitude
    if longitude is None:
        try:
            value = input("跑步起点经度（例如 116.4074）: ").strip()
            longitude = float(value)
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return
        except ValueError:
            print("错误: 经度必须是数字")
            return

    try:
        coordinate = validate_coordinate(latitude, longitude)
    except ValueError as exc:
        print(f"错误: {exc}")
        return
    latitude, longitude = coordinate

    if distance <= 0 or duration <= 0 or steps < 0:
        print("错误: 距离和用时必须为正数，步数不能为负数")
        return

    pace_min = (duration / 60.0) / (distance / 1000.0)
    run_type = "计分跑" if args.type == 1 else "自由跑"
    print("\n本次跑步")
    print(f"类型: {run_type}")
    print(f"距离: {distance:.1f} 米")
    print(f"用时: {duration} 秒")
    print(f"步数: {steps}")
    print(f"定位锚点: {latitude:.6f}, {longitude:.6f}")
    print(f"配速: {pace_min:.2f} 分钟/公里")

    print("\n正在生成并提交记录..." if not args.dry_run else "\n正在生成并校验记录...")

    if args.dry_run:
        stop_time_ms = int(time.time() * 1000)
        start_time_ms = stop_time_ms - duration * 1000
        points, fixed_points = generate_synthetic_gps_track(
            latitude, longitude, int(round(distance)), duration, start_time_ms
        )
        _, record, _ = OutdoorRunRecordBuilder(
            uid=int(uid or 0), unid=int(args.unid), sport_type=args.type,
            sel_distance_m=int(round(distance)), sel_run_time_s=duration,
        ).build_record(
            int(round(distance)), duration, steps, start_time_ms, stop_time_ms,
            points, fixed_points,
        )
        res = {
            "error": 10000,
            "message": "dry-run: record generated and validated; nothing uploaded",
            "dryRun": True,
            "data": validate_outdoor_record_consistency(record),
        }
    else:
        from sport_client import SportClient
        client = SportClient(uid=uid, token=token, unid=int(args.unid), proxy=args.proxy)
        res = client.submit_outdoor_run(
            total_distance_m=distance,
            total_time_sec=duration,
            total_steps=steps,
            sport_type=args.type,
            start_lat=latitude,
            start_lon=longitude,
        )

    if res.get("error") == 10000 or res.get("code") == 0:
        print("\n" + ("校验通过（未上传）" if args.dry_run else "提交成功"))
    else:
        print("\n提交失败")
    print(json.dumps(redact_data(res), ensure_ascii=False, indent=2))
    print()


if __name__ == "__main__":
    main()
