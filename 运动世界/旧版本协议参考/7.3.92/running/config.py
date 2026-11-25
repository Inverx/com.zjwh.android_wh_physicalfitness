# -*- coding: utf-8 -*-
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core.config import HOST_RUN

# 7.3.92 跑步提交与 OBS 华为云网络端点
URL_OBS_TEMPORARY_URL = f"{HOST_RUN}/api/obs/temporary/url"
URL_SAVE_RECORD = f"{HOST_RUN}/api/v70260/runnings/save/record"
URL_RUN_DETAIL_CONFIG = f"{HOST_RUN}/api/v70340/activity/rundetail/config"

# 7.3.92 实测逐字节一致的 33 字节静态加盐
SPORT_STATIC_SALT = "2slhe02lsfiwowlcixisla_sls-_slaor"
OBS_BUCKET_NAME = "iydsj-hbase-hot"
