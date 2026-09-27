"""The phone's side of driving: tag parsing, stop, and one move per claim."""

import unittest

import herbie_drive as drive


class ExtractDriveTests(unittest.TestCase):
    def test_tags_are_removed_and_moves_returned_in_order(self):
        text, moves = drive.extract_drive("Coming! [drive left 0.5] [drive forward 2]")
        self.assertEqual(text, "Coming!")
        self.assertEqual(moves, [{"direction": "left", "ms": 500},
                                 {"direction": "forward", "ms": 2000}])

    def test_no_tag_leaves_text_alone(self):
        self.assertEqual(drive.extract_drive("I'd rather not [laughs]"),
                         ("I'd rather not [laughs]", []))

    def test_defaults_clamps_and_spellings(self):
        _, moves = drive.extract_drive("[DRIVE Back] [drive forwards 9 seconds] [drive right 0.05s]")
        self.assertEqual(moves, [{"direction": "backward", "ms": 1000},
                                 {"direction": "forward", "ms": 2000},
                                 {"direction": "right", "ms": 200}])

    def test_at_most_three_moves(self):
        text, moves = drive.extract_drive("[drive left] " * 5 + "wheee")
        self.assertEqual(len(moves), drive.MAX_MOVES)
        self.assertEqual(text, "wheee")

    def test_stop_words(self):
        for message in ("Stop!", "herbie halt", "whoa whoa", "don't move", "freeze"):
            self.assertTrue(drive.says_stop(message), message)
        self.assertFalse(drive.says_stop("drive forward a bit"))


class DriveStateTests(unittest.TestCase):
    def test_no_controller_means_no_driving(self):
        self.assertFalse(drive.DriveState().available(now=0))

    def test_moves_are_handed_out_one_per_claim(self):
        state = drive.DriveState()
        state.request([{"direction": "left", "ms": 500},
                       {"direction": "forward", "ms": 1000}], now=0)
        self.assertEqual(state.claim(now=1)["direction"], "left")
        self.assertIsNone(state.claim(busy=True, now=2))
        second = state.claim(now=3)
        self.assertEqual((second["direction"], second["ms"], second["step"]), ("forward", 1000, 2))
        self.assertIsNone(state.claim(now=4))
        self.assertTrue(state.available(now=4))

    def test_stop_drops_what_has_not_started(self):
        state = drive.DriveState()
        state.request([{"direction": "left", "ms": 500}] * 3, now=0)
        state.claim(now=1)
        self.assertEqual(state.stop(), 2)
        self.assertIsNone(state.claim(now=2))

    def test_stale_moves_are_dropped(self):
        state = drive.DriveState()
        state.request([{"direction": "forward", "ms": 500}], now=0)
        self.assertIsNone(state.claim(now=1 + drive.REQUEST_TTL_S))

    def test_newer_reply_replaces_older_moves(self):
        state = drive.DriveState()
        state.request([{"direction": "forward", "ms": 500}] * 2, now=0)
        state.request([{"direction": "backward", "ms": 300}], now=1)
        self.assertEqual(state.claim(now=2)["direction"], "backward")
        self.assertIsNone(state.claim(now=3))

    def test_bad_requests_are_rejected(self):
        state = drive.DriveState()
        for moves in ([], [{"direction": "up", "ms": 500}],
                      [{"direction": "left", "ms": 5000}],
                      [{"direction": "left", "ms": True}],
                      [{"direction": "left", "ms": 500}] * 4):
            with self.assertRaisesRegex(ValueError, "invalid_moves"):
                state.request(moves)
        with self.assertRaisesRegex(ValueError, "invalid_busy"):
            state.claim(busy="no")


if __name__ == "__main__":
    unittest.main()
