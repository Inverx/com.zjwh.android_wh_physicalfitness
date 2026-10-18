# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class GpsPoint:
    """单个 GPS 运动轨迹采样点"""
    lat: float
    lon: float
    time: int
    speed: float = 2.5
    accuracy: float = 3.0
    isValid: bool = True

    def to_dict(self) -> dict:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "time": self.time,
            "speed": self.speed,
            "accuracy": self.accuracy,
            "isValid": self.isValid
        }


@dataclass
class FivePoint:
    """必经打卡目标点"""
    lat: float
    lon: float
    isFixed: int = 1
    isPass: bool = True
    pointName: str = ""
    position: int = 0

    def to_dict(self) -> dict:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "isFixed": self.isFixed,
            "isPass": self.isPass,
            "pointName": self.pointName,
            "position": self.position
        }


@dataclass
class StepBucket:
    """10秒步频分桶统计"""
    stepsNum: int = 0
    beginTime: int = 0
    endTime: int = 0
    flag: int = 0
    maxDiff: float = 0.0
    minDiff: float = 0.0
    avgDiff: float = 0.0
    state: int = 0
    queueNum: int = 1

    def __init__(self, stepsNum: int = 0, beginTime: int = 0, endTime: int = 0,
                 flag: int = 0, maxDiff: float = 0.0, minDiff: float = 0.0,
                 avgDiff: float = 0.0, state: int = 0, queueNum: int = 1,
                 steps_num: Optional[int] = None, begin_time: Optional[int] = None,
                 end_time: Optional[int] = None, max_diff: Optional[float] = None,
                 min_diff: Optional[float] = None, avg_diff: Optional[float] = None,
                 queue_num: Optional[int] = None):
        self.stepsNum = steps_num if steps_num is not None else stepsNum
        self.beginTime = begin_time if begin_time is not None else beginTime
        self.endTime = end_time if end_time is not None else endTime
        self.flag = flag
        self.maxDiff = max_diff if max_diff is not None else maxDiff
        self.minDiff = min_diff if min_diff is not None else minDiff
        self.avgDiff = avg_diff if avg_diff is not None else avgDiff
        self.state = state
        self.queueNum = queue_num if queue_num is not None else queueNum

    def to_dict(self) -> dict:
        return {
            "stepsNum": self.stepsNum,
            "beginTime": self.beginTime,
            "endTime": self.endTime,
            "flag": self.flag,
            "maxDiff": self.maxDiff,
            "minDiff": self.minDiff,
            "avgDiff": self.avgDiff,
            "state": self.state,
            "queueNum": self.queueNum
        }


@dataclass
class SpeedBucket:
    """10秒速度分桶统计"""
    distance: float = 0.0
    beginTime: int = 0
    endTime: int = 0
    flag: int = 0
    state: int = 0
    queueNum: int = 1

    def __init__(self, distance: float = 0.0, beginTime: int = 0, endTime: int = 0,
                 flag: int = 0, state: int = 0, queueNum: int = 1,
                 begin_time: Optional[int] = None, end_time: Optional[int] = None,
                 queue_num: Optional[int] = None):
        self.distance = distance
        self.beginTime = begin_time if begin_time is not None else beginTime
        self.endTime = end_time if end_time is not None else endTime
        self.flag = flag
        self.state = state
        self.queueNum = queue_num if queue_num is not None else queueNum

    def to_dict(self) -> dict:
        return {
            "distance": self.distance,
            "beginTime": self.beginTime,
            "endTime": self.endTime,
            "flag": self.flag,
            "state": self.state,
            "queueNum": self.queueNum
        }


@dataclass
class RunningSubmissionResult:
    """跑步提交结果模型"""
    success: bool
    rrid: Optional[int] = None
    error_code: int = -1
    message: str = ""
    total_distance: float = 0.0
    total_time: int = 0
    is_valid: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)
