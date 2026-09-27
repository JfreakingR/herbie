"""Tests for Herbie's autonomic layer.

Time is injected everywhere, so these assert real behaviour over hours without
waiting for hours, and without depending on what time the suite happens to run.
"""

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


def at(hour, minute=0, day=9):
    """A local-time moment, converted to aware UTC."""
    naive = datetime(2026, 9, day, hour, minute)
    return naive.astimezone()


class AutonomicTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["HERBIE_MEMORY_DB"] = str(Path(self.tempdir.name) / "memory.sqlite3")
        import herbie_memory

        self.memory = importlib.reload(herbie_memory)
        self.memory.initialize()
        import herbie_autonomic

        self.auto = importlib.reload(herbie_autonomic)

    def tearDown(self):
        self.tempdir.cleanup()

    def _seed(self, when):
        self.memory.autonomic_update(
            last_tick_at=when.isoformat(timespec="seconds"),
            last_interaction_at=when.isoformat(timespec="seconds"),
            last_initiative_at=None,
        )


class DriftTests(AutonomicTestCase):
    def test_drives_build_with_no_input_at_all(self):
        """The core of the illusion: something changes while nothing happens."""
        start = at(12)
        self._seed(start)
        before = self.memory.drives_snapshot()

        self.auto.tick(start + timedelta(minutes=45))
        after = self.memory.drives_snapshot()

        self.assertGreater(after["connect"], before["connect"])
        self.assertGreater(after["explore"], before["explore"])
        self.assertGreater(
            after["connect"] - before["connect"],
            after["explore"] - before["explore"],
            "loneliness should build faster than boredom",
        )

    def test_interaction_discharges_loneliness(self):
        start = at(12)
        self._seed(start)
        self.auto.tick(start + timedelta(hours=2))
        lonely = self.memory.drives_snapshot()["connect"]

        self.auto.note_interaction(start + timedelta(hours=2))
        after = self.memory.drives_snapshot()["connect"]

        self.assertLess(after, lonely)
        self.assertGreater(after, 0.0)

    def test_a_long_gap_does_not_slam_every_drive(self):
        """A restart after days away must not produce a maximally frantic robot."""
        start = at(12)
        self._seed(start)
        self.auto.tick(start + timedelta(days=5))
        drives = self.memory.drives_snapshot()
        self.assertLess(
            drives["connect"], 0.95, "elapsed time must be capped, not accumulated"
        )

    def test_drives_stay_within_bounds(self):
        start = at(12)
        self._seed(start)
        now = start
        for _ in range(60):
            now += timedelta(minutes=30)
            self.auto.tick(now)
        for name, value in self.memory.drives_snapshot().items():
            self.assertGreaterEqual(value, 0.0, name)
            self.assertLessEqual(value, 1.0, name)


class CircadianTests(AutonomicTestCase):
    def test_night_is_low_energy_and_afternoon_is_high(self):
        night = self.auto.circadian_energy(at(4))
        afternoon = self.auto.circadian_energy(at(16))
        self.assertLess(night, 0.2)
        self.assertGreater(afternoon, 0.8)
        self.assertGreater(afternoon, night)

    def test_energy_is_bounded(self):
        for hour in range(24):
            energy = self.auto.circadian_energy(at(hour))
            self.assertGreaterEqual(energy, 0.0)
            self.assertLessEqual(energy, 1.0)

    def test_arousal_follows_the_clock(self):
        """Late at night Herbie should wind down without being told to."""
        start = at(2)
        self._seed(start)
        self.memory.set_affect(0.3, 0.9)
        self.auto.tick(start + timedelta(minutes=30))
        self.assertLess(self.memory.expression_snapshot()["arousal"], 0.6)

    def test_mood_has_inertia(self):
        """Valence must move slower than arousal, or moods feel like switches."""
        start = at(12)
        self._seed(start)
        self.memory.set_affect(-0.9, 0.95)
        before = self.memory.expression_snapshot()

        self.auto.tick(start + timedelta(minutes=2))
        after = self.memory.expression_snapshot()

        arousal_moved = abs(after["arousal"] - before["arousal"])
        valence_moved = abs(after["valence"] - before["valence"])
        self.assertGreater(arousal_moved, valence_moved)
        self.assertGreater(after["valence"], before["valence"], "should recover, slowly")


