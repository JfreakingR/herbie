"""Shapeshifting requests: which messages change Herbie's on-screen form."""

import unittest

import herbie_form as form


class RequestedTests(unittest.TestCase):
    def test_asks_for_each_form(self):
        self.assertEqual(form.requested("Herbie, turn into the moon"), "moon")
        self.assertEqual(form.requested("can you become the sun?"), "sun")
        self.assertEqual(form.requested("Transform into a football!"), "football")
        self.assertEqual(form.requested("change to just your face"), "face")
        self.assertEqual(form.requested("okay, turn back to normal"), "spirit")

    def test_mentions_without_asking_change_nothing(self):
        self.assertIsNone(form.requested("The moon was bright last night"))
        self.assertIsNone(form.requested("Did you watch the football game?"))
        self.assertIsNone(form.requested("turn the music down"))


class FormStateTests(unittest.TestCase):
    def test_starts_as_spirit_and_remembers_changes(self):
        state = form.FormState()
        self.assertEqual(state.current, "spirit")
        state.set("sun")
        self.assertEqual(state.current, "sun")

    def test_unknown_form_is_refused(self):
        with self.assertRaisesRegex(ValueError, "invalid_form"):
            form.FormState().set("dragon")

    def test_context_line_names_the_form(self):
        self.assertIn("the moon", form.context_line("moon"))
        self.assertIn("eyes and mouth", form.context_line("face"))
        self.assertIn("spirit", form.context_line("spirit"))


class FaceTests(unittest.TestCase):
    def test_asking_for_a_face(self):
        self.assertEqual(form.requested_expression("Herbie, make an angry face"), "angry")
        self.assertEqual(form.requested_expression("can you look happy?"), "happy")
        self.assertEqual(form.requested_expression("show me a sad face"), "concerned")
        self.assertIsNone(form.requested_expression("I'm happy today"))
        self.assertIsNone(form.requested_expression("look behind you"))

    def test_face_tags_are_removed_and_read(self):
        self.assertEqual(form.extract_face("Grr! [face angry] Happy now?"), ("Grr! Happy now?", "angry"))
        self.assertEqual(form.extract_face("[FACE Surprised] Oh!"), ("Oh!", "surprised"))
        self.assertEqual(form.extract_face("Hello there"), ("Hello there", None))
        self.assertEqual(form.extract_face("Hmm [face banana]")[1], None)

    def test_face_counts_as_connected_only_while_it_checks_in(self):
        now = [100.0]
        watch = form.FaceWatch(clock=lambda: now[0])
        self.assertFalse(watch.connected())
        watch.seen()
        self.assertTrue(watch.connected())
        now[0] += form.FACE_TIMEOUT_SECONDS + 1
        self.assertFalse(watch.connected())


if __name__ == "__main__":
    unittest.main()
