"""跑步历史记录分页与详情穿透命令行工具。"""
import argparse
import datetime
import os
import sys
import time

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from client import ShanDongClient
from logger import log_status, log_fields, log_error, log_detail

def format_record_line(r: dict, r_type: str = "阳光跑") -> None:
    """输出单条记录字段化概要。"""
    start_ts = r.get("startTime") or r.get("createTime")
    time_str = "未知"
    if start_ts:
        try:
            dt = datetime.datetime.fromtimestamp(int(start_ts) / 1000)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

    dist_m = r.get("distance") or r.get("validDistance") or 0
    dur_s = r.get("duration") or 0
    dur_str = f"{dur_s // 60}分{dur_s % 60}秒" if dur_s else "0秒"
    pace = r.get("pace") or 0
    p_str = f"{pace // 60}分{pace % 60}秒" if pace else "无"
    
    status_code = r.get("sunRunRecordStatus") or r.get("status") or 0
    status_map = {1: "达标", 2: "已完成", 3: "作弊/无效", 4: "机审未通过"}
    status_text = status_map.get(status_code, "有效" if status_code in [1, 2] else "未知")
    r_code = r.get("runRecordCode") or "无单号"
    steps = r.get("totalStep") or 0
    cal = r.get("calorie") or 0
    cal_str = f"{cal/1000.0 if cal>1000 else cal:.1f}kcal"

    log_fields(
        类型=r_type,
        单号=r_code,
        时间=time_str,
        里程=f"{dist_m}m",
        耗时=dur_str,
        配速=p_str,
        步数=steps,
        热量=cal_str,
        状态=status_text
    )

def show_record_detail(client: ShanDongClient, run_record_code: str):
    """穿透查询单笔跑单详情与机审报告。"""
    log_status(f"查询跑单详情 {run_record_code}", ok=True)
    res = client.run_record_detail(run_record_code)
    if res.get("code") != 0 or not res.get("data"):
        log_status("查询跑单详情", ok=False)
        log_error(res.get("message", "查询失败"))
        log_detail(res)
        return

    d = res["data"]
    sport_type_str = "阳光跑" if d.get("sportType") == 1 else "自由跑" if d.get("sportType") == 2 else f"运动{d.get('sportType')}"
    dist_m = d.get("validDistance") or d.get("distance", 0)
    dur_s = d.get("duration", 0)
    dur_str = f"{dur_s // 60}分{dur_s % 60}秒"
    pace_s = d.get("pace", 0)
    pace_str = f"{pace_s // 60}分{pace_s % 60}秒/km"
    status_val = d.get("status", 0)
    status_str = "正常达标" if status_val in [1, 2] else f"状态代码{status_val}"

    log_status("跑单全量数据", ok=True)
    log_fields(
        跑单编号=run_record_code,
        运动类型=sport_type_str,
        有效里程=f"{dist_m}m",
        实际耗时=dur_str,
        平均配速=pace_str,
        总步数=f"{d.get('totalStep', 0)}步",
        平均步频=f"{d.get('frequency', 0)}步/分",
        消耗热量=f"{d.get('calorie', 0)}cal",
        最终状态=status_str
    )

    # 1. 必经打卡点核验
    t_points = d.get("targetPoints") or d.get("faceClockList") or []
    if t_points:
        log_status("打卡点位核验", ok=True)
        log_fields(打卡点总数=len(t_points))
        for i, tp in enumerate(t_points, 1):
            passed = tp.get("passStatus", False)
            log_fields(点位=f"第{i}点", 坐标=f"({tp.get('lat')}, {tp.get('lng')})", 状态="已打卡" if passed else "未打卡")

    # 2. GPS 轨迹采样
    pois = d.get("pois", [])
    if pois:
        log_status("轨迹采样数据", ok=True)
        log_fields(
            采样点总数=len(pois),
            起点=f"({pois[0].get('lat')}, {pois[0].get('lng')})",
            终点=f"({pois[-1].get('lat')}, {pois[-1].get('lng')})",
            采样密度=f"{(dist_m / max(1, len(pois))):.1f}m/点"
        )

    # 3. 分段配速
    paces = d.get("paceList", [])
    if paces:
        log_status("分段配速切片", ok=True)
        log_fields(切片包数=len(paces))
        for idx, pc in enumerate(paces[:5], 1):
            if isinstance(pc, dict):
                log_fields(分段=f"第{idx}段", 距离=f"{pc.get('distance', 50)}m", 用时=f"{pc.get('time', 0)}s")
            elif isinstance(pc, (int, float)):
                log_fields(分段=f"第{idx}公里", 配速=f"{int(pc)//60}分{int(pc)%60}秒/km")

    # 4. 离线机审报告
    audit = d.get("auditDetail", [])
    if not audit:
        log_status("官方离线机审", ok=True, status_text="零异常通过")
    else:
        log_status("官方离线机审", ok=False, status_text="触发异常")
        log_error(f"异常判定项: {audit}")

