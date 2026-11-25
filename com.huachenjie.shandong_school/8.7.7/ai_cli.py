"""AI 室内运动一键结算命令行工具。"""
import argparse
import datetime
import os
import sys
import time

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from client import ShanDongClient
from logger import log_status, log_fields, log_error, log_detail

SPORT_NAMES = {
    1: "深蹲",
    2: "开合跳",
    3: "跳绳",
    4: "高抬腿",
    5: "俯卧撑",
    6: "平板支撑",
    7: "下蹲开合跳",
    8: "水平开合跳",
    9: "深蹲跳",
    10: "仰卧起坐",
    11: "波比跳",
    12: "卷腹",
    13: "坐位体前屈"
}

def list_categories(client: ShanDongClient):
    """查询可用 AI 动作清单。"""
    log_status("查询动作清单", ok=True)
    res = client.get_ai_categories()
    if res.get("code") == 0 and res.get("data"):
        data = res["data"]
        for group_name, items in data.items():
            if isinstance(items, list):
                log_status(f"分类 {group_name}", ok=True)
                log_fields(动作总数=len(items))
                for it in items:
                    t = it.get("sportType")
                    n = it.get("sportName")
                    dur = it.get("exerciseTime", 60)
                    log_fields(编号=t, 动作=n, 规定时长=f"{dur}s")
    else:
        log_status("查询动作清单", ok=False)
        log_error(res.get("message", "查询失败"))
        log_detail(res)

def show_history(client: ShanDongClient, sport_type: int):
    """查询指定动作的历史打卡。"""
    name = SPORT_NAMES.get(sport_type, f"动作{sport_type}")
    log_status(f"查询历史打卡 {name}", ok=True)
    page_res = client.get_sports_page(sport_type=sport_type, page_num=1, page_size=10)
    if page_res.get("code") == 0 and page_res.get("data"):
        d = page_res["data"]
        records = d.get("list", [])
        log_fields(总计记录=d.get("total", len(records)))
        for r in records:
            st = r.get("startTime", 0)
            t_str = "未知"
            if st:
                try:
                    t_str = datetime.datetime.fromtimestamp(st / 1000).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
            cnt = r.get("completeCount", 0)
            dur = r.get("duration", 0)
            cal = r.get("calorie", 0)
            log_fields(时间=t_str, 完成=f"{cnt}个", 用时=f"{dur}s", 消耗=f"{cal}cal")
    else:
        log_status("查询历史记录", ok=False)
        log_error(page_res.get("message", "查询异常"))
        log_detail(page_res)

def main():
    parser = argparse.ArgumentParser(description="AI 室内运动一键结算")
    parser.add_argument("-s", "--sport", type=int, default=2, choices=list(SPORT_NAMES.keys()),
                        help="运动类型: 1=深蹲, 2=开合跳(默认), 3=跳绳, 4=高抬腿, 5=俯卧撑, 6=平板支撑...")
    parser.add_argument("-c", "--count", type=int, default=35, help="完成动作次数 (默认 35)")
    parser.add_argument("-d", "--duration", type=int, default=62, help="实际用时秒数 (默认 62)")
    parser.add_argument("-l", "--list", action="store_true", help="列出全部可用的 AI 运动动作分类")
    parser.add_argument("--history", action="store_true", help="查看指定动作的历史打卡记录")
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
    log_fields(Token=client.transport.token[:12] + "...", 模式="AI室内运动结算")

    if args.list:
        list_categories(client)
        return

    if args.history:
        show_history(client, args.sport)
        return

    sport_name = SPORT_NAMES.get(args.sport, "未知运动")
    log_status(f"发起运动结算 {sport_name}", ok=True, status_text="开始")
    log_fields(项目=sport_name, 设定完成数=f"{args.count}次", 设定用时=f"{args.duration}秒")

    t0 = time.time()
    res = client.execute_complete_ai_exercise(
        sport_type=args.sport,
        total=args.count,
        duration=args.duration
    )
    elapsed = time.time() - t0

    if res.get("code") == 0 and res.get("data"):
        data = res["data"]
        log_status(f"运动结算 {sport_name}", ok=True)
        log_fields(
            跑单代码=data.get("sportsRecordCode"),
            获得能量=f"+{data.get('energy', 0)}",
            消耗热量=f"{data.get('calorie', 0)}cal",
            记录耗时=f"{data.get('duration')}s",
            发包总耗时=f"{elapsed:.2f}s"
        )
    else:
        log_status(f"运动结算 {sport_name}", ok=False)
        log_error(res.get("message", "结算未通过"))
        log_detail(res)

if __name__ == "__main__":
    main()
