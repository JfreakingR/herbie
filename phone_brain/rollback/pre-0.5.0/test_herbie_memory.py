import os
import tempfile
import unittest
from pathlib import Path


class HerbieMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["HERBIE_MEMORY_DB"] = str(Path(self.tempdir.name) / "memory.sqlite3")
        import importlib
        import herbie_memory

        self.memory = importlib.reload(herbie_memory)
        self.memory.initialize()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_identity_and_safety_are_fixed(self):
        state = self.memory.self_snapshot()
        self.assertEqual(state["name"], "Herbie")
        self.assertFalse(state["motor_authority"])
        self.assertEqual(state["safe_motion_state"], "STOP")

    def test_memory_survives_new_connection(self):
        result = self.memory.remember(
            {
                "content": "Phyllis wants Herbie to remember and develop over time.",
                "kind": "relationship",
                "importance": 1.0,
                "source": "owner",
                "tags": ["identity", "memory"],
            }
        )
        self.assertGreater(result["memory_id"], 0)
        recalled = self.memory.recent(query="develop")
        self.assertEqual(len(recalled), 1)
        self.assertEqual(recalled[0]["source"], "owner")

    def test_personality_changes_slowly_and_is_audited(self):
        before = self.memory.self_snapshot()["personality"]["curiosity"]
        result = self.memory.experience(
            {
                "content": "Herbie discovered a new object safely.",
                "kind": "experience",
                "importance": 0.7,
                "source": "self",
                "signals": {"curiosity": 1.0, "confidence": 0.5},
                "learning_reason": "safe discovery",
            }
        )
        after = self.memory.self_snapshot()["personality"]["curiosity"]
        self.assertAlmostEqual(after - before, self.memory.LEARNING_RATE, places=4)
        self.assertIn("curiosity", result["personality_changes"])

    def test_invalid_trait_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_trait"):
            self.memory.experience(
                {
                    "content": "Invalid learning request.",
                    "source": "test",
                    "signals": {"motor_authority": 1.0},
                }
            )

    def test_expression_state_is_persistent_and_validated(self):
        changed = self.memory.set_expression(
            {
                "expression": "happy",
                "valence": 0.8,
                "arousal": 0.6,
                "attention": "owner",
                "listening": True,
            }
        )
        self.assertEqual(changed["expression"], "happy")
        self.assertTrue(changed["listening"])
        self.assertEqual(self.memory.expression_snapshot()["attention"], "owner")
        with self.assertRaisesRegex(ValueError, "invalid_expression"):
            self.memory.set_expression({"expression": "unsafe-unbounded-state"})

    def test_privacy_mode_blocks_senses_and_persists(self):
        self.memory.set_expression(
            {
                "expression": "curious",
                "listening": True,
                "camera_active": True,
            }
        )
        privacy = self.memory.set_privacy({"privacy_mode": True})
        self.assertTrue(privacy["privacy_mode"])
        self.assertEqual(privacy["expression"], "calm")
        self.assertFalse(privacy["listening"])
        self.assertFalse(privacy["camera_active"])
        self.assertFalse(privacy["camera_allowed"])
        self.assertFalse(privacy["microphone_allowed"])
        self.assertEqual(privacy["attention"], "privacy")
        with self.assertRaisesRegex(ValueError, "privacy_blocks_senses"):
            self.memory.set_expression({"listening": True})
        with self.assertRaisesRegex(ValueError, "privacy_blocks_senses"):
            self.memory.set_expression({"camera_active": True})
        import importlib

        reloaded = importlib.reload(self.memory)
        reloaded.initialize()
        restored = reloaded.expression_snapshot()
        self.assertTrue(restored["privacy_mode"])
        self.assertFalse(restored["camera_allowed"])
        self.assertFalse(restored["listening"])

    def test_privacy_off_restores_sense_permission(self):
        self.memory.set_privacy({"privacy_mode": True})
        restored = self.memory.set_privacy({"privacy_mode": False})
        self.assertFalse(restored["privacy_mode"])
        self.assertTrue(restored["camera_allowed"])
        self.assertTrue(restored["microphone_allowed"])
        self.assertEqual(restored["attention"], "")
        listening = self.memory.set_expression({"listening": True, "expression": "curious"})
        self.assertTrue(listening["listening"])


if __name__ == "__main__":
    unittest.main()
