# -*- coding: utf-8 -*-
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core.config import HOST_DATAPOINT, HOST_PARTNER, HOST_DISCOVERY

URL_STARTUP_PV = f"{HOST_DATAPOINT}/api/v76/startup/pv"
URL_DATA_COLLECTION_PV = f"{HOST_DATAPOINT}/api/v76/datacollection/pv"
URL_AD_PV = f"{HOST_DATAPOINT}/api/v70260/datacollection/ad/pv"
URL_DEVICE_VERIFY = f"{HOST_PARTNER}/api/v620/datacollection/geetest/deviceVerify"
URL_CONTROL_MESSAGE = "https://control.gxapp.iydsj.com/getMessage"
URL_BARRIER_FREE = f"{HOST_DISCOVERY}/api/v1/barrierFree/getBarrierFree"
URL_CHEAT_LIST = f"{HOST_DISCOVERY}/api/v78/cheat/cheatlist"
URL_RANK_LIST = f"{HOST_DISCOVERY}/api/v41/rank"
URL_CREDIT_POPUP = "https://run.gxapp.iydsj.com/api/creditscore/v70390/popup?taskType=2"
