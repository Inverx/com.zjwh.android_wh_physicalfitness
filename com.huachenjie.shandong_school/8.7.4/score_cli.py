"""全维度长跑成绩与学校考核规则查询命令行工具。"""
import argparse
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from client import ShanDongClient
from logger import log_status, log_fields, log_error, log_detail

def check_run_score(client: ShanDongClient, semester_code: str = "current") -> None:
    """查询长跑成绩与学校考核规则。"""
    if semester_code == "all":
        log_status("拉取历年全部学期汇总", ok=True)
        sem_res = client.get_semester_list()
        sems = sem_res.get("data", []) if sem_res.get("code") == 0 else []
        for s in sems:
            scode = s.get("semesterCode")
            sname = s.get("name") or s.get("semesterName")
            res = client.query_sun_run_abstract_info_v2(semester_code=scode)
            if res.get("code") == 0 and res.get("data"):
                d = res["data"]
                r = d.get("schoolDemandRule", {})
                done_m = d.get("doneDistance", 0)
                target_times = d.get("doneTargetTimes", 0)
                status_str = "已达标" if d.get("validStatus") else "未达标"
                rule_dist = f"{r.get('singleMinDistance', 0)}~{r.get('singleMaxDistance', 0)}m"
                rule_pace = f"{r.get('maxPace', 0)}~{r.get('minPace', 0)}s"
                times = r.get("timeFragment", [{}])[0].get("times", "") if r.get("timeFragment") else ""
                log_fields(
                    学期=scode,
                    名称=sname,
                    已跑=f"{done_m}m",
                    达标=f"{target_times}次",
                    状态=status_str,
                    里程规则=rule_dist,
                    配速规则=rule_pace,
                    有效时段=times
                )
        return

    sc = "" if semester_code == "current" else semester_code
    res = client.query_sun_run_abstract_info_v2(semester_code=sc)
    if res.get("code") == 0 and res.get("data"):
        data = res["data"]
        rule = data.get("schoolDemandRule", {})
        done_info = data.get("studentDoneRuleInfo", {})
        log_status("查询学期长跑成绩", ok=True)
        log_fields(
            学期代码=data.get("semesterCode", sc or "当前学期"),
            跑步方案=data.get("runPlanCode", "无"),
            已跑总里程=f"{data.get('doneDistance', 0)}m",
            达标总次数=f"{data.get('doneTargetTimes', 0)}次",
            本周已完成=f"{data.get('weekAlreadyTimes', 0)}次",
            本周剩余=f"{data.get('weekRemainTimes', 0)}次",
            考核状态="已达标" if data.get("validStatus") else "未达标",
            完成率=f"{done_info.get('donePercent', 0)}%"
        )
        if rule:
            log_status("学校长跑硬性考核规则", ok=True)
            times = rule.get("timeFragment", [{}])[0].get("times", "未限定") if rule.get("timeFragment") else "未限定"
            clk = rule.get("clockModeList", [{}])[0] if rule.get("clockModeList") else {}
            log_fields(
                单次里程限制=f"{rule.get('singleMinDistance', 0)}m ~ {rule.get('singleMaxDistance', 0)}m",
                合格配速区间=f"{rule.get('maxPace', 0)}s/km ~ {rule.get('minPace', 0)}s/km",
                每日限跑次数=f"{rule.get('dayMaxTimes', 0)}次",
                每天最高计入=f"{rule.get('dayMaxDistance', 0)}m",
                允许跑步时段=times,
                学期起止日期=f"{rule.get('startDate', '')}至{rule.get('endDate', '')}",
                禁止校园WiFi=bool(rule.get("forbiddenWiFi")),
                打卡模式=f"模式{clk.get('clockMode', 3)}: 总计{clk.get('totalGoalCounts', 3)}点"
            )
    else:
        log_status("查询学期长跑成绩", ok=False)
        log_error(res.get("message", "长跑成绩查询失败"))
        log_detail(res)

    cnt_res = client.query_run_record_count()
    if cnt_res.get("code") == 0 and cnt_res.get("data"):
        c_data = cnt_res["data"]
        log_status("查询运动累计历史统计", ok=True)
        log_fields(
            打卡总天数=f"{c_data.get('checkDays', 0)}天",
            累计总里程=f"{c_data.get('totalDistance', 0)}m",
            最佳配速=f"{c_data.get('bestPace', 0)}s/km",
            消耗总热量=f"{c_data.get('totalCalorie', 0)}kcal"
        )

def check_fitness_score(client: ShanDongClient) -> None:
    """查询国家体测成绩。"""
    res = client.get_fitness_test_records(page_num=1, page_size=5)
    if res.get("code") == 0 and res.get("data"):
        data = res["data"]
        r_list = data.get("list", [])
        log_status("查询国家体质测试成绩", ok=True)
        log_fields(体测记录数=len(r_list))
        for r in r_list:
            log_fields(
                学年=r.get("academicYear"),
                总分=r.get("totalScore"),
                等级=r.get("level"),
                是否合格="合格" if r.get("isPass") else "不合格"
            )
    else:
        log_status("查询国家体质测试成绩", ok=False)
        log_error(res.get("message", "体测记录查询失败"))
        log_detail(res)

def check_exam_score(client: ShanDongClient) -> None:
    """查询体育理论考试。"""
    res = client.get_exam_list()
    if res.get("code") == 0 and res.get("data"):
        data = res["data"]
        e_list = data.get("list", [])
        log_status("查询体育理论考试", ok=True)
        log_fields(考试任务数=len(e_list))
        for e in e_list:
            log_fields(
                考试名称=e.get("examName"),
                学期代码=e.get("semesterCode"),
                考试状态="已提交" if e.get("submitStatus") == 1 else "待作答",
                得分=e.get("score") if e.get("score") is not None else "未判分"
            )
    else:
        log_status("查询体育理论考试", ok=False)
        log_error(res.get("message", "理论考试查询失败"))
        log_detail(res)

def check_attend_score(client: ShanDongClient) -> None:
    """查询体育课考勤平时分。"""
    res = client.get_attend_statistics()
    if res.get("code") == 0 and res.get("data"):
        data = res["data"]
        log_status("查询体育课考勤", ok=True)
        log_fields(
            出勤总数=f"{data.get('totalCount', 0)}次",
            正常出勤=f"{data.get('normalCount', 0)}次",
            请假次数=f"{data.get('leaveCount', 0)}次",
            缺勤旷课=f"{data.get('absentCount', 0)}次",
            平时得分=f"{data.get('score', 100)}分"
        )
    else:
        log_status("查询体育课考勤", ok=False)
        log_error(res.get("message", "考勤成绩查询失败"))
        log_detail(res)

def main():
    parser = argparse.ArgumentParser(description="长跑考核成绩与学校规则查询")
    parser.add_argument("-t", "--type", choices=["all", "run", "fitness", "exam", "attend"], default="run",
                        help="成绩类型: run (长跑与规则, 默认), fitness (体测), exam (考试), attend (考勤), all (全部)")
    parser.add_argument("-s", "--semester", default="current",
                        help="指定学期代码: current (当前学期, 默认), 12, 11, 10... 或 all (全量汇总)")
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
    log_fields(Token=client.transport.token[:10] + "...", 模式=args.type, 学期=args.semester)

    if args.type in ["all", "run"]:
        check_run_score(client, semester_code=args.semester)
    if args.type in ["all", "fitness"]:
        check_fitness_score(client)
    if args.type in ["all", "exam"]:
        check_exam_score(client)
    if args.type in ["all", "attend"]:
        check_attend_score(client)

if __name__ == "__main__":
    main()
