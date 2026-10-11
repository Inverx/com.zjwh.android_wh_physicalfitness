import base64
import collections
import gzip
import hashlib
import json
import math
import random
import time
import uuid
from typing import Dict, List, Optional, Tuple, Union
from whsport.coordinate_utils import Coordinate, coordinates_match, validate_coordinate

SPORT_STATIC_SALT = "2slhe02lsfiwowlcixisla_sls-_slaor"


# --- Physiological / device estimates -------------------------------------
#
# These keep the aggregate fields the app renders (消耗/爬升高度/平均功率/配速/步幅)
# mutually consistent with totalDis / totalTime / totalSteps, instead of being
# hard-coded constants that never change between runs.

# Fallback body weight used when the caller does not supply one.  The app asks
# users to "完善体重信息" precisely because calorie depends on it.
DEFAULT_BODY_WEIGHT_KG = 60.0

# Official calorie coefficient: kcal = 1.036 * kg * km.
KCAL_PER_KG_KM = 1.036

# Horizontal running power coefficient (W per kg per m/s).
RUNNING_POWER_COEFF = 0.98

# Elevation steps smaller than this are treated as GPS/barometer noise.
ELE_NOISE_M = 0.15

DEFAULT_HEIGHT_CM = 172.0


def estimate_calorie(total_distance_m: float, total_time_sec: int,
                     weight_kg: float = DEFAULT_BODY_WEIGHT_KG,
                     total_ascent_m: int = 0) -> int:
    """Energy expenditure in 千卡 (kcal).

    Official app formula: kcal = 1.036 * weight(kg) * distance(km).
    """
    if total_distance_m <= 0:
        return 0
    return int(round(max(0.0, weight_kg) * (total_distance_m / 1000.0) * KCAL_PER_KG_KM))


def estimate_avg_power(total_distance_m: float, total_time_sec: int,
                       total_ascent_m: int = 0,
                       weight_kg: float = DEFAULT_BODY_WEIGHT_KG) -> int:
    """Average running power in 瓦 (W).

    Official app formula: W = 0.98 * weight(kg) * speed(m/s).
    """
    if total_distance_m <= 0 or total_time_sec <= 0:
        return 0
    return int(round(max(0.0, weight_kg) * (total_distance_m / total_time_sec)
                     * RUNNING_POWER_COEFF))


def estimate_stride_cm(total_distance_m: float, total_steps: int) -> float:
    """Average stride length in 厘米 (cm) = distance / steps."""
    if total_steps <= 0:
        return 0.0
    return round(total_distance_m / total_steps * 100.0, 1)


def _smooth_series(values: List[float], window: int = 5) -> List[float]:
    """Light moving average (device-like filtering for derived metrics)."""
    n = len(values)
    if n == 0 or window <= 1:
        return list(values)
    half = window // 2
    out = []
    for i in range(n):
        a, b = max(0, i - half), min(n, i + half + 1)
        out.append(sum(values[a:b]) / (b - a))
    return out


def elevation_gain(elevations) -> float:
    """Cumulative climb, ignoring sub-ELE_NOISE_M jitter (official口径)."""
    gain = 0.0
    prev = None
    for e in elevations:
        e = float(e or 0.0)
        if prev is not None and e - prev > ELE_NOISE_M:
            gain += e - prev
        prev = e
    return round(gain, 2)


def estimate_total_ascent(total_distance_m: float,
                          rng: Optional[random.Random] = None) -> int:
    """Fallback climb estimate when no elevation profile is available."""
    if total_distance_m <= 0:
        return 0
    rng = rng or random
    return int(round((total_distance_m / 1000.0) * rng.uniform(3.0, 9.0)))


# --- WGS-84 → GCJ-02 (Mars coordinates) ------------------------------------

_GCJ_A = 6378245.0
_GCJ_EE = 0.00669342162296594323


def _out_of_china(lat: float, lon: float) -> bool:
    return not (73.66 < lon < 135.05 and 3.86 < lat < 53.55)


def _gcj_transform_lat(x: float, y: float) -> float:
    ret = (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y
           + 0.2 * math.sqrt(abs(x)))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _gcj_transform_lon(x: float, y: float) -> float:
    ret = (300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x)))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lat: float, lon: float) -> Tuple[float, float]:
    """Convert WGS-84 to GCJ-02, as the app stores/renders on the map."""
    if _out_of_china(lat, lon):
        return lat, lon
    dlat = _gcj_transform_lat(lon - 105.0, lat - 35.0)
    dlon = _gcj_transform_lon(lon - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - _GCJ_EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_GCJ_A * (1 - _GCJ_EE)) / (magic * sqrt_magic) * math.pi)
    dlon = (dlon * 180.0) / (_GCJ_A / sqrt_magic * math.cos(rad_lat) * math.pi)
    return round(lat + dlat, 7), round(lon + dlon, 7)


def gcj02_to_wgs84(lat: float, lon: float) -> Tuple[float, float]:
    """Convert GCJ-02 back to WGS-84 (single-step inverse, ~1 m error).

    The server hands out check-in points as lat/lon (BD-09) + glat/glon (GCJ-02);
    the generator works in WGS-84, so feed it gcj02_to_wgs84(glat, glon).
    """
    if _out_of_china(lat, lon):
        return lat, lon
    dlat = _gcj_transform_lat(lon - 105.0, lat - 35.0)
    dlon = _gcj_transform_lon(lon - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - _GCJ_EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_GCJ_A * (1 - _GCJ_EE)) / (magic * sqrt_magic) * math.pi)
    dlon = (dlon * 180.0) / (_GCJ_A / sqrt_magic * math.cos(rad_lat) * math.pi)
    return round(lat - dlat, 7), round(lon - dlon, 7)


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
                 avg_diff: float = 0.0, state: int = 0, queue_num: int = 1,
                 bucket_id: int = 0):
        self.stepsNum = steps_num
        self.beginTime = begin_time
        self.endTime = end_time
        self.flag = flag
        self.maxDiff = max_diff
        self.minDiff = min_diff
        self.avgDiff = avg_diff
        self.state = state
        self.queueNum = queue_num
        self.id = bucket_id

    def to_dict(self) -> dict:
        # Key set matches the real device payload exactly (avgDiff=0, maxDiff=0,
        # minDiff=1000, state=0, flag=start_ms).
        return {
            "stepsNum": self.stepsNum,
            "beginTime": self.beginTime,
            "endTime": self.endTime,
            "flag": self.flag,
            "id": self.id,
            "maxDiff": self.maxDiff,
            "minDiff": self.minDiff,
            "avgDiff": self.avgDiff,
            "state": self.state,
            "queueNum": self.queueNum
        }