class InitiativeTests(AutonomicTestCase):
    def _raise_connect(self):
        """Push loneliness over threshold WITHOUT touching initiative history."""
        drives = self.memory.drives_snapshot()
        drives["connect"] = 0.93
        self.memory.set_drives(drives)

    def _make_lonely(self, start):
        self._seed(start)
        self._raise_connect()

    def test_an_unmet_drive_produces_an_urge(self):
        start = at(14)
        self._make_lonely(start)
        result = self.auto.tick(start + timedelta(seconds=30))
        self.assertEqual(result["urge"], "connect")

    def test_taking_an_urge_yields_words_and_a_face_but_no_movement(self):
        start = at(14)
        self._make_lonely(start)
        self.auto.tick(start + timedelta(seconds=30))

        urge = self.auto.take_urge(start + timedelta(seconds=31))
        self.assertIsNotNone(urge)
        self.assertEqual(urge["urge"], "connect")
        self.assertTrue(urge["spontaneous"])
        self.assertIn(urge["expression"], self.memory.EXPRESSIONS)
        self.assertTrue(urge["text"].strip())
        self.assertFalse(urge["motor_authority"])
        self.assertEqual(urge["safe_motion_state"], "STOP")
        self.assertNotIn("motion", urge)

        # Claimed urges do not linger.
        self.assertIsNone(self.auto.take_urge(start + timedelta(seconds=32)))

    def test_initiative_is_rate_limited(self):
        """Herbie should have impulses, not deliver a monologue."""
        start = at(14)
        self._make_lonely(start)
        self.auto.tick(start + timedelta(seconds=30))
        self.auto.take_urge(start + timedelta(seconds=31))

        # Still lonely, but the urge was only just voiced.
        self._raise_connect()
        soon = self.auto.tick(start + timedelta(seconds=60))
        self.assertIsNone(soon["urge"], "a second urge one minute later is too soon")

        # One urge has gone unanswered, so the gap is now widened by backoff.
        gap = self.auto.MIN_SECONDS_BETWEEN_URGES * self.auto.URGE_BACKOFF_FACTOR
        self._raise_connect()
        later = self.auto.tick(start + timedelta(seconds=gap + 120))
        self.assertEqual(later["urge"], "connect")

    def test_being_ignored_makes_him_quieter_not_more_insistent(self):
        """Habituation: unanswered impulses back off instead of escalating."""
        start = at(14)
        self._make_lonely(start)
        now = start

        gaps = []
        for _ in range(4):
            self._raise_connect()
            # Advance far enough that only backoff can hold him back.
            for _ in range(40):
                now += timedelta(minutes=15)
                result = self.auto.tick(now)
                if result.get("urge"):
                    break
            taken = self.auto.take_urge(now)
            self.assertIsNotNone(taken, "should eventually speak")
            gaps.append(now)

        intervals = [
            (gaps[i + 1] - gaps[i]).total_seconds() for i in range(len(gaps) - 1)
        ]
        self.assertTrue(
            all(intervals[i] <= intervals[i + 1] for i in range(len(intervals) - 1)),
            f"silences should lengthen while ignored, got {intervals}",
        )

    def test_answering_him_resets_the_backoff(self):
        start = at(14)
        self._make_lonely(start)
        self.auto.tick(start + timedelta(seconds=30))
        self.auto.take_urge(start + timedelta(seconds=31))
        self.assertEqual(self.memory.autonomic_snapshot()["unanswered_urges"], 1)

        self.auto.note_interaction(start + timedelta(seconds=40))
        self.assertEqual(self.memory.autonomic_snapshot()["unanswered_urges"], 0)

    def test_he_does_not_repeat_the_same_line_twice_running(self):
        start = at(14)
        now = start
        said = []
        for _ in range(4):
            self._seed(now)
            self._raise_connect()
            self.auto.tick(now + timedelta(seconds=30))
            taken = self.auto.take_urge(now + timedelta(seconds=31))
            if taken and taken["text"]:
                said.append(taken["text"])
            now += timedelta(hours=1)
        for i in range(len(said) - 1):
            self.assertNotEqual(said[i], said[i + 1], "immediate repeat breaks the spell")
    def test_privacy_mode_silences_initiative(self):
        """Someone who asked for privacy does not want unprompted remarks."""
        start = at(14)
        self._make_lonely(start)
        self.memory.set_privacy({"privacy_mode": True})

        result = self.auto.tick(start + timedelta(seconds=30))
        self.assertIsNone(result["urge"])
        self.assertIsNone(self.auto.take_urge(start + timedelta(seconds=31)))

    def test_urges_stop_when_the_autonomic_layer_is_disabled(self):
        start = at(14)
        self._make_lonely(start)
        self.memory.autonomic_update(enabled=False)
        result = self.auto.tick(start + timedelta(seconds=30))
        self.assertFalse(result["ticked"])
        self.assertEqual(result["reason"], "disabled")




