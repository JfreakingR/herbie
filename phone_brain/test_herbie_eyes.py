"""Herbie's sight: the [see] tag, the camera request, and the privacy gate."""

import base64
import unittest
from unittest import mock

import herbie_chat
import herbie_cloud
import herbie_eyes as eyes

JPEG = b"\xff\xd8\xff\xe0" + b"x" * 100


class ExtractSeeTests(unittest.TestCase):
    def test_tag_is_removed(self):
        self.assertEqual(eyes.extract_see("Let me look. [see]"), ("Let me look.", True))
        self.assertEqual(eyes.extract_see("[SEE] hm, what's that?"), ("hm, what's that?", True))

    def test_no_tag(self):
        self.assertEqual(eyes.extract_see("Hi there"), ("Hi there", False))


class LookNowTests(unittest.TestCase):
    def open_camera(self, reply=None, error=None, permitted=True):
        with mock.patch.object(eyes, "camera_permitted", return_value=permitted), \
                mock.patch.object(herbie_chat, "post_bridge_voice",
                                  return_value=reply, side_effect=error) as bridge:
            return eyes.look_now(), bridge

    def test_decodes_the_apps_jpeg(self):
        jpeg, bridge = self.open_camera({"jpeg_base64": base64.b64encode(JPEG).decode()})
        self.assertEqual(jpeg, JPEG)
        self.assertEqual(bridge.call_args.args[0], "/v1/see")

    def test_privacy_mode_takes_no_photo(self):
        with mock.patch.object(eyes, "camera_permitted", return_value=False), \
                mock.patch.object(herbie_chat, "post_bridge_voice") as bridge:
            with self.assertRaisesRegex(eyes.EyesUnavailable, "not_permitted"):
                eyes.look_now()
        bridge.assert_not_called()

    def test_failures_become_eyes_unavailable(self):
        for reply, error in (
            (None, herbie_chat.ChatUnavailable("down")),
            ({"error": "camera_not_allowed"}, None),
            ({"jpeg_base64": base64.b64encode(b"not a jpeg").decode()}, None),
        ):
            with self.subTest(reply=reply, error=error):
                with self.assertRaises(eyes.EyesUnavailable):
                    self.open_camera(reply, error)


class CloudImageTests(unittest.TestCase):
    def test_photo_goes_before_the_question(self):
        body = herbie_cloud.build_request("m", "what is it?", "", 64, image=JPEG)
        content = body["messages"][0]["content"]
        self.assertEqual(content[0]["type"], "image")
        self.assertEqual(content[0]["source"]["media_type"], "image/jpeg")
        self.assertEqual(base64.b64decode(content[0]["source"]["data"]), JPEG)
        self.assertEqual(content[1], {"type": "text", "text": "what is it?"})

    def test_text_only_stays_plain(self):
        body = herbie_cloud.build_request("m", "hi", "", 64)
        self.assertEqual(body["messages"][0]["content"], "hi")


if __name__ == "__main__":
    unittest.main()
