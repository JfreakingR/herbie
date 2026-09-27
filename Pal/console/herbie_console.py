#!/usr/bin/env python3
"""Herbie console - a local control panel for Herbie.

Serves a web page on http://127.0.0.1:8899 and talks to three things:

  * the phone brain on the Galaxy  (mood, drives, memories, speech)
  * the J21 wire tap on the ESP32  (Herbie's own internal chatter)
  * Herbie's board over adb        (movement commands)

Everything is served from one origin so the browser never has to make a
cross-origin request, and no page ever holds the brain's API token.

Nothing here is required for Herbie to run. Close it and he carries on.

    python herbie_console.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "phone_brain"))

import herbie_vava_protocol as vava  # noqa: E402

LISTEN_PORT = 8899
BRAIN_URL = "http://127.0.0.1:18765"
BRAIN_FORWARD = ("tcp:18765", "tcp:8765")
TOKEN_PATH = os.path.join(os.path.expanduser("~"), ".herbie", "api-token")
ADB = os.path.join(REPO, "tools", "scrcpy-win64-v4.1", "scrcpy-win64-v4.1", "adb.exe")
GALAXY_SERIAL = "R5CR11QCHPY"
HERBIE_SERIAL = "0123456789ABCDEF"
TAP_PORT = "COM7"
TAP_BAUD = 115200

# Herbie's own frames are pushed here before being written to his serial port.
STAGING = "/sdcard/.herbie_console_frame.bin"

# Duration is capped in the protocol module too; this is a second, visible cap
# because the console puts movement behind a button a human can hold down.
MAX_MOVE_MS = 2000

DIRECTIONS = {"forward": 4, "backward": 3, "left": 2, "right": 1}


def _token() -> str:
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


# --------------------------------------------------------------- the wire tap
class Tap:
    """Reads the ESP32 listener and decodes Herbie's internal traffic.

    The listener prints human-readable lines with the raw bytes in them, so we
    pull the hex back out and run it through the real protocol parser rather
    than re-implementing the decode here.
    """

    def __init__(self):
        self.events = deque(maxlen=300)
        self.power = None
        self.last_seen = None
        self.connected = False
        self._buf = ""
        self._bytes = bytearray()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            try:
                import serial

                # DTR/RTS must be low BEFORE the port opens. Opening with them
                # asserted pulses the ESP32's reset line, so the listener
                # reboots on every connect and never gets as far as reporting
                # a frame.
                port = serial.Serial()
                port.port = TAP_PORT
                port.baudrate = TAP_BAUD
                port.timeout = 1
                port.dtr = False
                port.rts = False
                port.open()
                with port:
                    self.connected = True
                    while True:
                        chunk = port.read(512)
                        if chunk:
                            self._feed(chunk.decode("ascii", "replace"))
                        else:
                            time.sleep(0.05)
            except Exception:
                self.connected = False
                time.sleep(3)

    def _feed(self, text: str):
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._line(line)

    def _line(self, line: str):
        # Listener lines look like:  "   156506 ms | 00 AA 55 ... | ..U..."
        # The hex is the MIDDLE column, between the two pipes.
        parts = line.split("|")
        if len(parts) < 2:
            return
        hexpart = parts[1]
        for token in hexpart.split():
            if len(token) == 2:
                try:
                    self._bytes.append(int(token, 16))
                except ValueError:
                    pass
        self._drain()

    def _drain(self):
        data = bytes(self._bytes)
        consumed = 0
        for frame in vava.iter_frames(data):
            raw = frame["raw"]
            consumed = data.find(raw, consumed) + len(raw)
            self._record(frame)
        if consumed:
            del self._bytes[:consumed]
        if len(self._bytes) > 4096:
            del self._bytes[:-1024]

    def _record(self, frame):
        if not frame["crc_ok"]:
            return
        self.last_seen = time.time()
        cmd = frame["command"]
        payload = frame["payload"]

        if cmd == vava.CMD_HEARTBEAT and len(payload) >= 2:
            self.power = payload[1]
            return          # heartbeats are constant noise; don't list them

        self.events.appendleft({
            "at": time.strftime("%H:%M:%S"),
            "text": self._plain(frame),
            "hex": frame["raw"].hex(" "),
        })

    @staticmethod
    def _plain(frame) -> str:
        """Describe a frame the way a person would say it."""
        cmd = frame["command"]
        p = frame["payload"]
        if cmd == vava.CMD_KEY_EVENT and len(p) >= 2:
            key = vava.KEY_NAMES.get(p[0], f"sensor {p[0]}")
            action = vava.KEY_ACTION_NAMES.get(p[1], str(p[1]))
            return f"{key} -> {action}"
        if cmd == vava.CMD_GENERAL_RESPONSE and len(p) >= 2:
            orig = vava.COMMAND_NAMES.get(p[1], f"0x{p[1]:02X}")
            return f"acknowledged: {orig} (msg #{p[0]})"
        if cmd == vava.CMD_CONTROL_PANTILT and len(p) >= 4:
            name = {4: "forward", 3: "backward", 2: "left", 1: "right"}.get(p[1], f"dir {p[1]}")
            return f"MOVE {name} for {(p[2] << 8) | p[3]} ms"
        if cmd == vava.CMD_CONTROL_LIGHT and len(p) >= 6:
            return f"light {p[0]}: action {p[1]}, colour {p[2]}"
        if cmd == vava.CMD_CONTROL_SERVO and len(p) >= 4:
            return f"servo {p[0]}: action {p[1]}"
        return vava.describe(frame)


# ------------------------------------------------------------------- the brain
def brain(path: str, method: str = "GET", body: dict | None = None):
    url = BRAIN_URL + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    token = _token()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode() or "{}")


def ensure_forward():
    """Re-establish the adb port forward. Cheap, and survives a phone replug."""
    try:
        subprocess.run([ADB, "-s", GALAXY_SERIAL, "forward", *BRAIN_FORWARD],
                       capture_output=True, timeout=10)
    except Exception:
        pass


# ------------------------------------------------------------------- movement
def send_move(direction: str, duration_ms: int) -> dict:
    """Push one CONTROL_PANTILT frame to Herbie's board and write it to the UART.

    Herbie's Android side reboots every few minutes, so this reports a clear
    'he is not reachable' rather than raising.
    """
    if direction not in DIRECTIONS:
        return {"ok": False, "error": "unknown direction"}
    duration_ms = max(1, min(int(duration_ms), MAX_MOVE_MS))
    payload = bytes([1, DIRECTIONS[direction],
                     (duration_ms >> 8) & 0xFF, duration_ms & 0xFF])
    frame = vava.to_wire(vava.build_frame(vava.CMD_CONTROL_PANTILT,
                                          int(time.time()) & 0xFF, payload))
    local = os.path.join(HERE, ".frame.bin")
    with open(local, "wb") as fh:
        fh.write(frame)
    try:
        push = subprocess.run([ADB, "-s", HERBIE_SERIAL, "push", local, STAGING],
                              capture_output=True, timeout=15)
        if push.returncode != 0:
            return {"ok": False, "error": "Herbie is not reachable (he restarts often)"}
        subprocess.run([ADB, "-s", HERBIE_SERIAL, "shell",
                        f"cat {STAGING} > /dev/ttyMT1"], capture_output=True, timeout=15)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timed out talking to Herbie"}
    return {"ok": True, "sent": frame.hex(" "), "direction": direction,
            "duration_ms": duration_ms}


def herbie_state() -> dict:
    try:
        out = subprocess.run([ADB, "devices"], capture_output=True, timeout=10)
        listed = out.stdout.decode(errors="replace")
    except Exception:
        return {"reachable": False, "awake_seconds": None}
    reachable = f"{HERBIE_SERIAL}\tdevice" in listed
    awake = None
    if reachable:
        try:
            up = subprocess.run([ADB, "-s", HERBIE_SERIAL, "shell", "cat /proc/uptime"],
                                capture_output=True, timeout=10)
            awake = int(float(up.stdout.decode().split()[0]))
        except Exception:
            pass
    return {"reachable": reachable, "awake_seconds": awake}


# --------------------------------------------------------------------- server
TAP = Tap()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                with open(os.path.join(HERE, "console.html"), "rb") as fh:
                    page = fh.read()
            except OSError:
                self.send_error(500, "console.html missing")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return

        if self.path == "/api/state":
            state = {
                "tap": {
                    "connected": TAP.connected,
                    "power": TAP.power,
                    "last_seen": TAP.last_seen,
                },
                "herbie": herbie_state(),
                "brain": None,
                "brain_error": None,
            }
            try:
                state["brain"] = brain("/v1/self")
            except Exception as exc:
                ensure_forward()
                try:
                    state["brain"] = brain("/v1/self")
                except Exception:
                    state["brain_error"] = str(exc)
            self._send(state)
            return

        if self.path == "/api/events":
            self._send({"events": list(TAP.events)[:80]})
            return

        self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send({"ok": False, "error": "bad json"}, 400)
            return

        if self.path == "/api/say":
            text = (body.get("text") or "").strip()
            if not text:
                self._send({"ok": False, "error": "nothing to say"}, 400)
                return
            try:
                self._send({"ok": True, "result": brain("/v1/speak", "POST", {"text": text})})
            except Exception as exc:
                self._send({"ok": False, "error": str(exc)}, 502)
            return

        if self.path == "/api/remember":
            text = (body.get("text") or "").strip()
            if not text:
                self._send({"ok": False, "error": "nothing to remember"}, 400)
                return
            try:
                self._send({"ok": True, "result": brain("/v1/remember", "POST", {"text": text})})
            except Exception as exc:
                self._send({"ok": False, "error": str(exc)}, 502)
            return

        if self.path == "/api/move":
            self._send(send_move(body.get("direction", ""), body.get("duration_ms", 1000)))
            return

        self.send_error(404)


def main():
    ensure_forward()
    server = ThreadingHTTPServer(("127.0.0.1", LISTEN_PORT), Handler)
    print(f"Herbie console: http://127.0.0.1:{LISTEN_PORT}")
    print("Press Ctrl+C to stop. Herbie is unaffected either way.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
