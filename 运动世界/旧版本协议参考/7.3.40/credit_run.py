"""Legacy standalone runner.

Deprecated: use ``run_cli.py`` and ``sport_client.py`` instead.  This file is
kept only for backwards compatibility and is not part of the maintained path.
"""

import argparse
import base64
import collections
import hashlib
import json
import math
import os
import random
import string
import struct
import subprocess
import sys
import time
import uuid
from typing import Dict, Optional, Tuple, Union, Any, Callable, List
from coordinate_utils import Coordinate, validate_coordinate

import requests
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad, unpad
from running_protocol import validate_outdoor_record_consistency
from security_utils import redact_data



SPORT_STATIC_SALT = "2slhe02lsfiwowlcixisla_sls-_slaor"
SPORT_FALLBACK_SALT = "&wh2016_swcampus"

REQUEST_RSA_PUBKEY_PKCS1_B64 = (
    "MIGJAoGBALmmqVPOwY1mTVHGEfg7jHck1MNXsVtUfrqY99bm/W2cjLi3LvG/wMYw"
    "bhmf9O+y3CUlZ5g4AMd2Ly4XbWUloG/O8+1USGJ8ddmrzbl8j2EZi0OhpVCYI381"
    "+zZ0qa3z1cOuG2XdJnE7pO6Y4JNC37miqMXYmjejVi2QDIbONomfAgMBAAE="
)

RESPONSE_VERIFY_PUBKEY_SPKI_B64 = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDMs6bFhb5lrf/xqwtNcKVHW09c"
    "oMbtLAmr9Rti7vnSnVroFuLHJEzxMqPQeItByr1Fu4RAQMR/aq/oknn53kCOuSaV"
    "sd9mnDCusrs7GmExDxlKe2pNAKTEZnT1FITQYT2SJkeCZ8iBKujqN61C3SXQ4Xa8"
    "QRr2uMTicec6XC08WQIDAQAB"
)

DEFAULT_HOST_RUN = "https://run.gxapp.iydsj.com"
DEFAULT_HOST_DISCOVERY = "https://discovery.gxapp.iydsj.com"
DEFAULT_HOST_DATAPOINT = "https://datapoint.gxapp.iydsj.com"


def legacy_validate_coordinate(latitude: float, longitude: float) -> Coordinate:
    return validate_coordinate(latitude, longitude)


def compute_token_sign(params: Dict[str, Union[str, int, float, None]],
                       salt: str = SPORT_STATIC_SALT) -> str:
    valid_items = []
    for k, v in params.items():
        if v is None:
            continue
        if k.lower() == "signature":
            continue
        valid_items.append((k, str(v)))
    valid_items.sort(key=lambda x: (x[0].lower(), x[0]))
    canonical_str = "&".join(f"{k}={v}" for k, v in valid_items)
    to_hash = (canonical_str + salt).encode("utf-8")
    return hashlib.md5(to_hash).hexdigest().lower()


def _byte_hash(data: bytes) -> int:
    h = 0
    for b in data:
        h = ((b | ((h << 8) & 0xFFFFFFFF)) ^ ((h >> 24) & 0xFF)) & 0xFFFFFFFF
    return h


def _feistel_transform(s0: int, s1: int, s2: int, s3: int) -> Tuple[int, int, int, int]:
    M = 0xFFFFFFFF
    t = (s2 ^ s0) & M
    mix = (((t >> 24) | (t << 8)) & M) ^ (((t >> 8) | (t << 24)) & M) ^ t
    mix &= M
    new_s1 = (mix ^ s1) & M
    new_s3 = (mix ^ s3) & M
    t2 = (new_s3 ^ new_s1) & M
    mix2 = (((t2 >> 24) | (t2 << 8)) & M) ^ (((t2 >> 8) | (t2 << 24)) & M) ^ t2
    mix2 &= M
    new_s0 = (mix2 ^ s0) & M
    new_s2 = (mix2 ^ s2) & M
    return new_s0, new_s1, new_s2, new_s3


def _final_mix(s0: int, s1: int, s2: int, s3: int) -> bytes:
    M = 0xFFFFFFFF
    a = (~(s2 | s3) & M) ^ s1
    b = ((s2 ^ s3) ^ a) & M
    c = ((a & s2) ^ s0) & M
    b = (b ^ c) & M
    a = (~(b | c) & M) ^ a
    d = ((a & b) ^ s3) & M
    return struct.pack("<IIII", d, a, b, c)


def response_kdf(kd1: Union[str, bytes],
                 kd2: Union[str, bytes],
                 kd3: Union[str, bytes],
                 kd4: Union[str, bytes]) -> bytes:
    if isinstance(kd1, str): kd1 = kd1.encode("utf-8")
    if isinstance(kd2, str): kd2 = kd2.encode("utf-8")
    if isinstance(kd3, str): kd3 = kd3.encode("utf-8")
    if isinstance(kd4, str): kd4 = kd4.encode("utf-8")
    h1, h2, h3, h4 = _byte_hash(kd1), _byte_hash(kd2), _byte_hash(kd3), _byte_hash(kd4)
    s0, s1, s2, s3 = _feistel_transform(h1, h2, h3, h4)
    return _final_mix(s0, s1, s2, s3)


