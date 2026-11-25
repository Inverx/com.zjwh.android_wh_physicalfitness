"""校园长跑政策与电子围栏查询命令行工具。"""
import argparse
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from client import ShanDongClient
from logger import log_status, log_fields, log_error, log_detail

def main():
    parser = argparse.ArgumentParser(description="长跑方案与电子围栏信息查询")
    parser.add_argument("--token", help="临时指定 Token 凭证")
    parser.add_argument("--transport", default="direct", choices=["direct", "adb", "proxy"], help="网络传输模式")
    parser.add_argument("--proxy", help="代理服务器地址")
    parser.add_argument("--adb-path", help="ADB 命令路径")
    parser.add_argument("--adb-device", help="ADB 目标设备编号")
    args = parser.parse_args()

    client = ShanDongClient(
        token=args.token,
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
    log_fields(Token=client.transport.token[:12] + "...", 设备=client.transport.model_name)

    # 1. 跑步方案查询
    plan_res = client.get_run_plan_list()
    if plan_res.get("code") == 0 and plan_res.get("data"):
        p_list = plan_res["data"].get("list", [])
        log_status("查询跑步方案", ok=True)
        log_fields(方案总数=len(p_list))
        for p in p_list:
            log_fields(
                方案编号=p.get("runPlanCode"),
                方案名称=p.get("runPlanName"),
                方案状态="启用" if p.get("planStatus") == 1 else "停用",
                适用模式=p.get("applyModel")
            )
    else:
        log_status("查询跑步方案", ok=False)
        log_error(plan_res.get("message", "查询失败"))
        log_detail(plan_res)

    # 2. 电子围栏全量数据查询
    f_res = client.query_school_fences()
    if f_res.get("code") == 0 and f_res.get("data"):
        fences = f_res["data"]
        log_status("查询电子围栏", ok=True)
        log_fields(围栏总数=len(fences))
        for f in fences:
            if isinstance(f, dict):
                pts = f.get("fenceList") or f.get("fencePoints") or []
                clk = f"模式{f.get('clockMode', 3)}: 总计{f.get('totalGoalCounts', 3)}点 (必选{f.get('requiredPointCounts', 2)}+可选{f.get('optionalPointCounts', 1)})"
                face_sw = f.get("runSceneSwitch", {})
                face_str = "启用" if face_sw.get("faceRecognition") else "关闭"
                op_status = "全天开放" if f.get("openStatus") else "关闭"
                log_status(f"围栏 {f.get('fenceName')}", ok=True)
                log_fields(
                    围栏编号=f.get("fenceCode"),
                    所属校区=f.get("subSchoolName"),
                    中心坐标=f"({f.get('lat')}, {f.get('lng')})",
                    边界顶点数=len(pts),
                    打卡模式=clk,
                    开放状态=op_status,
                    人脸认证=face_str
                )
    else:
        log_status("查询电子围栏", ok=False)
        log_error(f_res.get("message", "查询失败"))
        log_detail(f_res)

    # 3. 当前推荐可用围栏
    rec_res = client.filter_usable_fence()
    if rec_res.get("code") == 0 and rec_res.get("data"):
        log_status("查询推荐围栏", ok=True)
        log_fields(推荐围栏编号=rec_res["data"].get("fenceCode"))

    # 4. 围栏教学指南视频
    v_res = client.transport.post("/common/runVideo", {"type": 1})
    if v_res.get("code") == 0 and v_res.get("data", {}).get("list"):
        log_status("查询教学视频", ok=True)
        for v in v_res["data"]["list"]:
            vt = v.get("type")
            v_label = "配速规则" if vt == 1 else "打卡距离" if vt == 2 else "打卡点位" if vt == 3 else f"指南{vt}"
            log_fields(类别=v_label, 视频地址=v.get("url"))

if __name__ == "__main__":
    main()
