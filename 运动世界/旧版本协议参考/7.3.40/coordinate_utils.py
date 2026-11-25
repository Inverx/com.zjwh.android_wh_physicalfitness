"""Shared coordinate validation for record generation and CLI input."""

import math
from dataclasses import dataclass
from typing import Iterator, Tuple


@dataclass(frozen=True)
class Coordinate:
    """A validated GPS coordinate used as the single source of truth."""

    latitude: float
    longitude: float
    precision: int = 6

    @property
    def lat(self) -> float:
        return self.latitude

    @property
    def lon(self) -> float:
        return self.longitude

    def rounded(self) -> "Coordinate":
        return Coordinate(
            round(self.latitude, self.precision),
            round(self.longitude, self.precision),
            self.precision,
        )

    def __iter__(self) -> Iterator[float]:
        """Keep backwards-compatible tuple unpacking for existing callers."""
        yield self.latitude
        yield self.longitude


def validate_coordinate(latitude: float, longitude: float) -> Coordinate:
    """Return numeric coordinates or raise a clear validation error."""
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError) as exc:
        raise ValueError("latitude and longitude must be numeric") from exc

    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("latitude and longitude must be finite")
    if not -90.0 <= latitude <= 90.0:
        raise ValueError(f"latitude out of range: {latitude}")
    if not -180.0 <= longitude <= 180.0:
        raise ValueError(f"longitude out of range: {longitude}")
    return Coordinate(latitude, longitude)


def coordinates_match(left_lat: float, left_lon: float,
                     right_lat: float, right_lon: float,
                     tolerance: float = 1e-6) -> bool:
    """Compare two serialized coordinate pairs at GPS precision."""
    return (abs(float(left_lat) - float(right_lat)) <= tolerance and
            abs(float(left_lon) - float(right_lon)) <= tolerance)
