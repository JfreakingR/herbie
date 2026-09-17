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

# Movement is CONTROL_SERVO (0x22): {byte number, byte action, short value}.
# Ground truth is the factory self-test, test.SelfCheckTask:
#   "Test move": control_servo,0,0,1,{1,2,4,3},2000
#   "Test head": control_servo,0,0,2,{2,1},7000
# Servo 1 drives the wheels, servo 2 moves the head. Terminal.transferToSerialStr
# writes `value` WITHOUT LBE.swap16, so on the wire it is little-endian.
#
# Two things that looked like movement and are not:
#   * CONTROL_PANTILT (0x23) is the laser pen (number 1) and cat whip (number 2);
#     Terminal.onControlPantilt clamps them to 0-200 as laser X/Y.
#   * The text strings in SimpleMoveTask.doAction ("control_pantilt,0,0,1,4,1000")
#     have 6 tokens where the 0x23 branch demands 7, so the factory app itself
#     throws and sends nothing. They are dead code, not a recipe.
SERVO_DRIVE = 1
SERVO_HEAD = 2
DRIVE_ACTIONS = {"forward": 4, "backward": 3, "left": 2, "right": 1}
HEAD_ACTIONS = {"rise": 1, "bow": 2}
PANTILT_LASER_PEN = 1
PANTILT_CAT_WHIP = 2

# The drive cap is deliberately short: this is the last point before bytes reach
# a motor board. The head cap matches the factory self-test's 7000 ms.
MAX_DURATION_MS = 2000
MAX_HEAD_MS = 7000


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


# No toy_login() or command_line() builders, on purpose. TOY_LOGIN, COMMAND_LINE
# and GENERAL_CONTROL all extend the full network HEADER (8-byte device_no) and
# are parsed by TermSegoNetProtocolAdaptor: they belong to the dead VAVA cloud,
# not to the serial link. Serial text uses SERIAL_COMMAND_LINE = {byte size;
# byte[] text}, which nothing here needs now that movement is CONTROL_SERVO.


def control_servo(number: int, action: int, value: int, sequence: int) -> bytes:
    """A CONTROL_SERVO (0x22) frame: {byte number, byte action, short value}.

    `value` goes out little-endian - the factory app does not byte-swap it.
    Prefer move() and head(), which validate and cap; this is the raw builder.
    """
    for name, byte in (("number", number), ("action", action)):
        if not isinstance(byte, int) or not 0 <= byte <= 0xFF:
            raise ValueError(f"invalid_{name}")
    if not isinstance(value, int) or not 0 <= value <= 0xFFFF:
        raise ValueError("invalid_value")
    payload = bytes([number, action]) + value.to_bytes(2, "little")
    return build_frame(CMD_CONTROL_SERVO, sequence, payload)


def _duration(duration_ms: Any, cap: int) -> int:
    # bool is an int subclass; True would otherwise pass as 1 ms.
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or duration_ms <= 0:
        raise ValueError("invalid_duration")
    return min(duration_ms, cap)


def move(direction: str, duration_ms: int, sequence: int) -> bytes:
    """Drive the wheels: servo 1, forward 4 / backward 3 / left 2 / right 1.

    Duration is capped here rather than trusting the caller: this is the last
    point before bytes reach a motor board.

    As of 2026-09-16 the board acks this five times out of five (result 0), but
    the wheels have not been confirmed to turn. Directions follow the factory
    naming and are not yet physically confirmed.
    """
    if direction not in DRIVE_ACTIONS:
        raise ValueError("invalid_direction")
    duration_ms = _duration(duration_ms, MAX_DURATION_MS)
    return control_servo(SERVO_DRIVE, DRIVE_ACTIONS[direction], duration_ms, sequence)


def head(motion: str, duration_ms: int, sequence: int) -> bytes:
    """Move the head: servo 2, rise 1 / bow 2."""
    if motion not in HEAD_ACTIONS:
        raise ValueError("invalid_head_motion")
    duration_ms = _duration(duration_ms, MAX_HEAD_MS)
    return control_servo(SERVO_HEAD, HEAD_ACTIONS[motion], duration_ms, sequence)


def parse_general_response(frame: dict[str, Any]) -> dict[str, int] | None:
    """Decode a serial GENERAL_RESPONSE (0x01): which of OUR frames it answers.

    Payload is {byte src_sequence, byte src_command, int result}. The frame's
    own sequence byte is the board's counter; src_sequence echoes ours, so match
    replies on (src_sequence, src_command). Every result seen so far is 0, so
    the byte order of `result` is assumed little-endian (like the servo value)
    but unconfirmed.
    """
    if frame is None or frame.get("command") != CMD_GENERAL_RESPONSE:
        return None
    payload = frame["payload"]
    if len(payload) < 6:
        return None
    return {
        "src_sequence": payload[0],
        "src_command": payload[1],
        "result": int.from_bytes(payload[2:6], "little", signed=True),
    }


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


def describe(frame: dict[str, Any]) -> str:
    """Human-readable summary, for reading captures."""
    name = frame["command_name"]
    payload = frame["payload"]
    ack = parse_general_response(frame)
    if ack is not None:
        answered = COMMAND_NAMES.get(ack["src_command"], f"0x{ack['src_command']:02X}")
        return (f"ack {answered} seq={ack['src_sequence']} result={ack['result']}"
                + ("" if ack["result"] == 0 else " (REFUSED)"))
    if frame["command"] == CMD_CONTROL_SERVO and len(payload) >= 4:
        value = int.from_bytes(payload[2:4], "little")
        if payload[0] == SERVO_DRIVE:
            motion = {v: k for k, v in DRIVE_ACTIONS.items()}.get(payload[1], f"action {payload[1]}")
            return f"drive {motion} {value} ms"
        if payload[0] == SERVO_HEAD:
            motion = {v: k for k, v in HEAD_ACTIONS.items()}.get(payload[1], f"action {payload[1]}")
            return f"head {motion} {value} ms"
        return f"servo {payload[0]} action {payload[1]} value {value}"
    if frame["command"] == CMD_CONTROL_PANTILT and len(payload) >= 2:
        part = {PANTILT_LASER_PEN: "laser pen", PANTILT_CAT_WHIP: "cat whip"}.get(
            payload[0], f"pantilt {payload[0]}")
        return f"{part} action {payload[1]} values {payload[2:].hex(' ')}"
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
