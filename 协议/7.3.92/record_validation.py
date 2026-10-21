"""Local validation and lossless ten-second summary buckets."""
import math
from decimal import Decimal, ROUND_HALF_UP


def validate_run(total_time_sec, total_steps, start_time_ms, stop_time_ms,
                 total_distance_m=None):
    for name, value in (("total_time_sec", total_time_sec),
                        ("total_steps", total_steps),
                        ("start_time_ms", start_time_ms),
                        ("stop_time_ms", stop_time_ms)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer")
    if not 0 < total_time_sec <= 7200:
        raise ValueError("total_time_sec must be between 1 and 7200")
    if total_steps < 0 or start_time_ms < 0:
        raise ValueError("steps and start time cannot be negative")
    if stop_time_ms - start_time_ms != total_time_sec * 1000:
        raise ValueError("timestamps must match total_time_sec")
    if total_distance_m is not None:
        if (isinstance(total_distance_m, bool)
                or not isinstance(total_distance_m, (int, float))
                or not math.isfinite(total_distance_m) or total_distance_m <= 0):
            raise ValueError("total_distance_m must be positive and finite")


def time_buckets(total_time_sec, total_steps, start_time_ms, stop_time_ms,
                 total_distance_m=None):
    validate_run(total_time_sec, total_steps, start_time_ms, stop_time_ms,
                 total_distance_m)
    cents = (int((Decimal(str(total_distance_m)) * 100).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP)) if total_distance_m is not None else 0)
    for begin in range(0, total_time_sec, 10):
        end = min(begin + 10, total_time_sec)
        steps = total_steps * end // total_time_sec - total_steps * begin // total_time_sec
        distance = (cents * end // total_time_sec - cents * begin // total_time_sec) / 100
        yield start_time_ms + begin * 1000, start_time_ms + end * 1000, steps, distance


def validate_coordinate(latitude, longitude):
    if isinstance(latitude, bool) or isinstance(longitude, bool):
        raise ValueError("coordinates must be numeric")
    latitude, longitude = float(latitude), float(longitude)
    if (not math.isfinite(latitude) or not math.isfinite(longitude)
            or not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
        raise ValueError("coordinates must be finite and in range")
    return latitude, longitude
