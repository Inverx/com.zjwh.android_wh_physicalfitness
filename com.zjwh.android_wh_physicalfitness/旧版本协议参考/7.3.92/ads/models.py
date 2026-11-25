# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class AdWatchResult:
    """看广告与激励视频模拟结果"""
    success: bool
    ad_position: str
    message: str
    events_count: int = 0
    duration_sec: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)
