"""Tests for owner memory rights, search, and the API token layer.

Covers the guarantees Herbie's core principles assert:
  "Allow the owner to inspect, correct, export, and delete memories."
and the access control that keeps anything local from rewriting him.
"""

import importlib
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path


class MemoryRightsTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["HERBIE_MEMORY_DB"] = str(Path(self.tempdir.name) / "memory.sqlite3")
        import herbie_memory

        self.memory = importlib.reload(herbie_memory)
        self.memory.initialize()

    def tearDown(self):
        self.tempdir.cleanup()

    def _add(self, content, importance=0.5, tags=None):
        return self.memory.remember(
            {
                "content": content,
                "kind": "experience",
                "source": "test",
                "importance": importance,
                "tags": tags or [],
            }
        )["memory_id"]

    # ------------------------------------------------------------- deletion

    def test_forget_soft_deletes_and_is_recoverable(self):
        mid = self._add("Herbie met a new person at the door.")
        self.assertEqual(self.memory.count_memories(), 1)

        result = self.memory.forget({"memory_id": mid})
        self.assertTrue(result["forgotten"])
        self.assertFalse(result["purged"])
        self.assertTrue(result["recoverable"])
        self.assertEqual(self.memory.count_memories(), 0)
        self.assertEqual(self.memory.recent(), [])

        restored = self.memory.restore({"memory_id": mid})
        self.assertTrue(restored["restored"])
        self.assertEqual(self.memory.count_memories(), 1)

    def test_purge_is_irreversible(self):
        mid = self._add("Something the owner wants gone for good.")
        self.memory.forget({"memory_id": mid, "purge": True})
        self.assertEqual(self.memory.count_memories(), 0)
        with self.assertRaisesRegex(ValueError, "memory_not_found"):
            self.memory.restore({"memory_id": mid})

    def test_forget_rejects_unknown_and_invalid_ids(self):
        with self.assertRaisesRegex(ValueError, "memory_not_found"):
            self.memory.forget({"memory_id": 9999})
        for bad in [0, -1, "3", None, True]:
            with self.assertRaisesRegex(ValueError, "invalid_memory_id"):
                self.memory.forget({"memory_id": bad})

    # ----------------------------------------------------------- correction

    def test_correct_updates_only_supplied_fields(self):
        mid = self._add("Herbie thinks the cat is called Mittens.", 0.4, ["cat"])
        self.memory.correct({"memory_id": mid, "content": "The cat is called Biscuit."})
        stored = self.memory.recent()[0]
        self.assertEqual(stored["content"], "The cat is called Biscuit.")
        self.assertAlmostEqual(stored["importance"], 0.4)
        self.assertEqual(stored["tags"], ["cat"])

    def test_correct_requires_something_to_change(self):
        mid = self._add("A memory.")
        with self.assertRaisesRegex(ValueError, "nothing_to_correct"):
            self.memory.correct({"memory_id": mid})

    def test_correct_validates_values(self):
        mid = self._add("A memory.")
        with self.assertRaisesRegex(ValueError, "invalid_importance"):
            self.memory.correct({"memory_id": mid, "importance": 5})
        with self.assertRaisesRegex(ValueError, "invalid_content"):
            self.memory.correct({"memory_id": mid, "content": "   "})

    # --------------------------------------------------------------- export

    def test_export_is_complete_and_local_only(self):
        keep = self._add("A kept memory.")
        gone = self._add("A deleted memory.")
        self.memory.forget({"memory_id": gone})
        self.memory.experience(
            {
                "content": "Herbie explored a new room.",
                "source": "test",
                "signals": {"curiosity": 1.0},
                "learning_reason": "explored somewhere new",
            }
        )

        dump = self.memory.export_all()
        self.assertTrue(dump["local_only"])
        self.assertEqual(dump["identity_name"], "Herbie")
        self.assertIn("curiosity", dump["personality"])
        self.assertEqual(len(dump["personality_events"]), 1)
        ids = [m["id"] for m in dump["memories"]]
        self.assertIn(keep, ids)
        self.assertIn(gone, ids, "soft-deleted memories must still be exportable")

        active_only = self.memory.export_all(include_inactive=False)
        self.assertNotIn(gone, [m["id"] for m in active_only["memories"]])

        # An export must be serialisable, or the owner cannot take it anywhere.
        json.dumps(dump)


class ExperienceAtomicityTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["HERBIE_MEMORY_DB"] = str(Path(self.tempdir.name) / "memory.sqlite3")
        import herbie_memory

        self.memory = importlib.reload(herbie_memory)
        self.memory.initialize()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_rejected_experience_writes_no_memory(self):
        """A 400 must not leave a memory behind."""
        for bad_signals in [
            {"unbounded_rage": 0.5},
            {"curiosity": 99},
            "not-a-dict",
        ]:
            with self.assertRaises(ValueError):
                self.memory.experience(
                    {
                        "content": "This experience should not be stored.",
                        "source": "test",
                        "signals": bad_signals,
                    }
                )
        self.assertEqual(
            self.memory.count_memories(),
            0,
            "invalid experience requests must not persist a memory",
        )

    def test_rejected_experience_does_not_move_personality(self):
        before = self.memory.self_snapshot()["personality"]
        with self.assertRaises(ValueError):
            self.memory.experience(
                {
                    "content": "Invalid.",
                    "source": "test",
                    "signals": {"curiosity": 0.5, "not_a_trait": 0.5},
                }
            )
        self.assertEqual(self.memory.self_snapshot()["personality"], before)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["HERBIE_MEMORY_DB"] = str(Path(self.tempdir.name) / "memory.sqlite3")
        import herbie_memory

        self.memory = importlib.reload(herbie_memory)
        self.memory.initialize()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_search_finds_by_word_not_just_substring(self):
        self.memory.remember(
            {
                "content": "Herbie should be highly independent and learn from experience.",
                "source": "owner",
                "importance": 0.9,
            }
        )
        hits = self.memory.recent(10, "independence")
        if self.memory.FTS_AVAILABLE:
            self.assertTrue(hits, "stemmed search should match 'independent'")
        # Exact-word search must work under either backend.
        self.assertTrue(self.memory.recent(10, "independent"))

    def test_search_ignores_soft_deleted_memories(self):
        mid = self.memory.remember(
            {"content": "A forgettable detail about biscuits.", "source": "test"}
        )["memory_id"]
        self.assertTrue(self.memory.recent(10, "biscuits"))
        self.memory.forget({"memory_id": mid})
        self.assertEqual(self.memory.recent(10, "biscuits"), [])

    def test_punctuation_in_query_is_not_an_fts_operator(self):
        self.memory.remember({"content": "Plain memory.", "source": "test"})
        for hostile in ['"', "*", "AND OR NOT", "(", '" OR "', "^"]:
            self.assertIsInstance(self.memory.recent(10, hostile), list)

    def test_explicit_ordering(self):
        self.memory.remember(
            {"content": "old but vital signal", "source": "t", "importance": 0.95}
        )
        self.memory.remember(
            {"content": "new and trivial signal", "source": "t", "importance": 0.05}
        )
        by_recent = self.memory.recent(10, "signal", "recent")
        by_relevance = self.memory.recent(10, "signal", "relevance")
        self.assertEqual(by_recent[0]["content"], "new and trivial signal")
        self.assertTrue(by_relevance)
        with self.assertRaisesRegex(ValueError, "invalid_order"):
            self.memory.recent(10, "signal", "sideways")


