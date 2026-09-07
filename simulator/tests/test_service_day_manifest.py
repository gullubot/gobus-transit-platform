"""
Tests for ServiceDayManifest.

BUILD 4 Phase 5B: Sanitized manifest loader, security checks, and structure validation.
"""

from pathlib import Path
import tempfile
import unittest

from simulator.service_day.manifest import (
    ServiceDayManifest,
    load_manifest,
    create_default_manifest,
)


class TestServiceDayManifest(unittest.TestCase):

    def test_create_default_manifest(self):
        manifest = create_default_manifest(service_date="2026-09-03")
        self.assertEqual(manifest.service_date, "2026-09-03")
        self.assertEqual(manifest.timezone, "Asia/Kolkata")
        self.assertEqual(len(manifest.vehicles), 4)
        self.assertEqual(len(manifest.operators), 7)
        self.assertEqual(len(manifest.trips), 7)

    def test_load_manifest_from_dict(self):
        data = {
            "service_date": "2026-09-03",
            "timezone": "Asia/Kolkata",
            "vehicles": [{"vehicle_id": "v1", "vehicle_number": "BUS-1"}],
            "operators": [{"operator_code": "O-1", "operator_name": "Driver 1"}],
            "trips": [
                {
                    "trip_id": "t1",
                    "service_id": "s1",
                    "route_id": "r1",
                    "vehicle_id": "v1",
                    "operator_code": "O-1",
                    "direction": "A_TO_B",
                    "planned_start": "2026-09-03T06:00:00+05:30",
                }
            ],
        }
        manifest = load_manifest(data)
        self.assertEqual(manifest.service_date, "2026-09-03")
        self.assertEqual(len(manifest.vehicles), 1)
        self.assertEqual(len(manifest.trips), 1)

    def test_manifest_rejects_forbidden_secrets(self):
        data = {
            "service_date": "2026-09-03",
            "timezone": "Asia/Kolkata",
            "vehicles": [{"vehicle_id": "v1"}],
            "operators": [{"operator_code": "O-1", "password": "SuperSecretPassword123"}],
            "trips": [{"trip_id": "t1"}],
        }
        with self.assertRaises(ValueError) as ctx:
            load_manifest(data)
        self.assertIn("forbidden credential key 'password'", str(ctx.exception))

    def test_manifest_rejects_bearer_token(self):
        data = {
            "service_date": "2026-09-03",
            "timezone": "Asia/Kolkata",
            "vehicles": [{"vehicle_id": "v1"}],
            "operators": [{"operator_code": "O-1"}],
            "trips": [{"trip_id": "t1", "jwt": "eyJhbGciOi..."}],
        }
        with self.assertRaises(ValueError) as ctx:
            load_manifest(data)
        self.assertIn("forbidden credential key 'jwt'", str(ctx.exception))

    def test_manifest_missing_required_fields(self):
        data = {"service_date": "2026-09-03"}
        with self.assertRaises(ValueError) as ctx:
            load_manifest(data)
        self.assertIn("missing required field", str(ctx.exception))

    def test_manifest_save_and_reload(self):
        manifest = create_default_manifest()
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "test_manifest.json"
            manifest.save(file_path)

            loaded = load_manifest(file_path)
            self.assertEqual(loaded.service_date, manifest.service_date)
            self.assertEqual(len(loaded.trips), len(manifest.trips))


if __name__ == "__main__":
    unittest.main()
