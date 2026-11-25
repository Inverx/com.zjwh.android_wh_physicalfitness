"""跑步协议数据包结构定义。仅保留接口字段规范，具体轨迹计算算法请自行实现。"""
from typing import List, Dict, Any, Optional

def generate_trajectory_data(
    start_lat: float = 0.0,
    start_lng: float = 0.0,
    target_distance_m: float = 2000.0,
    avg_pace_sec_per_km: int = 360,
    start_timestamp_ms: Optional[int] = None
) -> Dict[str, Any]:
    """
    轨迹生成接口占位。
    开源版本已去除具体拟真与插值算法。
    调用者需自行实现坐标点序列生成与步频配速统计。
    """
    raise NotImplementedError("轨迹计算算法已移除，请自行完善坐标生成逻辑。")

# 8.7.7 官方跑步数据包字段规范参考：
# pois: List[Dict]: [{"lat": float, "lng": float, "stability": int, "accuracy": float, "collectTime": int}]
# stepList: List[Dict]: [{"index": int, "startTime": int, "endTime": int, "startStep": int, "endStep": int, "step": int, "time": int, "stability": int}]
# paceList: List[Dict]: [{"index": int, "startTime": int, "endTime": int, "startDistance": int, "endDistance": int, "distance": int, "time": int, "startStepCount": int, "endStepCount": int, "stepCount": int, "stability": int}]
# strideList: List[Dict]: [{"index": int, "time": int, "distance": int, "stride": int, "step": int}]
# targetPoints: List[Dict]: [{"code": int/str, "lat": float, "lng": float, "type": int, "passStatus": bool, "clockTime": int}]
