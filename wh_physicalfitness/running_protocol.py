import base64
import collections
import gzip
import hashlib
import json
import math
import time
import uuid
from typing import Dict, List, Optional, Tuple, Union
from coordinate_utils import Coordinate, coordinates_match, validate_coordinate

SPORT_STATIC_SALT = "2slhe02lsfiwowlcixisla_sls-_slaor"


def legacy_validate_coordinate(latitude: float, longitude: float) -> Coordinate:
    """Validate and normalize the single coordinate source used by a run."""
    return validate_coordinate(latitude, longitude)


def compute_sport_signature(field_map: Dict[str, Union[str, int, float, bool, None]],
                            salt: str = SPORT_STATIC_SALT) -> str:
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
    if isinstance(data, str):
        data_bytes = data.encode("utf-8")
    else:
        data_bytes = data
    compressed = gzip.compress(data_bytes)
    return base64.b64encode(compressed).decode("ascii")


def gzip_base64_decode(b64_str: str) -> str:
    compressed = base64.b64decode(b64_str)
    decompressed = gzip.decompress(compressed)
    return decompressed.decode("utf-8")


class StepBucket:
    def __init__(self, steps_num: int, begin_time: int, end_time: int,
                 flag: int = 0, max_diff: float = 0.0, min_diff: float = 0.0,
                 avg_diff: float = 0.0, state: int = 0, queue_num: int = 1):
        self.stepsNum = steps_num
        self.beginTime = begin_time
        self.endTime = end_time
        self.flag = flag
        self.maxDiff = max_diff
        self.minDiff = min_diff
        self.avgDiff = avg_diff
        self.state = state
        self.queueNum = queue_num

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


class SpeedBucket:
    def __init__(self, distance: float, begin_time: int, end_time: int,
                 flag: int = 0, state: int = 0, queue_num: int = 1):
        self.distance = distance
        self.beginTime = begin_time
        self.endTime = end_time
        self.flag = flag
        self.state = state
        self.queueNum = queue_num

    def to_dict(self) -> dict:
        return {
            "distance": self.distance,
            "beginTime": self.beginTime,
            "endTime": self.endTime,
            "flag": self.flag,
            "state": self.state,
            "queueNum": self.queueNum
        }


class GpsPoint:
    def __init__(self, lat: float, lon: float, time_ms: int,
                 speed: float = 0.0, accuracy: float = 5.0, is_valid: bool = True):
        self.lat = lat
        self.lon = lon
        self.time = time_ms
        self.speed = speed
        self.accuracy = accuracy
        self.isValid = is_valid

    def to_dict(self) -> dict:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "time": self.time,
            "speed": self.speed,
            "accuracy": self.accuracy,
            "isValid": self.isValid
        }


class FivePoint:
    def __init__(self, lat: float, lon: float, is_fixed: int = 1,
                 is_pass: bool = True, point_name: str = "", position: int = 0):
        self.lat = lat
        self.lon = lon
        self.isFixed = is_fixed
        self.isPass = is_pass
        self.pointName = point_name
        self.position = position

    def to_dict(self) -> dict:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "isFixed": self.isFixed,
            "isPass": self.isPass,
            "pointName": self.pointName,
            "position": self.position
        }


