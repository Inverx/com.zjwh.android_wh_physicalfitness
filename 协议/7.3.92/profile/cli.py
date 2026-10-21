# -*- coding: utf-8 -*-
import argparse
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from profile.client import ProfileClient


def main():
    parser = argparse.ArgumentParser(description="运动世界 7.3.92 个人档案与时钟同步终端")
    parser.add_argument("-t", "--token", help="登录 Token")
    parser.add_argument("-u", "--uid", help="用户 UID")
    parser.add_argument("--unid", help="学校 UNID")
    args = parser.parse_args()

    client = ProfileClient(uid=args.uid, token=args.token, unid=args.unid)

    # 1. 服务端时间同步
    st = client.get_server_time()
    if not st.synchronized:
        print(f"时钟同步失败: {st.error_message}")
        return 1
    print(f"时钟同步: 服务端时间={st.server_datetime} 偏斜={st.offset_seconds:+.3f}s 时间戳={st.server_timestamp_ms}")

    if not args.token:
        print("个人档案: 失败 原因=缺少Token")
        return 1

    # 2. 首页基础信息
    base_info = client.get_home_base_user_info()
    if base_info:
        print(f"基础信息: 姓名={base_info.name} 学号={base_info.student_no} 学校={base_info.university_name} 学院={base_info.department_name}")
    else:
        print(f"基础信息: 失败 uid={client.uid} 原因=查询为空")

    # 3. 详细个人档案
    detail = client.get_user_info()
    if detail:
        print(f"详细档案: 班级={detail.grade_class} 专业={detail.major} 性别={detail.sex} 手机={detail.phone}")
    else:
        print(f"详细档案: 失败 uid={client.uid} 原因=查询为空")


if __name__ == "__main__":
    sys.exit(main())
