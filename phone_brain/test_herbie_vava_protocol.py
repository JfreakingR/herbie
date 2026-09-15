"""Validate the recovered SEGO/VAVA protocol against real captured frames.

The frames below were recorded from J21 in earlier sessions, long before the
factory app was decompiled. If the spec recovered from the DEX parses them and
reproduces their checksums, the decode is right — that is the whole point of
these tests.
"""

import os
import unittest

import herbie_vava_protocol as vava


# Verbatim from VAVA_UART_PROTOCOL_NOTES.md, captured on J21 at 115200 8N1.
HEARTBEATS = [
    "00 AA 55 00 07 02 08 00 5A 00 00 A8",
    "00 AA 55 00 07 02 09 00 5A 00 00 A9",
    "00 AA 55 00 07 02 0A 00 5A 00 00 AA",
    "00 AA 55 00 07 02 11 00 5A 00 00 B1",
    "00 AA 55 00 07 02 12 00 5A 00 00 B2",
    "00 AA 55 00 07 02 13 00 5A 00 00 B3",
]

KEY_EVENT_FRAME = "00 AA 55 00 05 25 86 0B 01 53"

# Pulled from /sdcard/reply.bin on 2026-09-09. This is the reply that the
# movement handoff identified as the decisive missing protocol proof.
BOARD_VERSION_REPLY = (
    "AA 55 00 1D A6 AA 05 26 31 2E 32 00 32 30 31 39 30 35 32 37 "
    "31 2E 32 00 32 30 31 38 31 32 32 34 C9"
)


def raw(text):
    return bytes.fromhex(text.replace(" ", ""))


class CapturedFrameTests(unittest.TestCase):
    def test_heartbeats_parse_with_valid_checksums(self):
        for text in HEARTBEATS:
            with self.subTest(frame=text):
                frame = vava.parse_frame(raw(text))
                self.assertIsNotNone(frame, "should locate the AA55 header")
                self.assertTrue(frame["crc_ok"], "recovered XOR spec must match")
                self.assertEqual(frame["command"], vava.CMD_HEARTBEAT)
                self.assertEqual(frame["command_name"], "heartbeat")

    def test_heartbeat_sequence_is_the_incrementing_byte(self):
        """The J21 notes called this 'the seventh byte increments'."""
        sequences = [vava.parse_frame(raw(t))["sequence"] for t in HEARTBEATS]
        self.assertEqual(sequences, [0x08, 0x09, 0x0A, 0x11, 0x12, 0x13])

    def test_key_event_frame_decodes_as_a_button(self):
        frame = vava.parse_frame(raw(KEY_EVENT_FRAME))
        self.assertIsNotNone(frame)
        self.assertTrue(frame["crc_ok"])
        self.assertEqual(frame["command"], vava.CMD_KEY_EVENT)
        self.assertEqual(len(frame["payload"]), 2, "KEY_EVENT is {number, action}")

    def test_length_covers_command_through_crc(self):
        frame = vava.parse_frame(raw(HEARTBEATS[0]))
        # length 7 = command + sequence + 4 payload + crc
        self.assertEqual(len(frame["payload"]), 4)

    def test_a_corrupted_frame_is_rejected(self):
        broken = raw(HEARTBEATS[0])[:-1] + b"\xFF"
        frame = vava.parse_frame(broken)
        self.assertFalse(frame["crc_ok"])

    def test_iter_frames_walks_a_concatenated_capture(self):
        stream = b"".join(raw(t) for t in HEARTBEATS)
        frames = list(vava.iter_frames(stream))
        self.assertEqual(len(frames), len(HEARTBEATS))
        self.assertTrue(all(f["crc_ok"] for f in frames))

    def test_board_version_reply_is_a_real_valid_response(self):
        frame = vava.parse_frame(raw(BOARD_VERSION_REPLY))
        self.assertIsNotNone(frame)
        self.assertTrue(frame["crc_ok"])
        self.assertEqual(frame["command"], vava.CMD_TMRSP_QUERY_BOARD_VERSION)
        self.assertEqual(frame["command_name"], "board_version_reply")
        self.assertEqual(frame["payload"][:2], bytes.fromhex("05 26"))
        self.assertEqual(
            frame["payload"][2:].split(b"\x00"),
            [b"1.2", b"201905271.2", b"20181224"],
        )

    def test_board_version_reply_description_preserves_unknown_metadata(self):
        description = vava.describe(vava.parse_frame(raw(BOARD_VERSION_REPLY)))
        self.assertIn("metadata=05 26", description)
        self.assertIn("201905271.2", description)


