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


class FakeLook:
    class vava:
        NECK_DEGREES_PER_STEP = 22.5

    def __init__(self, step):
        self.step = step
        self.calls = []

    def read_step(self):
        return self.step

    def main(self, argv):
        self.calls.append(argv)
        return 0


class NeckControllerTests(unittest.TestCase):
    def poll(self, look, reply):
        controller = coordinator.NeckController(look)
        with mock.patch.object(coordinator, "request_json", return_value=reply) as sent:
            result = controller.poll("http://phone:8765", "t")
        if controller._thread is not None:
            controller._thread.join(1)
        return result, sent

    def test_checks_in_with_heading_and_runs_a_claimed_look(self):
        look = FakeLook(step=2)
        result, sent = self.poll(look, {"look": {"id": 1, "degrees": 90}})
        self.assertEqual(result, 90)
        self.assertEqual(sent.call_args.args[1], "/v1/neck/claim")
        self.assertEqual(sent.call_args.kwargs["payload"], {"facing": 45.0, "busy": False})
        self.assertEqual(look.calls, [["herbie-look", "90"]])

    def test_nothing_waiting_moves_nothing(self):
        look = FakeLook(step=0)
        result, _ = self.poll(look, {"look": None})
        self.assertIsNone(result)
        self.assertEqual(look.calls, [])

    def test_unknown_heading_refuses_to_guess(self):
        look = FakeLook(step=None)
        result, sent = self.poll(look, {"look": {"id": 1, "degrees": 90}})
        self.assertIsNone(result)
        self.assertEqual(look.calls, [])
        self.assertIsNone(sent.call_args.kwargs["payload"]["facing"])


if __name__ == "__main__":
    unittest.main()
