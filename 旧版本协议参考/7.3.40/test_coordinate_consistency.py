import json
import unittest

from running_protocol import (
    OutdoorRunRecordBuilder,
    generate_synthetic_gps_track,
    validate_outdoor_record_consistency,
)
from coordinate_utils import Coordinate, coordinates_match, validate_coordinate
from security_utils import redact_data, redact_text


class CoordinateConsistencyTests(unittest.TestCase):
    def test_coordinate_is_shared_value_object(self):
        coordinate = validate_coordinate("39.9042", "116.4074")
        self.assertIsInstance(coordinate, Coordinate)
        self.assertEqual(tuple(coordinate), (39.9042, 116.4074))

    def test_track_and_record_share_anchor(self):
        latitude, longitude = 39.9042, 116.4074
        points, fixed_points = generate_synthetic_gps_track(
            latitude, longitude, 2000, 1200, 0
        )
        _, record, _ = OutdoorRunRecordBuilder(
            uid=1, unid=2, sel_distance_m=2000, sel_run_time_s=1200
        ).build_record(
            total_distance_m=2000,
            total_time_sec=1200,
            total_steps=2000,
            start_time_ms=0,
            stop_time_ms=1200000,
            gps_points=points,
            five_points=fixed_points,
        )

        track = json.loads(record["allLocJson"])
        fixed = json.loads(record["fivePointJson"])
        self.assertTrue(coordinates_match(
            record["latitude"], record["longitude"],
            track[0]["lat"], track[0]["lon"],
        ))
        self.assertTrue(coordinates_match(
            fixed[0]["lat"], fixed[0]["lon"],
            track[0]["lat"], track[0]["lon"],
        ))
        summary = validate_outdoor_record_consistency(record)
        self.assertEqual(summary["trackPoints"], len(track))

    def test_first_track_point_offset_is_rejected(self):
        points, fixed_points = generate_synthetic_gps_track(39.9042, 116.4074, 2000, 1200, 0)
        _, record, _ = OutdoorRunRecordBuilder(1, 2).build_record(
            2000, 1200, 2000, 0, 1200000, points, fixed_points,
        )
        track = json.loads(record["allLocJson"])
        track[0]["lat"] += 0.01
        record["allLocJson"] = json.dumps(track)
        with self.assertRaisesRegex(ValueError, "anchor"):
            validate_outdoor_record_consistency(record)

    def test_empty_track_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            validate_outdoor_record_consistency({
                "latitude": 39.9,
                "longitude": 116.4,
                "allLocJson": "[]",
                "fivePointJson": "[]",
            })

    def test_coordinate_boundaries_and_non_finite_values(self):
        self.assertEqual(validate_coordinate(-90, -180).latitude, -90)
        self.assertEqual(validate_coordinate(90, 180).longitude, 180)
        for latitude, longitude in ((90.1, 0), (0, 180.1), (float("nan"), 0)):
            with self.assertRaises(ValueError):
                validate_coordinate(latitude, longitude)

    def test_fixed_point_must_belong_to_full_track(self):
        points, fixed_points = generate_synthetic_gps_track(
            39.9042, 116.4074, 2000, 1200, 0
        )
        _, record, _ = OutdoorRunRecordBuilder(1, 2).build_record(
            2000, 1200, 2000, 0, 1200000, points, fixed_points,
        )
        fixed = json.loads(record["fivePointJson"])
        fixed[0]["lon"] = 116.0
        record["fivePointJson"] = json.dumps(fixed)
        with self.assertRaisesRegex(ValueError, "fixed point"):
            validate_outdoor_record_consistency(record)

    def test_missing_coordinate_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_outdoor_record_consistency({
                "allLocJson": json.dumps([{"lat": 39.9, "lon": 116.4}]),
                "fivePointJson": "[]",
            })

    def test_sensitive_values_are_redacted(self):
        data = redact_data({"Token": "secret-token", "DeviceId": "device-123", "name": "ok"})
        self.assertNotEqual(data["Token"], "secret-token")
        self.assertNotEqual(data["DeviceId"], "device-123")
        self.assertEqual(data["name"], "ok")
        message = redact_text("token=secret-token uid=123456")
        self.assertNotIn("secret-token", message)
        self.assertNotIn("123456", message)


if __name__ == "__main__":
    unittest.main()