def scroll_fetch_records(client: ShanDongClient, r_type: str = "sun", page_size: int = 10, max_pages: int = 10, semester_code: str = "current") -> list:
    """分页拉取跑单记录。"""
    all_records = []
    current_page = 1
    sc = "" if semester_code == "current" else semester_code

    while current_page <= max_pages:
        if r_type == "sun":
            res = client.page_sun_run_record(page_num=current_page, page_size=page_size, semester_code=sc)
        else:
            res = client.page_free_run_record_list(page_num=current_page, page_size=page_size)

        if res.get("code") != 0 or not res.get("data"):
            if current_page == 1:
                log_status(f"查询第 {current_page} 页记录", ok=False)
                log_error(res.get("message", "查询失败"))
                log_detail(res)
            break

        r_list = res["data"].get("list", [])
        if not r_list:
            break

        log_status(f"加载第 {current_page} 页", ok=True)
        log_fields(获取条数=len(r_list))
        for r in r_list:
            all_records.append(r)
            type_label = "阳光跑" if r_type == "sun" else "自由跑"
            format_record_line(r, type_label)

        if len(r_list) < page_size:
            break

        current_page += 1
        time.sleep(0.3)

    return all_records

def main():
    parser = argparse.ArgumentParser(description="跑步历史记录分页与详情查询")
    parser.add_argument("-t", "--type", choices=["sun", "free", "all"], default="sun", help="跑步类型: sun (阳光跑, 默认), free (自由跑), all (全部)")
    parser.add_argument("-s", "--size", type=int, default=10, help="每页拉取条数 (默认 10，最低 5)")
    parser.add_argument("-m", "--max-pages", type=int, default=10, help="持续分页最大页数 (默认 10)")
    parser.add_argument("-sem", "--semester", default="current", help="指定学期代码: current (当前学期, 默认), 12, 11, 10 等")
    parser.add_argument("--detail", help="查看指定单号的完整跑单详情与轨迹报告")
    parser.add_argument("--token", help="临时传入 Token 凭证")
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
    log_fields(Token=client.transport.token[:10] + "...", 最大页数=args.max_pages, 单页条数=args.size)

    if args.detail:
        show_record_detail(client, args.detail)
        return

    # 1. 查询概况
    sc = "" if args.semester == "current" else args.semester
    sum_res = client.query_sun_run_abstract_info_v2(semester_code=sc)
    if sum_res.get("code") == 0 and sum_res.get("data"):
        s_data = sum_res["data"]
        log_status("查询学期跑量总览", ok=True)
        log_fields(
            学期已跑=f"{s_data.get('doneDistance', 0)}m",
            本周已跑=f"{s_data.get('weekAlreadyTimes', 0)}次",
            本周剩余=f"{s_data.get('weekRemainTimes', 0)}次",
            有效状态="正常" if s_data.get("validStatus") else "异常"
        )

    # 2. 连续分页获取
    total_count = 0
    if args.type in ["sun", "all"]:
        log_status("拉取阳光跑记录", ok=True, status_text="开始")
        sun_recs = scroll_fetch_records(client, r_type="sun", page_size=max(5, args.size), max_pages=args.max_pages, semester_code=args.semester)
        total_count += len(sun_recs)
        log_status("拉取阳光跑记录", ok=True, status_text="完成")
        log_fields(累计条数=f"{len(sun_recs)}条")

    if args.type in ["free", "all"]:
        log_status("拉取自由跑记录", ok=True, status_text="开始")
        free_recs = scroll_fetch_records(client, r_type="free", page_size=max(5, args.size), max_pages=args.max_pages, semester_code=args.semester)
        total_count += len(free_recs)
        log_status("拉取自由跑记录", ok=True, status_text="完成")
        log_fields(累计条数=f"{len(free_recs)}条")

    log_status("全部记录巡检", ok=True, status_text="完成")
    log_fields(总记录数=f"{total_count}条")

if __name__ == "__main__":
    main()
