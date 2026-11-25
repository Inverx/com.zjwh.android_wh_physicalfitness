"""每日任务、申诉与福利大厅查询命令行工具。"""
import argparse
import json
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from client import ShanDongClient
from logger import log_status, log_fields, log_error, log_detail

def main():
    parser = argparse.ArgumentParser(description="每日任务、申诉与福利大厅管理")
    parser.add_argument("--claim-login", action="store_true", help="领取每日登录奖励任务")
    parser.add_argument("--tasks", action="store_true", help="查询每日可用任务列表")
    parser.add_argument("--appeals", action="store_true", help="查询历史跑单申诉记录")
    parser.add_argument("--jackpot", action="store_true", help="查看福利大厅抽奖配置")
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
    log_fields(Token=client.transport.token[:12] + "...", 设备=client.transport.model_name)

    # 1. 领取每日登录奖励
    if args.claim_login:
        log_status("领取登录奖励", ok=True, status_text="提交")
        l_res = client.login_once_task()
        if l_res.get("code") == 0:
            log_status("领取登录奖励", ok=True)
            log_fields(结果="领取成功")
        else:
            log_status("领取登录奖励", ok=False)
            log_error(l_res.get("message", "已领取或异常"))
            log_detail(l_res)
        return

    # 2. 查询申诉列表
    if args.appeals:
        log_status("查询申诉记录", ok=True)
        a_res = client.query_appeal_list()
        if a_res.get("code") == 0:
            list_data = a_res.get("data", [])
            log_fields(申诉总数=len(list_data))
            for item in list_data:
                log_fields(跑单=item.get("runRecordCode"), 理由=item.get("problemContent"), 状态=item.get("auditStatus"))
        else:
            log_status("查询申诉记录", ok=False)
            log_error(a_res.get("message", "查询异常"))
            log_detail(a_res)
        return

    # 3. 查看幸运大厅
    if args.jackpot:
        log_status("查询福利抽奖", ok=True)
        j_res = client.get_award_home()
        if j_res.get("code") == 0 and j_res.get("data"):
            jd = j_res["data"]
            cfg = jd.get("themeConfig", {})
            log_fields(主题=cfg.get("themeDesc", "无"), 奖品数=len(jd.get("awardList", [])))
        else:
            log_status("查询福利抽奖", ok=False)
            log_error(j_res.get("message", "查询失败"))
            log_detail(j_res)
        return

    # 4. 默认查询每日可用任务
    log_status("查询可用任务", ok=True)
    t_res = client.get_available_tasks()
    if t_res.get("code") == 0 and t_res.get("data"):
        td = t_res["data"]
        t_list = td.get("list", [])
        log_fields(任务总数=len(t_list))
        for t in t_list:
            t_name = t.get("name", "未命名任务")
            t_no = t.get("taskConfigNo")
            prog = t.get("progress", {})
            c_cnt = prog.get("completedCount", 0)
            m_cnt = prog.get("maxCompleteCount", 1)
            is_done = "已完成" if c_cnt >= m_cnt else f"进行中({c_cnt}/{m_cnt})"
            log_fields(任务=t_name, 进度=is_done, 编号=t_no)
    else:
        log_status("查询可用任务", ok=False)
        log_error(t_res.get("message", "查询失败"))
        log_detail(t_res)

if __name__ == "__main__":
    main()