class NightTests(AutonomicTestCase):
    def _raise_connect(self):
        drives = self.memory.drives_snapshot()
        drives["connect"] = 0.95
        self.memory.set_drives(drives)

    def test_he_does_not_call_out_in_the_middle_of_the_night(self):
        """A device that pipes up at 03:00 to say it is lonely is a nuisance."""
        start = at(3)
        self._seed(start)
        self._raise_connect()
        result = self.auto.tick(start + timedelta(seconds=30))
        self.assertNotEqual(
            result["urge"], "connect", "loneliness must not wake the house"
        )

    def test_night_urges_are_silent_and_only_about_tiredness(self):
        start = at(3)
        self._seed(start)
        drives = self.memory.drives_snapshot()
        drives["rest"] = 0.95
        drives["connect"] = 0.95
        self.memory.set_drives(drives)

        result = self.auto.tick(start + timedelta(seconds=30))
        self.assertEqual(result["urge"], "rest")

        taken = self.auto.take_urge(start + timedelta(seconds=31))
        self.assertTrue(taken["silent"])
        self.assertEqual(taken["text"], "", "the face changes, nothing is said aloud")
        self.assertEqual(taken["expression"], "sleepy")

    def test_mood_reports_asleep_at_night_and_awake_by_day(self):
        self._seed(at(3))
        self.assertTrue(self.auto.mood_snapshot(at(3))["asleep"])
        self.assertFalse(self.auto.mood_snapshot(at(15))["asleep"])


class MoodVariationTests(AutonomicTestCase):
    def test_prolonged_loneliness_lowers_the_mood(self):
        """Valence must actually move across a day, not sit on one number."""
        start = at(10)
        self._seed(start)
        now = start
        for _ in range(16):
            now += timedelta(minutes=30)
            self.auto.tick(now)
        lonely_valence = self.memory.expression_snapshot()["valence"]

        self.auto.note_interaction(now)
        for _ in range(16):
            now += timedelta(minutes=5)
            self.auto.tick(now)
        after_company = self.memory.expression_snapshot()["valence"]

        self.assertGreater(
            after_company, lonely_valence, "company should lift the mood"
        )

    def test_drives_saturate_smoothly_rather_than_pinning(self):
        start = at(10)
        self._seed(start)
        now = start
        for _ in range(12):
            now += timedelta(minutes=30)
            self.auto.tick(now)
        first = self.memory.drives_snapshot()["connect"]
        for _ in range(12):
            now += timedelta(minutes=30)
            self.auto.tick(now)
        second = self.memory.drives_snapshot()["connect"]

        self.assertGreater(second, first)
        self.assertLess(
            second - first,
            first - 0.55,
            "growth should slow as the drive saturates",
        )

class MoodReportTests(AutonomicTestCase):
    def test_mood_snapshot_reports_state_and_safety(self):
        start = at(15)
        self._seed(start)
        self.auto.tick(start + timedelta(minutes=10))

        mood = self.auto.mood_snapshot(start + timedelta(minutes=10))
        self.assertIn("circadian_energy", mood)
        self.assertIn("drives", mood)
        self.assertIn("seconds_since_interaction", mood)
        self.assertFalse(mood["motor_authority"])
        self.assertEqual(mood["safe_motion_state"], "STOP")
        self.assertTrue(mood["autonomic_enabled"])


class SafetyTests(AutonomicTestCase):
    def test_no_urge_type_corresponds_to_movement(self):
        """The autonomic layer must have no vocabulary for motion."""
        forbidden = {"move", "drive", "roll", "turn", "motor", "wheel", "laser", "treat"}
        self.assertFalse(set(self.auto.URGE_THRESHOLDS) & forbidden)
        self.assertFalse(set(self.auto.URGE_LINES) & forbidden)
        self.assertFalse(set(self.auto.URGE_EXPRESSION) & forbidden)

    def test_every_urge_maps_to_a_valid_expression_and_line(self):
        for urge in self.auto.URGE_THRESHOLDS:
            self.assertIn(urge, self.auto.URGE_EXPRESSION)
            self.assertIn(self.auto.URGE_EXPRESSION[urge], self.memory.EXPRESSIONS)
            self.assertTrue(self.auto.URGE_LINES.get(urge))

    def test_a_failing_tick_does_not_kill_the_loop(self):
        loop = self.auto.AutonomicLoop(interval=0.01)
        original = self.auto.tick
        calls = []

        def exploding(now=None):
            calls.append(1)
            raise RuntimeError("boom")

        self.auto.tick = exploding
        try:
            loop.start()
            deadline = datetime.now(timezone.utc) + timedelta(seconds=1)
            while len(calls) < 3 and datetime.now(timezone.utc) < deadline:
                pass
            loop.stop()
        finally:
            self.auto.tick = original

        self.assertGreaterEqual(len(calls), 2, "loop should survive a raising tick")
        self.assertIn("boom", loop.last_error or "")


if __name__ == "__main__":
    unittest.main()
