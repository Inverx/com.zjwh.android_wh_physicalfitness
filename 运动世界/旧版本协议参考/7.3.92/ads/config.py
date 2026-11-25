# -*- coding: utf-8 -*-
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core.config import HOST_DISCOVERY, HOST_DATAPOINT

URL_AD_CONFIG = f"{HOST_DISCOVERY}/api/v70360/ad/config"
URL_SLOT_LIST = f"{HOST_DISCOVERY}/api/v70340/resource/slot/list"
URL_AD_PV = f"{HOST_DATAPOINT}/api/v70260/datacollection/ad/pv"
URL_ADSC = "https://api.yfanads.com/api/v2/ads/adsc"
URL_BATCH_UPLOAD = "https://tracker.yfanads.com/api/v2/ads/batchUpload"
