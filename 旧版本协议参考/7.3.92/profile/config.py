# -*- coding: utf-8 -*-
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core.config import HOST_RUN, HOST_DISCOVERY

# 用户与时间相关网络端点
URL_SERVER_TIME = f"{HOST_RUN}/api/v3/getserver/gmttime"
URL_USER_INFO = f"{HOST_RUN}/api/v70390/user/info"
URL_HOME_BASE_USER = f"{HOST_RUN}/api/v76/user/homePageBaseUserInfo"
URL_HOME_EXTENDED_USER = f"{HOST_DISCOVERY}/api/v70370/user/homePageExtendedInfo"