class NetSecSession:
    def __init__(self, fixed_uuid: Optional[str] = None):
        if fixed_uuid:
            raw_uuid = fixed_uuid.replace("-", "")
        else:
            raw_uuid = str(uuid.uuid4()).replace("-", "")
        printable_pool = [chr(i) for i in range(0x21, 0x7E)]
        random_suffix = "".join(random.choice(printable_pool) for _ in range(16))
        candidate_pool = raw_uuid + random_suffix
        pos = 0
        segments = []
        for _ in range(4):
            seg_len = random.randint(8, 12)
            if pos + seg_len <= len(candidate_pool):
                segments.append(candidate_pool[pos:pos + seg_len])
                pos += seg_len
            else:
                segments.append(candidate_pool[pos:])
                pos = len(candidate_pool)
        while len(segments) < 4:
            segments.append("1234567890")
        self.keyDataOne = segments[0]
        self.keyDataTwo = segments[1]
        self.keyDataThree = segments[2]
        self.keyDataFour = segments[3]
        self.response_aes_key = response_kdf(
            self.keyDataOne, self.keyDataTwo, self.keyDataThree, self.keyDataFour
        )

    def get_key_data_dict(self) -> Dict[str, str]:
        return {
            "keyDataOne": self.keyDataOne,
            "keyDataTwo": self.keyDataTwo,
            "keyDataThree": self.keyDataThree,
            "keyDataFour": self.keyDataFour,
        }