def generate_synthetic_gps_track(start_lat: float, start_lon: float,
                                 total_distance_m: int, total_time_sec: int,
                                 start_time_ms: int) -> Tuple[List[GpsPoint], List[FivePoint]]:
    start_lat, start_lon = validate_coordinate(start_lat, start_lon)
    if total_distance_m <= 0:
        raise ValueError("total_distance_m must be positive")
    if total_time_sec <= 0:
        raise ValueError("total_time_sec must be positive")
    num_points = max(2, total_time_sec // 5)
    points = []
    radius = (total_distance_m / (2 * math.pi))
    deg_per_meter = 1.0 / 111320.0
    r_deg = radius * deg_per_meter
    
    for i in range(num_points):
        t_frac = i / (num_points - 1)
        pt_time = int(start_time_ms + t_frac * (total_time_sec * 1000))
        angle = 2 * math.pi * t_frac
        lat = start_lat + r_deg * math.sin(angle)
        lon = start_lon + (r_deg / math.cos(math.radians(start_lat))) * (1 - math.cos(angle))
        speed = (total_distance_m / total_time_sec) if total_time_sec > 0 else 2.5
        points.append(GpsPoint(round(lat, 6), round(lon, 6), pt_time, round(speed, 2), accuracy=3.0))
    
    five_points = []
    for i in range(5):
        idx = min(len(points) - 1, int(i * len(points) / 5))
        pt = points[idx]
        five_points.append(FivePoint(pt.lat, pt.lon, is_fixed=1, is_pass=True,
                                     point_name=f"FixedPoint_{i+1}", position=i+1))
    return points, five_points


def validate_outdoor_record_consistency(record: dict,
                                        tolerance: float = 1e-6) -> dict:
    """Validate that record coordinates all describe the same track.

    This is intentionally local and side-effect free so callers can run it in
    dry-run mode before any network request is made.
    """
    if not isinstance(record, dict):
        raise ValueError("record must be a dictionary")
    try:
        track = json.loads(record.get("allLocJson") or "[]")
        fixed = json.loads(record.get("fivePointJson") or "[]")
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("record location fields must contain valid JSON") from exc
    if not isinstance(track, list) or not track:
        raise ValueError("allLocJson must contain at least one point")
    if not isinstance(fixed, list) or len(fixed) != 5:
        raise ValueError("fivePointJson must contain exactly five points")
    if any(not isinstance(point, dict) for point in track):
        raise ValueError("allLocJson points must be objects")
    if any(not isinstance(point, dict) for point in fixed):
        raise ValueError("fivePointJson points must be objects")

    anchor = validate_coordinate(record.get("latitude"), record.get("longitude"))
    first = validate_coordinate(track[0].get("lat"), track[0].get("lon"))
    if not coordinates_match(anchor.latitude, anchor.longitude,
                             first.latitude, first.longitude, tolerance):
        raise ValueError("record anchor does not match the first track point")

    track_coordinates = [
        validate_coordinate(point.get("lat"), point.get("lon"))
        for point in track
    ]
    for point in fixed:
        fixed_coord = validate_coordinate(point.get("lat"), point.get("lon"))
        if not any(coordinates_match(fixed_coord.latitude, fixed_coord.longitude,
                                     track_point.latitude, track_point.longitude,
                                     tolerance) for track_point in track_coordinates):
            raise ValueError("a fixed point is not present in the full track")

    return {"trackPoints": len(track), "fixedPoints": len(fixed),
            "latitude": first.latitude, "longitude": first.longitude}


class IndoorRunRecordBuilder:
    def __init__(self, uid: int, unid: int, sel_min_time: int = 1200, min_steps: int = 2000,
                 uuid_str: Optional[str] = None):
        self.uid = uid
        self.unid = unid
        self.sel_min_time = sel_min_time
        self.min_steps = min_steps
        self.uuid_str = uuid_str or str(uuid.uuid4())

    def build_record(self, total_time_sec: int, total_steps: int,
                      start_time_ms: int, stop_time_ms: int,
                      latitude: float = 0.0, longitude: float = 0.0,
                      step_buckets: Optional[List[StepBucket]] = None,
                      calorie: int = 0) -> Tuple[str, dict, dict]:
        complete = (total_time_sec >= self.sel_min_time) and (total_steps >= self.min_steps)
        if complete:
            un_complete_reason = 0
        elif total_time_sec < self.sel_min_time:
            un_complete_reason = 10
        else:
            un_complete_reason = 11

        avg_step_freq = round(total_steps * 60.0 / total_time_sec) if total_time_sec > 0 else 0

        sign_map = {
            "avgStepFreq": avg_step_freq,
            "complete": complete,
            "latitude": latitude,
            "longitude": longitude,
            "maxRunTime": 7200,
            "minSteps": self.min_steps,
            "policy": 1,
            "selRunTime": self.sel_min_time,
            "selectedUnid": self.unid,
            "sportType": 5,
            "startTime": start_time_ms,
            "stopTime": stop_time_ms,
            "totalSteps": total_steps,
            "totalTime": total_time_sec,
            "unCompleteReason": un_complete_reason,
            "uuid": self.uuid_str
        }

        signature = compute_sport_signature(sign_map)

        if step_buckets is None:
            step_buckets = []
            num_buckets = max(1, total_time_sec // 10)
            steps_per_bucket = total_steps // num_buckets
            for i in range(num_buckets):
                b_start = start_time_ms + i * 10000
                b_end = min(stop_time_ms, b_start + 10000)
                step_buckets.append(StepBucket(steps_per_bucket, b_start, b_end, queue_num=i + 1))

        steps_json = json.dumps([b.to_dict() for b in step_buckets], separators=(",", ":"))

        save_record = {
            "address": "",
            "allLocJson": "",
            "avgPower": 0,
            "avgStepFreq": avg_step_freq,
            "calorie": calorie,
            "complete": complete,
            "errorCode": 0,
            "faceCheck": 0,
            "fivePointJson": "",
            "geeToken": "",
            "getPrize": False,
            "goalId": None,
            "isUpload": False,
            "latitude": latitude,
            "longitude": longitude,
            "maxRunTime": 7200,
            "minSteps": self.min_steps,
            "policy": 1,
            "recordUrl": "",
            "roomId": 0,
            "segmentJson": "",
            "selDistance": 0,
            "selRunTime": self.sel_min_time,
            "selectedUnid": self.unid,
            "signature": signature,
            "speed": 0,
            "speedPerTenSec": [],
            "sportType": 5,
            "startTime": start_time_ms,
            "status": 1,
            "stepsPerTenSec": [b.to_dict() for b in step_buckets],
            "stopTime": stop_time_ms,
            "themeId": 0,
            "totalAscent": 0,
            "totalDis": 0,
            "totalSteps": total_steps,
            "totalTime": total_time_sec,
            "uid": self.uid,
            "unCompleteReason": un_complete_reason,
            "unauthorized": 0,
            "useMobilityTools": 0,
            "uuid": self.uuid_str,
            "validDis": 0,
            "validTime": total_time_sec
        }

        cos_payload = {
            "uid": gzip_base64_encode(str(self.uid)),
            "uuid": gzip_base64_encode(self.uuid_str),
            "step_json": gzip_base64_encode(steps_json)
        }

        return "/api/v68/indoor/save/record", save_record, cos_payload


class OutdoorRunRecordBuilder:
    def __init__(self, uid: int, unid: int, sport_type: int = 1,
                 sel_distance_m: int = 2000, sel_run_time_s: int = 1200,
                 uuid_str: Optional[str] = None):
        self.uid = uid
        self.unid = unid
        self.sport_type = sport_type
        self.sel_distance_m = sel_distance_m
        self.sel_run_time_s = sel_run_time_s
        self.uuid_str = uuid_str or str(uuid.uuid4())

    def build_record(self, total_distance_m: int, total_time_sec: int, total_steps: int,
                     start_time_ms: int, stop_time_ms: int,
                     gps_points: List[GpsPoint],
                     five_points: Optional[List[FivePoint]] = None,
                     calorie: int = 120, avg_power: int = 150,
                     room_id: int = 0) -> Tuple[str, dict, dict]:
        if not gps_points:
            raise ValueError("gps_points cannot be empty")

        # The record-level location is deliberately derived from the same first
        # point that is serialized into allLocJson.  Do not accept a second,
        # independent coordinate source here.
        anchor = validate_coordinate(gps_points[0].lat, gps_points[0].lon)
        anchor_lat, anchor_lon = anchor
        complete = (total_distance_m >= self.sel_distance_m) and (total_time_sec >= self.sel_run_time_s)
        un_complete_reason = 0 if complete else 10
        avg_step_freq = round(total_steps * 60.0 / total_time_sec) if total_time_sec > 0 else 0
        speed_val = round((total_distance_m / total_time_sec) * 1000) if total_time_sec > 0 else 0

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
            # Java reflection signs String.valueOf(null), not an omitted field.
            "goalId": "null",
            "policy": 1,
            "selDistance": self.sel_distance_m,
            "selRunTime": self.sel_run_time_s,
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
        if self.sport_type == 3:
            sign_map["roomId"] = room_id

        signature = compute_sport_signature(sign_map)
        original_sign = compute_original_sign(sign_map)

        num_buckets = max(1, total_time_sec // 10)
        dist_per_bucket = total_distance_m / num_buckets
        steps_per_bucket = total_steps // num_buckets
        speed_buckets = []
        step_buckets = []
        for i in range(num_buckets):
            b_start = start_time_ms + i * 10000
            b_end = min(stop_time_ms, b_start + 10000)
            speed_buckets.append(SpeedBucket(dist_per_bucket, b_start, b_end, queue_num=i + 1))
            step_buckets.append(StepBucket(steps_per_bucket, b_start, b_end, queue_num=i + 1))

        all_loc_json = json.dumps([p.to_dict() for p in gps_points], separators=(",", ":"))
        five_pt_json = json.dumps([p.to_dict() for p in (five_points or [])], separators=(",", ":"))
        speed_json = json.dumps([b.to_dict() for b in speed_buckets], separators=(",", ":"))
        step_json = json.dumps([b.to_dict() for b in step_buckets], separators=(",", ":"))

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
            "latitude": anchor_lat,
            "longitude": anchor_lon,
            "maxRunTime": 7200,
            "minSteps": 2000,
            "originalSign": original_sign,
            "policy": 1,
            "recordUrl": "",
            "roomId": room_id,
            "segmentJson": "[]",
            "selDistance": self.sel_distance_m,
            "selRunTime": self.sel_run_time_s,
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

        validate_outdoor_record_consistency(save_record)

        cos_payload = {
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

        return "/api/v70260/runnings/save/record", save_record, cos_payload
