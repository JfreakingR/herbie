"""The SEGO/VAVA serial protocol, as spoken to Herbie's STM32 motor board.

Recovered from the factory app (`com.sego.toy.ctl`) by parsing its DEX: the
JNA Structure field order, the `TermSegoValue` command constants, and the
literal command strings inside `board.SimpleMoveTask.doAction()`. Nothing here
is guessed at from traffic; it is the app's own definitions.

The decode is confirmed against frames captured from J21 in earlier sessions:

    AA 55 | 00 07 | 02 | 08 | 00 5A 00 00 | A8
           length   cmd  seq    payload     crc

    length 7  = bytes from `command` through `crc` inclusive          [matches]
    cmd 0x02  = cmd_heartbeat, and those were the ~22 s idle frames   [matches]
    cmd 0x25  = cmd_key_event, seen when the power button was pressed [matches]
    KEY_EVENT is {number, action}, exactly the 2 payload bytes there  [matches]

This module only builds and parses bytes. It opens no port and moves nothing;
transmission is the caller's decision.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------- constants
# From TermSegoValue. Values are the app's own, not inferred.
FRAME_HEADER = b"\xAA\x55"
DEVICENO_SIZE = 8

# The wire is ASYMMETRIC, confirmed by the 2026-09-14 capture:
#
#   host -> board   REQUIRES a leading 0x00. Without it the board ignores the
#                   frame entirely. `00 AA 55 00 03 26 01 DB` drew a reply in
#                   209 ms; the same frame unpadded drew nothing.
#   board -> host   carries NO pad. Every captured reply begins at `AA 55`.
#
# The pad is a transmission artifact, not part of the frame, so `build_frame`
# stays pad-free and can still rebuild a board frame byte-exactly. Anything
# actually leaving a port must go through `to_wire` first.
WIRE_PAD = b"\x00"

CMD_GENERAL_RESPONSE = 0x01
CMD_HEARTBEAT = 0x02
CMD_TOY_LOGIN = 0x12
CMD_GENERAL_CONTROL = 0x20
CMD_TOGGLE_PERIPHERAL = 0x21
CMD_CONTROL_SERVO = 0x22
CMD_CONTROL_PANTILT = 0x23
CMD_CONTROL_LIGHT = 0x24
CMD_KEY_EVENT = 0x25
CMD_QUERY_BOARD_VERSION = 0x26
CMD_TAKE_SNAPSHOT = 0x2A
CMD_COMMAND_LINE = 0x2C
CMD_SET_BOARD_TIME = 0x2D
CMD_SERIAL_COMMAND_LINE = 0x2E
CMD_POSITION_STATUS = 0x30
CMD_START_RECORD = 0x40
CMD_STOP_RECORD = 0x41
CMD_QUERY_BOARD_CONFIG = 0x44

# Remaining commands from TermSegoValue, recovered 2026-09-14.
CMD_CONNECT_LOAD_BALANCE = 0x03
CMD_PLAYER_LOGIN = 0x13
CMD_SET_PARAMETERS = 0x14
CMD_QUERY_PARAMETERS = 0x15
CMD_SET_PARAMETER = 0x16
CMD_QUERY_PARAMETER = 0x17
CMD_TOY_LOGOUT = 0x18
CMD_BEGIN_UPDATE = 0x27
CMD_GET_UPDATE_BLOCK = 0x28
CMD_UPLOAD_FILE = 0x2B
CMD_PC_TRANSPARENT_DATA_UP = 0x33
CMD_USER_TRANSPARENT_DATA_UP = 0x34
CMD_QUERY_PANTILT_MOVE_REGION = 0x36
CMD_QUERY_PERIPHERAL_STATUS = 0x37
CMD_PC_TRANSPARENT_DATA_DOWN = 0x43

# Responses. The board sets bit 7 of the request code: response = request|0x80.
# Verified across every request/response pair in TermSegoValue (15 of them),
# and against the real 0x26 -> 0xA6 capture of 2026-09-14.
RESPONSE_BIT = 0x80
CMD_SVRSP_TOY_LOGIN = 0x92
CMD_TMRSP_QUERY_BOARD_VERSION = 0xA6
CMD_TMRSP_COMMAND_LINE = 0xAC
CMD_TMRSP_SERIAL_COMMAND_LINE = 0xAE
CMD_TMRSP_QUERY_BOARD_CONFIG = 0xC4
CMD_TMRSP_QUERY_PERIPHERAL_STATUS = 0xB7
CMD_TMRSP_QUERY_PANTILT_MOVE_REGION = 0xB6


def response_code(command: int) -> int:
    """The code the board answers `command` with."""
    if not 0 <= command <= 0x7F:
        raise ValueError("invalid_command")
    return command | RESPONSE_BIT


COMMAND_NAMES = {
    0x01: "general_response", 0x02: "heartbeat", 0x03: "connect_load_balance",
    0x12: "toy_login", 0x13: "player_login", 0x14: "set_parameters",
    0x15: "query_parameters", 0x16: "set_parameter", 0x17: "query_parameter",
    0x18: "toy_logout",
    0x20: "general_control", 0x21: "toggle_peripheral", 0x22: "control_servo",
    0x23: "control_pantilt", 0x24: "control_light", 0x25: "key_event",
    0x26: "query_board_version", 0x27: "begin_update",
    0x28: "get_update_block", 0x2A: "take_snapshot", 0x2B: "upload_file",
    0x2C: "command_line", 0x2D: "set_board_time",
    0x2E: "serial_command_line",
    0x30: "position_status", 0x33: "pc_transparent_data_up",
    0x34: "user_transparent_data_up", 0x36: "query_pantilt_move_region",
    0x37: "query_peripheral_status",
    0x40: "start_record", 0x41: "stop_record", 0x43: "pc_transparent_data_down",
    0x44: "query_board_config",
    0x83: "svrsp_connect_load_balance", 0x92: "svrsp_toy_login",
    0x94: "tmrsp_set_parameters", 0x95: "tmrsp_query_parameters",
    0x96: "tmrsp_set_parameter", 0x97: "tmrsp_query_parameter",
    0xA6: "board_version_reply", 0xA8: "svrsp_get_update_block",
    0xAA: "tmrsp_take_snapshot", 0xAB: "tmrsp_upload_file",
    0xAC: "tmrsp_command_line", 0xAE: "tmrsp_serial_command_line",
    0xB6: "tmrsp_query_pantilt_move_region",
    0xB7: "tmrsp_query_peripheral_status",
    0xC4: "tmrsp_query_board_config",
}

# COMMAND_LINE.operation, from the msgop_* constants.
MSGOP_FTP_COMMAND = 1
MSGOP_DEV_COMMAND = 2
MSGOP_APP_COMMAND = 3

# Key event numbers, useful for reading the board's own reports.
KEY_POWER = 1
KEY_COLLISION_WARNING = 5
KEY_LOW_VOLTAGE = 3
KEY_TOUCH1 = 6
KEY_TOUCH2 = 7
KEY_FUNCTION = 2
KEY_INFRARED_LED = 11
KEY_NAMES = {1: "power", 2: "function", 3: "low_voltage",
             4: "snack_lattices_protection", 5: "collision_warning",
             6: "touch1", 7: "touch2", 8: "ball_launcher_shift",
             9: "computer_screen", 10: "calling", 11: "infrared_led"}

# All five actions, from TermSegoValue. Only click and long_hold were known
# before; a frame carrying 1, 3 or 4 previously decoded as "click".
KEY_ACTION_CLICK = 0
KEY_ACTION_SHORT_HOLD = 1
KEY_ACTION_LONG_HOLD = 2
KEY_ACTION_SHORT_NOTIFY = 3
KEY_ACTION_LONG_NOTIFY = 4
KEY_ACTION_NAMES = {0: "click", 1: "short_hold", 2: "long_hold",
                    3: "short_notify", 4: "long_notify"}

# Movement, verbatim from SimpleMoveTask.doAction(). The direction lives in the
# fifth field; duration is milliseconds.
MOVE_COMMANDS = {
    "forward": "control_pantilt,0,0,1,4,{ms}",
    "backward": "control_pantilt,0,0,1,3,{ms}",
    "left": "control_pantilt,0,0,1,2,{ms}",
    "right": "control_pantilt,0,0,1,1,{ms}",
    "head_rise": "control_servo,0,0,2,1,{ms}",
    "head_bow": "control_servo,0,0,2,2,{ms}",
}

MAX_DURATION_MS = 2000


def checksum(data: bytes) -> int:
    """XOR of every byte before the crc, as TermSegoPacket$TAIL defines it."""
    crc = 0
    for byte in data:
        crc ^= byte
    return crc & 0xFF


def build_frame(command: int, sequence: int, payload: bytes = b"") -> bytes:
    """SHORT_HEADER + payload + TAIL.

    `length` counts from `command` through `crc` inclusive, which is what the
    captured heartbeat frames show.
    """
    if not 0 <= command <= 0xFF:
        raise ValueError("invalid_command")
    if not 0 <= sequence <= 0xFF:
        raise ValueError("invalid_sequence")
    length = 1 + 1 + len(payload) + 1          # command + sequence + payload + crc
    if length > 0xFFFF:
        raise ValueError("payload_too_long")
    body = FRAME_HEADER + length.to_bytes(2, "big") + bytes([command, sequence]) + payload
    return body + bytes([checksum(body)])


def to_wire(frame: bytes) -> bytes:
    """Prepend the leading 0x00 the board requires on host->board frames.

    Every byte sent to `/dev/ttyMT1` must pass through here. A frame written
    without the pad is silently ignored by the board — it does not error, it
    simply never answers, which is what made this expensive to find.
    """
    if not frame.startswith(FRAME_HEADER):
        raise ValueError("not_a_frame")
    return WIRE_PAD + frame


def toy_login(password: str = "", sequence: int = 0) -> bytes:
    """A cmd_toy_login (0x12) frame.

    TOY_LOGIN is `{STRING password; TAIL crc}` and STRING is a bare `byte[]`
    with no length prefix, so the payload is just the NUL-terminated password.
    Field order came from TermSegoPacket$TOY_LOGIN.getFieldOrder().

    The password itself is NOT known. No default was found in the dex, so the
    empty string is a starting guess, not a recovered value. The board answers
    with CMD_SVRSP_TOY_LOGIN (0x92) whether or not it accepts.
    """
    return build_frame(CMD_TOY_LOGIN, sequence, password.encode("ascii") + b"\x00")


def parse_frame(data: bytes) -> dict[str, Any] | None:
    """Parse one frame. Returns None if it is malformed or the crc fails."""
    start = data.find(FRAME_HEADER)
    if start < 0 or len(data) - start < 7:
        return None
    length = int.from_bytes(data[start + 2:start + 4], "big")
    end = start + 4 + length
    if length < 3 or end > len(data):
        return None
    frame = data[start:end]
    expected = checksum(frame[:-1])
    actual = frame[-1]
    return {
        "command": frame[4],
        "command_name": COMMAND_NAMES.get(frame[4], f"unknown_0x{frame[4]:02X}"),
        "sequence": frame[5],
        "payload": frame[6:-1],
        "crc_ok": expected == actual,
        "raw": frame,
    }


def iter_frames(data: bytes):
    """Yield every parseable frame in a capture, skipping padding bytes."""
    offset = 0
    while True:
        start = data.find(FRAME_HEADER, offset)
        if start < 0:
            return
        frame = parse_frame(data[start:])
        if frame is None:
            offset = start + 2
            continue
        yield frame
        offset = start + len(frame["raw"])


def command_line(text: str, sequence: int,
                 operation: int = MSGOP_DEV_COMMAND) -> bytes:
    """A COMMAND_LINE packet: operation (int) + text + crc."""
    if not isinstance(text, str) or not text or len(text) > 200:
        raise ValueError("invalid_command_text")
    payload = operation.to_bytes(4, "big") + text.encode("ascii") + b"\x00"
    return build_frame(CMD_SERIAL_COMMAND_LINE, sequence, payload)


def move(direction: str, duration_ms: int, sequence: int) -> bytes:
    """Build a movement frame.

    Duration is capped here rather than trusting the caller: this is the last
    point before bytes reach a motor board.
    """
    if direction not in MOVE_COMMANDS:
        raise ValueError("invalid_direction")
    if not isinstance(duration_ms, int) or duration_ms <= 0:
        raise ValueError("invalid_duration")
    duration_ms = min(duration_ms, MAX_DURATION_MS)
    return command_line(MOVE_COMMANDS[direction].format(ms=duration_ms), sequence)


def describe(frame: dict[str, Any]) -> str:
    """Human-readable summary, for reading captures."""
    name = frame["command_name"]
    payload = frame["payload"]
    if frame["command"] == CMD_KEY_EVENT and len(payload) >= 2:
        key = KEY_NAMES.get(payload[0], str(payload[0]))
        action = KEY_ACTION_NAMES.get(payload[1], str(payload[1]))
        return f"key_event {key} {action}"
    if frame["command"] == CMD_HEARTBEAT:
        return f"heartbeat seq={frame['sequence']} payload={payload.hex(' ')}"
    if frame["command"] == CMD_TMRSP_QUERY_BOARD_VERSION:
        # The first two payload bytes are retained as opaque protocol metadata;
        # the remaining NUL-separated ASCII fields are reported without
        # inventing semantic names for them.
        fields = [part.decode("ascii", "replace") for part in payload[2:].split(b"\x00")]
        return (
            f"board_version_reply seq={frame['sequence']} "
            f"metadata={payload[:2].hex(' ')} fields={fields}"
        )
    return f"{name} seq={frame['sequence']} payload={payload.hex(' ')}"