class NetSecCrypto:
    def __init__(self,
                 request_rsa_key_b64: str = REQUEST_RSA_PUBKEY_PKCS1_B64,
                 response_rsa_key_b64: str = RESPONSE_VERIFY_PUBKEY_SPKI_B64):
        req_der = base64.b64decode(request_rsa_key_b64)
        self.request_rsa_key = RSA.import_key(req_der)
        self.request_rsa_cipher = PKCS1_v1_5.new(self.request_rsa_key)
        resp_der = base64.b64decode(response_rsa_key_b64)
        self.response_rsa_key = RSA.import_key(resp_der)

    def encrypt_request(self,
                        caller_plaintext: Union[str, bytes, dict, list],
                        session: NetSecSession,
                        timestamp_sec: Optional[int] = None) -> Dict[str, str]:
        if isinstance(caller_plaintext, (dict, list)):
            caller_bytes = json.dumps(caller_plaintext, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        elif isinstance(caller_plaintext, str):
            caller_bytes = caller_plaintext.encode("utf-8")
        else:
            caller_bytes = caller_plaintext
        b64_data = base64.b64encode(caller_bytes).decode("ascii")
        if timestamp_sec is None:
            timestamp_sec = int(time.time())
        inner_dict = collections.OrderedDict([
            ("data", b64_data),
            ("keyDataFour", session.keyDataFour),
            ("keyDataOne", session.keyDataOne),
            ("keyDataThree", session.keyDataThree),
            ("keyDataTwo", session.keyDataTwo),
            ("platform", 2),
            ("timeStamp", timestamp_sec),
        ])
        inner_json = json.dumps(inner_dict, separators=(",", ":"), ensure_ascii=False) + chr(10)
        inner_bytes = inner_json.encode("utf-8")
        h = hashlib.md5(inner_bytes).hexdigest().lower()
        printable_pool = [chr(i) for i in range(0x21, 0x7E)]
        req_aes_key = "".join(random.choice(printable_pool) for _ in range(16)).encode("ascii")
        zero_iv = bytes(16)
        aes_cipher = AES.new(req_aes_key, AES.MODE_CBC, iv=zero_iv)
        ciphertext = aes_cipher.encrypt(pad(inner_bytes, 16))
        d = base64.b64encode(ciphertext).decode("ascii")
        rsa_cipher = PKCS1_v1_5.new(self.request_rsa_key)
        enc_key = rsa_cipher.encrypt(req_aes_key)
        k = base64.b64encode(enc_key).decode("ascii")
        return {
            "d": d,
            "h": h,
            "k": k,
            "p": "101",
            "t": "0"
        }

    def decrypt_response(self,
                         wire_response: Union[str, dict],
                         session: NetSecSession,
                         verify_sig: bool = True) -> str:
        if isinstance(wire_response, str):
            res_obj = json.loads(wire_response)
        else:
            res_obj = wire_response
        v = res_obj.get("v")
        if v != 101 and str(v) != "101":
            raise ValueError(f"Unsupported response version: {v}, expected 101")
        r_b64 = res_obj["r"]
        s_b64 = res_obj["s"]
        cipher_bytes = base64.b64decode(r_b64)
        zero_iv = bytes(16)
        aes_cipher = AES.new(session.response_aes_key, AES.MODE_CBC, iv=zero_iv)
        padded_plain = aes_cipher.decrypt(cipher_bytes)
        try:
            inner_plain_bytes = unpad(padded_plain, 16)
        except ValueError:
            inner_plain_bytes = padded_plain
        if verify_sig:
            digest_hex = hashlib.md5(inner_plain_bytes).hexdigest().lower().encode("ascii")
            sig_bytes = base64.b64decode(s_b64)
            block_size = (self.response_rsa_key.n.bit_length() + 7) // 8
            if len(sig_bytes) != block_size:
                raise ValueError(
                    f"Invalid response signature length: {len(sig_bytes)}, expected {block_size}"
                )
            sig_int = int.from_bytes(sig_bytes, "big")
            recovered_int = pow(sig_int, self.response_rsa_key.e, self.response_rsa_key.n)
            recovered_bytes = recovered_int.to_bytes(block_size, "big")
            sep_idx = recovered_bytes.find(bytes([0]), 2)
            valid_padding = (
                recovered_bytes.startswith(b"\x00\x01")
                and sep_idx >= 10
                and all(value == 0xFF for value in recovered_bytes[2:sep_idx])
            )
            if not valid_padding:
                raise ValueError("Invalid PKCS#1 v1.5 response signature padding")
            recovered_digest = recovered_bytes[sep_idx + 1:]
            if recovered_digest.lower() != digest_hex.lower():
                raise ValueError(
                    f"Signature mismatch: recovered={recovered_digest!r} vs expected={digest_hex!r}"
                )
        inner_obj = json.loads(inner_plain_bytes.decode("utf-8"))
        data_b64 = inner_obj.get("data", "")
        business_bytes = base64.b64decode(data_b64)
        return business_bytes.decode("utf-8")

    def simulate_server_encrypt(self,
                                business_obj: Union[str, dict, list],
                                session: NetSecSession) -> Dict[str, Union[str, int]]:
        if isinstance(business_obj, (dict, list)):
            business_str = json.dumps(business_obj, separators=(",", ":"), ensure_ascii=False)
        else:
            business_str = str(business_obj)
        inner_obj = {"data": base64.b64encode(business_str.encode("utf-8")).decode("ascii")}
        inner_bytes = json.dumps(inner_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        aes_cipher = AES.new(session.response_aes_key, AES.MODE_CBC, iv=bytes(16))
        cipher_bytes = aes_cipher.encrypt(pad(inner_bytes, 16))
        return {
            "r": base64.b64encode(cipher_bytes).decode("ascii"),
            "s": "MOCK_SERVER_SIGNATURE_PLACEHOLDER",
            "v": 101
        }




SPORT_STATIC_SALT = "2slhe02lsfiwowlcixisla_sls-_slaor"


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
            "latitude": gps_points[0].lat if gps_points else 0.0,
            "longitude": gps_points[0].lon if gps_points else 0.0,
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


"""
Sport World Campus (运动世界校园) Pure Protocol Unified Client
--------------------------------------------------------------
High-level pure-protocol client for all operations:
- Random device model & random 32-char DeviceID generation.
- Login authentication with automated GeeTest v4 solving.
- Policy & GeoFence queries.
- Semester scores & progress queries.
- Run history & workout record queries.
- Multi-dimensional leaderboards & cheat list queries.
- Real campus track GPS simulation & outdoor running submission.
- Indoor exercise submission.
"""

import base64
import collections
import json
import logging
import math
import os
import random
import subprocess
import time
import uuid

import requests


logger = logging.getLogger("sport_client")

DEFAULT_HOST_RUN = "https://run.gxapp.iydsj.com"
DEFAULT_HOST_DISCOVERY = "https://discovery.gxapp.iydsj.com"

PHONE_MODELS = [
    "Xiaomi 14 Pro", "Xiaomi 13", "Redmi K70", "vivo X100", 
    "OPPO Find X7", "HUAWEI Mate 60 Pro", "Honor Magic6", "OnePlus 12",
    "Galaxy S23", "iQOO 12", "realme GT5"
]

KNOWN_CAMPUS_GEO = {
    114201: (31.894350, 118.892580),
    52801:  (28.204500, 112.986300),
    10001:  (39.990465, 116.305374),
    10003:  (39.999863, 116.326260),
    10246:  (31.299564, 121.503417),
    10248:  (31.026402, 121.437435),
    10335:  (30.263590, 120.121545),
    10284:  (32.056637, 118.778841),
    10486:  (30.539328, 114.363953),
    10558:  (23.096756, 113.298285),
    10610:  (30.676648, 104.093120),
}


from typing import Optional


class RankType:
    PERSONAL = 1
    CLASS = 2
    DEPARTMENT = 3


class RankSortType:
    DAY = 1
    MONTH = 2


class RankGender:
    ALL = None
    FEMALE = 0
    MALE = 1


class IndoorDateRange:
    DAY = 1
    WEEK = 2
    MONTH = 3


class LeaderboardRequestBuilder:
    def __init__(self, unid: int = 0, uid: Optional[int] = None):
        self.unid = int(unid) if unid else 0
        self.uid = uid

    def build_main_rank_body(self,
                             unid: Optional[int] = None,
                             rank_type: int = RankType.PERSONAL,
                             sort_type: int = RankSortType.DAY,
                             date_str: Optional[str] = None,
                             gender: Optional[int] = RankGender.ALL) -> dict:
        target_unid = int(unid) if unid is not None else self.unid
        body = {
            "unid": target_unid,
            "type": rank_type,
            "sortType": sort_type,
        }
        if date_str:
            body["date"] = date_str
        if gender is not None:
            body["gender"] = gender
        return body

    def build_indoor_rank_body(self,
                               page_num: int = 1,
                               page_size: int = 20,
                               gender: int = RankGender.FEMALE,
                               date_range: int = IndoorDateRange.DAY) -> dict:
        body = {
            "pageNum": page_num,
            "pageSize": page_size,
            "gender": gender,
            "dateRange": date_range
        }
        return body

    def build_history_rank_body(self,
                                 unid: Optional[int] = None,
                                 sort_type: int = RankSortType.DAY,
                                 gender: int = RankGender.FEMALE,
                                page_num: int = 1,
                                page_size: int = 20) -> dict:
        target_unid = int(unid) if unid is not None else self.unid
        body = {
            "unid": target_unid,
            "sortType": sort_type,
            "gender": gender,
            "pageNo": page_num,
            "pageSize": page_size
        }
        return body

    def build_cheat_list_body(self,
                              unid: Optional[int] = None,
                              page_num: int = 1,
                              page_size: int = 20) -> dict:
        target_unid = int(unid) if unid is not None else self.unid
        body = {
            "pageNum": page_num,
            "pageSize": page_size,
            "unid": target_unid
        }
        return body


class SportClient:
    def __init__(self,
                 uid: Optional[Union[int, str]] = None,
                 token: Optional[str] = None,
                 unid: int = 0,
                 device_id: Optional[str] = None,
                 app_version: str = "7.3.90",
                 os_version: str = "14",
                 device_name: Optional[str] = None,
                 proxy: Optional[str] = None,
                 adb_path: Optional[str] = None):
        self.uid = str(uid) if uid else None
        self.token = token
        self.unid = int(unid) if unid else 0
        self.device_id = device_id or os.urandom(16).hex()
        self.app_version = app_version
        self.os_version = os_version
        self.device_name = device_name or random.choice(PHONE_MODELS)
        self.proxy = proxy
        self.adb_path = adb_path or os.path.join("D:", os.sep, "Android", "Sdk", "platform-tools", "adb.exe")

        self.session = NetSecSession()
        self.crypto = NetSecCrypto()
        self.rank_builder = LeaderboardRequestBuilder(unid=self.unid, uid=int(self.uid) if self.uid else None)
                
    def set_credentials(self, uid: Union[int, str], token: str, unid: Optional[int] = None):
        self.uid = str(uid)
        self.token = token
        if unid is not None:
            self.unid = int(unid)
            self.rank_builder.unid = int(unid)
        if self.uid:
            self.rank_builder.uid = int(self.uid)

    def build_public_headers(self, custom_headers: Optional[Dict[str, str]] = None, sign_params: Optional[Dict[str, str]] = None) -> collections.OrderedDict:
        now_ms = int(time.time() * 1000)
        nonce = str(uuid.uuid4())

        headers = collections.OrderedDict([
            ("Accept", "application/json"),
            ("Content-Type", "application/json"),
            ("appVersion", self.app_version),
            ("physicPixel", "1080x2222"),
            ("logicPixel", "411x846"),
            ("isRoot", "0"),
            ("osType", "0"),
        ])
        if self.uid:
            headers["uid"] = str(self.uid)

        headers.update([
            ("IMEI", ""),
            ("timeStamp", str(now_ms)),
            ("blMac", ""),
            ("nonce", nonce),
        ])

        if self.token:
            headers["token"] = str(self.token)

        headers.update([
            ("cpuModel", "arm64-v8a"),
            ("deviceName", self.device_name),
            ("appInstallTime", "1784102941895"),
            ("androidId", ""),
            ("DeviceId", self.device_id),
            ("appUpdateTime", "1784102941895"),
            ("wifiMac", ""),
            ("CustomDeviceId", ""),
            ("osVersion", self.os_version),
            ("User-Agent", "okhttp/4.12.0")
        ])

        if custom_headers:
            headers.update(custom_headers)

        sign_dict = {
            "timeStamp": str(now_ms),
            "token": str(self.token or ""),
            "uid": str(self.uid or "")
        }
        if sign_params:
            sign_dict.update(sign_params)

        headers["tokenSign"] = compute_token_sign(sign_dict)
        return headers

    def build_header_sign(self, headers: Dict[str, str]) -> Dict[str, str]:
        headers_json = json.dumps(headers, separators=(",", ":"), ensure_ascii=False)
        return self.crypto.encrypt_request(headers_json.strip(), self.session)

    def execute_request(self,
                        method: str,
                        url: str,
                        body_plain: Optional[Union[dict, list]] = None,
                        custom_headers: Optional[Dict[str, str]] = None,
                        sign_params: Optional[Dict[str, str]] = None,
                        timeout: int = 25) -> Any:
        headers = self.build_public_headers(custom_headers, sign_params)
        h_sign = self.build_header_sign(headers)
        headers["headerSign"] = json.dumps(h_sign, separators=(",", ":"), ensure_ascii=False)

        encrypted_body = None
        if body_plain is not None:
            encrypted_body = self.crypto.encrypt_request(body_plain, self.session)

        # Fallback to connected Android Phone via ADB
        if os.path.exists(self.adb_path):
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            local_body = os.path.join(cur_dir, "body_tmp.json")
            remote_body = "/data/local/tmp/body_tmp.json"
            local_cfg = os.path.join(cur_dir, "curl_cfg.txt")
            remote_cfg = "/data/local/tmp/curl_cfg.txt"

            cfg_lines = [
                f'url = "{url}"',
                f'request = "{method.upper()}"',
                'silent',
                'show-error'
            ]
            for k, v in headers.items():
                safe_v = v.replace(chr(92), chr(92)+chr(92)).replace(chr(34), chr(92)+chr(34))
                cfg_lines.append(f'header = "{k}: {safe_v}"')

            if encrypted_body is not None:
                body_bytes = json.dumps(encrypted_body, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
                with open(local_body, 'wb') as f:
                    f.write(body_bytes)
                subprocess.run([self.adb_path, 'push', local_body, remote_body], capture_output=True)
                cfg_lines.append('header = "Content-Type: application/json;charset=utf-8"')
                cfg_lines.append(f'data-binary = "@{remote_body}"')

            with open(local_cfg, 'w', encoding='utf-8') as f:
                f.write(chr(10).join(cfg_lines) + chr(10))

            subprocess.run([self.adb_path, 'push', local_cfg, remote_cfg], capture_output=True)
            res = subprocess.run([self.adb_path, 'shell', 'curl', '-K', remote_cfg], capture_output=True, timeout=timeout)
            raw = res.stdout.decode('utf-8', errors='ignore').strip()
            
            for p in (local_body, local_cfg):
                if os.path.exists(p):
                    try: os.remove(p)
                    except: pass

            try:
                resp_obj = json.loads(raw)
                if resp_obj.get("v") in (101, "101"):
                    dec = self.crypto.decrypt_response(resp_obj, self.session, verify_sig=False)
                    return json.loads(dec)
                return resp_obj
            except Exception:
                return {"error": -1, "raw": raw}

        req_kwargs = {
            "method": method.upper(),
            "url": url,
            "headers": headers,
            "timeout": 10
        }
        if self.proxy:
            req_kwargs["proxies"] = {"http": self.proxy, "https": self.proxy}
        if encrypted_body is not None:
            req_kwargs["json"] = encrypted_body

        resp = requests.request(**req_kwargs)
        if resp.status_code == 200:
            raw_json = resp.json()
            if raw_json.get("v") in (101, "101"):
                dec_str = self.crypto.decrypt_response(raw_json, self.session, verify_sig=False)
                return json.loads(dec_str)
            return raw_json

        return {"error": resp.status_code, "raw": resp.text}

    

    def get_run_policy(self, run_mode: int = 1) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v70103/runModePolicy"
        body = {
            "runMode": run_mode,
            "ruleUpdateTime": 0,
            "geoFenceUpdateTime": 0,
            "selectUnid": self.unid,
            "operateType": 0
        }
        return self.execute_request("POST", url, body)

    def get_geo_fence(self, update_time: int = 0) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v1/getGeoFenceForRun"
        return self.execute_request("POST", url, {"updateTime": update_time})

    def get_history_config(self) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v70100/run/getHistoryConfig"
        return self.execute_request("GET", url)

    def get_semester_completed(self, sid: int = 0) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v55/runnings/recordssummary/semester"
        return self.execute_request("POST", url, {"sid": sid})

    def get_semester_info(self, run_mode: int = 1) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v41/running/getPersonalSemesterInfo"
        return self.execute_request("POST", url, {"runMode": run_mode})

    def get_run_history(self, page_num: int = 1, page_size: int = 20, sid: int = 0, sport_type: int = 1) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v70230/runnings/records"
        return self.execute_request("POST", url, {"sid": sid, "type": sport_type})

    def get_run_detail(self, rrid: int) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v70320/runnings/get_one_record"
        return self.execute_request("POST", url, {"rrid": rrid})

    def get_indoor_history(self, page_num: int = 1, page_size: int = 20) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v74/runnings/indoor/findForPage"
        return self.execute_request("POST", url, {"pageNum": page_num, "pageSize": page_size})

    def get_main_rank(self,
                      rank_type: int = RankType.PERSONAL,
                      sort_type: int = RankSortType.DAY,
                      gender: int = RankGender.ALL,
                      page_num: int = 1,
                      page_size: int = 20) -> dict:
        url = f"{DEFAULT_HOST_DISCOVERY}/api/v41/rank"
        body = self.rank_builder.build_main_rank_body(
            unid=self.unid,
            rank_type=rank_type,
            sort_type=sort_type,
            gender=gender,
            page_num=page_num,
            page_size=page_size
        )
        return self.execute_request("POST", url, body)

    def get_indoor_rank(self, page_num: int = 1, page_size: int = 20, date_range: int = IndoorDateRange.WEEK) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v43/runnings/indoor/studentRank"
        body = self.rank_builder.build_indoor_rank_body(
            unid=self.unid,
            page_num=page_num,
            page_size=page_size,
            date_range=date_range
        )
        return self.execute_request("POST", url, body)

    def get_history_rank(self) -> dict:
        url = f"{DEFAULT_HOST_DISCOVERY}/api/v41/historyRank"
        body = self.rank_builder.build_history_rank_body(unid=self.unid)
        return self.execute_request("POST", url, body)

    def get_cheat_list(self, page_num: int = 1, page_size: int = 20) -> dict:
        url = f"{DEFAULT_HOST_RUN}/api/v78/cheat/cheatlist"
        body = self.rank_builder.build_cheat_list_body(unid=self.unid, page_num=page_num, page_size=page_size)
        return self.execute_request("POST", url, body)

    def get_campus_center_geo(self) -> Tuple[float, float]:
        if self.unid in KNOWN_CAMPUS_GEO:
            return KNOWN_CAMPUS_GEO[self.unid]
        
        try:
            fence_res = self.get_geo_fence()
            if fence_res.get("error") == 10000 and fence_res.get("data"):
                fences = fence_res["data"].get("geoFences") or []
                if fences and isinstance(fences, list):
                    first_fence = fences[0]
                    pts = first_fence.get("points") or []
                    if pts:
                        lats = [p.get("lat") or p.get("latitude") for p in pts if p]
                        lons = [p.get("lon") or p.get("longitude") for p in pts if p]
                        if lats and lons:
                            return sum(lats)/len(lats), sum(lons)/len(lons)
        except Exception:
            pass

        return 31.894350, 118.892580

    def generate_campus_track_gps(self,
                                  distance_m: float,
                                  total_seconds: int,
                                  start_time_ms: int,
                                  base_lat: Optional[float] = None,
                                  base_lon: Optional[float] = None) -> List[GpsPoint]:
        if base_lat is None or base_lon is None:
            base_lat, base_lon = self.get_campus_center_geo()
        base_lat, base_lon = validate_coordinate(base_lat, base_lon)

        lat_scale = 1.0 / 111000.0
        lon_scale = 1.0 / (111000.0 * math.cos(math.radians(base_lat)))
        radius_lat = 70.0 * lat_scale
        radius_lon = 35.0 * lon_scale

        num_points = max(10, total_seconds // 2)
        dist_per_step = distance_m / num_points
        current_dist = 0.0

        points = []
        for i in range(num_points):
            p_time = start_time_ms + i * 2000
            angle = (current_dist / 400.0) * 2 * math.pi
            jitter_lat = random.uniform(-0.25, 0.25) * lat_scale
            jitter_lon = random.uniform(-0.25, 0.25) * lon_scale

            if i == 0:
                # Keep the first track point exactly equal to the configured
                # anchor. Record-level coordinates are derived from this point.
                lat, lon = base_lat, base_lon
            else:
                lat = base_lat + radius_lat * math.sin(angle) + jitter_lat
                lon = base_lon + radius_lon * math.cos(angle) + jitter_lon
            speed = round((dist_per_step / 2.0), 2)
            current_dist += dist_per_step

            points.append(GpsPoint(
                lat=round(lat, 6),
                lon=round(lon, 6),
                time_ms=p_time,
                speed=speed,
                accuracy=random.choice([3.0, 5.0, 6.0]),
                is_valid=True
            ))

        return points

    def submit_outdoor_run(self,
                           total_distance_m: float = 2500.0,
                           total_time_sec: int = 750,
                           total_steps: int = 2100,
                           sport_type: int = 1,
                           base_lat: Optional[float] = None,
                           base_lon: Optional[float] = None) -> dict:
        start_time_ms = int((time.time() - total_time_sec - 30) * 1000)
        stop_time_ms = start_time_ms + total_time_sec * 1000
        uuid_str = str(uuid.uuid4())

        if base_lat is None or base_lon is None:
            base_lat, base_lon = self.get_campus_center_geo()

        gps_pts = self.generate_campus_track_gps(
            distance_m=total_distance_m,
            total_seconds=total_time_sec,
            start_time_ms=start_time_ms,
            base_lat=base_lat,
            base_lon=base_lon
        )
        anchor_lat, anchor_lon = validate_coordinate(gps_pts[0].lat, gps_pts[0].lon)

        speed_val = round((total_distance_m / total_time_sec) * 1000) if total_time_sec > 0 else 0
        avg_step_freq = round(total_steps * 60.0 / total_time_sec) if total_time_sec > 0 else 0

        sign_map = {
            "address": "",
            "avgPower": 150,
            "avgStepFreq": avg_step_freq,
            "calorie": round(total_distance_m * 0.055),
            "complete": True,
            "errorCode": 0,
            "faceCheck": 0,
            "geeToken": "",
            "getPrize": False,
            "goalId": "null",
            "policy": 0,
            "selDistance": 2400,
            "selRunTime": 0,
            "selectedUnid": self.unid,
            "speed": speed_val,
            "sportType": sport_type,
            "startTime": start_time_ms,
            "status": 1,
            "stopTime": stop_time_ms,
            "themeId": 0,
            "totalAscent": 0,
            "totalDis": int(total_distance_m),
            "totalSteps": total_steps,
            "totalTime": total_time_sec,
            "uid": int(self.uid) if self.uid else 0,
            "unCompleteReason": 0,
            "unauthorized": 0,
            "useMobilityTools": 0,
            "uuid": uuid_str,
            "validDis": int(total_distance_m),
            "validTime": total_time_sec
        }

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
            speed_buckets.append({"distance": dist_per_bucket, "startTime": b_start, "stopTime": b_end, "queueNum": i + 1})
            step_buckets.append({"step": steps_per_bucket, "startTime": b_start, "stopTime": b_end, "queueNum": i + 1})

        all_loc_json = json.dumps([p.to_dict() for p in gps_pts], separators=(",", ":"))
        five_points = []
        for index in range(5):
            point = gps_pts[min(len(gps_pts) - 1, int(index * len(gps_pts) / 5))]
            five_points.append({
                "lat": point.lat,
                "lon": point.lon,
                "isFixed": 1,
                "isPass": True,
                "pointName": f"FixedPoint_{index + 1}",
                "position": index + 1,
            })
        five_point_json = json.dumps(five_points, separators=(",", ":"))
        speed_json = json.dumps(speed_buckets, separators=(",", ":"))
        step_json = json.dumps(step_buckets, separators=(",", ":"))

        save_record = {
            "address": "",
            "allLocJson": all_loc_json,
            "avgPower": 150,
            "avgStepFreq": avg_step_freq,
            "calorie": round(total_distance_m * 0.055),
            "complete": True,
            "errorCode": 0,
            "faceCheck": 0,
            "fivePointJson": five_point_json,
            "geeToken": "",
            "getPrize": False,
            "goalId": None,
            "isUpload": False,
            "latitude": anchor_lat,
            "longitude": anchor_lon,
            "maxRunTime": 7200,
            "minSteps": 2000,
            "originalSign": original_sign,
            "policy": 0,
            "recordUrl": "",
            "roomId": 0,
            "segmentJson": "[]",
            "selDistance": 2400,
            "selRunTime": 0,
            "selectedUnid": self.unid,
            "signature": signature,
            "speed": speed_val,
            "speedPerTenSec": speed_buckets,
            "sportType": sport_type,
            "startTime": start_time_ms,
            "status": 1,
            "stepsPerTenSec": step_buckets,
            "stopTime": stop_time_ms,
            "themeId": 0,
            "totalAscent": 0,
            "totalDis": int(total_distance_m),
            "totalSteps": total_steps,
            "totalTime": total_time_sec,
            "uid": int(self.uid) if self.uid else 0,
            "unCompleteReason": 0,
            "unauthorized": 0,
            "useMobilityTools": 0,
            "uuid": uuid_str,
            "validDis": int(total_distance_m),
            "validTime": total_time_sec
        }

        validate_outdoor_record_consistency(save_record)

        save_res = self.execute_request("POST", f"{DEFAULT_HOST_RUN}/api/v70260/runnings/save/record", save_record)
        if save_res.get("error") == 10000:
            return save_res

        orig_res = self.execute_request("POST", f"{DEFAULT_HOST_RUN}/api/runnings/upload/originalSign", {
            "uuid": uuid_str,
            "originalSign": original_sign
        })
        if orig_res.get("error") == 10000:
            return {
                "error": 10000,
                "message": "打卡成功 (通过签名通道完成成绩入库)",
                "data": {"uuid": uuid_str, "distance": total_distance_m, "time": total_time_sec}
            }

        return save_res

    def submit_indoor_exercise(self,
                               total_time_sec: int = 1200,
                               total_steps: int = 1800,
                               calorie: int = 150) -> dict:
        builder = IndoorRunRecordBuilder(
            total_time_sec=total_time_sec,
            total_steps=total_steps,
            calorie=calorie
        )
        bundle = builder.build()
        save_body = bundle["save_plaintext"]
        url = f"{DEFAULT_HOST_RUN}/api/v68/indoor/save/record"
        return self.execute_request("POST", url, save_body)


def format_pace(seconds: int, meters: float) -> str:
    km = meters / 1000.0
    sec_per_km = seconds / km
    return f"{int(sec_per_km // 60)}'{int(sec_per_km % 60):02d}\""


def main():
    parser = argparse.ArgumentParser(description="运动世界校园计分跑打卡")
    parser.add_argument("-t", "--token", help="登录 Token")
    parser.add_argument("-u", "--uid", help="用户 UID")
    parser.add_argument("--unid", help="学校 UNID")
    parser.add_argument("-d", "--distance", type=float, help="跑步距离(米)")
    parser.add_argument("--time", type=int, help="跑步用时(秒)")
    parser.add_argument("--steps", type=int, help="步数")
    parser.add_argument("--latitude", "--lat", dest="latitude", type=float,
                        help="跑步起点纬度；不提供时使用学校围栏中心")
    parser.add_argument("--longitude", "--lon", dest="longitude", type=float,
                        help="跑步起点经度；不提供时使用学校围栏中心")
    args = parser.parse_args()

    print("警告: credit_run.py 已废弃，请改用 run_cli.py（支持统一坐标校验和 --dry-run）")
    print("运动世界校园 / 计分跑打卡")
    print("-" * 35)

    token = args.token
    if not token:
        try:
            token = input("登录 Token: ").strip()
        except (KeyboardInterrupt, EOFError):
            print(); print("操作已取消")
            return

    if not token:
        print("错误: Token 不能为空")
        return

    uid = args.uid
    if not uid:
        try:
            uid = input("用户 UID: ").strip()
        except (KeyboardInterrupt, EOFError):
            print(); print("操作已取消")
            return

    if not uid:
        print("错误: UID 不能为空")
        return

    unid_val = args.unid
    if not unid_val:
        try:
            unid_str = input("学校 UNID: ").strip()
            unid_val = int(unid_str) if unid_str else 0
        except (KeyboardInterrupt, EOFError):
            print(); print("操作已取消")
            return
        except ValueError:
            unid_val = 0
    else:
        unid_val = int(unid_val)

    print(); print("正在获取学校规则与坐标...")
    client = SportClient(uid=uid, token=token, unid=unid_val)
    p_res = client.get_run_policy()

    min_dist = 2400.0
    if p_res.get("error") == 10000 and p_res.get("data"):
        r = p_res["data"].get("runRuleModel", {})
        min_dist = float(r.get("minDistance", 2400) or 2400)

    if (args.latitude is None) != (args.longitude is None):
        print("错误: 纬度和经度必须同时提供")
        return
    if args.latitude is None:
        base_lat, base_lon = client.get_campus_center_geo()
    else:
        try:
            base_lat, base_lon = validate_coordinate(args.latitude, args.longitude)
        except ValueError as exc:
            print(f"错误: {exc}")
            return

    distance = args.distance or (min_dist + 100.0)
    duration = args.time or int((distance / 1000.0) * 300)
    steps = args.steps or int((duration / 60.0) * 168)

    print(f"模式: 计分跑")
    print(f"坐标: {base_lat:.6f}, {base_lon:.6f}")
    print(f"距离: {distance:.1f} 米")
    print(f"用时: {duration} 秒 ({duration//60}分{duration%60}秒)")
    print(f"配速: {format_pace(duration, distance)} /公里")
    print(f"步数: {steps}")

    print(); print("正在生成轨迹并提交记录...")
    res = client.submit_outdoor_run(
        total_distance_m=distance,
        total_time_sec=duration,
        total_steps=steps,
        sport_type=1,
        base_lat=base_lat,
        base_lon=base_lon
    )

    print("-" * 35)
    if res.get("error") == 10000:
        print("状态: 成功")
        print(f"消息: {res.get('message', '打卡成功')}")
        data = redact_data(res.get("data"))
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"{k}: {v}")
    else:
        print("状态: 失败")
        print(f"错误码: {res.get('error', -1)}")
        print(f"消息: {res.get('message', '未知错误')}")
        print("原始返回:")
        print(json.dumps(redact_data(res), ensure_ascii=False, indent=2))
    print("-" * 35)


if __name__ == "__main__":
    main()
