import base64
import gzip
import hashlib
import json
import math
import random
import time
import uuid
from typing import List, Tuple, Dict, Any, Optional, Union

from record_validation import validate_run, time_buckets, validate_coordinate

from .config import SPORT_STATIC_SALT
from .models import GpsPoint, FivePoint, StepBucket, SpeedBucket


def compute_sport_signature(field_map: Dict[str, Union[str, int, float, bool, None]],
                            salt: str = SPORT_STATIC_SALT) -> str:
    """计算 31 参数运动学加盐 MD5 校验签名"""
    valid_items = []
    for k, v in field_map.items():
        if v is None:
            continue
        if k.lower() == "signature":
            continue
        valid_items.append((k, str(v).lower() if isinstance(v, bool) else str(v)))
    
    valid_items.sort(key=lambda x: (x[0].lower(), x[0]))
    canonical_str = "&".join(f"{k}={v}" for k, v in valid_items)
    to_hash = (canonical_str + salt).encode("utf-8")
    return hashlib.md5(to_hash).hexdigest().lower()


def compute_original_sign(field_map: Dict[str, Union[str, int, float, bool, None]]) -> str:
    """计算原始参数键值对拼接串"""
    valid_items = []
    for k, v in field_map.items():
        if v is None:
            continue
        if k.lower() == "signature":
            continue
        valid_items.append((k, str(v).lower() if isinstance(v, bool) else str(v)))
    
    valid_items.sort(key=lambda x: x[0])
    return "&".join(f"{k}={v}" for k, v in valid_items)


def gzip_base64_encode(data: Union[str, bytes]) -> str:
    """Gzip 压缩并转为 Base64 字符串"""
    if isinstance(data, str):
        data_bytes = data.encode("utf-8")
    else:
        data_bytes = data
    compressed = gzip.compress(data_bytes)
    return base64.b64encode(compressed).decode("ascii")


