"""闪信与消息通知中心命令行工具。"""
import argparse
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from client import ShanDongClient
from logger import log_status, log_fields, log_error, log_detail

def show_overview(client: ShanDongClient):
    """查询闪信消息总览与未读红点。"""
    log_status("查询闪信红点", ok=True)
    r_dot = client.get_message_red_dot()
    if r_dot.get("code") == 0 and r_dot.get("data"):
        log_fields(未读红点=bool(r_dot["data"].get("redDotFlag")))
    else:
        log_status("查询闪信红点", ok=False)

    log_status("查询会话分组", ok=True)
    r_grp = client.get_message_user_groups()
    if r_grp.get("code") == 0 and r_grp.get("data"):
        groups = r_grp["data"].get("list", [])
        log_fields(分组总数=len(groups))
        for g in groups:
            log_fields(分组名=g.get("groupName"), 未读数=g.get("unReadCount", 0))
    else:
        log_status("查询会话分组", ok=False)
        log_error(r_grp.get("message", "查询失败"))

def show_comments(client: ShanDongClient, page: int = 1, size: int = 10):
    """查询收到的评论回复消息。"""
    log_status("查询互动评论消息", ok=True)
    res = client.get_comment_message_list(page_num=page, page_size=size)
    if res.get("code") == 0 and res.get("data"):
        d = res["data"]
        c_list = d.get("list", [])
        log_fields(消息总数=d.get("total", len(c_list)))
        for c in c_list:
            log_fields(发送人=c.get("nickName"), 评论内容=c.get("content"), 帖子=c.get("worksTitle"))
    else:
        log_status("查询互动评论消息", ok=False)
        log_error(res.get("message", "查询失败"))

def show_favors(client: ShanDongClient, page: int = 1, size: int = 10):
    """查询收到的点赞互动消息。"""
    log_status("查询点赞消息", ok=True)
    res = client.get_favor_message_list(page_num=page, page_size=size)
    if res.get("code") == 0 and res.get("data"):
        d = res["data"]
        f_list = d.get("list", [])
        log_fields(点赞总数=d.get("total", len(f_list)))
        for f in f_list:
            log_fields(点赞人=f.get("nickName"), 关联帖子=f.get("worksTitle"))
    else:
        log_status("查询点赞消息", ok=False)
        log_error(res.get("message", "查询失败"))

def show_buddies(client: ShanDongClient):
    """查询好友通讯录与群聊。"""
    log_status("查询好友通讯录", ok=True)
    res = client.get_buddy_home()
    if res.get("code") == 0 and res.get("data"):
        b_list = res["data"].get("list", [])
        log_fields(好友总数=len(b_list))
        for b in b_list:
            log_fields(好友姓名=b.get("userName"), 签名=b.get("slogan"), 用户代码=b.get("appUserCode"))
    else:
        log_status("查询好友通讯录", ok=False)
        log_error(res.get("message", "查询失败"))

def main():
    parser = argparse.ArgumentParser(description="闪信与消息中心查询工具")
    parser.add_argument("-p", "--page", type=int, default=1, help="页码 (默认 1)")
    parser.add_argument("-s", "--size", type=int, default=10, help="每页条数 (默认 10)")
    parser.add_argument("--comments", action="store_true", help="查询收到的评论回复消息")
    parser.add_argument("--favors", action="store_true", help="查询收到的点赞互动消息")
    parser.add_argument("--fans", action="store_true", help="查询收到的粉丝关注消息")
    parser.add_argument("--buddies", action="store_true", help="查询好友通讯录列表")
    parser.add_argument("--box", action="store_true", help="查询系统小秘书通知信箱")
    parser.add_argument("--clear-reddot", action="store_true", help="一键消除未读红点标记")
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

    if args.clear_reddot:
        log_status("清除红点标记", ok=True, status_text="提交")
        c_res = client.clear_message_red_dot()
        if c_res.get("code") == 0:
            log_status("清除红点标记", ok=True)
        else:
            log_status("清除红点标记", ok=False)
            log_error(c_res.get("message", "清除失败"))
        return

    if args.comments:
        show_comments(client, page=args.page, size=args.size)
        return

    if args.favors:
        show_favors(client, page=args.page, size=args.size)
        return

    if args.fans:
        log_status("查询粉丝消息", ok=True)
        f_res = client.get_fans_message_list(page_num=args.page, page_size=args.size)
        if f_res.get("code") == 0 and f_res.get("data"):
            fd = f_res["data"]
            log_fields(粉丝总数=fd.get("total", len(fd.get("list", []))))
        else:
            log_status("查询粉丝消息", ok=False)
        return

    if args.buddies:
        show_buddies(client)
        return

    if args.box:
        log_status("查询系统通知信箱", ok=True)
        b_res = client.get_system_message_box(page_num=args.page, page_size=args.size)
        if b_res.get("code") == 0 and b_res.get("data"):
            bd = b_res["data"]
            log_fields(通知总数=bd.get("total", len(bd.get("list", []))))
        else:
            log_status("查询系统通知信箱", ok=False)
        return

    # 默认展示消息总览与分组
    show_overview(client)

if __name__ == "__main__":
    main()
