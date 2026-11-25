"""本校专区与校友推荐查询命令行工具。"""
import argparse
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from client import ShanDongClient
from logger import log_status, log_fields, log_error, log_detail

def show_school_info(client: ShanDongClient):
    """查询本校官方频道与概况。"""
    log_status("查询本校频道", ok=True)
    res = client.get_myschool_info()
    if res.get("code") == 0 and res.get("data"):
        d = res["data"]
        ch = d.get("officialChannel", {})
        log_fields(
            频道名称=ch.get("channelName", "未命名"),
            频道编号=ch.get("channelNo"),
            频道号=ch.get("channelNumber"),
            加入状态="已加入" if ch.get("joinFlag") else "未加入",
            封面图=ch.get("coverUrl", "无")
        )
    else:
        log_status("查询本校频道", ok=False)
        log_error(res.get("message", "查询失败"))
        log_detail(res)

def show_schoolmate_config(client: ShanDongClient):
    """查询校友圈筛选配置。"""
    log_status("查询校友筛选配置", ok=True)
    res = client.get_schoolmate_config()
    if res.get("code") == 0 and res.get("data"):
        d = res["data"]
        grades = d.get("gradeList", [])
        tags = d.get("tagList", [])
        log_fields(年级数=len(grades), 标签大类数=len(tags))
        for g in grades:
            log_fields(年级代码=g.get("gradeCode"), 年级名称=g.get("gradeName"))
        for t in tags:
            sub_names = [it.get("tagName") for it in t.get("list", []) if isinstance(it, dict)]
            log_fields(类别=t.get("typeName"), 包含标签=",".join(sub_names[:5]))
    else:
        log_status("查询校友筛选配置", ok=False)
        log_error(res.get("message", "查询失败"))
        log_detail(res)

def show_schoolmates(client: ShanDongClient, page: int = 1, size: int = 10, grade: str = "", tag: str = ""):
    """分页查询校友推荐。"""
    log_status("检索同校校友", ok=True)
    res = client.search_schoolmates(page_num=page, page_size=size, grade_code=grade, tag_no=tag)
    if res.get("code") == 0 and res.get("data"):
        d = res["data"]
        m_list = d.get("list", [])
        log_fields(校友总数=d.get("total", len(m_list)), 当前页条数=len(m_list))
        for m in m_list:
            u_name = m.get("userName") or "匿名用户"
            g_name = m.get("gradeName") or "未知年级"
            tag_names = [it.get("tagName") for it in m.get("tagList", []) if isinstance(it, dict)]
            sex_str = "女" if m.get("sex") == 2 else "男" if m.get("sex") == 1 else "保密"
            log_fields(
                用户代码=m.get("appUserCode"),
                姓名=u_name,
                性别=sex_str,
                年级=g_name,
                签名=(m.get("slogan") or "").replace("
", " ")[:25],
                标签=",".join(tag_names[:3]) if tag_names else "无"
            )
    else:
        log_status("检索同校校友", ok=False)
        log_error(res.get("message", "检索失败"))
        log_detail(res)

def main():
    parser = argparse.ArgumentParser(description="本校专区与校友互动工具")
    parser.add_argument("-p", "--page", type=int, default=1, help="页码 (默认 1)")
    parser.add_argument("-s", "--size", type=int, default=10, help="每页条数 (默认 10)")
    parser.add_argument("--grade", default="", help="按年级代码筛选")
    parser.add_argument("--tag", default="", help="按标签编号筛选")
    parser.add_argument("--schoolmates", action="store_true", help="查询校友推荐列表")
    parser.add_argument("--config", action="store_true", help="查询校友搜索年级与标签配置")
    parser.add_argument("--hello", help="向指定校友用户代码打招呼互动")
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

    if args.hello:
        log_status(f"打招呼互动 {args.hello}", ok=True, status_text="发送")
        h_res = client.say_hello_to_schoolmate(args.hello)
        if h_res.get("code") == 0:
            log_status(f"打招呼互动 {args.hello}", ok=True)
            log_fields(结果="已打招呼")
        else:
            log_status(f"打招呼互动 {args.hello}", ok=False)
            log_error(h_res.get("message", "发送失败"))
        return

    if args.config:
        show_schoolmate_config(client)
        return

    if args.schoolmates:
        show_schoolmates(client, page=args.page, size=args.size, grade=args.grade, tag=args.tag)
        return

    # 默认展示本校频道信息
    show_school_info(client)

if __name__ == "__main__":
    main()
