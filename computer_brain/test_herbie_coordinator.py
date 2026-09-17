import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import herbie_coordinator as coordinator


class CoordinatorTests(unittest.TestCase):
    def test_normalizes_endpoint(self):
        self.assertEqual(
            coordinator.normalized_endpoint("192.168.1.185:8765/"),
            "http://192.168.1.185:8765",
        )

    def test_cached_endpoint_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "endpoint.json"
            coordinator.save_endpoint("http://192.168.1.185:8765", path)
            self.assertEqual(
                coordinator.cached_endpoint(path), "http://192.168.1.185:8765"
            )

    def test_lease_payload_claims_no_motor_authority(self):
        response = {
            "coordination": {
                "active_brain": "windows-computer",
                "phone_fallback_ready": True,
                "memory_writer": "phone",
                "motor_authority": False,
                "safe_motion_state": "STOP",
            }
        }
        with mock.patch.object(coordinator, "discover_phone", return_value="http://phone:8765"), mock.patch.object(
            coordinator, "load_token", return_value="test-token"
        ), mock.patch.object(coordinator, "renew_lease", return_value=response) as renew:
            result = coordinator.run_once(None, 15, "http://192.168.1.10:18766")
        renew.assert_called_once_with(
            "http://phone:8765", "test-token", 15, "http://192.168.1.10:18766"
        )
        self.assertEqual(result["memory_writer"], "phone")
        self.assertFalse(result["motor_authority"])
        self.assertEqual(result["safe_motion_state"], "STOP")


if __name__ == "__main__":
    unittest.main()
