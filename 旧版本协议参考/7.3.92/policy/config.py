# -*- coding: utf-8 -*-
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(cur_dir)
for p in [cur_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core.config import HOST_RUN

# 规则与围栏接口端点
URL_RUN_POLICY = f"{HOST_RUN}/api/v70103/runModePolicy"
URL_INDOOR_POLICY = f"{HOST_RUN}/api/v59/indoorRunModePolicy"
URL_GEO_FENCE = f"{HOST_RUN}/api/v1/getGeoFenceForRun"
URL_SEMESTER_INFO = f"{HOST_RUN}/api/v41/running/getPersonalSemesterInfo"
URL_SEMESTER_SUMMARY = f"{HOST_RUN}/api/v55/runnings/recordssummary/semester"
URL_RUN_GOALS = f"{HOST_RUN}/api/run/goals/v70260/query"
