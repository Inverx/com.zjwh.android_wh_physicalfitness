# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class RunRecordDetail:
    """单次跑步详情模型 (/api/v70320/runnings/get_one_record)"""
    rrid: int
    sport_type: int
    total_distance: float
    valid_distance: float
    total_time: int
    valid_time: int
    calorie: int
    status: int
    is_valid: bool
    uncomplete_reason: int
    start_time: int
    stop_time: int
    avg_speed: str
    avg_step_freq: int
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_data(cls, data: Dict[str, Any]) -> "RunRecordDetail":
        status = int(data.get("status", 0))
        un_reason = int(data.get("unCompleteReason", 0))
        # status == 1 and unCompleteReason == 0 视为合规达标
        is_valid = (status == 1 and un_reason == 0)
        return cls(
            rrid=int(data.get("rrid", 0) or data.get("id", 0)),
            sport_type=int(data.get("sportType", 1)),
            total_distance=float(data.get("totalDis", 0.0) or data.get("distance", 0.0)),
            valid_distance=float(data.get("validDis", 0.0)),
            total_time=int(data.get("totalTime", 0) or data.get("costTime", 0)),
            valid_time=int(data.get("validTime", 0)),
            calorie=int(data.get("calorie", 0)),
            status=status,
            is_valid=is_valid,
            uncomplete_reason=un_reason,
            start_time=int(data.get("startTime", 0)),
            stop_time=int(data.get("stopTime", 0)),
            avg_speed=str(data.get("speed", "-")),
            avg_step_freq=int(data.get("avgStepFreq", 0)),
            raw=data
        )

def parse_history_records(data):
    """Accept the current list response and the older recordList envelope."""
    if isinstance(data, str):
        import json
        data = json.loads(data)
    if data is None:
        return []
    if isinstance(data, dict):
        if "recordList" not in data:
            raise ValueError("历史响应对象缺少 recordList")
        data = data["recordList"]
        if data is None:
            return []
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ValueError("历史记录应为对象列表")
    return data


def history_record_status(record):
    """A normal status alone does not establish that the run was completed."""
    if record.get("complete") is False or record.get("isValid") is False:
        return "未达标"
    if record.get("isValid") is True or (record.get("status") == 1 and record.get("complete") is True):
        return "达标"
    return f"状态码={record.get('status')}"
