import base64
import json
import time
from typing import Dict, Any, List, Optional, Tuple, Callable

import crypto
import captcha_solver
import session_store
from transport import HttpTransport

class ShanDongClient:
    def __init__(
        self,
        token: Optional[str] = None,
        satoken: Optional[str] = None,
        user_id: Optional[str] = None,
        school_code: Optional[str] = None,
        transport_mode: str = "direct",
        proxy: Optional[str] = None,
        adb_path: Optional[str] = None,
        adb_device: Optional[str] = None,
        device_id: Optional[str] = None,
        model_name: Optional[str] = None,
        system_version: Optional[str] = None
    ):
        self.transport = HttpTransport(
            token=token,
            satoken=satoken,
            device_id=device_id,
            model_name=model_name,
            system_version=system_version,
            transport_mode=transport_mode,
            proxy=proxy,
            adb_path=adb_path,
            adb_device=adb_device
        )
        self.user_id = user_id
        self.school_code = school_code
        self.user_name = None

        if not self.transport.token:
            self._load_saved_session()

    def _load_saved_session(self) -> None:
        s = session_store.load_session()
        if s:
            self.transport.token = s.get("token") or ""
            self.transport.satoken = s.get("satoken") or ""
            self.user_id = s.get("userId")
            self.school_code = s.get("schoolCode")
            self.user_name = s.get("userName")
            if s.get("deviceId"):
                self.transport.device_id = s["deviceId"]

    def _save_current_session(self) -> None:
        s = {
            "token": self.transport.token,
            "satoken": self.transport.satoken,
            "userId": self.user_id,
            "schoolCode": self.school_code,
            "userName": self.user_name,
            "deviceId": self.transport.device_id,
            "updatedAt": int(time.time())
        }
        session_store.save_session(s)

    def clear_saved_session(self) -> None:
        session_store.clear_session()
        self.transport.token = ""
        self.transport.satoken = ""
        self.user_id = None
        self.school_code = None
        self.user_name = None

    # --- 1. 验证码与账号登录 ---
    def get_slider_captcha(self) -> Dict[str, Any]:
        return self.transport.post("/login/front/slider/check/get", {})

    def verify_slider_captcha(self, point_json: str, captcha_token: str) -> Dict[str, Any]:
        return self.transport.post("/login/front/slider/check/verify", {
            "pointJson": point_json,
            "token": captcha_token
        })

    def login_check(self, mobile: str) -> Dict[str, Any]:
        """8.7.7 登录前置探测"""
        return self.transport.post("/auth/loginCheck", {"loginName": mobile}, v="loginCheck", api="auth")

    def get_slider_captcha(self) -> Dict[str, Any]:
        """8.7.7 获取滑块验证码"""
        return self.transport.post("/captcha/get", {"captchaType": "blockPuzzle"}, add_common=False)

    def verify_slider_captcha(self, token: str, raw_x: float) -> Tuple[Dict[str, Any], str]:
        """8.7.7 校验滑块验证码"""
        enc_point = crypto.encrypt_slider_point(raw_x)
        payload = {
            "captchaType": "blockPuzzle",
            "pointJson": enc_point,
            "token": token
        }
        res = self.transport.post("/captcha/check", payload, add_common=False)
        return res, enc_point

    def login_by_password(self, mobile: str, password: str, captcha_point: Optional[str] = None) -> Dict[str, Any]:
        """8.7.7 账号密码登录"""
        enc_pwd = crypto.encrypt_password(password)
        payload = {
            "loginName": mobile,
            "password": enc_pwd
        }
        if captcha_point:
            payload["captchaPoint"] = captcha_point

        res = self.transport.post("/auth/loginPassword", payload, v="loginPassword", api="auth")
        if res.get("code") == 0 and res.get("data"):
            data = res["data"]
            self.transport.token = data.get("token") or ""
            self.transport.satoken = data.get("satoken") or ""
            self.user_id = data.get("userId")
            self.school_code = data.get("schoolCode")
            self.user_name = data.get("userName") or data.get("realName")
            self._save_current_session()
        return res

    def query_common_user_info(self) -> Dict[str, Any]:
        """8.7.7 查询用户基础信息"""
        return self.transport.post("/account/queryCommonUserInfo", {}, v="queryCommonUserInfo", api="account")

    # --- 2. 用户信息与学校配置 ---
    def get_personal_info(self) -> Dict[str, Any]:
        return self.transport.post("/account/personal", {})

    def get_student_card(self) -> Dict[str, Any]:
        return self.transport.post("/account/queryStudentCard", {})

    def get_user_settings(self) -> Dict[str, Any]:
        return self.transport.post("/account/getUserSettings", {})

    def get_school_details(self, school_code: Optional[str] = None) -> Dict[str, Any]:
        sc = school_code or self.school_code or ""
        return self.transport.post("/api/school/details", {"schoolCode": sc})

    def filter_usable_fence(self, fence_code_list: Optional[List[str]] = None) -> Dict[str, Any]:
        """过滤当前可用跑步围栏 (school/filterUsableFence)"""
        return self.transport.post("/school/filterUsableFence", {"fenceCodeList": fence_code_list or []})

    def query_school_fences(self, school_code: Optional[str] = None) -> Dict[str, Any]:
        sc = school_code or self.school_code or ""
        return self.transport.post("/school/querySchoolFences", {"schoolCode": sc})

    # --- 3. 跑步方案与线路 (8.7.7) ---
    def get_run_plan_list(self) -> Dict[str, Any]:
        return self.transport.post("/run/plan/selectList", {"semesterCode": ""})

    def check_sun_run_config(
        self,
        run_plan_code: str = "",
        fence_code: str = "",
        sub_school_code: str = "",
        target_distance: str = "2000",
        activity_code: str = "",
        sport_type: str = "1"
    ) -> Dict[str, Any]:
        """长跑考核配置预检 (run/checkSunRunConfig)"""
        return self.transport.post("/run/checkSunRunConfig", {
            "schoolCode": self.school_code or "",
            "subSchoolCode": sub_school_code,
            "targetDistance": str(target_distance),
            "activityCode": activity_code,
            "runPlanCode": run_plan_code,
            "fenceCode": fence_code,
            "sportType": str(sport_type)
        })

    def get_pre_run_check_in(self) -> Dict[str, Any]:
        return self.transport.post("/run/getPreRunCheckIn", {})

    def start_sun_run_v2(
        self,
        run_plan_code: str,
        target_distance: str = "1800",
        lng: str = "0.000000",
        lat: str = "0.000000",
        use_credit_sword: bool = False
    ) -> Dict[str, Any]:
        return self.transport.post("/run/startSunRun_v2", {
            "runPlanCode": run_plan_code,
            "targetDistance": str(target_distance),
            "sportType": "1",
            "lng": str(lng),
            "lat": str(lat),
            "useCreditSword": "true" if use_credit_sword else "false"
        })

    def upload_run_record(self, run_record_code: str, pois: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.transport.post("/run/uploadRunRecord", {
            "runRecordCode": run_record_code,
            "pois": pois
        })

    def upload_steps_record(self, run_record_code: str, step_list: List[Dict[str, Any]], step_interval: int = 20) -> Dict[str, Any]:
        return self.transport.post("/run/uploadStepsRecord", {
            "runRecordCode": run_record_code,
            "stepList": step_list,
            "stepInterval": step_interval
        })

    def upload_pace_record(self, run_record_code: str, pace_list: List[Dict[str, Any]], pace_interval: int = 50) -> Dict[str, Any]:
        return self.transport.post("/run/uploadPaceRecord", {
            "runRecordCode": run_record_code,
            "paceList": pace_list,
            "paceInterval": pace_interval
        })

    def upload_pass_point(self, run_record_code: str, target_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.transport.post("/run/uploadPassPoint", {
            "runRecordCode": run_record_code,
            "targetPoints": target_points
        })

    def upload_stride_record(self, run_record_code: str, stride_list: List[Dict[str, Any]], stride_interval: int = 200) -> Dict[str, Any]:
        return self.transport.post("/run/uploadStrideRecord", {
            "runRecordCode": run_record_code,
            "strideList": stride_list,
            "strideInterval": stride_interval
        })

    def finish_sun_run_v2(
        self,
        run_record_code: str,
        distance: int,
        target_points: List[Dict[str, Any]],
        step_interval: int = 20,
        run_img_record: Optional[str] = None,
        face_check_record_list: Optional[List[Dict[str, Any]]] = None,
        pause_count: int = 0,
        pause_times: int = 0,
        duration: Optional[int] = None
    ) -> Dict[str, Any]:
        now_ts = str(int(time.time() * 1000))
        img_rec = run_img_record or crypto.calculate_run_img_record(run_record_code, now_ts)
        payload = {
            "runRecordCode": run_record_code,
            "distance": str(distance),
            "stepInterval": step_interval,
            "targetPoints": target_points,
            "runImgRecord": img_rec,
            "timestamp": now_ts,
            "pauseCount": pause_count,
            "pauseTimes": pause_times,
            "faceCheckRecordList": face_check_record_list or []
        }
        if duration is not None:
            payload["duration"] = str(duration)
        return self.transport.post("/run/finishSunRun_v2", payload)

    def run_record_detail(self, run_record_code: str) -> Dict[str, Any]:
        return self.transport.post("/run/runRecordDetail", {
            "runRecordCode": run_record_code,
            "sportType": 1
        })

    # --- 4. 自由跑链路 ---
    def start_free_run(self, aim_distance: str = "1600", lng: str = "0.000000", lat: str = "0.000000") -> Dict[str, Any]:
        """8.7.7 发起自由跑"""
        return self.transport.post("/run/startFreeRun", {
            "aimDistance": str(aim_distance),
            "lng": str(lng),
            "lat": str(lat)
        })

    def finish_free_run(
        self,
        run_record_code: str,
        distance: int,
        duration: int,
        total_step: int,
        pois: List[Dict[str, Any]],
        step_list: List[Dict[str, Any]],
        pace_list: List[Dict[str, Any]],
        step_interval: int = 20,
        pace_interval: int = 50,
        status: int = 2
    ) -> Dict[str, Any]:
        """8.7.7 结束自由跑并提交结算"""
        return self.transport.post("/run/finishFreeRun", {
            "runRecordCode": run_record_code,
            "distance": str(distance),
            "duration": str(duration),
            "totalStep": str(total_step),
            "stepInterval": step_interval,
            "paceInterval": pace_interval,
            "status": status,
            "pois": pois,
            "stepList": step_list,
            "paceList": pace_list
        })

    def free_detail(self, run_record_code: str = "", biz_no: str = "", free_detail_no: str = "") -> Dict[str, Any]:
        """8.7.7 查询自由跑详情"""
        payload = {}
        if run_record_code:
            payload["runRecordCode"] = run_record_code
        if biz_no:
            payload["bizNo"] = biz_no
        if free_detail_no:
            payload["freeDetailNo"] = free_detail_no
        return self.transport.post("/run/free/detail", payload)

    def get_student_qr_code(self) -> Dict[str, Any]:
        """8.7.7 获取学生卡二维码信息"""
        return self.transport.post("/account/getStudentQrCode", {})

    def find_my_course(self) -> Dict[str, Any]:
        """8.7.7 查询我的体育课"""
        return self.transport.post("/course/findMyCourse", {})

    # --- 5. 跑步历史与统计 ---
    def page_sun_run_record(self, run_plan_code: str = "", page_num: int = 1, page_size: int = 10, semester_code: str = "") -> Dict[str, Any]:
        sc = str(semester_code) if semester_code else ""
        return self.transport.post("/run/pageSunRunRecord", {
            "runPlanCode": run_plan_code,
            "pageNum": str(page_num),
            "pageSize": str(page_size),
            "semesterCode": sc
        })

    def query_sun_run_abstract_info_v2(self, run_plan_code: str = "", semester_code: str = "") -> Dict[str, Any]:
        return self.transport.post("/run/querySunRunAbstractInfoV2", {
            "runPlanCode": run_plan_code,
            "semesterCode": str(semester_code),
            "sportType": "1"
        })

    def query_run_record_count(self, sport_type: str = "1", time_type: str = "3") -> Dict[str, Any]:
        return self.transport.post("/run/queryRunRecordCount", {
            "sportType": sport_type,
            "timeType": time_type
        })

    def query_school_run_summary(self) -> Dict[str, Any]:
        return self.transport.post("/run/querySchoolRunSummary", {
            "time": str(int(time.time() * 1000))
        })

    # --- 6. 人脸底图与直传 STS ---
    def get_user_face_img(self) -> Dict[str, Any]:
        return self.transport.post("/face/getUserFaceImg", {})

    def get_oss_token(self) -> Dict[str, Any]:
        return self.transport.post("/aliyun/oss/getToken", {})

    # --- 7. 排行榜与任务活动 ---
    def get_rank_distance(
        self,
        run_plan_code: str = "",
        sex: int = 1,
        scope: int = 10,
        rank_cycle: int = 10,
        rank_type: int = 1
    ) -> Dict[str, Any]:
        """查询个人里程排行榜 (rank/distance)"""
        return self.transport.post("/rank/distance", {
            "sex": str(sex),
            "scope": str(scope),
            "rankCycle": str(rank_cycle),
            "type": str(rank_type),
            "runPlanCode": run_plan_code
        })

    def get_rank_run_progress(
        self,
        run_plan_code: str = "",
        sex: int = 1,
        scope: int = 10
    ) -> Dict[str, Any]:
        """查询阳光跑达标进度排行榜 (rank/runProgress)"""
        return self.transport.post("/rank/runProgress", {
            "sex": str(sex),
            "scope": str(scope),
            "runPlanCode": run_plan_code
        })

    def sign_today_status(self) -> Dict[str, Any]:
        return self.transport.post("/api/sign/todayStatus", {})

    def login_once_task(self) -> Dict[str, Any]:
        return self.transport.post("/api/tasks/loginOnce", {})

    def run_task(self, task_code: str) -> Dict[str, Any]:
        return self.transport.post("/api/tasks/runTask", {"taskCode": task_code})

    def get_award_home(self) -> Dict[str, Any]:
        return self.transport.post("/api/jackpot/award/home", {})

    def get_lottery_page(self) -> Dict[str, Any]:
        return self.transport.post("/api/jackpot/award/lotteryPage", {})

    def get_fitness_permission(self) -> Dict[str, Any]:
        return self.transport.post("/fitness/permission/query", {})

    def get_fitness_academic_years(self) -> Dict[str, Any]:
        return self.transport.post("/fitness/listAcademicYearByGrade", {})

    def get_fitness_test_records(self, page_num: int = 1, page_size: int = 10) -> Dict[str, Any]:
        return self.transport.post("/fitness/pageFitnessTest", {
            "pageNum": str(page_num),
            "pageSize": str(page_size)
        })

    def get_fitness_detail(self, test_id: str) -> Dict[str, Any]:
        return self.transport.post("/fitness/getFitnessDetail", {"testId": str(test_id)})

    def get_fitness_test_result(self, academic_year: str = "") -> Dict[str, Any]:
        return self.transport.post("/fitness/getFitnessTestResult", {"academicYear": academic_year})

    def get_exam_list(self) -> Dict[str, Any]:
        return self.transport.post("/exam/list", {})

    def get_exam_result(self, exam_id: str = "") -> Dict[str, Any]:
        return self.transport.post("/exam/result", {"examId": str(exam_id)} if exam_id else {})

    def get_exam_paper_detail(self, paper_id: str) -> Dict[str, Any]:
        return self.transport.post("/exam/paper-detail", {"paperId": str(paper_id)})

    def get_attend_statistics(self, semester_code: str = "") -> Dict[str, Any]:
        return self.transport.post("/attend/statistics", {"semesterCode": semester_code})

    def get_student_course_attend_list(self, semester_code: str = "") -> Dict[str, Any]:
        return self.transport.post("/attend/studentCourseAttendList", {"semesterCode": semester_code})


    def list_academic_year_by_grade(self) -> Dict[str, Any]:
        return self.get_fitness_academic_years()

    def page_free_run_record_list(self, page_num: int = 1, page_size: int = 10) -> Dict[str, Any]:
        return self.transport.post("/run/pageFreeRunRecord", {"pageNum": str(page_num), "pageSize": str(page_size)})

    # --- 6. AI 室内运动核心业务 (8.7.7) ---
    def get_ai_categories(self) -> Dict[str, Any]:
        """获取 AI 运动项目分类及各动作配置"""
        return self.transport.post("/ai/getAICategory", {}, v="getAICategory", api="ai")

    def get_indoor_config(self, sport_type: int = 2) -> Dict[str, Any]:
        """获取指定 AI 运动项目的考核配置 (requireTime, aiPattern)"""
        return self.transport.post("/indoor/config", {"type": sport_type}, v="config", api="indoor")

    def get_sport_count(self, sport_type: int = 2) -> Dict[str, Any]:
        """查询 AI 运动项目累计完成数据 (completeTotal, timeTotal, calorieTotal)"""
        return self.transport.post("/indoor/sportCount", {"type": sport_type}, v="sportCount", api="indoor")

    def get_sports_page(self, sport_type: int = 2, page_num: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """查询 AI 运动项目历史记录分页"""
        return self.transport.post("/indoor/sportsPage", {
            "type": sport_type,
            "pageNum": str(page_num),
            "pageSize": str(page_size)
        }, v="sportsPage", api="indoor")

    def finish_indoor_exercise(
        self,
        sport_type: int = 2,
        total: int = 35,
        duration: int = 60,
        require_duration: int = 60,
        start_time_ms: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        AI 室内运动一键结算 (indoor/finish)
        """
        now_ms = int(time.time() * 1000)
        start_ms = start_time_ms or (now_ms - duration * 1000)
        payload = {
            "type": int(sport_type),
            "startTime": str(start_ms),
            "total": str(total),
            "duration": str(duration),
            "requireDuration": str(require_duration)
        }
        return self.transport.post("/indoor/finish", payload, v="finish", api="indoor")

    def execute_complete_ai_exercise(
        self,
        sport_type: int = 2,
        total: int = 35,
        duration: int = 62
    ) -> Dict[str, Any]:
        """
        一键秒级完成指定 AI 运动：拉取配置 -> 推算时间 -> 提交结算
        """
        cfg_res = self.get_indoor_config(sport_type)
        require_time = 60
        if cfg_res.get("code") == 0 and cfg_res.get("data"):
            require_time = cfg_res["data"].get("requireTime", 60)

        finish_res = self.finish_indoor_exercise(
            sport_type=sport_type,
            total=total,
            duration=duration,
            require_duration=require_time
        )
        return finish_res

    def get_semester_list(self) -> Dict[str, Any]:
        """获取全量历史学期列表"""
        return self.transport.post("/attend/semesterSelector", {})

    # --- 7. 人脸认证、跑单申诉与日常任务 (8.7.7) ---
    def bind_user_face(self, face_img_url: str) -> Dict[str, Any]:
        """首次绑定/人脸认证底图 (face/bindUserFace)"""
        return self.transport.post("/face/bindUserFace", {"faceImg": face_img_url})

    def update_user_face(self, face_img_url: str) -> Dict[str, Any]:
        """更新/重新认证人脸底图 (face/updateUserFace)"""
        return self.transport.post("/face/updateUserFace", {"faceImg": face_img_url})

    def close_user_face(self) -> Dict[str, Any]:
        """关闭人脸识别认证 (face/closeUserFace)"""
        return self.transport.post("/face/closeUserFace", {})

    def get_available_tasks(self) -> Dict[str, Any]:
        """查询每日可用任务列表 (api/tasks/available/list)"""
        return self.transport.post("/api/tasks/available/list", {})

    def query_appeal_list(self) -> Dict[str, Any]:
        """查询历史跑单申诉记录 (sport/appealList)"""
        return self.transport.post("/sport/appealList", {})

    def submit_run_appeal(self, run_record_code: str, problem_content: str, img_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """提交异常跑单申诉 (run/appealRunRecord)"""
        payload = {
            "runRecordCode": run_record_code,
            "problemContent": problem_content,
            "images": img_urls or []
        }
        return self.transport.post("/run/appealRunRecord", payload)

    def abandon_unfinished_run(self, run_record_code: str) -> Dict[str, Any]:
        """放弃挂起的未完成跑单 (run/abnormalFinishSunRun)"""
        return self.transport.post("/run/abnormalFinishSunRun", {"runRecordCode": run_record_code})

    # --- 8. 社区动态、校园新鲜事与帖子浏览 (8.7.7) ---
    def get_works_recommend_pool(self, page_num: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """查询首页校园新鲜事推荐流 (api/works/recommend/pool/list)"""
        return self.transport.post("/api/works/recommend/pool/list", {
            "pageNum": str(page_num),
            "pageSize": str(page_size)
        })

    def get_works_detail(self, works_no: str) -> Dict[str, Any]:
        """查询指定帖子图文详情 (api/works/details)"""
        return self.transport.post("/api/works/details", {"worksNo": works_no})

    def get_works_comments(self, works_no: str, page_num: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """查询帖子一级评论列表 (api/works/comment/pageList)"""
        return self.transport.post("/api/works/comment/pageList", {
            "worksNo": works_no,
            "pageNum": str(page_num),
            "pageSize": str(page_size)
        })

    def get_works_sub_comments(self, works_no: str, comment_id: str, page_num: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """查询帖子楼中楼二级回复列表 (api/works/comment/sub/pageList)"""
        return self.transport.post("/api/works/comment/sub/pageList", {
            "worksNo": works_no,
            "commentId": str(comment_id),
            "pageNum": str(page_num),
            "pageSize": str(page_size)
        })

    def get_works_categories(self) -> Dict[str, Any]:
        """查询社区作品分类专区列表 (api/works/category/list)"""
        return self.transport.post("/api/works/category/list", {})

    def search_works(self, keyword: str, page_num: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """根据关键词检索帖子作品 (api/works/search/pageList)"""
        return self.transport.post("/api/works/search/pageList", {
            "searchContent": keyword,
            "pageNum": str(page_num),
            "pageSize": str(page_size)
        })

    def get_channel_hotspot_list(self) -> Dict[str, Any]:
        """查询校园热门频道与话题榜单 (api/channel/hotspot/list)"""
        return self.transport.post("/api/channel/hotspot/list", {})

    def update_works_visit(self, works_no: str) -> Dict[str, Any]:
        """上报帖子作品浏览记录 (api/works/updateVisit)"""
        return self.transport.post("/api/works/updateVisit", {"worksNo": works_no})

    # --- 9. 本校板块与校友录 (8.7.7) ---
    def get_myschool_info(self) -> Dict[str, Any]:
        """查询本校官方频道与基础信息 (mySchool/simpleInfo)"""
        return self.transport.post("/mySchool/simpleInfo", {})

    def get_schoolmate_config(self) -> Dict[str, Any]:
        """查询校友圈年级与标签筛选配置 (api/schoolmate/search/config)"""
        return self.transport.post("/api/schoolmate/search/config", {})

    def search_schoolmates(
        self,
        page_num: int = 1,
        page_size: int = 10,
        grade_code: str = "",
        tag_no: str = ""
    ) -> Dict[str, Any]:
        """分页检索同校校友推荐列表 (api/schoolmate/recommend/search)"""
        payload = {
            "pageNum": str(page_num),
            "pageSize": str(page_size)
        }
        if grade_code:
            payload["gradeCode"] = grade_code
        if tag_no:
            payload["tagNo"] = tag_no
        return self.transport.post("/api/schoolmate/recommend/search", payload)

    def say_hello_to_schoolmate(self, target_user_code: str) -> Dict[str, Any]:
        """向同校校友打招呼互动 (api/social/sayHello)"""
        return self.transport.post("/api/social/sayHello", {"targetUserCode": target_user_code})

    # --- 10. 闪信与消息通知中心 (8.7.7) ---
    def get_message_user_groups(self) -> Dict[str, Any]:
        """查询消息中心会话与未读分组 (api/message/userGroup)"""
        return self.transport.post("/api/message/userGroup", {})

    def get_message_red_dot(self) -> Dict[str, Any]:
        """查询闪信消息未读红点状态 (api/message/redDot)"""
        return self.transport.post("/api/message/redDot", {})

    def clear_message_red_dot(self, group_id: str = "") -> Dict[str, Any]:
        """一键消除消息未读红点标记 (api/message/clearRedDot)"""
        return self.transport.post("/api/message/clearRedDot", {"groupId": group_id} if group_id else {})

    def get_system_message_box(self, page_num: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """查询系统小秘书通知信箱分页 (api/message/messageBox)"""
        return self.transport.post("/api/message/messageBox", {
            "pageNum": str(page_num),
            "pageSize": str(page_size)
        })

    def get_comment_message_list(self, page_num: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """查询收到的评论回复消息列表 (api/message/commentList)"""
        return self.transport.post("/api/message/commentList", {
            "pageNum": str(page_num),
            "pageSize": str(page_size)
        })

    def get_favor_message_list(self, page_num: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """查询收到的点赞互动消息列表 (api/message/favorList)"""
        return self.transport.post("/api/message/favorList", {
            "pageNum": str(page_num),
            "pageSize": str(page_size)
        })

    def get_fans_message_list(self, page_num: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """查询收到的粉丝关注消息列表 (api/message/fansList)"""
        return self.transport.post("/api/message/fansList", {
            "pageNum": str(page_num),
            "pageSize": str(page_size)
        })

    def get_buddy_home(self) -> Dict[str, Any]:
        """查询好友通讯录与单聊会话主页 (buddy/home)"""
        return self.transport.post("/buddy/home", {})

    def search_buddies(self, keyword: str = "") -> Dict[str, Any]:
        """搜索闪信联系人与好友 (buddy/search)"""
        return self.transport.post("/buddy/search", {"keyword": keyword})

    def apply_buddy(self, target_user_id: str, reason: str = "") -> Dict[str, Any]:
        """发送添加闪信好友申请 (buddy/apply)"""
        return self.transport.post("/buddy/apply", {
            "targetUserId": target_user_id,
            "applyReason": reason
        })

    def get_chatroom_list(self) -> Dict[str, Any]:
        """查询聊天室与群组会话列表 (buddy/chatRoom/list)"""
        return self.transport.post("/buddy/chatRoom/list", {})
