"""用户资料与学生卡查询命令行工具。"""
import argparse
import os
import sys
import urllib.parse

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)

from client import ShanDongClient
from logger import log_status, log_fields, log_error, log_detail
import crypto

def main():
    parser = argparse.ArgumentParser(description="用户档案与学生卡信息查询")
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

    # 1. 个人中心基础资料
    u_res = client.query_common_user_info()
    if u_res.get("code") == 0 and u_res.get("data"):
        ud = u_res["data"]
        name_plain = crypto.decrypt_field(ud.get("userName") or "")
        phone_plain = crypto.decrypt_field(ud.get("phone") or "")
        school_plain = crypto.decrypt_field(ud.get("schoolName") or "")
        stuno_plain = crypto.decrypt_field(ud.get("studentNumber") or "")
        sex_str = "女" if ud.get("sex") == 2 else "男" if ud.get("sex") == 1 else "未知"

        log_status("查询个人资料", ok=True)
        log_fields(
            姓名=name_plain,
            性别=sex_str,
            学号=stuno_plain,
            手机号=phone_plain,
            学校=school_plain,
            用户ID=ud.get("userId"),
            学校编号=ud.get("schoolCode"),
            昵称=ud.get("nickName") or "无"
        )
    else:
        log_status("查询个人资料", ok=False)
        log_error(u_res.get("message", "查询失败"))
        log_detail(u_res)

    # 2. 电子学生卡档案
    card_res = client.get_student_card()
    if card_res.get("code") == 0 and card_res.get("data"):
        cd = card_res["data"]
        sinfo = cd.get("schoolInfo", {})
        log_status("查询学生卡", ok=True)
        log_fields(
            姓名=crypto.decrypt_field(cd.get("userName") or ""),
            学校=crypto.decrypt_field(sinfo.get("schoolName") or ""),
            学号=crypto.decrypt_field(sinfo.get("studentNumber") or ""),
            学院=sinfo.get("departmentName") or "无",
            班级=sinfo.get("className") or "无",
            校区=sinfo.get("subSchoolName") or "本部",
            年级=sinfo.get("gradeName") or "无",
            班级编号=sinfo.get("classCode") or "无"
        )
    else:
        log_status("查询学生卡", ok=False)
        log_error(card_res.get("message", "查询失败"))
        log_detail(card_res)

    # 3. 学生卡动态二维码
    qr_res = client.get_student_qr_code()
    if qr_res.get("code") == 0 and qr_res.get("data"):
        raw_qr = qr_res["data"].get("qrCode", "")
        parsed_qr = urllib.parse.unquote(raw_qr)
        log_status("查询动态码", ok=True)
        log_fields(二维码=parsed_qr)
    else:
        log_status("查询动态码", ok=False)
        log_error(qr_res.get("message", "获取失败"))
        log_detail(qr_res)

    # 4. 我的体育课
    course_res = client.find_my_course()
    if course_res.get("code") == 0:
        c_list = course_res.get("data", {}).get("list", [])
        log_status("查询体育课", ok=True)
        log_fields(课程总数=len(c_list))
        for c in c_list:
            log_fields(
                课程=c.get("courseName"),
                教师=c.get("teacherName"),
                时间=c.get("courseTime"),
                地点=c.get("courseAddress")
            )
    else:
        log_status("查询体育课", ok=False)
        log_error(course_res.get("message", "查询失败"))
        log_detail(course_res)

    # 5. 人脸底图状态
    f_res = client.get_user_face_img()
    if f_res.get("code") == 0:
        f_data = f_res.get("data")
        f_url = f_data.get("faceImg") if isinstance(f_data, dict) else f_data
        log_status("查询人脸底图", ok=True)
        log_fields(在库=bool(f_url), 地址=str(f_url)[:50] + "..." if f_url else "无")
    else:
        log_status("查询人脸底图", ok=False)
        log_error(f_res.get("message", "查询异常"))
        log_detail(f_res)

    # 6. 可用围栏推荐
    fence_res = client.filter_usable_fence()
    if fence_res.get("code") == 0 and fence_res.get("data"):
        fdata = fence_res["data"]
        log_status("查询可用围栏", ok=True)
        if isinstance(fdata, dict):
            log_fields(推荐围栏=fdata.get("fenceCode", "无"))
        elif isinstance(fdata, list):
            f_names = [f.get("fenceName", "未命名") for f in fdata if isinstance(f, dict)]
            log_fields(围栏总数=len(fdata), 围栏列表=",".join(f_names[:3]))
    else:
        log_status("查询可用围栏", ok=False)
        log_error(fence_res.get("message", "查询失败"))
        log_detail(fence_res)

if __name__ == "__main__":
    main()
