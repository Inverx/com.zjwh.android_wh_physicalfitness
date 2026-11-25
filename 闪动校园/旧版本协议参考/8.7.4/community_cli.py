"""社区动态、校园新鲜事与帖子浏览命令行工具。"""
import argparse
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from client import ShanDongClient
from logger import log_status, log_fields, log_error, log_detail

def show_works_detail(client: ShanDongClient, works_no: str):
    """查看指定帖子详情与评论。"""
    log_status(f"查询帖子详情 {works_no}", ok=True)
    res = client.get_works_detail(works_no)
    if res.get("code") == 0 and res.get("data"):
        wd = res["data"]
        log_status("获取帖子内容", ok=True)
        log_fields(
            帖子编号=works_no,
            标题=wd.get("title") or "无标题",
            发布作者=wd.get("authorNickName") or "匿名用户",
            图片总数=len(wd.get("worksImgList", [])),
            浏览量=wd.get("viewCount", 0),
            点赞数=wd.get("likeCount", 0),
            评论数=wd.get("commentCount", 0)
        )
        content_snippet = (wd.get("content") or "").replace("
", " ")[:60]
        if content_snippet:
            log_fields(正文摘要=content_snippet + "...")
        client.update_works_visit(works_no)

        # 同步拉取一级评论
        c_res = client.get_works_comments(works_no, page_num=1, page_size=5)
        if c_res.get("code") == 0 and c_res.get("data"):
            cd = c_res["data"]
            comments = cd.get("list", [])
            log_status("拉取帖子评论", ok=True)
            log_fields(评论总数=cd.get("total", len(comments)))
            for c in comments:
                u_name = c.get("commentUserNickName") or "匿名"
                c_body = (c.get("commentContent") or "").replace("
", " ")[:40]
                log_fields(评论人=u_name, 内容=c_body)
    else:
        log_status("查询帖子详情", ok=False)
        log_error(res.get("message", "查询失败"))
        log_detail(res)

def show_hot_channels(client: ShanDongClient):
    """查看热门频道榜单。"""
    log_status("查询热门频道", ok=True)
    res = client.get_channel_hotspot_list()
    if res.get("code") == 0 and res.get("data"):
        channels = res["data"].get("list", [])
        log_fields(频道总数=len(channels))
        for ch in channels:
            log_fields(
                频道名称=ch.get("channelName"),
                简介=ch.get("blurb") or "无",
                热度=ch.get("popularityValue"),
                关注数=ch.get("followedCount"),
                频道号=ch.get("channelNo")
            )
    else:
        log_status("查询热门频道", ok=False)
        log_error(res.get("message", "查询失败"))
        log_detail(res)

def show_recommend_pool(client: ShanDongClient, page: int = 1, size: int = 10):
    """查询首页新鲜事推荐流。"""
    log_status("拉取校园新鲜事", ok=True)
    res = client.get_works_recommend_pool(page_num=page, page_size=size)
    if res.get("code") == 0 and res.get("data"):
        wd = res["data"]
        w_list = wd.get("list", [])
        log_fields(获取帖子数=len(w_list))
        for w in w_list:
            w_no = w.get("worksNo")
            author = w.get("authorNickName") or "匿名"
            title = w.get("title") or (w.get("content") or "").replace("
", " ")[:20]
            log_fields(单号=w_no, 标题=title or "无标题", 作者=author)
    else:
        log_status("拉取校园新鲜事", ok=False)
        log_error(res.get("message", "拉取失败"))
        log_detail(res)

def main():
    parser = argparse.ArgumentParser(description="社区动态与校园新鲜事浏览工具")
    parser.add_argument("-p", "--page", type=int, default=1, help="页码 (默认 1)")
    parser.add_argument("-s", "--size", type=int, default=10, help="每页条数 (默认 10)")
    parser.add_argument("--detail", help="查看指定单号的帖子图文详情与评论")
    parser.add_argument("--channels", action="store_true", help="查看热门频道与话题榜单")
    parser.add_argument("--categories", action="store_true", help="查询社区作品分类专区")
    parser.add_argument("--search", help="根据关键词搜索帖子")
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

    if args.detail:
        show_works_detail(client, args.detail)
        return

    if args.channels:
        show_hot_channels(client)
        return

    if args.categories:
        log_status("查询专区分类", ok=True)
        c_res = client.get_works_categories()
        if c_res.get("code") == 0 and c_res.get("data"):
            for c in c_res["data"]:
                log_fields(分类ID=c.get("categoryId"), 名称=c.get("categoryName"))
        else:
            log_status("查询专区分类", ok=False)
            log_error(c_res.get("message", "查询失败"))
        return

    if args.search:
        log_status(f"检索关键词 {args.search}", ok=True)
        s_res = client.search_works(args.search, page_num=args.page, page_size=args.size)
        if s_res.get("code") == 0 and s_res.get("data"):
            items = s_res["data"].get("list", [])
            log_fields(搜索结果数=len(items))
            for it in items:
                log_fields(单号=it.get("worksNo"), 标题=it.get("title") or "无标题", 作者=it.get("authorNickName"))
        else:
            log_status(f"检索关键词 {args.search}", ok=False)
            log_error(s_res.get("message", "检索失败"))
        return

    # 默认拉取首页推荐流
    show_recommend_pool(client, page=args.page, size=args.size)

if __name__ == "__main__":
    main()