class RunningTrackBuilder:
    """运动轨迹、传感器步频分桶与 7.3.92 报文组装构建器"""

    def __init__(self, uid: int, unid: int, sport_type: int = 1, uuid_str: Optional[str] = None):
        self.uid = int(uid)
        self.unid = int(unid)
        # sport_type: 1 为计分跑（校园考核），6 为自由跑（阳光跑/课外自由锻炼）
        self.sport_type = int(sport_type)
        self.uuid_str = uuid_str or str(uuid.uuid4())

    def generate_track_around_points(self,
                                    center_lat: float,
                                    center_lng: float,
                                    checkpoints: Optional[List[Dict[str, Any]]] = None,
                                    total_distance_m: int = 2100,
                                    total_time_sec: int = 760,
                                    start_time_ms: int = 0) -> Tuple[List[GpsPoint], List[FivePoint]]:
        """根据模式 (sportType=1 计分跑 vs sportType=6 自由跑) 生成真实平滑的 GPS 坐标序列"""
        validate_run(total_time_sec, 0, start_time_ms,
                     start_time_ms + total_time_sec * 1000, total_distance_m)
        center_lat, center_lng = validate_coordinate(center_lat, center_lng)
        if self.sport_type not in (1, 6):
            raise ValueError("unsupported sport type")
        if self.sport_type == 1 and not checkpoints:
            raise ValueError("required checkpoints are unavailable")
        interval_sec = 3
        num_points = max(10, total_time_sec // interval_sec)
        points = []

        waypoints = []
        five_points = []
        
        # 1. 计分跑 (sportType=1)：必须绑定打卡点
        if self.sport_type == 1 and checkpoints and len(checkpoints) > 0:
            for idx, cp in enumerate(checkpoints[:5]):
                c_lat = float(cp.get("lat") or cp.get("latitude") or center_lat)
                c_lng = float(cp.get("lng") or cp.get("longitude") or center_lng)
                validate_coordinate(c_lat, c_lng)
                waypoints.append((c_lat, c_lng))
                five_points.append(FivePoint(
                    lat=c_lat,
                    lon=c_lng,
                    isFixed=1,
                    isPass=True,
                    pointName=str(cp.get("name") or cp.get("pointName") or f"P_{idx+1}"),
                    position=idx + 1
                ))
        else:
            # 2. 自由跑 (sportType=6)：无必经打卡点约束 (fivePoints为空)，生成自然公路环线
            radius_deg = 0.0020
            for i in range(8):
                ang = (2 * math.pi * i) / 8
                c_lat = center_lat + radius_deg * math.cos(ang)
                c_lng = center_lng + radius_deg * math.sin(ang)
                waypoints.append((c_lat, c_lng))
            five_points = []

        # 插值生成连续轨迹点，添加拟人化高斯噪声与自然速度波动
        base_speed = (total_distance_m / total_time_sec) if total_time_sec > 0 else 2.6
        for i in range(num_points):
            t_frac = i / max(1, (num_points - 1))
            pt_time = int(start_time_ms + t_frac * (total_time_sec * 1000))
            
            cycle_pos = (t_frac * (len(waypoints) * 2)) % len(waypoints)
            w_idx1 = int(cycle_pos)
            w_idx2 = (w_idx1 + 1) % len(waypoints)
            w_frac = cycle_pos - w_idx1
            
            p1 = waypoints[w_idx1]
            p2 = waypoints[w_idx2]
            
            lat_base = p1[0] + (p2[0] - p1[0]) * w_frac
            lng_base = p1[1] + (p2[1] - p1[1]) * w_frac
            
            lat = round(lat_base + (random.random() - 0.5) * 0.00003, 6)
            lng = round(lng_base + (random.random() - 0.5) * 0.00003, 6)
            spd = round(max(1.8, min(4.2, base_speed + (random.random() - 0.5) * 0.4)), 2)
            acc = round(random.uniform(2.5, 4.8), 1)
            
            points.append(GpsPoint(lat=lat, lon=lng, time=pt_time, speed=spd, accuracy=acc, isValid=True))

        return points, five_points

    def build_submission_payload(self,
                                total_distance_m: int,
                                total_time_sec: int,
                                total_steps: int,
                                start_time_ms: int,
                                stop_time_ms: int,
                                gps_points: List[GpsPoint],
                                five_points: List[FivePoint],
                                sel_distance_m: int = 2000,
                                sel_run_time_s: Optional[int] = None,
                                calorie: int = 135,
                                avg_power: int = 150) -> Tuple[dict, dict, str]:
        """组装完整的 save/record 报文、OBS 上传大对象与相对路径"""
        validate_run(total_time_sec, total_steps, start_time_ms, stop_time_ms,
                     total_distance_m)
        if sel_run_time_s is None:
            sel_run_time_s = total_time_sec
        if (not gps_points or sel_distance_m <= 0 or sel_run_time_s <= 0
                or calorie < 0 or avg_power < 0):
            raise ValueError("track, positive thresholds and nonnegative energy are required")
        if gps_points[0].time != start_time_ms or gps_points[-1].time != stop_time_ms:
            raise ValueError("track timestamps must match the run")
        for point in gps_points:
            validate_coordinate(point.lat, point.lon)
            if (not isinstance(point.time, int) or not math.isfinite(point.speed)
                    or point.speed < 0 or not math.isfinite(point.accuracy) or point.accuracy < 0):
                raise ValueError("invalid track timestamp, speed or accuracy")
        if any(a.time >= b.time for a, b in zip(gps_points, gps_points[1:])):
            raise ValueError("track timestamps must increase")
        if self.sport_type == 1 and not five_points:
            raise ValueError("required checkpoints are unavailable")
        # selRunTime is a selected payload value, not a verified school minimum.
        # This local flag does not replace the server's record-validity verdict.
        complete = total_distance_m >= sel_distance_m
        un_complete_reason = 0 if complete else 10
        avg_step_freq = round(total_steps * 60.0 / total_time_sec) if total_time_sec > 0 else 165
        speed_val = round((total_distance_m / total_time_sec) * 1000) if total_time_sec > 0 else 2600

        # 1. 签名参数字典 (严格按照 7.3.92 规则)
        sign_map = {
            "address": "",
            "avgPower": avg_power,
            "avgStepFreq": avg_step_freq,
            "calorie": calorie,
            "complete": complete,
            "errorCode": 0,
            "faceCheck": 0,
            "geeToken": "",
            "getPrize": False,
            "goalId": "null",
            "policy": 1,
            "selDistance": sel_distance_m,
            "selRunTime": sel_run_time_s,
            "selectedUnid": self.unid,
            "speed": speed_val,
            "sportType": self.sport_type,
            "startTime": start_time_ms,
            "status": 1,
            "stopTime": stop_time_ms,
            "themeId": 0,
            "totalAscent": 0,
            "totalDis": total_distance_m,
            "totalSteps": total_steps,
            "totalTime": total_time_sec,
            "uid": self.uid,
            "unCompleteReason": un_complete_reason,
            "unauthorized": 0,
            "useMobilityTools": 0,
            "uuid": self.uuid_str,
            "validDis": total_distance_m,
            "validTime": total_time_sec
        }
        signature = compute_sport_signature(sign_map)
        original_sign = compute_original_sign(sign_map)

        # 2. 生成 10 秒步频与速度分桶
        speed_buckets = []
        step_buckets = []
        for i, (begin, end, steps, distance) in enumerate(time_buckets(
                total_time_sec, total_steps, start_time_ms, stop_time_ms, total_distance_m)):
            speed_buckets.append(SpeedBucket(distance, begin, end, queueNum=i + 1))
            step_buckets.append(StepBucket(steps, begin, end, queueNum=i + 1))

        all_loc_json = json.dumps([p.to_dict() for p in gps_points], separators=(",", ":"))
        five_pt_json = json.dumps([p.to_dict() for p in five_points], separators=(",", ":")) if five_points else "[]"
        speed_json = json.dumps([b.to_dict() for b in speed_buckets], separators=(",", ":"))
        step_json = json.dumps([b.to_dict() for b in step_buckets], separators=(",", ":"))

        # 3. 组装 save/record 报文体
        first_pt = gps_points[0] if gps_points else GpsPoint(0.0, 0.0, start_time_ms)
        save_record = {
            "address": "",
            "allLocJson": all_loc_json,
            "avgPower": avg_power,
            "avgStepFreq": avg_step_freq,
            "calorie": calorie,
            "complete": complete,
            "errorCode": 0,
            "faceCheck": 0,
            "fivePointJson": five_pt_json,
            "geeToken": "",
            "getPrize": False,
            "goalId": None,
            "isUpload": False,
            "latitude": first_pt.lat,
            "longitude": first_pt.lon,
            "maxRunTime": 7200,
            "minSteps": 2000,
            "originalSign": original_sign,
            "policy": 1,
            "recordUrl": "",
            "roomId": 0,
            "segmentJson": "[]",
            "selDistance": sel_distance_m,
            "selRunTime": sel_run_time_s,
            "selectedUnid": self.unid,
            "signature": signature,
            "speed": speed_val,
            "speedPerTenSec": [b.to_dict() for b in speed_buckets],
            "sportType": self.sport_type,
            "startTime": start_time_ms,
            "status": 1,
            "stepsPerTenSec": [b.to_dict() for b in step_buckets],
            "stopTime": stop_time_ms,
            "themeId": 0,
            "totalAscent": 0,
            "totalDis": total_distance_m,
            "totalSteps": total_steps,
            "totalTime": total_time_sec,
            "uid": self.uid,
            "unCompleteReason": un_complete_reason,
            "unauthorized": 0,
            "useMobilityTools": 0,
            "uuid": self.uuid_str,
            "validDis": total_distance_m,
            "validTime": total_time_sec
        }

        # 4. 组装 OBS Gzip-Base64 载荷
        obs_payload = {
            "rrid": gzip_base64_encode(""),
            "uid": gzip_base64_encode(str(self.uid)),
            "uuid": gzip_base64_encode(self.uuid_str),
            "run_data": gzip_base64_encode(all_loc_json),
            "step_freq_json": gzip_base64_encode(step_json),
            "speed_json": gzip_base64_encode(speed_json),
            "segment_json": gzip_base64_encode("[]"),
            "fixed_point_json": gzip_base64_encode(five_pt_json),
            "runFaceCheck": gzip_base64_encode(""),
            "extension_json": gzip_base64_encode(""),
            "laps_json": gzip_base64_encode("")
        }

        # 5. 生成 OBS 目标对象 Key
        hour_str = time.strftime("%Y%m%d%H", time.localtime(start_time_ms / 1000.0))
        object_key = f"run_data/{hour_str}/{self.uuid_str}.json"

        return save_record, obs_payload, object_key
