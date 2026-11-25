"""长跑业务接口调度工具。仅演示协议接口调用流程，具体轨迹生成算法请自行接入。"""
import argparse
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from client import ShanDongClient
from logger import log_status, log_fields, log_error, log_detail

def main():
    parser = argparse.ArgumentParser(description="长跑协议接口调度工具")
    parser.add_argument("-t", "--type", choices=["sun", "free"], default="sun", help="跑步类型: sun (阳光跑, 默认), free (自由跑)")
    parser.add_argument("-d", "--distance", type=int, default=2000, help="目标里程 (米)")
    parser.add_argument("-p", "--pace", type=int, default=360, help="平均配速 (秒/公里)")
    parser.add_argument("--plan-code", default="", help="长跑方案编号")
    parser.add_argument("--fence-code", default="", help="打卡电子围栏编号")
    parser.add_argument("--lat", type=float, default=0.0, help="起跑基准纬度")
    parser.add_argument("--lng", type=float, default=0.0, help="起跑基准经度")
    parser.add_argument("--token", help="临时指定 Token 凭证")
    parser.add_argument("--satoken", help="临时指定 SaToken 凭证")
    parser.add_argument("--transport", default="direct", choices=["direct", "adb", "proxy"], help="网络传输模式")
    parser.add_argument("--proxy", help="代理服务器地址")
    parser.add_argument("--adb-path", help="ADB 命令路径")
    parser.add_argument("--adb-device", help="ADB 目标设备编号")
    args = parser.parse_args()

    client = ShanDongClient(
        token=args.token,
        satoken=args.satoken,
        transport_mode=args.transport,
        proxy=args.proxy,
        adb_path=args.adb_path,
        adb_device=args.adb_device
    )
    if not client.transport.token:
        log_status("载入会话", ok=False)
        log_error("未检测到有效会话，请先执行 login_cli.py 进行验证")
        return

    log_status("载入会话", ok=True)
    log_fields(传输模式=args.transport, 设备机型=client.transport.model_name)

    # 1. 阳光跑业务流程
    if args.type == "sun":
        plan_code = args.plan_code
        if not plan_code:
            p_res = client.get_run_plan_list()
            if p_res.get("code") == 0 and p_res.get("data", {}).get("list"):
                plan_code = p_res["data"]["list"][0].get("runPlanCode", "")

        log_status("发起阳光跑起跑", ok=True, status_text="提交")
        log_fields(方案代码=plan_code or "未指定", 目标里程=f"{args.distance}m")

        start_res = client.start_sun_run_v2(
            run_plan_code=plan_code,
            target_distance=str(args.distance),
            lng=str(args.lng),
            lat=str(args.lat)
        )
        if start_res.get("code") != 0:
            log_status("发起阳光跑起跑", ok=False)
            log_error(start_res.get("message", "起跑失败"))
            log_detail(start_res)
            return

        run_record_code = start_res.get("data", {}).get("runRecordCode")
        log_status("发起阳光跑起跑", ok=True)
        log_fields(跑单编号=run_record_code)

        log_status("轨迹数据准备", ok=True, status_text="待完善")
        log_fields(说明="开源版本已剥离轨迹生成算法，请接入自备定位数据源后提交 finish_sun_run_v2 结算")

    # 2. 自由跑业务流程
    else:
        log_status("发起自由跑起跑", ok=True, status_text="提交")
        log_fields(目标里程=f"{args.distance}m", 起点经度=args.lng, 起点纬度=args.lat)

        start_res = client.start_free_run(
            aim_distance=str(args.distance),
            lng=str(args.lng),
            lat=str(args.lat)
        )
        if start_res.get("code") != 0:
            log_status("发起自由跑起跑", ok=False)
            log_error(start_res.get("message", "起跑失败"))
            log_detail(start_res)
            return

        run_record_code = start_res.get("data", {}).get("runRecordCode")
        log_status("发起自由跑起跑", ok=True)
        log_fields(跑单编号=run_record_code)

        log_status("轨迹数据准备", ok=True, status_text="待完善")
        log_fields(说明="开源版本已剥离轨迹生成算法，请接入自备定位数据源后提交 finish_free_run 结算")

if __name__ == "__main__":
    main()