class SpeedBucket:
    def __init__(self, distance: float, begin_time: int, end_time: int,
                 flag: int = 0, state: int = 0, queue_num: int = 1,
                 bucket_id: int = 0):
        self.distance = distance
        self.beginTime = begin_time
        self.endTime = end_time
        self.flag = flag
        self.state = state
        self.queueNum = queue_num
        self.id = bucket_id

    def to_dict(self) -> dict:
        return {
            "distance": self.distance,
            "beginTime": self.beginTime,
            "endTime": self.endTime,
            "flag": self.flag,
            "id": self.id,
            "queueNum": self.queueNum,
            "state": self.state
        }


class GpsPoint:
    def __init__(self, lat: float, lon: float, time_ms: int,
                 speed: float = 0.0, accuracy: float = 5.0, is_valid: bool = True,
                 ele: float = 0.0, cadence: float = 0.0, stride_cm: float = 0.0,
                 cum_dist: float = 0.0, cum_steps: float = 0.0, index: int = 0):
        self.lat = lat
        self.lon = lon
        self.time = time_ms
        self.speed = speed          # m/s
        self.accuracy = accuracy
        self.isValid = is_valid
        self.ele = ele              # metres
        self.cadence = cadence      # steps / minute
        self.stride_cm = stride_cm
        self.cum_dist = cum_dist    # metres travelled so far
        self.cum_steps = cum_steps  # cumulative steps (float)
        self.index = index

    def to_dict(self) -> dict:
        # Minimal shape kept for the record body / local validation.
        return {
            "lat": self.lat,
            "lon": self.lon,
            "time": self.time,
            "speed": self.speed,
            "accuracy": self.accuracy,
            "isValid": self.isValid
        }

    def pace_min_per_km(self) -> float:
        return (1000.0 / (self.speed * 60.0)) if self.speed > 0 else 0.0

    def to_obs_dict(self, start_ms: int, pt_type: int = 1) -> dict:
        """Real-device OBS point (27 keys, GCJ-02 coordinates)."""
        glat, glng = wgs84_to_gcj02(self.lat, self.lon)
        pace = round(self.pace_min_per_km(), 4)
        t_rel = int(round((self.time - start_ms) / 1000.0))
        return {
            "avgSpeed": pace,
            "bdA": round(self.ele, 2),
            "bdD": 0.0,
            "bdG": 0,
            "bdS": 0.0,
            "coorType": "gcj02",
            "count": 1,
            "dtr": 0.0,
            "flag": start_ms,
            "gLat": glat,
            "gLng": glng,
            "gainTime": 0,
            "id": int(self.index),
            "lat": -1.0,
            "lng": -1.0,
            "locType": 1,
            "locationId": "",
            "queueNum": 0,
            "radius": 0.0,
            "speed": pace,
            "state": 0,
            "stepDistance": 0.0,
            "totalDis": round(self.cum_dist, 4),
            "totalTime": t_rel,
            "type": int(pt_type),
            "validDis": round(self.cum_dist, 4),
            "validTime": t_rel,
        }


class FivePoint:
    def __init__(self, lat: float, lon: float, is_fixed: int = 1,
                 is_pass: bool = True, point_name: str = "", position: int = 0,
                 glat: Optional[float] = None, glon: Optional[float] = None,
                 radius: float = 15.0, start_ms: int = 0):
        self.lat = lat
        self.lon = lon
        self.glat = glat
        self.glon = glon
        self.isFixed = is_fixed
        self.isPass = is_pass
        self.pointName = point_name
        self.position = position
        self.radius = radius
        self.startTime = start_ms

    def _gcj(self) -> Tuple[float, float]:
        if self.glat is not None and self.glon is not None:
            return self.glat, self.glon
        return wgs84_to_gcj02(self.lat, self.lon)

    def to_dict(self) -> dict:
        glat, glon = self._gcj()
        return {
            "flag": self.startTime,
            "glat": glat,
            "glon": glon,
            "id": self.position,
            "isFixed": self.isFixed,
            "isPass": self.isPass,
            "lat": self.lat,
            "lng": self.lon,
            "pointName": self.pointName,
            "position": self.position,
            "radius": self.radius,
            "state": 0,
        }

    def to_obs_dict(self, start_ms: int, index: int) -> dict:
        """Record-side keys (glat/glon, lng, isFixed=0, position 999)."""
        glat, glon = self._gcj()
        return {
            "flag": start_ms,
            "glat": glat,
            "glon": glon,
            "id": index,
            "isFixed": 0,
            "isPass": True,
            "lat": round(self.lat, 7),
            "lng": round(self.lon, 7),
            "pointName": "",
            "position": 999,
            "state": 0,
        }


def _largest_remainder(total: int, weights: List[float]) -> List[int]:
    """Split an integer total across buckets so the parts always sum to total."""
    if not weights:
        return []
    s = sum(weights)
    if s <= 0:
        weights = [1.0] * len(weights)
        s = float(len(weights))
    exact = [total * w / s for w in weights]
    parts = [int(math.floor(x)) for x in exact]
    leftover = total - sum(parts)
    order = sorted(range(len(exact)), key=lambda i: exact[i] - parts[i], reverse=True)
    for i in order[:leftover]:
        parts[i] += 1
    return parts


def _weighted_split(total: float, weights: List[float]) -> List[float]:
    """Split a float total across buckets proportional to weights."""
    if not weights:
        return []
    s = sum(weights)
    if s <= 0:
        weights = [1.0] * len(weights)
        s = float(len(weights))
    return [total * w / s for w in weights]


