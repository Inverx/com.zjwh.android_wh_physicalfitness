"""校园排行榜查询命令行工具。"""
import argparse
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from client import ShanDongClient
from logger import log_status, log_fields, log_error, log_detail

def check_distance_rank(client: ShanDongClient) -> None:
    """查询里程榜。"""
    res = client.get_rank_distance()
    if res.get("code") == 0 and res.get("data"):
        data = res["data"]
        my_rank = data.get("myRank", {})
        r_list = data.get("rankList", [])
        stage = my_rank.get("stageName") or "暂无"
        my_num = my_rank.get("rankNumber")
        rank_display = f"第 {my_num} 名" if (my_num and my_num > 0) else "未上榜"
        my_dist = my_rank.get("distance", 0)

        log_status("查询学期里程榜", ok=True)
        log_fields(
            个人名次=rank_display,
            累积里程=f"{my_dist}m",
            称号=stage,
            上榜总人数=len(r_list)
        )
        for r in r_list[:10]:
            num = int(r.get("rankNumber") or r.get("rank", 0))
            name = r.get("name") or "匿名用户"
            dist = r.get("distance", 0)
            st = r.get("stageName", "无")
            log_fields(名次=f"第{num}名", 姓名=name, 里程=f"{dist}m", 称号=st)
    else:
        log_status("查询学期里程榜", ok=False)
        log_error(res.get("message", "查询失败"))
        log_detail(res)

def check_progress_rank(client: ShanDongClient) -> None:
    """查询达标进度榜。"""
    res = client.get_rank_run_progress()
    if res.get("code") == 0 and res.get("data"):
        data = res["data"]
        my_rank = data.get("myRank", {})
        r_list = data.get("rankList", [])
        my_num = my_rank.get("rankNumber")
        rank_display = f"第 {my_num} 名" if (my_num and my_num > 0) else "未上榜"
        my_prog = float(my_rank.get("progress", 0))
        p_str = f"{my_prog*100:.1f}%" if my_prog < 1.0 else f"{my_prog:.1f}%"

        log_status("查询达标进度榜", ok=True)
        log_fields(
            个人名次=rank_display,
            完成进度=p_str,
            上榜总人数=len(r_list)
        )
        for r in r_list[:10]:
            num = int(r.get("rankNumber") or r.get("rank", 0))
            name = r.get("name") or "匿名用户"
            prog = float(r.get("progress", 0))
            it_str = f"{prog*100:.1f}%" if prog < 1.0 else f"{prog:.1f}%"
            log_fields(名次=f"第{num}名", 姓名=name, 进度=it_str)
    else:
        log_status("查询达标进度榜", ok=False)
        log_error(res.get("message", "查询失败"))
        log_detail(res)

def main():
    parser = argparse.ArgumentParser(description="校园排行榜查询")
    parser.add_argument("-t", "--type", choices=["all", "distance", "progress"], default="all",
                        help="榜单类型: all (全部, 默认), distance (里程榜), progress (进度榜)")
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
    log_fields(Token=client.transport.token[:10] + "...", 巡检榜单=args.type)

    if args.type in ["all", "distance"]:
        check_distance_rank(client)

    if args.type in ["all", "progress"]:
        check_progress_rank(client)

if __name__ == "__main__":
    main()