class RoundTripTests(unittest.TestCase):
    def test_rebuilding_a_captured_heartbeat_reproduces_it_exactly(self):
        """The strongest check: our builder must emit the real bytes."""
        original = raw(HEARTBEATS[0])[1:]        # drop the inter-frame pad
        rebuilt = vava.build_frame(
            vava.CMD_HEARTBEAT, 0x08, bytes.fromhex("00 5A 00 00".replace(" ", ""))
        )
        self.assertEqual(rebuilt, original)

    def test_build_then_parse_is_lossless(self):
        frame = vava.build_frame(vava.CMD_CONTROL_PANTILT, 42, b"\x01\x02\x03")
        parsed = vava.parse_frame(frame)
        self.assertTrue(parsed["crc_ok"])
        self.assertEqual(parsed["command"], vava.CMD_CONTROL_PANTILT)
        self.assertEqual(parsed["sequence"], 42)
        self.assertEqual(parsed["payload"], b"\x01\x02\x03")


class MovementTests(unittest.TestCase):
    def test_every_direction_builds_a_valid_frame(self):
        for i, direction in enumerate(["forward", "backward", "left", "right"]):
            with self.subTest(direction=direction):
                frame = vava.move(direction, 1000, i)
                parsed = vava.parse_frame(frame)
                self.assertTrue(parsed["crc_ok"])
                self.assertEqual(parsed["command"], vava.CMD_SERIAL_COMMAND_LINE)
                self.assertIn(b"control_pantilt", parsed["payload"])

    def test_directions_match_the_factory_app_encoding(self):
        """From SimpleMoveTask.doAction(): forward=4, back=3, left=2, right=1."""
        expected = {"forward": b",1,4,", "backward": b",1,3,",
                    "left": b",1,2,", "right": b",1,1,"}
        for direction, marker in expected.items():
            payload = vava.parse_frame(vava.move(direction, 1000, 1))["payload"]
            self.assertIn(marker, payload, direction)

    def test_duration_is_capped_at_the_boundary(self):
        payload = vava.parse_frame(vava.move("forward", 999999, 1))["payload"]
        self.assertIn(str(vava.MAX_DURATION_MS).encode(), payload)
        self.assertNotIn(b"999999", payload)

    def test_invalid_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_direction"):
            vava.move("sideways", 500, 1)
        for bad in (0, -100, "500", None):
            with self.assertRaisesRegex(ValueError, "invalid_duration"):
                vava.move("forward", bad, 1)

    def test_head_movements_use_the_servo_command(self):
        for direction in ("head_rise", "head_bow"):
            payload = vava.parse_frame(vava.move(direction, 1000, 1))["payload"]
            self.assertIn(b"control_servo", payload)