def _effort_weights(num_buckets: int, rng: random.Random) -> List[float]:
    """Per-10s effort profile: gentle warm-up, steady middle, small kick.

    Bucket values are proportional to these weights, so the cadence and speed
    series rise and fall together instead of being flat lines, while the caller
    keeps their totals exact via _largest_remainder / _weighted_split.
    """
    if num_buckets <= 1:
        return [1.0]
    weights = []
    for i in range(num_buckets):
        t = i / (num_buckets - 1)
        envelope = 0.90 + 0.18 * math.sin(math.pi * t)
        weights.append(envelope * rng.uniform(0.92, 1.08))
    return weights


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2.0) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2)
    return 2.0 * r * math.asin(min(1.0, math.sqrt(a)))


def _point_at_distance(path, cum, d):
    """Interpolate position along a closed polyline at cumulative distance d."""
    total = cum[-1]
    if total <= 0:
        return path[0]
    d = d % total
    lo, hi = 0, len(cum) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if cum[mid] <= d:
            lo = mid
        else:
            hi = mid
    span = cum[hi] - cum[lo]
    f = 0.0 if span <= 1e-12 else (d - cum[lo]) / span
    la1, lo1 = path[lo]
    la2, lo2 = path[hi]
    return la1 + (la2 - la1) * f, lo1 + (lo2 - lo1) * f


