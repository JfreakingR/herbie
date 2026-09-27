"""The phone's side of Herbie's neck: tag parsing and the pending-look queue."""

import unittest

import herbie_neck as neck


class ExtractLookTests(unittest.TestCase):
    def test_tag_is_removed_and_angle_returned(self):
        self.assertEqual(neck.extract_look("Let me see. [look 90]"), ("Let me see.", 90))

    def test_no_tag_leaves_text_alone(self):
        self.assertEqual(neck.extract_look("Hi [laughs] there"), ("Hi [laughs] there", None))

    def test_variants_and_last_one_wins(self):
        text, look = neck.extract_look("[LOOK 45°] hmm [look 180 degrees], behind you?")
        self.assertEqual(look, 180)
        self.assertEqual(text, "hmm, behind you?")

    def test_angles_wrap_into_a_turn(self):
        self.assertEqual(neck.extract_look("[look 450]")[1], 90)
        self.assertEqual(neck.extract_look("[look -90]")[1], 270)
        self.assertEqual(neck.extract_look("[look 0]"), ("", 0))


class NeckStateTests(unittest.TestCase):
    def test_no_controller_means_no_neck(self):
        state = neck.NeckState()
        self.assertFalse(state.available(now=0))
        self.assertIsNone(state.context_line(now=0))

    def test_checkin_makes_it_available_until_it_goes_quiet(self):
        state = neck.NeckState()
        state.claim(facing=0, now=100)
        self.assertTrue(state.available(now=100 + neck.CONTROLLER_TIMEOUT_S))
        self.assertFalse(state.available(now=101 + neck.CONTROLLER_TIMEOUT_S))
        self.assertEqual(state.context_line(now=100), "Your head is facing straight ahead.")

    def test_request_is_claimed_once(self):
        state = neck.NeckState()
        request_id = state.request(90, now=0)
        claimed = state.claim(facing=0, now=1)
        self.assertEqual(claimed, {"id": request_id, "degrees": 90})
        self.assertIsNone(state.claim(facing=0, now=2))

    def test_busy_controller_leaves_the_request_waiting(self):
        state = neck.NeckState()
        state.request(90, now=0)
        self.assertIsNone(state.claim(facing=45, busy=True, now=1))
        self.assertIn("turning right now", state.context_line(now=1))
        self.assertEqual(state.claim(facing=90, now=2)["degrees"], 90)

    def test_newer_request_replaces_older_and_stale_ones_expire(self):
        state = neck.NeckState()
        state.request(90, now=0)
        state.request(180, now=1)
        self.assertEqual(state.claim(now=2)["degrees"], 180)
        state.request(270, now=10)
        self.assertIsNone(state.claim(now=11 + neck.REQUEST_TTL_S))

    def test_bad_checkins_are_rejected(self):
        state = neck.NeckState()
        for facing in (-1, 360, "90", True):
            with self.assertRaisesRegex(ValueError, "invalid_facing"):
                state.claim(facing=facing)
        with self.assertRaisesRegex(ValueError, "invalid_busy"):
            state.claim(busy="yes")
        with self.assertRaisesRegex(ValueError, "invalid_degrees"):
            state.request("90")

    def test_skill_keeps_the_wheels_off(self):
        self.assertIn("wheels stay off", neck.NECK_SKILL)
        self.assertIn("[look N]", neck.NECK_SKILL)


if __name__ == "__main__":
    unittest.main()
