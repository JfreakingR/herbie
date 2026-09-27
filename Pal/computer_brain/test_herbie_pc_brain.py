import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import herbie_pc_brain as brain


class PCBrainTests(unittest.TestCase):
    def test_only_local_addresses_are_allowed(self):
        self.assertTrue(brain.is_local_address("127.0.0.1"))
        self.assertTrue(brain.is_local_address("192.168.1.20"))
        self.assertFalse(brain.is_local_address("8.8.8.8"))
        self.assertFalse(brain.is_local_address("example.com"))

    def test_request_is_bounded(self):
        self.assertEqual(
            brain.validate_chat_request(
                {"message": "hello", "context": "memory", "max_tokens": 64}
            ),
            ("hello", "memory", 64),
        )
        for value in (0, 257, True, "64"):
            with self.assertRaises(ValueError):
                brain.validate_chat_request({"message": "hello", "max_tokens": value})

    def test_ollama_request_disables_thinking_and_motion(self):
        response = mock.MagicMock()
        response.read.return_value = json.dumps(
            {"message": {"content": "Hello from Herbie."}}
        ).encode()
        response.__enter__.return_value = response
        with mock.patch("urllib.request.urlopen", return_value=response) as opened:
            result = brain.ollama_chat("hello", "name=Herbie", 32)
        payload = json.loads(opened.call_args.args[0].data)
        self.assertFalse(payload["think"])
        self.assertEqual(payload["options"]["num_predict"], 32)
        self.assertFalse(result["motor_authority"])
        self.assertEqual(result["safe_motion_state"], "STOP")


if __name__ == "__main__":
    unittest.main()
