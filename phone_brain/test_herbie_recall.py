import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class RecallTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        folder = Path(self.tempdir.name)
        self.env = mock.patch.dict(
            os.environ,
            {
                "HERBIE_MEMORY_DB": str(folder / "memory.sqlite3"),
                "HERBIE_PENDING_MEMORIES": str(folder / "pending.json"),
                "HERBIE_RECENT_DIALOGUE": str(folder / "dialogue.json"),
                "HERBIE_CLOUD_CONFIG": str(folder / "no-cloud.json"),
            },
        )
        self.env.start()
        import herbie_memory

        self.memory = importlib.reload(herbie_memory)
        self.memory.initialize()
        import herbie_cloud
        import herbie_recall

        self.cloud = herbie_cloud
        self.recall = importlib.reload(herbie_recall)
        self.owner_id = self.memory.remember(
            {"content": "My name is Herbie.", "kind": "identity", "source": "owner",
             "importance": 1.0}
        )["memory_id"]

    def tearDown(self):
        self.env.stop()
        self.tempdir.cleanup()

    def contents(self):
        return [m["content"] for m in self.memory.recent(50, "", "recent")]

    def test_new_facts_are_stored_once(self):
        plan = {"remember": [{"content": "The owner's name is Sam.", "importance": 0.9},
                             {"content": "The owner's name is Sam.", "importance": 0.9}]}
        done = self.recall.apply_plan(plan, self.memory.recent(50, "", "recent"))
        self.assertEqual(done["remembered"], 1)
        stored = [m for m in self.memory.recent(50, "", "recent") if m["source"] == "conversation"]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["kind"], "fact")

    def test_owner_setup_memories_cannot_be_forgotten_by_voice(self):
        known = self.memory.recent(50, "", "recent")
        done = self.recall.apply_plan(
            {"forget": [self.owner_id], "update": [{"memory_id": self.owner_id, "content": "x"}]},
            known,
        )
        self.assertEqual(done, {"remembered": 0, "updated": 0, "forgotten": 0})
        self.assertIn("My name is Herbie.", self.contents())

    def test_conversation_memories_can_be_corrected_and_forgotten(self):
        self.recall.apply_plan({"remember": [{"content": "The owner likes tea."}]}, [])
        known = self.memory.recent(50, "", "recent")
        tea = next(m for m in known if "tea" in m["content"])
        self.recall.apply_plan(
            {"update": [{"memory_id": tea["id"], "content": "The owner likes coffee."}]}, known
        )
        self.assertIn("The owner likes coffee.", self.contents())
        self.recall.apply_plan({"forget": [tea["id"]]}, self.memory.recent(50, "", "recent"))
        self.assertNotIn("The owner likes coffee.", self.contents())

    def test_garbage_plans_are_ignored(self):
        done = self.recall.apply_plan(
            {"remember": ["nope", {"content": 5}], "update": [7], "forget": ["x"]}, []
        )
        self.assertEqual(done, {"remembered": 0, "updated": 0, "forgotten": 0})

    def test_explicit_remember_works_offline(self):
        self.recall.learn("Herbie, remember that my sister visits on Sunday", "Got it.")
        self.assertTrue(any("sister visits on Sunday" in c for c in self.contents()))

    def test_small_talk_offline_stores_nothing(self):
        before = len(self.contents())
        self.recall.learn("how's it going", "Pretty good!")
        self.assertEqual(len(self.contents()), before)

    def test_unreachable_cloud_queues_then_catches_up(self):
        with mock.patch.object(self.cloud, "load_config", return_value={"key": "k", "model": "m"}):
            with mock.patch.object(
                self.cloud, "extract_memories",
                side_effect=self.cloud.CloudUnavailable("cloud_unreachable"),
            ):
                self.recall.learn("I start a new job Monday", "Nice!")
            self.assertEqual(len(json.loads(Path(os.environ["HERBIE_PENDING_MEMORIES"]).read_text())), 1)
            with mock.patch.object(
                self.cloud, "extract_memories",
                return_value={"remember": [{"content": "The owner starts a new job on Monday."}],
                              "update": [], "forget": []},
            ):
                self.recall.learn("cool", "yep")
        self.assertIn("The owner starts a new job on Monday.", self.contents())
        self.assertEqual(json.loads(Path(os.environ["HERBIE_PENDING_MEMORIES"]).read_text()), [])

    def test_context_includes_relevant_and_key_memories(self):
        self.recall.apply_plan(
            {"remember": [{"content": "The owner's dog is named Biscuit.", "importance": 0.9}]}, []
        )
        lines = self.recall.context_memories("what's my dog called")
        self.assertIn("The owner's dog is named Biscuit.", lines)
        self.assertIn("My name is Herbie.", lines)

    def test_dialogue_survives_a_restart(self):
        turns = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hey"}]
        self.recall.save_dialogue(turns)
        self.assertEqual(importlib.reload(self.recall).load_dialogue(), turns)


if __name__ == "__main__":
    unittest.main()
