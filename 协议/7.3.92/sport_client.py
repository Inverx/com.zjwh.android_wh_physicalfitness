import os
import sys
from typing import Optional, Dict, Any, Union, Callable

cur_dir = os.path.dirname(os.path.abspath(__file__))
if cur_dir not in sys.path:
    sys.path.insert(0, cur_dir)

from core.config import DEFAULT_DEVICE_CONFIG, load_customer_device
from core.devices import DeviceStore
from login.client import LoginClient
from login.models import LoginResult
from profile.client import ProfileClient
from profile.models import ServerTime, UserProfileDetails
from policy.client import PolicyClient
from policy.models import RunRule, GeoFenceArea, SemesterInfo
from telemetry.client import TelemetryClient
from running.client import RunningClient
from running.models import RunningSubmissionResult
from history.client import HistoryClient
from history.models import RunRecordDetail
from ads.client import AdClient
from ads.models import AdWatchResult


class SportClient792:
    """运动世界校园 7.3.92 统一客户端门面对象"""

    def __init__(self,
                 uid: Optional[Union[int, str]] = None,
                 token: Optional[str] = None,
                 unid: Optional[Union[int, str]] = None,
                 device_config: Optional[Dict[str, Any]] = None,
                 account: Optional[str] = None,
                 device_dir: Optional[str] = None):
        self.device_store = DeviceStore(device_dir)
        self._explicit_device = device_config is not None
        self._account = account
        if self._explicit_device:
            self.device_config = load_customer_device()
            self.device_config.update(device_config)
        elif account:
            self.device_config = self.device_store.for_account(account)
        elif uid is not None and str(uid) != "-1":
            self.device_config = self.device_store.for_uid(uid)
        else:
            self.device_config = load_customer_device()

        self.uid = str(uid) if uid is not None and str(uid) != "-1" else None
        self.token = str(token) if token else None
        self.unid = str(unid) if unid is not None else None

        self._initialize_clients()

    def _initialize_clients(self):
        # Every subclient receives the same saved device configuration.
        self.login_client = LoginClient(device_config=self.device_config)
        self.telemetry = TelemetryClient(device_config=self.device_config)
        self.profile = ProfileClient(uid=self.uid, token=self.token, unid=self.unid, device_config=self.device_config)
        self.policy = PolicyClient(uid=self.uid, token=self.token, unid=self.unid, device_config=self.device_config)
        self.running = RunningClient(uid=self.uid, token=self.token, unid=self.unid, device_config=self.device_config)
        self.history = HistoryClient(uid=self.uid, token=self.token, unid=self.unid, device_config=self.device_config)
        self.ads = AdClient(uid=self.uid, token=self.token, unid=self.unid, device_config=self.device_config)

    def set_credentials(self, uid: Union[int, str], token: str, unid: Optional[Union[int, str]] = None):
        """更新当前客户端上下文中的认证凭据"""
        if not self._explicit_device:
            config = self.device_store.for_uid(uid)
            if config != self.device_config:
                self.device_config = config
                self._initialize_clients()
        self.uid = str(uid)
        self.token = str(token)
        if unid is not None:
            self.unid = str(unid)
        self.profile.set_credentials(self.uid, self.token, self.unid)
        self.policy.set_credentials(self.uid, self.token, self.unid)
        self.running.set_credentials(self.uid, self.token, self.unid)
        self.history.set_credentials(self.uid, self.token, self.unid)
        self.ads.set_credentials(self.uid, self.token, self.unid)

    # 1. 登录认证子系统
    def login(self, username: str, password: str, progress_callback: Optional[Callable[[str], None]] = None) -> LoginResult:
        """全自动登录 (checkGeeUse -> 极验 v4 无头识别与拟人滑动 -> geevalidate -> login)"""
        if not self._explicit_device:
            config = self.device_store.for_account(username)
            if config != self.device_config:
                self.device_config = config
                self._initialize_clients()
            self._account = username
        res = self.login_client.login(username, password, progress_callback=progress_callback)
        if res.success and res.user:
            if not self._explicit_device:
                self.device_store.bind_uid(username, res.user.uid)
            self.set_credentials(uid=res.user.uid, token=res.user.token, unid=res.user.unid)
        return res

    # 2. 时间与档案子系统
    def sync_server_time(self) -> ServerTime:
        return self.profile.get_server_time()

    def get_user_profile(self) -> Optional[UserProfileDetails]:
        profile = self.profile.get_user_info()
        if profile and not self.unid:
            try:
                if int(profile.uid) == int(self.uid) and int(profile.unid) > 0:
                    self.set_credentials(self.uid, self.token, profile.unid)
            except (TypeError, ValueError):
                pass
        return profile

    # 3. 规则与围栏子系统
    def get_run_policy(self, run_mode: int = 1) -> Optional[RunRule]:
        rule = self.policy.get_run_policy(run_mode=run_mode)
        if not self.unid and self.policy.unid:
            self.set_credentials(self.uid, self.token, self.policy.unid)
        return rule

    def get_geo_fences(self) -> list:
        return self.policy.get_geo_fence()

    def get_semester_progress(self, run_mode: int = 1) -> Optional[SemesterInfo]:
        return self.policy.get_semester_info(run_mode=run_mode)

    # 4. 跑步提交子系统 (支持 sport_type=1 计分跑 与 sport_type=6 自由跑)
    def execute_run(self,
                    target_distance_m: int = 2150,
                    target_time_sec: int = 1200,
                    sport_type: int = 1,
                    progress_callback: Optional[Callable[[str], None]] = None) -> RunningSubmissionResult:
        """
        全时序拟人跑步提交流程：
        - sport_type=1: 计分跑（校园考核，强制经过 5 个必经打卡点与围栏范围）；
        - sport_type=6: 自由跑（阳光跑，自由路线，无需必经打卡点）。
        """
        return self.running.execute_full_run(
            target_distance_m=target_distance_m,
            target_time_sec=target_time_sec,
            sport_type=sport_type,
            progress_callback=progress_callback
        )

    # 5. 看广告与激励视频子系统
    def watch_ad(self,
                 ad_position: str = "4",
                 duration_sec: int = 15,
                 progress_callback: Optional[Callable[[str], None]] = None) -> AdWatchResult:
        """
        模拟看广告与激励视频全流程：
        - ad_position="4": 激励视频 (运动完成奖励或看广告加倍)；
        - ad_position="2": 开屏/首页弹窗广告；
        - ad_position="1": 信息流 Banner 广告。
        """
        return self.ads.simulate_watch_ad(
            ad_position=ad_position,
            duration_sec=duration_sec,
            progress_callback=progress_callback
        )

    # 6. 历史记录与成绩自核验子系统
    def get_run_record_detail(self, rrid: int) -> Optional[RunRecordDetail]:
        return self.history.get_one_record(rrid=rrid)

    def get_history_records(self, page_num: int = 1, page_size: int = 20) -> dict:
        return self.history.get_run_records(page_num=page_num, page_size=page_size)

    def get_calendar(self, year: Optional[int] = None, month: Optional[int] = None) -> dict:
        return self.history.get_calendar_list(year=year, month=month)


    def get_cheat_blacklist(self) -> dict:
        return self.telemetry.get_cheat_blacklist(self.profile)

    def get_barrier_free_policy(self) -> dict:
        return self.telemetry.get_barrier_free_policy(self.profile)

    def get_ranks(self, rank_type: int = 1) -> dict:
        return self.telemetry.get_rank_list(self.profile, rank_type=rank_type)

    def get_credit_popup(self) -> dict:
        return self.telemetry.get_credit_popup(self.profile)


    def warmup_home(self) -> dict:
        return self.profile.warmup_dashboard_session()

    def get_distance_route(self, sport_type: int = 1, distance_m: int = 1000) -> dict:
        return self.policy.get_distance_route_points(sport_type=sport_type, distance_m=distance_m)