class SafetyTests(unittest.TestCase):
    def test_this_module_only_makes_bytes(self):
        """It must not be able to transmit; sending is a separate decision.

        Checked by inspecting the AST rather than grepping for substrings: the
        constant name CMD_SERIAL_COMMAND_LINE contains "serial" and is not I/O.
        """
        import ast
        from pathlib import Path

        source = Path(vava.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)

        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            imported <= {"__future__", "typing"},
            f"protocol module should be pure; it imports {sorted(imported)}",
        )

        called = {
            node.func.id for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        for forbidden in ("open", "exec", "eval", "__import__"):
            self.assertNotIn(forbidden, called)

    def test_duration_cap_is_enforced_in_the_builder(self):
        """The cap must live here, not in whatever calls it."""
        self.assertLessEqual(vava.MAX_DURATION_MS, 2000)
        for direction in vava.MOVE_COMMANDS:
            payload = vava.parse_frame(vava.move(direction, 10 ** 6, 1))["payload"]
            number = int(payload.rstrip(b"\x00").split(b",")[-1])
            self.assertLessEqual(number, vava.MAX_DURATION_MS)



class CapturedExchange20260914(unittest.TestCase):
    """The real query/reply captured on 2026-09-14, used as byte fixtures."""

    def setUp(self):
        here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
        with open(os.path.join(here, "herbie_reply_20260914.bin"), "rb") as fh:
            self.reply = fh.read()
        with open(os.path.join(here, "herbie_query_version_20260914.bin"), "rb") as fh:
            self.query = fh.read()

    def test_capture_is_four_heartbeats_then_a_version_reply(self):
        frames = list(vava.iter_frames(self.reply))
        self.assertEqual([f["command"] for f in frames],
                         [0x02, 0x02, 0x02, 0x02, 0xA6])
        self.assertTrue(all(f["crc_ok"] for f in frames))

    def test_the_reply_is_33_bytes_not_three_heartbeats(self):
        # The 2026-09-09 session could not tell `rx +33` from 3 x 11-byte
        # heartbeats. The 0xA6 frame is itself exactly 33 bytes.
        reply = [f for f in vava.iter_frames(self.reply) if f["command"] == 0xA6][0]
        self.assertEqual(len(reply["raw"]), 33)

    def test_sequence_is_the_boards_counter_and_is_not_echoed(self):
        frames = list(vava.iter_frames(self.reply))
        self.assertEqual(frames[-2]["sequence"], 0x96)
        self.assertEqual(frames[-1]["sequence"], 0x97)   # continues, not our 0x01

    def test_board_frames_carry_no_leading_pad(self):
        self.assertTrue(self.reply.startswith(vava.FRAME_HEADER))

    def test_to_wire_reproduces_the_frame_that_actually_worked(self):
        built = vava.build_frame(vava.CMD_QUERY_BOARD_VERSION, 0x01)
        self.assertEqual(vava.to_wire(built), self.query)
        self.assertNotEqual(built, self.query)          # the pad is the difference

    def test_to_wire_refuses_something_that_is_not_a_frame(self):
        with self.assertRaises(ValueError):
            vava.to_wire(vava.WIRE_PAD + vava.FRAME_HEADER)   # already padded


class ResponseCodes(unittest.TestCase):

    def test_response_is_request_with_bit_7_set(self):
        for request, expected in [
            (0x26, 0xA6), (0x12, 0x92), (0x2C, 0xAC), (0x2E, 0xAE),
            (0x44, 0xC4), (0x36, 0xB6), (0x37, 0xB7), (0x28, 0xA8),
        ]:
            self.assertEqual(vava.response_code(request), expected)

    def test_a_response_code_is_not_a_valid_request(self):
        with self.assertRaises(ValueError):
            vava.response_code(0xA6)


class ToyLogin(unittest.TestCase):

    def test_login_frame_parses_back(self):
        frame = vava.toy_login("", 0)
        parsed = vava.parse_frame(frame)
        self.assertEqual(parsed["command"], vava.CMD_TOY_LOGIN)
        self.assertTrue(parsed["crc_ok"])

    def test_password_is_nul_terminated_in_the_payload(self):
        self.assertEqual(vava.parse_frame(vava.toy_login("abc", 0))["payload"],
                         b"abc\x00")


class KeyEventActions(unittest.TestCase):

    def test_all_five_actions_decode_distinctly(self):
        seen = set()
        for action in range(5):
            frame = vava.build_frame(vava.CMD_KEY_EVENT, 0,
                                     bytes([vava.KEY_COLLISION_WARNING, action]))
            seen.add(vava.describe(vava.parse_frame(frame)))
        self.assertEqual(len(seen), 5)   # previously 1,3,4 all read as "click"

if __name__ == "__main__":
    unittest.main()
