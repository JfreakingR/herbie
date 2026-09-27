"""Both face renderers must satisfy the same contract.

herbie_face3d is a drop-in restyle of herbie_face, so anything that consumes a
face — the Pi renderer, a future screen driver — must be able to swap them
without noticing. These tests run the identical checks against both, so a
styling change cannot quietly drop a consent indicator.
"""

import re
import unittest

import herbie_face
import herbie_face3d

RENDERERS = [("herbie_face", herbie_face), ("herbie_face3d", herbie_face3d)]


class FaceContractTests(unittest.TestCase):
    def test_every_expression_renders_valid_svg(self):
        for name, renderer in RENDERERS:
            for expression in sorted(renderer.EXPRESSIONS):
                with self.subTest(renderer=name, expression=expression):
                    state = renderer.merge_expression(
                        renderer.DEFAULT_STATE, {"expression": expression}
                    )
                    svg = renderer.render_svg(state)
                    self.assertTrue(svg.lstrip().startswith("<svg"))
                    self.assertIn("viewBox", svg)
                    self.assertTrue(svg.rstrip().endswith("</svg>"))
                    # Roughly balanced tags: catches truncated output.
                    self.assertEqual(svg.count("<svg"), 1)

    def test_identity_is_present_for_screen_readers(self):
        for name, renderer in RENDERERS:
            with self.subTest(renderer=name):
                svg = renderer.render_svg(renderer.DEFAULT_STATE)
                self.assertIn(renderer.IDENTITY_NAME, svg)

    def test_invalid_expression_is_rejected(self):
        for name, renderer in RENDERERS:
            with self.subTest(renderer=name):
                with self.assertRaisesRegex(ValueError, "invalid_expression"):
                    renderer.render_svg({**renderer.DEFAULT_STATE,
                                         "expression": "unbounded-rage"})

    def test_listening_is_always_visible(self):
        """The mic indicator is a consent signal; a restyle must not lose it."""
        for name, renderer in RENDERERS:
            with self.subTest(renderer=name):
                state = renderer.merge_expression(
                    renderer.DEFAULT_STATE,
                    {"listening": True, "expression": "curious"},
                )
                svg = renderer.render_svg(state)
                self.assertIn("MIC", svg)

    def test_privacy_is_always_visible(self):
        for name, renderer in RENDERERS:
            with self.subTest(renderer=name):
                private = renderer.set_privacy(
                    renderer.DEFAULT_STATE, {"privacy_mode": True}
                )
                svg = renderer.render_svg(private)
                self.assertIn("PRIV", svg)
                self.assertTrue(private["privacy_mode"])
                self.assertFalse(private["listening"])

    def test_privacy_still_blocks_senses_in_both(self):
        for name, renderer in RENDERERS:
            with self.subTest(renderer=name):
                private = renderer.set_privacy(
                    renderer.DEFAULT_STATE, {"privacy_mode": True}
                )
                with self.assertRaisesRegex(ValueError, "privacy_blocks_senses"):
                    renderer.merge_expression(private, {"listening": True})
                with self.assertRaisesRegex(ValueError, "privacy_blocks_senses"):
                    renderer.merge_expression(private, {"camera_active": True})

    def test_mood_changes_the_rendering(self):
        """Valence and arousal must actually reach the pixels."""
        for name, renderer in RENDERERS:
            with self.subTest(renderer=name):
                low = renderer.render_svg(
                    {**renderer.DEFAULT_STATE, "valence": -0.9, "arousal": 0.1}
                )
                high = renderer.render_svg(
                    {**renderer.DEFAULT_STATE, "valence": 0.9, "arousal": 0.9}
                )
                self.assertNotEqual(
                    low, high, "a face that ignores mood cannot look alive"
                )

    def test_no_external_references(self):
        """Must render standalone: no network fetches on a robot with no internet."""
        for name, renderer in RENDERERS:
            with self.subTest(renderer=name):
                svg = renderer.render_svg(renderer.DEFAULT_STATE)
                # The SVG/xlink namespace URIs are identifiers, never fetched.
                stripped = svg.replace("http://www.w3.org/2000/svg", "").replace(
                    "http://www.w3.org/1999/xlink", ""
                )
                self.assertNotIn("http://", stripped)
                self.assertNotIn("https://", stripped)
                self.assertNotIn("<image", stripped)

    def test_colours_are_well_formed(self):
        for name, renderer in RENDERERS:
            with self.subTest(renderer=name):
                for valence in (-1.0, -0.5, 0.0, 0.5, 1.0):
                    svg = renderer.render_svg(
                        {**renderer.DEFAULT_STATE, "valence": valence}
                    )
                    for colour in re.findall(r"#[0-9a-fA-F]*", svg):
                        self.assertIn(
                            len(colour) - 1, (3, 6), f"malformed colour {colour}"
                        )


if __name__ == "__main__":
    unittest.main()
