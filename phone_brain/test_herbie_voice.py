"""Tests for Herbie's voice shaping.

No speaker required: the prosody, latency and imperfection functions are pure
and take an injectable RNG, so the behaviour that makes the voice sound alive
can be asserted directly.
"""

import importlib
import os
import random
import tempfile
import unittest
from pathlib import Path


class VoiceTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["HERBIE_MEMORY_DB"] = str(Path(self.tempdir.name) / "memory.sqlite3")
        import herbie_memory

        self.memory = importlib.reload(herbie_memory)
        self.memory.initialize()
        import herbie_voice

        self.voice = importlib.reload(herbie_voice)

    def tearDown(self):
        self.tempdir.cleanup()


class ProsodyTests(VoiceTestCase):
    def test_low_mood_speaks_lower_than_high_mood(self):
        rng = random.Random(1)
        sad = self.voice.voice_params(valence=-0.9, arousal=0.5, rng=rng)
        rng = random.Random(1)
        glad = self.voice.voice_params(valence=0.9, arousal=0.5, rng=rng)
        self.assertLess(sad["pitch"], glad["pitch"])

    def test_high_arousal_speaks_faster(self):
        rng = random.Random(2)
        sleepy = self.voice.voice_params(valence=0.0, arousal=0.05, rng=rng)
        rng = random.Random(2)
        alert = self.voice.voice_params(valence=0.0, arousal=0.95, rng=rng)
        self.assertLess(sleepy["rate"], alert["rate"])

    def test_calm_pauses_longer_before_answering(self):
        rng = random.Random(3)
        calm = self.voice.voice_params(valence=0.0, arousal=0.05, rng=rng)
        rng = random.Random(3)
        alert = self.voice.voice_params(valence=0.0, arousal=0.95, rng=rng)
        self.assertGreater(calm["latency_seconds"], alert["latency_seconds"])

    def test_no_two_utterances_are_acoustically_identical(self):
        """Jitter is what separates a voice from a recording."""
        seen = {
            (
                self.voice.voice_params(valence=0.2, arousal=0.5)["pitch"],
                self.voice.voice_params(valence=0.2, arousal=0.5)["rate"],
            )
            for _ in range(30)
        }
        self.assertGreater(len(seen), 10, "prosody should vary between utterances")

    def test_parameters_stay_within_engine_bounds(self):
        for valence in (-1.0, -0.4, 0.0, 0.4, 1.0):
            for arousal in (0.0, 0.25, 0.5, 0.75, 1.0):
                for _ in range(12):
                    p = self.voice.voice_params(valence=valence, arousal=arousal)
                    self.assertGreaterEqual(p["pitch"], self.voice.PITCH_RANGE[0])
                    self.assertLessEqual(p["pitch"], self.voice.PITCH_RANGE[1])
                    self.assertGreaterEqual(p["rate"], self.voice.RATE_RANGE[0])
                    self.assertLessEqual(p["rate"], self.voice.RATE_RANGE[1])
                    self.assertGreater(p["latency_seconds"], 0)
                    self.assertLess(p["latency_seconds"], 2.0)

    def test_mood_is_read_from_live_state_when_not_supplied(self):
        self.memory.set_affect(-0.85, 0.1)
        low = self.voice.voice_params()
        self.memory.set_affect(0.85, 0.9)
        high = self.voice.voice_params()
        self.assertLess(low["pitch"], high["pitch"])
        self.assertLess(low["rate"], high["rate"])


class ImperfectionTests(VoiceTestCase):
    def test_imperfection_is_rare(self):
        rng = random.Random(7)
        text = "The kettle has boiled."
        changed = sum(
            1 for _ in range(400)
            if self.voice.add_imperfection(text, 0.5, rng) != text
        )
        # Rare enough not to grate, common enough to notice.
        self.assertGreater(changed, 20)
        self.assertLess(changed, 140)

    def test_the_actual_message_is_never_lost(self):
        rng = random.Random(11)
        text = "Your toast is burning"
        for _ in range(200):
            out = self.voice.add_imperfection(text, 0.5, rng)
            self.assertIn("toast is burning", out)

    def test_hesitation_belongs_to_low_arousal(self):
        rng = random.Random(5)
        drowsy = [
            self.voice.add_imperfection("Fine.", 0.05, rng) for _ in range(400)
        ]
        rng = random.Random(5)
        alert = [
            self.voice.add_imperfection("Fine.", 0.95, rng) for _ in range(400)
        ]
        drowsy_openers = sum(
            1 for line in drowsy if any(line.startswith(o) for o in self.voice.OPENERS)
        )
        alert_openers = sum(
            1 for line in alert if any(line.startswith(o) for o in self.voice.OPENERS)
        )
        self.assertGreater(drowsy_openers, alert_openers)
        self.assertEqual(alert_openers, 0, "alert speech should not hesitate")


class SpeakContractTests(VoiceTestCase):
    def test_speech_is_validated_before_anything_happens(self):
        for bad in [None, "", "   ", 42, "x" * 1001]:
            with self.assertRaises(ValueError):
                self.voice.speak({"text": bad})

    def test_invalid_expression_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_expression"):
            self.voice.speak({"text": "hello", "expression": "unbounded-rage"})

    def test_invalid_prosody_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_pitch"):
            self.voice.speak({"text": "hello", "pitch": 9})
        with self.assertRaisesRegex(ValueError, "invalid_rate"):
            self.voice.speak({"text": "hello", "rate": 0.1})
        with self.assertRaisesRegex(ValueError, "invalid_natural"):
            self.voice.speak({"text": "hello", "natural": "yes"})

    def test_missing_engine_is_reported_clearly(self):
        """A missing TTS engine must fail loudly, not silently.

        The engine is stubbed out rather than assumed absent: on the phone it
        genuinely exists, so the original version of this test passed on the
        workstation, failed on the device, and made Herbie say "hello" out loud
        during the test run.
        """
        import shutil

        original = shutil.which
        shutil.which = lambda name: None
        try:
            with self.assertRaisesRegex(RuntimeError, "tts_unavailable"):
                self.voice.speak({"text": "hello"})
        finally:
            shutil.which = original

    def test_validation_happens_before_the_engine_is_touched(self):
        """Bad input must be rejected without ever reaching the speaker."""
        import shutil

        calls = []
        original = shutil.which

        def spy(name):
            calls.append(name)
            return original(name)

        shutil.which = spy
        try:
            with self.assertRaises(ValueError):
                self.voice.speak({"text": ""})
            with self.assertRaises(ValueError):
                self.voice.speak({"text": "hi", "expression": "nonsense"})
        finally:
            shutil.which = original
        self.assertEqual(calls, [], "invalid input reached the TTS engine")

    def test_stop_is_safe_when_nothing_is_speaking(self):
        result = self.voice.stop()
        self.assertFalse(result["stopped"])
        self.assertFalse(result["motor_authority"])
        self.assertEqual(result["safe_motion_state"], "STOP")
        self.assertFalse(self.memory.expression_snapshot()["speaking"])


# Cost and locality are now asserted project-wide in test_herbie_is_free.py,
# which scans every module rather than this one file.


if __name__ == "__main__":
    unittest.main()
