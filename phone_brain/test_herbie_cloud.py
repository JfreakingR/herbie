import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import herbie_chat
import herbie_cloud


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.config = Path(self.folder.name) / "herbie-cloud.json"
        patcher = mock.patch.dict(os.environ, {"HERBIE_CLOUD_CONFIG": str(self.config)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.folder.cleanup)

    def provision(self, **extra):
        self.config.write_text(json.dumps({"anthropic_key": "k" * 40, **extra}), encoding="utf-8")

    def test_unprovisioned_cloud_is_skipped(self):
        self.assertIsNone(herbie_cloud.load_config())
        with self.assertRaisesRegex(herbie_cloud.CloudUnavailable, "not_provisioned"):
            herbie_cloud.chat("hi", "", 64)

    def test_default_model_is_sonnet_5(self):
        self.provision()
        self.assertEqual(herbie_cloud.load_config()["model"], "claude-sonnet-5")

    def test_request_is_spoken_small_talk(self):
        body = herbie_cloud.build_request("claude-sonnet-5", "hello", "Identity: Herbie.", 64)
        self.assertEqual(body["thinking"], {"type": "disabled"})
        self.assertNotIn("temperature", body)
        self.assertIn("Identity: Herbie.", body["system"])
        self.assertEqual(body["messages"], [{"role": "user", "content": "hello"}])

    def test_reply_text_is_joined_from_text_blocks(self):
        reply = herbie_cloud.parse_reply(
            {"stop_reason": "end_turn", "content": [
                {"type": "text", "text": "[laughs] Hey"}, {"type": "text", "text": " there."}]}
        )
        self.assertEqual(reply, "[laughs] Hey there.")

    def test_refusal_falls_back(self):
        with self.assertRaisesRegex(herbie_cloud.CloudUnavailable, "declined"):
            herbie_cloud.parse_reply({"stop_reason": "refusal", "content": []})

    def test_router_uses_local_brains_when_cloud_fails(self):
        local = {"text": "local reply", "motor_authority": False, "safe_motion_state": "STOP"}
        with mock.patch.object(
            herbie_cloud, "chat", side_effect=herbie_cloud.CloudUnavailable("cloud_unreachable")
        ), mock.patch.object(herbie_chat, "post_local_chat", return_value=dict(local)) as pc:
            result = herbie_chat.route_chat(
                {"message": "hi"},
                computer_available=True,
                computer_url="http://192.168.1.10:8770",
                computer_token="t" * 32,
                context="",
            )
        self.assertEqual(result["text"], "local reply")
        pc.assert_called_once()

    def test_router_prefers_cloud(self):
        cloud = {"text": "cloud reply", "brain": "cloud"}
        with mock.patch.object(herbie_cloud, "chat", return_value=cloud), mock.patch.object(
            herbie_chat, "post_local_chat"
        ) as pc:
            result = herbie_chat.route_chat(
                {"message": "hi"},
                computer_available=True,
                computer_url="http://192.168.1.10:8770",
                computer_token="t" * 32,
                context="",
            )
        self.assertEqual(result["brain"], "cloud")
        pc.assert_not_called()

    def test_memory_plan_tolerates_prose_and_nonsense(self):
        plan = herbie_cloud.parse_memory_plan(
            'Sure! {"remember": [{"content": "The owner is Sam."}], "forget": [3]} done'
        )
        self.assertEqual(plan["remember"], [{"content": "The owner is Sam."}])
        self.assertEqual(plan["forget"], [3])
        self.assertEqual(plan["update"], [])
        self.assertEqual(
            herbie_cloud.parse_memory_plan("no json here"),
            {"remember": [], "update": [], "forget": []},
        )


if __name__ == "__main__":
    unittest.main()
