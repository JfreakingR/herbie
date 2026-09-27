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


if __name__ == "__main__":
    unittest.main()
