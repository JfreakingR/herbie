import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import herbie_desk


SAFE = {"motor_authority": False, "safe_motion_state": "STOP"}


class FakeGalaxy:
    def __init__(self):
        self.calls = []
        self.reply = {"text": "Hey. Nice desk.", **SAFE}
        self.down = False

    def __call__(self, url, token, body, timeout):
        path = url.split("18765", 1)[1]
        self.calls.append((path, body))
        if self.down:
            raise urllib.error.URLError("unplugged")
        if path == "/health":
            return {"ready": True, **SAFE}
        if path == "/v1/expression":
            return {"expression": "happy", "speaking": False, "listening": False}
        if path == "/v1/chat":
            return self.reply
        if path == "/v1/speak":
            return {"spoken": True}
        raise AssertionError(path)


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class BrainTests(unittest.TestCase):
    def setUp(self):
        self.galaxy = FakeGalaxy()
        self.clock = Clock()
        self.brain = herbie_desk.Brain(herbie_desk.DEFAULT_BRAIN, "tok",
                                       fetch=self.galaxy, clock=self.clock)

    def test_chat_is_spoken_by_galaxy_and_mouth_follows(self):
        [event] = self.brain.chat("hello")
        self.assertEqual(event["type"], "done")
        self.assertEqual(event["text"], "Hey. Nice desk.")
        self.assertEqual(event["spoken_by"], "galaxy")
        self.assertEqual(event["herbie_expression"], "happy")
        self.assertIn(("/v1/speak", {"text": "Hey. Nice desk."}), self.galaxy.calls)
        self.assertTrue(self.brain.expression()["speaking"])
        self.clock.now += 30
        self.assertFalse(self.brain.expression()["speaking"])

    def test_screen_voice_does_not_use_galaxy_speaker(self):
        brain = herbie_desk.Brain(herbie_desk.DEFAULT_BRAIN, "tok", voice="screen",
                                  fetch=self.galaxy, clock=self.clock)
        [event] = brain.chat("hello")
        self.assertEqual(event["spoken_by"], "screen")
        self.assertNotIn("/v1/speak", [path for path, _ in self.galaxy.calls])

    def test_unsafe_reply_is_refused(self):
        self.galaxy.reply = {"text": "vroom", "motor_authority": True, "safe_motion_state": "GO"}
        [event] = self.brain.chat("drive")
        self.assertEqual(event, {"type": "error", "error": "motor_safety_check_failed"})

    def test_unplugged_galaxy_reads_as_absent(self):
        self.galaxy.down = True
        self.assertEqual(self.brain.expression(), {"herbie": False})
        self.assertEqual(self.brain.chat("hi")[0]["error"], "brain_unreachable")
        self.assertFalse(self.brain.status()["brain_ready"])

    def test_no_token_means_face_only(self):
        brain = herbie_desk.Brain(herbie_desk.DEFAULT_BRAIN, "", fetch=self.galaxy)
        status = brain.status()
        self.assertFalse(status["brain"])
        self.assertFalse(status["motor_authority"])
        self.assertEqual(brain.chat("hi")[0]["error"], "no_brain_token")


class ReconnectTests(unittest.TestCase):
    def test_replugged_phone_is_reconnected(self):
        galaxy = FakeGalaxy()
        galaxy.down = True
        brain = herbie_desk.Brain(herbie_desk.DEFAULT_BRAIN, "", fetch=galaxy)
        stop = threading.Event()
        attempts = []

        def connect():
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("still unplugged")
            galaxy.down = False
            stop.set()
            return "fresh"

        herbie_desk.keep_connected(brain, connect, every=0.01, stop=stop)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(brain.token, "fresh")
        self.assertTrue(brain.ready())


class WifiPhoneTests(unittest.TestCase):
    def test_wifi_address_is_connected_and_used_as_the_phone(self):
        import sys
        from unittest import mock
        sys.path.insert(0, str(herbie_desk.REPO / "tools"))
        import herbie_presence
        calls = []
        with mock.patch.object(herbie_desk.shutil, "which", return_value="/usr/bin/adb"), \
             mock.patch.object(herbie_desk.subprocess, "run",
                               side_effect=lambda cmd, **kw: calls.append(cmd)), \
             mock.patch.object(herbie_presence, "connect", return_value="tok"), \
             mock.patch.object(herbie_presence, "PHONE_SERIAL", "R5CR11QCHPY"):
            self.assertEqual(herbie_desk.connect_over_adb("192.168.1.50:5555"), "tok")
            self.assertEqual(herbie_presence.PHONE_SERIAL, "192.168.1.50:5555")
        self.assertEqual(calls, [["/usr/bin/adb", "connect", "192.168.1.50:5555"]])


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.galaxy = FakeGalaxy()
        brain = herbie_desk.Brain(herbie_desk.DEFAULT_BRAIN, "tok", fetch=cls.galaxy)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), herbie_desk.make_handler(brain))
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            return response.status, response.read()

    def test_serves_face(self):
        status, body = self.get("/face/?kiosk=1")
        self.assertEqual(status, 200)
        self.assertIn(b"face-svg", body)

    def test_serves_spirit_and_its_bundled_3d_library(self):
        status, body = self.get("/face/spirit.html?kiosk=1")
        self.assertEqual(status, 200)
        self.assertIn(b"./vendor/three/build/three.module.js", body)
        status, _ = self.get("/face/vendor/three/build/three.module.js")
        self.assertEqual(status, 200)
        status, _ = self.get("/face/vendor/three/examples/jsm/postprocessing/UnrealBloomPass.js")
        self.assertEqual(status, 200)

    def test_face_path_cannot_escape(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/face/../desk/herbie_desk.py")
        self.assertEqual(caught.exception.code, 404)

    def test_status_names_the_galaxy_brain(self):
        _, body = self.get("/status")
        status = json.loads(body)
        self.assertTrue(status["companion"])
        self.assertTrue(status["brain"])
        self.assertTrue(status["brain_ready"])
        self.assertEqual(status["voice"], "galaxy")

    def test_chat_streams_ndjson(self):
        request = urllib.request.Request(
            self.base + "/v1/chat", data=json.dumps({"text": "hi"}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            lines = [json.loads(line) for line in response.read().splitlines() if line]
        self.assertEqual(lines[-1]["type"], "done")

    def test_chat_rejects_empty_text(self):
        request = urllib.request.Request(self.base + "/v1/chat", data=b'{"text": " "}')
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