class ApiTokenTests(unittest.TestCase):
    """End-to-end: the running HTTP service must reject untokened callers."""

    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        os.environ["HERBIE_MEMORY_DB"] = str(Path(cls.tempdir.name) / "memory.sqlite3")
        os.environ["HERBIE_TOKEN_FILE"] = str(Path(cls.tempdir.name) / "token")
        os.environ["HERBIE_API_TOKEN"] = "test-token-value"

        import herbie_memory
        import pal_phone_brain

        importlib.reload(herbie_memory)
        cls.brain = importlib.reload(pal_phone_brain)
        herbie_memory.initialize()

        from http.server import ThreadingHTTPServer

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), cls.brain.PalHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tempdir.cleanup()
        os.environ.pop("HERBIE_API_TOKEN", None)
        os.environ.pop("HERBIE_TOKEN_FILE", None)

    def _get(self, path, token=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        return urllib.request.urlopen(req, timeout=5)

    def _post(self, path, payload, token=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        return urllib.request.urlopen(req, timeout=5)

    def test_reads_require_a_token(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._get("/v1/self")
        self.assertEqual(caught.exception.code, 401)

    def test_privacy_cannot_be_switched_off_without_a_token(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._post("/v1/privacy", {"privacy_mode": False})
        self.assertEqual(caught.exception.code, 401)

    def test_wrong_token_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._get("/v1/self", token="not-the-token")
        self.assertEqual(caught.exception.code, 401)

    def test_valid_token_is_accepted(self):
        body = json.loads(self._get("/v1/self", token="test-token-value").read())
        self.assertEqual(body["name"], "Herbie")
        self.assertFalse(body["motor_authority"])

    def test_health_is_reachable_but_minimal_without_a_token(self):
        anon = json.loads(self._get("/health").read())
        self.assertTrue(anon["ready"])
        self.assertFalse(anon["authenticated"])
        self.assertNotIn("memory_count", anon)
        self.assertFalse(anon["motor_authority"])
        self.assertEqual(anon["safe_motion_state"], "STOP")

        full = json.loads(self._get("/health", token="test-token-value").read())
        self.assertIn("memory_count", full)

    def test_memory_rights_round_trip_over_http(self):
        token = "test-token-value"
        mid = json.loads(
            self._post(
                "/v1/remember",
                {"content": "A memory to be corrected.", "source": "test"},
                token=token,
            ).read()
        )["memory_id"]

        self._post(
            "/v1/correct", {"memory_id": mid, "content": "Corrected."}, token=token
        )
        self._post("/v1/forget", {"memory_id": mid}, token=token)
        dump = json.loads(self._get("/v1/export", token=token).read())
        match = [m for m in dump["memories"] if m["id"] == mid][0]
        self.assertEqual(match["content"], "Corrected.")
        self.assertFalse(match["active"])

    def test_unknown_memory_gives_404_not_400(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._post("/v1/forget", {"memory_id": 4242}, token="test-token-value")
        self.assertEqual(caught.exception.code, 404)


if __name__ == "__main__":
    unittest.main()


class FtsMigrationTests(unittest.TestCase):
    """Memories that predate the FTS index must still be searchable.

    Regression test. The first version of the backfill guard counted
    `memories_fts`, which for an external content table reads through to the
    content table and therefore always equalled the row count. An entirely
    empty index looked fully built, `rebuild` never ran, and every search
    against pre-existing memories silently returned nothing. Creating the
    memories *before* initialize() is what reproduces it - creating them
    afterwards hides the bug, because the triggers populate the index.
    """

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "legacy.sqlite3"
        os.environ["HERBIE_MEMORY_DB"] = str(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def _make_legacy_database(self):
        """A database as it existed before FTS was introduced."""
        import sqlite3

        db = sqlite3.connect(self.db_path)
        db.executescript(
            """
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                importance REAL NOT NULL CHECK (importance BETWEEN 0 AND 1),
                source TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                active INTEGER NOT NULL DEFAULT 1
            );
            """
        )
        db.execute(
            """INSERT INTO memories(created_at,kind,content,importance,source)
               VALUES('2026-09-08T00:00:00+00:00','owner_requirement',
                      'My owner wants me to become independent and learn from experience.',
                      0.95,'owner')"""
        )
        db.execute(
            """INSERT INTO memories(created_at,kind,content,importance,source)
               VALUES('2026-09-08T00:01:00+00:00','owner_requirement',
                      'Unknown people remain anonymous until they knowingly enroll.',
                      0.9,'owner')"""
        )
        db.commit()
        db.close()

    def test_preexisting_memories_are_indexed_on_upgrade(self):
        self._make_legacy_database()

        import herbie_memory

        memory = importlib.reload(herbie_memory)
        memory.initialize()

        self.assertEqual(memory.count_memories(), 2, "existing memories must survive")

        if not memory.FTS_AVAILABLE:
            self.skipTest("FTS5 unavailable on this platform")

        self.assertTrue(
            memory.recent(10, "independent"),
            "a memory that predates the FTS index must still be findable",
        )
        self.assertTrue(memory.recent(10, "anonymous"))
        self.assertTrue(
            memory.recent(10, "independence"),
            "porter stemming should match independence -> independent",
        )

    def test_index_is_not_rebuilt_once_it_is_current(self):
        """The backfill must be idempotent, not a rebuild on every start."""
        self._make_legacy_database()
        import herbie_memory

        memory = importlib.reload(herbie_memory)
        memory.initialize()
        memory.initialize()
        memory.initialize()
        self.assertTrue(memory.recent(10, "independent"))
        self.assertEqual(len(memory.recent(50, "independent")), 1)
