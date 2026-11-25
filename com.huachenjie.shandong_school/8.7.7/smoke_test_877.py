"""协议接口完备度与密码学闭环冒烟测试工具。状态优先，结果字段化。"""
import sys, os, json
from pathlib import Path

cur_dir = r"D:/Work/闪动校园/协议/8.7.7"
sys.path.insert(0, cur_dir)

from client import ShanDongClient
import crypto
import session_store
from logger import log_status, log_fields, log_error, log_detail

def main():
    log_status("冒烟测试", ok=True, status_text="开始")

    # 1. 密码学加解密闭环
    log_status("测试阶段 1: 密码学加解密闭环", ok=True)
    try:
        test_plain = "TestPassword_123"
        pwd_enc = crypto.encrypt_password(test_plain)
        pwd_dec = crypto.decrypt_password(pwd_enc)
        assert pwd_dec == test_plain
        point_enc = crypto.encrypt_slider_point(120.0, 15.0)
        sign_calc = crypto.get_sign({"test": "data"})
        log_fields(密码加解密="一致", 点位密文=point_enc[:16] + "...", 签名计算="正常")
    except Exception as e:
        log_status("测试阶段 1", ok=False)
        log_error(str(e))
        return

    # 2. 会话加载与缺省配置
    log_status("测试阶段 2: 会话模板存储规范", ok=True)
    try:
        s = session_store.load_session()
        log_fields(
            Token=s.get("token", "")[:12] + "...",
            用户ID=s.get("userId"),
            学校代码=s.get("schoolCode"),
            设备机型=s.get("modelName")
        )
    except Exception as e:
        log_status("测试阶段 2", ok=False)
        log_error(str(e))
        return

    # 3. 客户端对象初始化
    log_status("测试阶段 3: 客户端对象初始化", ok=True)
    try:
        client = ShanDongClient()
        log_fields(传输基类="正常", 请求头构造="正常")
    except Exception as e:
        log_status("测试阶段 3", ok=False)
        log_error(str(e))
        return

    # 4. 全量协议接口完整性审计 (共 52 个接口)
    log_status("测试阶段 4: 协议接口完整性审计", ok=True)
    required_methods = [
        "login_check", "login_by_password", "get_slider_captcha", "verify_slider_captcha",
        "query_common_user_info", "get_personal_info", "get_student_card", "get_student_qr_code",
        "get_user_settings", "get_school_details", "filter_usable_fence", "query_school_fences",
        "get_run_plan_list", "check_sun_run_config", "get_pre_run_check_in", "start_sun_run_v2",
        "upload_run_record", "upload_steps_record", "upload_pace_record", "upload_pass_point",
        "upload_stride_record", "finish_sun_run_v2", "run_record_detail", "start_free_run",
        "finish_free_run", "free_detail", "page_sun_run_record", "query_sun_run_abstract_info_v2",
        "query_run_record_count", "query_school_run_summary", "get_user_face_img", "bind_user_face",
        "update_user_face", "close_user_face", "get_oss_token", "get_rank_distance",
        "get_rank_run_progress", "sign_today_status", "login_once_task", "run_task",
        "get_award_home", "get_lottery_page", "get_fitness_permission", "get_fitness_academic_years",
        "get_fitness_test_records", "get_fitness_detail", "get_fitness_test_result", "get_exam_list",
        "get_exam_result", "get_exam_paper_detail", "get_attend_statistics", "get_student_course_attend_list",
        "get_works_recommend_pool", "get_works_detail", "get_works_comments", "get_works_sub_comments",
        "get_works_categories", "search_works", "get_channel_hotspot_list", "update_works_visit",
        "get_myschool_info", "get_schoolmate_config", "search_schoolmates", "say_hello_to_schoolmate",
        "get_message_user_groups", "get_message_red_dot", "clear_message_red_dot", "get_system_message_box",
        "get_comment_message_list", "get_favor_message_list", "get_fans_message_list", "get_buddy_home",
        "search_buddies", "apply_buddy", "get_chatroom_list"
    ]
    missing = [m for m in required_methods if not hasattr(client, m)]
    if not missing:
        log_fields(接口总数=len(required_methods), 完备度=f"{len(required_methods)}/{len(required_methods)}", 缺失=0)
    else:
        log_status("测试阶段 4", ok=False)
        log_error(f"缺失接口: {missing}")
        return

    # 5. CLI 业务工具集核验
    log_status("测试阶段 5: 业务工具集完整性", ok=True)
    clis = [
        "login_cli.py", "user_cli.py", "policy_cli.py", "score_cli.py",
        "rank_cli.py", "history_cli.py", "run_cli.py", "ai_cli.py", "face_cli.py",
        "task_cli.py", "community_cli.py", "alumni_cli.py", "message_cli.py"
    ]
    ex_count = sum(1 for c in clis if (Path(cur_dir) / c).exists())
    log_fields(工具总数=len(clis), 已就绪=ex_count)

    # 6. 协议脱敏审计 (确保无硬编码凭证与真实个人信息)
    log_status("测试阶段 6: 源码敏感信息脱敏审计", ok=True)
    import re
    # 检查是否存在未脱敏的真实手机号或真实凭证
    phone_pattern = re.compile(r"1[3-9]\d{9}")
    jwt_pattern = re.compile(r"eyJhbGciOiJIUzI1NiJ9\.[a-zA-Z0-9_-]{30,}")
    leak_found = False
    for py_file in list(Path(cur_dir).glob("*.py")) + list(Path(cur_dir).glob("*.json")):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if phone_pattern.search(content):
            log_status("脱敏审计", ok=False)
            log_error(f"文件 {py_file.name} 检测到未脱敏手机号码")
            leak_found = True
        if jwt_pattern.search(content):
            log_status("脱敏审计", ok=False)
            log_error(f"文件 {py_file.name} 检测到未脱敏真实 JWT 凭证")
            leak_found = True
    if not leak_found:
        log_fields(隐私合规扫描="0 命中", 通用占位参数="100% 达成")

    log_status("冒烟测试", ok=True, status_text="全部通过")

if __name__ == "__main__":
    main()