def _build_route(start_lat, start_lon, target_len_m, rng, n_dense=900):
    """Organic closed loop (Fourier-modulated radius) scaled to target length.

    Avoids the "perfect circle" fingerprint: harmonics 2-5 with random phases
    produce a plausible campus ring while keeping the start anchored.
    """
    harmonics = [(k, rng.uniform(0.03, 0.12), rng.uniform(0.0, 2.0 * math.pi))
                 for k in range(2, 6)]
    xy = []
    for i in range(n_dense):
        th = 2.0 * math.pi * i / n_dense
        r = 1.0 + sum(a * math.cos(k * th + ph) for k, a, ph in harmonics)
        xy.append((r * math.cos(th), r * math.sin(th)))

    def seg(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    length = (sum(seg(xy[i - 1], xy[i]) for i in range(1, len(xy)))
              + seg(xy[-1], xy[0]))
    scale = target_len_m / max(length, 1e-9)
    x0, y0 = xy[0]
    m_lat = 111320.0
    m_lon = 111320.0 * math.cos(math.radians(start_lat))
    path = [(start_lat + (y - y0) * scale / m_lat,
             start_lon + (x - x0) * scale / m_lon) for x, y in xy]
    cum = [0.0]
    for i in range(1, len(path)):
        cum.append(cum[-1] + _haversine_m(path[i - 1][0], path[i - 1][1],
                                          path[i][0], path[i][1]))
    cum.append(cum[-1] + _haversine_m(path[-1][0], path[-1][1],
                                      path[0][0], path[0][1]))
    path.append(path[0])
    return path, cum


def _poisson(rng: random.Random, lam: float) -> int:
    """Knuth Poisson sampler (lam is small here, so the loop is cheap)."""
    if lam <= 0:
        return 0
    limit = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= limit:
            return k - 1


def _speed_profile(n: int, base_speed: float, duration_s: float,
                   rng: random.Random) -> List[float]:
    """Instantaneous speed (m/s) as a layered, human-like model.

    ``base_speed * warm-up * fatigue * recovery * oscillation * AR(1) jitter``
    plus occasional short slowdowns.  Unlike a hard low-pass filter, the AR(1)
    term keeps real, auto-correlated jitter.  The mean is normalised to
    ``base_speed`` so total distance and time are unchanged; only the shape
    gains a gentle downward trend instead of being a flat line.
    """
    t = [i / max(1, n - 1) for i in range(n)]
    minutes = duration_s / 60.0

    # 1) trend: wide warm-up + fatigue that scales with duration
    fatigue = min(max(0.03 + 0.0035 * minutes, 0.04), 0.11)
    power = rng.uniform(1.1, 1.5)
    bumps = [(rng.uniform(0.25, 0.9), rng.uniform(0.04, 0.09), rng.uniform(0.015, 0.035))
             for _ in range(rng.randint(1, 2))]

    # 2) randomised oscillations (frequencies/phases change every run)
    oscillations = [(rng.uniform(3.0, 40.0), rng.uniform(0.0, 2 * math.pi),
                     rng.uniform(0.004, 0.010)) for _ in range(rng.randint(2, 4))]

    # 3) AR(1) jitter, deliberately NOT smoothed away
    rho = rng.uniform(0.50, 0.80)
    sigma = rng.uniform(0.012, 0.020)
    ar = [0.0] * n
    for i in range(1, n):
        ar[i] = ar[i - 1] * rho + sigma * math.sqrt(1 - rho * rho) * rng.gauss(0.0, 1.0)

    lo, hi = 0.80 * base_speed, 1.20 * base_speed
    speeds = []
    for i in range(n):
        ti = t[i]
        warm = 1.0 - 0.05 * math.exp(-ti / 0.05)
        fade = 1.0 - fatigue * (ti ** power)
        recovery = 1.0 + sum(a * math.exp(-((ti - mu) / s) ** 2) for mu, s, a in bumps)
        osc = 1.0 + sum(a * math.sin(2 * math.pi * f * ti + ph) for f, ph, a in oscillations)
        # small independent micro-jitter so consecutive samples differ
        v = base_speed * warm * fade * recovery * osc * (1.0 + ar[i] + rng.gauss(0.0, 0.004))
        speeds.append(min(hi, max(lo, v)))

    # 4) occasional short slowdowns (crossing, phone, etc.)
    for _ in range(_poisson(rng, minutes / 5.0)):
        c = rng.randrange(n)
        for j in range(c, min(n, c + rng.randint(1, 2))):
            speeds[j] *= 1.0 - rng.uniform(0.04, 0.08)

    m = sum(speeds) / n
    if m > 1e-9:
        speeds = [v * base_speed / m for v in speeds]
    return speeds


def _sample_deltas(n: int, total_s: float, rng: random.Random) -> List[float]:
    """Sampling intervals (s) summing exactly to total_s.

    Real devices keep ~80% of samples on the nominal grid and scatter the rest,
    so the integer-second timestamps are irregular rather than a perfect grid.
    """
    m = n - 1
    if m <= 0:
        return []
    if total_s <= m * 2.5:
        return [total_s / m] * m
    dt = total_s / m
    deltas = []
    for _ in range(m):
        r = rng.random()
        if r < 0.70:
            deltas.append(dt)
        elif r < 0.90:
            deltas.append(dt * rng.uniform(0.85, 1.15))   # near-nominal jitter
        else:
            deltas.append(dt * rng.uniform(1.30, 1.90))   # lost fix / longer gap
    loose = [i for i, s in enumerate(deltas) if s != dt]
    delta = total_s - sum(deltas)
    if loose and abs(delta) > 1e-9:
        per = delta / len(loose)
        for i in loose:
            deltas[i] = max(0.5, deltas[i] + per)
    resid = total_s - sum(deltas)
    if abs(resid) > 1e-6 and sum(deltas) > 0:
        k = total_s / sum(deltas)
        deltas = [s * k for s in deltas]
    return deltas


def _ensure_cumulative(points: List[GpsPoint], total_distance_m: float,
                       total_steps: int) -> None:
    """Backfill per-point cumulative distance/steps if a caller omitted them."""
    if not points:
        return
    if not any(p.cum_dist for p in points):
        cum = [0.0]
        for i in range(1, len(points)):
            cum.append(cum[-1] + _haversine_m(points[i - 1].lat, points[i - 1].lon,
                                              points[i].lat, points[i].lon))
        if cum[-1] > 0:
            k = total_distance_m / cum[-1]
            cum = [c * k for c in cum]
        for p, c in zip(points, cum):
            p.cum_dist = round(c, 3)
    if not any(p.cum_steps for p in points) and total_distance_m > 0:
        for p in points:
            p.cum_steps = round(p.cum_dist / total_distance_m * total_steps, 2)
        points[-1].cum_steps = float(total_steps)


def _ten_sec_windows(points: List[GpsPoint], start_ms: int, total_time: int,
                     rrid: int = 0, queue_seq: bool = True,
                     total_steps: Optional[int] = None,
                     total_distance: Optional[float] = None):
    """Divide the run into 10 s windows using whole-second quota carry.

    Returns (speed_windows, step_windows). Distance and steps are accumulated
    with carry so the totals are exact and no value is ever a flat constant.
    When ``total_steps`` / ``total_distance`` are given the values are scaled
    so sum(speedPerTenSec.distance) == total_distance and
    sum(stepsPerTenSec) == total_steps hold exactly (the server checks steps).
    """
    segs = []
    for i in range(1, len(points)):
        a, b = points[i - 1], points[i]
        dt = (b.time - a.time) / 1000.0
        if dt <= 1e-9:
            continue
        segs.append([dt, b.cum_dist - a.cum_dist, b.cum_steps - a.cum_steps])

    seed = ((rrid % 100000) * 1000) if rrid else 60000
    n_win = max(1, int(total_time // 10))
    speed_windows = []
    raw_steps = []
    idx = 0
    rem = list(segs[0]) if segs else [0.0, 0.0, 0.0]
    for k in range(n_win):
        begin = start_ms + k * 10000
        hi = min((k + 1) * 10, total_time)
        end = start_ms + hi * 1000
        left = float(hi - k * 10)
        dist = steps = 0.0
        while left > 1e-9 and (idx < len(segs) or rem[0] > 1e-9):
            if rem[0] <= 1e-9:
                idx += 1
                if idx < len(segs):
                    rem = list(segs[idx])
                continue
            take = min(left, rem[0])
            f = take / rem[0]
            dist += rem[1] * f
            steps += rem[2] * f
            rem = [rem[0] - take, rem[1] - rem[1] * f, rem[2] - rem[2] * f]
            left -= take
        qn = k if queue_seq else 0
        win_id = seed + hi
        speed_windows.append({"beginTime": begin, "distance": max(dist, 0.0),
                              "endTime": end, "flag": start_ms, "id": win_id,
                              "queueNum": qn, "state": 0})
        raw_steps.append(max(steps, 0.0))

    # Make the distance totals exact even when total_time is not a multiple of
    # 10 (the trailing partial window would otherwise be dropped).
    if total_distance is not None and speed_windows:
        raw_dist_sum = sum(w["distance"] for w in speed_windows)
        if raw_dist_sum > 0:
            k = float(total_distance) / raw_dist_sum
            for w in speed_windows:
                w["distance"] = w["distance"] * k
    for w in speed_windows:
        w["distance"] = round(w["distance"], 4)

    # Realistic pedometer counting noise, deterministic per (start_ms, window) so
    # the record body and the OBS object stay identical.
    for k in range(len(raw_steps)):
        hv = int.from_bytes(hashlib.md5(f"{start_ms}:{k}".encode()).digest()[:3], "big")
        raw_steps[k] = max(0.0, raw_steps[k] + (hv / 0xFFFFFF - 0.5) * 2.6)

    if total_steps is not None and raw_steps and sum(raw_steps) > 0:
        counts = _largest_remainder(int(total_steps), raw_steps)
    else:
        counts = [int(s) for s in raw_steps]

    step_windows = []
    for k, win in enumerate(speed_windows):
        step_windows.append({"avgDiff": 0.0, "beginTime": win["beginTime"],
                             "endTime": win["endTime"], "flag": start_ms,
                             "id": win["id"], "maxDiff": 0.0, "minDiff": 1000.0,
                             "queueNum": win["queueNum"], "state": 0,
                             "stepsNum": counts[k]})
    return speed_windows, step_windows


def build_laps(points: List[GpsPoint], start_ms: int) -> List[dict]:
    """Per-kilometre laps (the app's "每公里数据"), contiguous and exact."""
    laps = []
    if len(points) < 2:
        return laps
    ds = [p.cum_dist for p in points]
    ts = [(p.time - start_ms) / 1000.0 for p in points]
    es = [p.ele for p in points]
    ss = [p.cum_steps for p in points]
    total_d = ds[-1]
    if total_d <= 0:
        return laps
    alt0 = es[0]

    def _at(d):
        if d <= ds[0]:
            return ts[0], es[0], ss[0]
        if d >= total_d:
            return ts[-1], es[-1], ss[-1]
        lo, hi = 0, len(ds) - 1
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if ds[mid] <= d:
                lo = mid
            else:
                hi = mid
        span = ds[hi] - ds[lo]
        f = 0.0 if span <= 1e-9 else (d - ds[lo]) / span
        return (ts[lo] + (ts[hi] - ts[lo]) * f,
                es[lo] + (es[hi] - es[lo]) * f,
                ss[lo] + (ss[hi] - ss[lo]) * f)

    def _gain(d_a, d_b):
        eles = [_at(d_a)[1]]
        for i, d in enumerate(ds):
            if d <= d_a:
                continue
            if d >= d_b:
                break
            eles.append(es[i])
        eles.append(_at(d_b)[1])
        return elevation_gain(eles)

    bounds = []
    k = 0
    while (k + 1) * 1000.0 <= total_d + 1e-6:
        bounds.append([k * 1000.0, (k + 1) * 1000.0])
        k += 1
    tail = total_d - k * 1000.0
    if tail > 0 and bounds:
        t_tail = _at(total_d)[0] - _at(k * 1000.0)[0]
        if tail >= 1.0 and t_tail >= 2.0:
            bounds.append([k * 1000.0, total_d])
        else:
            bounds[-1][1] = total_d
    if not bounds:
        bounds = [[0.0, total_d]]

    prev_cum = 0
    for i, (d_a, d_b) in enumerate(bounds):
        t_a, e_a, s_a = _at(d_a)
        t_b, e_b, s_b = _at(d_b)
        lap_d = d_b - d_a
        raw_t = max(1e-9, t_b - t_a)
        cum = int(round(t_b))
        lap_dur = cum - prev_cum
        prev_cum = cum
        lap_steps = int(max(0.0, s_b - s_a))
        laps.append({
            "avgCadence": round(lap_steps / (raw_t / 60.0), 2),
            "avgPace": round((raw_t / 60.0) / max(lap_d / 1000.0, 0.001), 2),
            "avgStride": round(lap_d / max(1, lap_steps) * 100.0, 2),
            "cumulativeDuration": cum,
            "distance": round(lap_d, 4),
            "duration": lap_dur,
            "elevationGain": _gain(d_a, d_b),
            "endAltAbs": round(e_b, 2),
            "endAltRel": round(e_b - alt0, 2),
            "flag": start_ms,
            "id": i + 1,
            "isFullLap": lap_d >= 1000.0 - 1e-9,
            "lapIndex": i + 1,
            "step": lap_steps,
        })
    return laps


def build_obs_payload(gps_points: List[GpsPoint], five_points: Optional[List[FivePoint]], *,
                      uid: int, uuid_str: str, start_time_ms: int, total_time_sec: int,
                      total_distance_m: int, total_steps: int, rrid: int = 0,
                      sport_type: int = 1,
                      weight_kg: float = DEFAULT_BODY_WEIGHT_KG) -> dict:
    """Assemble the 10-key OBS object (single-layer gzip+base64 values).

    ``rrid`` is only known *after* the record is saved, so the caller rebuilds
    this object once the server returns it; the 10 s window ids then use the
    real rrid (id = (rrid % 100000) * 1000 + window right edge).
    """
    _ensure_cumulative(gps_points, float(total_distance_m), int(total_steps))
    speed_windows, step_windows = _ten_sec_windows(
        gps_points, start_time_ms, total_time_sec, rrid=int(rrid or 0),
        queue_seq=False, total_steps=int(total_steps),
        total_distance=float(total_distance_m))
    laps = build_laps(gps_points, start_time_ms)

    obs_points = [p.to_obs_dict(start_time_ms) for p in gps_points]
    if obs_points:
        obs_points[0] = gps_points[0].to_obs_dict(start_time_ms, pt_type=5)
        obs_points[-1] = gps_points[-1].to_obs_dict(start_time_ms, pt_type=6)
    run_wrap = json.dumps({
        "allLocJson": json.dumps(obs_points, separators=(",", ":")),
        "useZip": False,
    }, separators=(",", ":"), ensure_ascii=False)

    five_list = [fp.to_obs_dict(start_time_ms, i + 1)
                 for i, fp in enumerate(five_points or [])]
    fx = {
        # The app's Bean declares both of these as String; the value is a JSON
        # array *text*.  Sending a raw array throws on Gson parse.
        "fivePointJson": json.dumps(five_list, separators=(",", ":"), ensure_ascii=False),
        "freedomShowFence": False,
        "geoFencesJson": "[]",
        "runAreaId": -1,
        "useZip": False,
    }

    return {
        "rrid": gzip_base64_encode(str(rrid) if rrid else ""),
        "uid": gzip_base64_encode(str(uid)),
        "uuid": gzip_base64_encode(uuid_str),
        "run_data": gzip_base64_encode(run_wrap),
        "step_freq_json": gzip_base64_encode(json.dumps(step_windows, separators=(",", ":"))),
        "speed_json": gzip_base64_encode(json.dumps(speed_windows, separators=(",", ":"))),
        "segment_json": gzip_base64_encode(""),
        "fixed_point_json": gzip_base64_encode(
            json.dumps(fx, separators=(",", ":"), ensure_ascii=False)),
        "runFaceCheck": gzip_base64_encode(""),
        "extension_json": gzip_base64_encode(""),
        "laps_json": gzip_base64_encode(json.dumps(laps, separators=(",", ":"))),
    }


def order_points_loop(points_ll: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Order (lat, lon) points into a simple loop by bearing around the centroid."""
    if len(points_ll) < 3:
        return list(points_ll)
    lat0 = sum(p[0] for p in points_ll) / len(points_ll)
    lon0 = sum(p[1] for p in points_ll) / len(points_ll)
    kx = math.cos(math.radians(lat0))

    def _ang(p):
        return math.atan2(p[0] - lat0, (p[1] - lon0) * kx)

    return sorted(points_ll, key=_ang)


def _build_loop_through_points(control_ll, n_per_seg: int = 60):
    """Closed polygon through the control points with rounded corners.

    control_ll: list of (lat, lon) in WGS-84, in visit order.  Straight edges
    plus a small quadratic fillet at each vertex mimic running along campus
    roads (long straights + turns) far better than a Catmull-Rom spline, whose
    near-constant curvature is itself a fingerprint.  The ring is rotated so it
    starts at the point farthest from any control point.
    """
    n = len(control_ll)
    lat0 = sum(p[0] for p in control_ll) / n
    lon0 = sum(p[1] for p in control_ll) / n
    kx = math.cos(math.radians(lat0))
    m_lat = 111320.0
    m_lon = 111320.0 * kx
    xy = [((lon - lon0) * m_lon, (lat - lat0) * m_lat) for lat, lon in control_ll]

    def _unit(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy) or 1.0
        return (dx / length, dy / length), length

    # entry/exit points of the rounded corner at each vertex
    entry = []
    exit_ = []
    for i in range(n):
        prev, cur, nxt = xy[(i - 1) % n], xy[i], xy[(i + 1) % n]
        u_in, len_prev = _unit(cur, prev)
        u_out, len_next = _unit(cur, nxt)
        r = min(len_prev, len_next) * 0.15
        entry.append((cur[0] + u_in[0] * r, cur[1] + u_in[1] * r))
        exit_.append((cur[0] + u_out[0] * r, cur[1] + u_out[1] * r))

    dense = []
    for i in range(n):
        a = exit_[i]                 # leave vertex i
        b = entry[(i + 1) % n]       # arrive at vertex i+1
        for j in range(n_per_seg):   # straight edge
            t = j / n_per_seg
            dense.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        v = xy[(i + 1) % n]          # rounded corner (quadratic Bezier)
        p0, p2 = entry[(i + 1) % n], exit_[(i + 1) % n]
        steps = max(2, n_per_seg // 4)
        for j in range(steps):
            t = j / steps
            mt = 1.0 - t
            dense.append((mt * mt * p0[0] + 2 * mt * t * v[0] + t * t * p2[0],
                          mt * mt * p0[1] + 2 * mt * t * v[1] + t * t * p2[1]))
    body = [(lat0 + y / m_lat, lon0 + x / m_lon) for x, y in dense]

    # Rotate the ring so it starts at the point farthest from every control point.
    best_i, best_d = 0, -1.0
    for i, (la, lo) in enumerate(body):
        d = min(_haversine_m(la, lo, cl[0], cl[1]) for cl in control_ll)
        if d > best_d:
            best_d, best_i = d, i
    if best_i:
        body = body[best_i:] + body[:best_i]

    def _cum(path):
        c = [0.0]
        for i in range(1, len(path)):
            c.append(c[-1] + _haversine_m(path[i - 1][0], path[i - 1][1],
                                          path[i][0], path[i][1]))
        c.append(c[-1] + _haversine_m(path[-1][0], path[-1][1],
                                      path[0][0], path[0][1]))
        return c

    cum = _cum(body)
    path = body + [body[0]]
    return path, cum


def generate_synthetic_gps_track(start_lat: float, start_lon: float,
                                 total_distance_m: int, total_time_sec: int,
                                 start_time_ms: int,
                                 total_steps: Optional[int] = None,
                                 weight_kg: float = DEFAULT_BODY_WEIGHT_KG,
                                 height_cm: float = DEFAULT_HEIGHT_CM,
                                 control_points: Optional[List[Tuple[float, float]]] = None,
                                 rng: Optional[random.Random] = None
                                 ) -> Tuple[List[GpsPoint], List[FivePoint]]:
    start_lat, start_lon = validate_coordinate(start_lat, start_lon)
    if total_distance_m <= 0:
        raise ValueError("total_distance_m must be positive")
    if total_time_sec <= 0:
        raise ValueError("total_time_sec must be positive")
    rng = rng or random
    if total_steps is None:
        total_steps = max(1, int(round(total_distance_m * 1.05)))

    n = max(2, int(total_time_sec) // 5)
    base_speed = total_distance_m / total_time_sec

    deltas = _sample_deltas(n, float(total_time_sec), rng)
    if len(deltas) != n - 1:
        deltas = [float(total_time_sec) / (n - 1)] * (n - 1)

    def _cumulate(vs: List[float]) -> List[float]:
        c = [0.0]
        for i in range(1, n):
            c.append(c[-1] + 0.5 * (vs[i - 1] + vs[i]) * deltas[i - 1])
        if c[-1] > 0:
            k = total_distance_m / c[-1]
            c = [x * k for x in c]
        c[-1] = float(total_distance_m)
        return c

    # 1) base speed: trend + oscillation + AR(1) jitter
    speeds0 = _speed_profile(n, base_speed, float(total_time_sec), rng)
    cum0 = _cumulate(speeds0)

    # 2) elevation profile (a function of distance) and its slope
    e_base = rng.uniform(15.0, 130.0)
    # 4-6 terrain components so the altitude power spectrum is broadband
    # instead of two clean spikes.
    terrain_terms = [(rng.uniform(0.3, 2.4), rng.uniform(220.0, 2600.0),
                      rng.uniform(0.0, 2 * math.pi)) for _ in range(rng.randint(4, 6))]

    def _elev(d: float) -> float:
        return e_base + sum(a * math.sin(2 * math.pi * d / w + p)
                            for a, w, p in terrain_terms)

    def _grade(d: float) -> float:
        return sum(a * (2 * math.pi / w) * math.cos(2 * math.pi * d / w + p)
                   for a, w, p in terrain_terms)

    # 3) terrain coupling: uphill slows, downhill only slightly speeds up
    k_up, k_down = rng.uniform(1.2, 2.2), rng.uniform(0.6, 1.2)
    speeds = []
    for i in range(n):
        g = _grade(cum0[i])
        factor = (1.0 - k_up * g) if g > 0 else (1.0 - k_down * g)
        speeds.append(speeds0[i] * min(1.06, max(0.90, factor)))
    m = sum(speeds) / n
    if m > 1e-9:
        speeds = [v * base_speed / m for v in speeds]
    cum = _cumulate(speeds)

    path, path_cum = (_build_loop_through_points(control_points)
                      if control_points and len(control_points) >= 2
                      else _build_route(start_lat, start_lon, float(total_distance_m), rng))

    # Cadence follows speed weakly (v**0.16) plus a slow drift and per-window
    # counting noise, then is scaled so the integral equals the requested total
    # number of steps exactly.  The variation (not just the level) is what keeps
    # 10 s windows from collapsing to a two-value pattern on steady runs.
    alpha = rng.uniform(0.20, 0.35)
    rho_c, sigma_c = rng.uniform(0.60, 0.85), rng.uniform(0.020, 0.035)
    cad_ar = [0.0] * n
    for i in range(1, n):
        cad_ar[i] = (cad_ar[i - 1] * rho_c
                     + sigma_c * math.sqrt(1 - rho_c * rho_c) * rng.gauss(0.0, 1.0))
    cad_prof = [((max(0.35, speeds[i]) / base_speed) ** alpha) * (1.0 + cad_ar[i])
                for i in range(n)]
    integral = sum(0.5 * (cad_prof[i - 1] + cad_prof[i]) / 60.0 * deltas[i - 1]
                   for i in range(1, n))
    cad_scale = (float(total_steps) / integral) if integral > 0 else 0.0
    cadence = [min(300.0, max(40.0, c * cad_scale)) for c in cad_prof]

    steps_cum = [0.0]
    for i in range(1, n):
        steps_cum.append(steps_cum[-1] + 0.5 * (cadence[i - 1] + cadence[i]) / 60.0 * deltas[i - 1])
    if steps_cum[-1] > 0:
        sf = float(total_steps) / steps_cum[-1]
        steps_cum = [s * sf for s in steps_cum]

    drift = 1.5 / 111320.0
    cos_lat = math.cos(math.radians(start_lat))
    # Autocorrelated (colored) GPS drift — real receiver error is not white noise.
    rho_g = rng.uniform(0.55, 0.85)
    gps_n = gps_e = 0.0
    # Colored barometric altitude noise (kept in the OBS; ascent uses a smoothed copy).
    rho_e = rng.uniform(0.75, 0.92)
    sigma_e = rng.uniform(0.45, 0.80)
    ele_noise = [0.0] * n
    for i in range(1, n):
        ele_noise[i] = (ele_noise[i - 1] * rho_e
                        + sigma_e * math.sqrt(1 - rho_e * rho_e) * rng.gauss(0.0, 1.0))
    points = []
    elapsed_ms = 0.0
    for i in range(n):
        if i > 0:
            elapsed_ms += deltas[i - 1] * 1000.0
        pt_time = int(round(start_time_ms + elapsed_ms))
        lat, lon = _point_at_distance(path, path_cum, cum[i])
        if i > 0:
            gps_n = gps_n * rho_g + drift * math.sqrt(1 - rho_g * rho_g) * rng.gauss(0.0, 1.0)
            gps_e = gps_e * rho_g + drift * math.sqrt(1 - rho_g * rho_g) * rng.gauss(0.0, 1.0)
            lat += gps_n
            lon += gps_e / cos_lat
        ele = _elev(cum[i]) + ele_noise[i]
        cad = cadence[i]
        stride = (speeds[i] / (cad / 60.0) * 100.0) if cad > 0 else 0.0
        stride = max(height_cm * 0.42, min(height_cm * 1.15, stride))
        acc = min(25.0, max(1.5, rng.gauss(5.0, 2.0)))
        points.append(GpsPoint(round(lat, 6), round(lon, 6), pt_time,
                               round(speeds[i], 3), accuracy=round(acc, 1),
                               ele=round(ele, 2), cadence=round(cad, 1),
                               stride_cm=round(stride, 1), cum_dist=round(cum[i], 3),
                               cum_steps=round(steps_cum[i], 2), index=i))

    # The OBS keeps the (noisier) per-fix altitude; totalAscent is computed from
    # a device-like smoothed copy in build_record.

    # Five fixed checkpoints; the first doubles as the run anchor.
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
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("record location fields must contain valid JSON") from exc
    fixed_raw = record.get("fivePointJson") or "[]"
    try:
        parsed_fixed = json.loads(fixed_raw) if isinstance(fixed_raw, str) else fixed_raw
        # Body fivePointJson is a wrapper string; unwrap to the inner array.
        if isinstance(parsed_fixed, dict) and "fivePointJson" in parsed_fixed:
            inner = parsed_fixed["fivePointJson"]
            fixed = json.loads(inner) if isinstance(inner, str) else inner
        else:
            fixed = parsed_fixed
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
    track_gcj = [wgs84_to_gcj02(tp.latitude, tp.longitude) for tp in track_coordinates]
    for point in fixed:
        if point.get("glat") is not None and point.get("glon") is not None:
            # Server check-in point: judge in GCJ within the hit radius.
            fixed_coord = validate_coordinate(point.get("glat"), point.get("glon"))
            limit = max(float(point.get("radius") or 15.0), 20.0)
            hit = any(_haversine_m(fixed_coord.latitude, fixed_coord.longitude,
                                   gla, glo) <= limit for gla, glo in track_gcj)
        else:
            fixed_coord = validate_coordinate(point.get("lat"),
                                              point.get("lon", point.get("lng")))
            hit = any(coordinates_match(fixed_coord.latitude, fixed_coord.longitude,
                                        tp.latitude, tp.longitude, tolerance)
                      for tp in track_coordinates)
        if not hit:
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
                      calorie: int = 0,
                      rng: Optional[random.Random] = None) -> Tuple[str, dict, dict]:
        rng = rng or random
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
            weights = _effort_weights(num_buckets, rng)
            step_counts = _largest_remainder(total_steps, weights)
            for i in range(num_buckets):
                b_start = start_time_ms + i * 10000
                b_end = min(stop_time_ms, b_start + 10000)
                step_buckets.append(StepBucket(step_counts[i], b_start, b_end, queue_num=i + 1))

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
                     calorie: Optional[int] = None, avg_power: Optional[int] = None,
                     total_ascent: Optional[int] = None,
                     weight_kg: float = DEFAULT_BODY_WEIGHT_KG,
                     rng: Optional[random.Random] = None,
                     policy: int = 1,
                     sel_distance: Optional[int] = None,
                     sel_run_time: Optional[int] = None,
                     face_check: int = 0,
                     address: str = "",
                     room_id: int = 0) -> Tuple[str, dict, dict]:
        if not gps_points:
            raise ValueError("gps_points cannot be empty")

        # The record-level location is deliberately derived from the same first
        # point that is serialized into allLocJson.  Do not accept a second,
        # independent coordinate source here.
        anchor = validate_coordinate(gps_points[0].lat, gps_points[0].lon)
        anchor_lat, anchor_lon = anchor

        rng = rng or random
        _ensure_cumulative(gps_points, float(total_distance_m), int(total_steps))

        # 10 s windows share the device's whole-second quota-carry semantics, so
        # sum(stepsPerTenSec) == totalSteps and sum(speedPerTenSec) == totalDis
        # hold exactly (the server checks the step sum).
        speed_windows, step_windows = _ten_sec_windows(
            gps_points, start_time_ms, total_time_sec, rrid=0, queue_seq=True,
            total_steps=int(total_steps), total_distance=float(total_distance_m))
        window_steps = sum(w["stepsNum"] for w in step_windows)
        if window_steps > 0:
            total_steps = window_steps

        sel_distance = self.sel_distance_m if sel_distance is None else int(sel_distance)
        sel_run_time = self.sel_run_time_s if sel_run_time is None else int(sel_run_time)
        complete = (total_distance_m >= sel_distance) and (total_time_sec >= sel_run_time)
        un_complete_reason = 0 if complete else 10
        avg_step_freq = round(total_steps * 60.0 / total_time_sec) if total_time_sec > 0 else 0
        # `speed` is the app's 毫-分/公里 unit: pace (min/km) × 1000.
        speed_val = (int(round((total_time_sec / 60.0) / (total_distance_m / 1000.0) * 1000.0))
                     if total_distance_m > 0 and total_time_sec > 0 else 0)

        if total_ascent is None:
            if any(p.ele for p in gps_points):
                eles = _smooth_series([p.ele for p in gps_points], 5)
                total_ascent = int(round(elevation_gain(eles)))
            else:
                total_ascent = estimate_total_ascent(total_distance_m, rng)
        if calorie is None:
            calorie = estimate_calorie(total_distance_m, total_time_sec, weight_kg)
        if avg_power is None:
            avg_power = estimate_avg_power(total_distance_m, total_time_sec,
                                           total_ascent, weight_kg)

        sign_map = {
            "address": address,
            "avgPower": avg_power,
            "avgStepFreq": avg_step_freq,
            "calorie": calorie,
            "complete": complete,
            "errorCode": 0,
            "faceCheck": face_check,
            "geeToken": "",
            "getPrize": False,
            # Java reflection signs String.valueOf(null), not an omitted field.
            "goalId": "null",
            "policy": policy,
            "selDistance": sel_distance,
            "selRunTime": sel_run_time,
            "selectedUnid": self.unid,
            "speed": speed_val,
            "sportType": self.sport_type,
            "startTime": start_time_ms,
            "status": 1,
            "stopTime": stop_time_ms,
            "themeId": 0,
            "totalAscent": total_ascent,
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

        speed_buckets = [
            SpeedBucket(w["distance"], w["beginTime"], w["endTime"], flag=w["flag"],
                        state=w["state"], queue_num=w["queueNum"], bucket_id=w["id"])
            for w in speed_windows
        ]
        step_buckets = [
            StepBucket(w["stepsNum"], w["beginTime"], w["endTime"], flag=w["flag"],
                       max_diff=w["maxDiff"], min_diff=w["minDiff"],
                       avg_diff=w["avgDiff"], state=w["state"],
                       queue_num=w["queueNum"], bucket_id=w["id"])
            for w in step_windows
        ]

        all_loc_json = json.dumps([p.to_dict() for p in gps_points], separators=(",", ":"))
        # Body fivePointJson is a wrapper string (the app's Bean reads it as a
        # String whose content is the JSON array text).
        five_inner = json.dumps([p.to_dict() for p in (five_points or [])],
                                separators=(",", ":"), ensure_ascii=False)
        five_pt_json = json.dumps({
            "useZip": False,
            "fivePointJson": five_inner,
            "runAreaId": -1,
            "geoFencesJson": "[]",
            "freedomShowFence": False,
        }, separators=(",", ":"), ensure_ascii=False)


        save_record = {
            "address": address,
            "allLocJson": all_loc_json,
            "avgPower": avg_power,
            "avgStepFreq": avg_step_freq,
            "calorie": calorie,
            "complete": complete,
            "errorCode": 0,
            "faceCheck": face_check,
            "fivePointJson": five_pt_json,
            "geeToken": "",
            "getPrize": False,
            "goalId": None,
            "isUpload": False,
            "more": False,
            "latitude": anchor_lat,
            "longitude": anchor_lon,
            "maxRunTime": 0,
            "minSteps": 0,
            "originalSign": original_sign,
            "policy": policy,
            "recordUrl": "",
            "roomId": room_id,
            "segmentJson": "[]",
            "selDistance": sel_distance,
            "selRunTime": sel_run_time,
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
            "totalAscent": total_ascent,
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

        # OBS built with rrid=0; submit_outdoor_run rebuilds it with the real
        # rrid once the save response returns it.
        cos_payload = build_obs_payload(
            gps_points, five_points, uid=self.uid, uuid_str=self.uuid_str,
            start_time_ms=start_time_ms, total_time_sec=total_time_sec,
            total_distance_m=total_distance_m, total_steps=total_steps,
            rrid=0, sport_type=self.sport_type, weight_kg=weight_kg,
        )

        return "/api/v70260/runnings/save/record", save_record, cos_payload
