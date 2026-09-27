import unittest

import herbie_face


class HerbieFaceTests(unittest.TestCase):
    def test_default_identity_is_herbie(self):
        svg = herbie_face.render_svg(herbie_face.DEFAULT_STATE)
        self.assertIn("Herbie", svg)
        self.assertIn("curious", svg)
        self.assertIn("<svg", svg)

    def test_each_expression_renders(self):
        for expression in sorted(herbie_face.EXPRESSIONS):
            state = herbie_face.merge_expression(
                herbie_face.DEFAULT_STATE, {"expression": expression}
            )
            svg = herbie_face.render_svg(state)
            self.assertIn(expression, svg)
            self.assertIn("viewBox", svg)

    def test_privacy_and_listening_indicators(self):
        listening = herbie_face.merge_expression(
            herbie_face.DEFAULT_STATE, {"listening": True, "expression": "curious"}
        )
        svg = herbie_face.render_svg(listening)
        self.assertIn("MIC", svg)
        self.assertIn("#5aa7c8", svg)
        privacy = herbie_face.set_privacy(listening, {"privacy_mode": True})
        self.assertTrue(privacy["privacy_mode"])
        self.assertFalse(privacy["listening"])
        self.assertEqual(privacy["expression"], "calm")
        private_svg = herbie_face.render_svg(privacy)
        self.assertIn("PRIV", private_svg)
        self.assertIn("privacy", private_svg)

    def test_privacy_blocks_camera_and_mic(self):
        private = herbie_face.set_privacy(herbie_face.DEFAULT_STATE, {"privacy_mode": True})
        with self.assertRaisesRegex(ValueError, "privacy_blocks_senses"):
            herbie_face.merge_expression(private, {"listening": True})
        with self.assertRaisesRegex(ValueError, "privacy_blocks_senses"):
            herbie_face.merge_expression(private, {"camera_active": True})

    def test_invalid_expression_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_expression"):
            herbie_face.merge_expression(
                herbie_face.DEFAULT_STATE, {"expression": "unbounded-rage"}
            )


if __name__ == "__main__":
    unittest.main()
