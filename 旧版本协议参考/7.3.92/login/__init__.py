# -*- coding: utf-8 -*-
"""
运动世界校园 7.3.92 独立登录模块
提供纯协议登录、极验 v4 自动化滑块识别、会话签名与 Token 获取能力。
"""

from .config import (
    DEFAULT_HOST_RUN,
    DEFAULT_HOST_DISCOVERY,
    URL_CHECK_GEE_USE,
    URL_GEE_VALIDATE,
    URL_LOGIN,
    LOGIN_CAPTCHA_ID,
    DEFAULT_DEVICE_CONFIG,
)
from .models import (
    GeetestResult,
    UserProfile,
    LoginResult,
)
from .captcha import GeetestV4Solver
from .client import LoginClient

__all__ = [
    "LoginClient",
    "LoginResult",
    "UserProfile",
    "GeetestResult",
    "GeetestV4Solver",
    "DEFAULT_DEVICE_CONFIG",
    "URL_CHECK_GEE_USE",
    "URL_GEE_VALIDATE",
    "URL_LOGIN",
    "LOGIN_CAPTCHA_ID",
]

