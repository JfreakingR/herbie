#!/usr/bin/env python3
"""Herbie as a stationary desk bot: his face on a screen, his brain on the Galaxy.

Serves the animated face (pi_bridge/face/index.html) on loopback and answers
the three calls it makes:

- GET  /status          what the face is connected to
- GET  /v1/expression   the Galaxy brain's expression, plus "speaking" while
                        a reply from this screen is being said aloud
- POST /v1/chat         {"text": ...} -> the Galaxy brain, as NDJSON events

The Galaxy stays the only writer of identity and memory. Nothing here reaches
the VAVA body, the ESP32, or any motor; every brain reply is checked for
motor_authority=false and safe_motion_state=STOP before it is shown.

On the Windows PC the default brain URL is the ADB forward that
tools/herbie_presence.py sets up. Any other machine can pass --brain.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


REPO = Path(__file__).resolve().parents[1]
FACE_DIR = REPO / "pi_bridge" / "face"
DEFAULT_BRAIN = "http://127.0.0.1:18765"
DEFAULT_TOKEN_FILE = Path.home() / ".herbie" / "api-token"
DEFAULT_PORT = 8766
MAX_BODY_BYTES = 8192
MAX_MESSAGE_CHARS = 1000
VOICES = ("galaxy", "screen")
# Android TTS speaks roughly 2.6 words a second; the mouth moves for that long.
SECONDS_PER_WORD = 0.38
SPEECH_PADDING = 0.8

Fetch = Callable[[str, str, "dict[str, Any] | None", float], "dict[str, Any]"]


def http_fetch(url: str, token: str, body: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def speaking_seconds(text: str) -> float:
    return len(text.split()) * SECONDS_PER_WORD + SPEECH_PADDING


def motor_safe(payload: dict[str, Any]) -> bool:
    return payload.get("motor_authority") is False and payload.get("safe_motion_state") == "STOP"


class Brain:
    """The Galaxy brain as the face sees it. Failures read as 'not here'."""

    def __init__(
        self,
        url: str,
        token: str,
        voice: str = "galaxy",
        fetch: Fetch = http_fetch,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if voice not in VOICES:
            raise ValueError("invalid_voice")
        self.url = url.rstrip("/")
        self.token = token
        self.voice = voice
        self.fetch = fetch
        self.clock = clock
        self.lock = threading.Lock()
        self.speaking_until = 0.0

    def call(self, path: str, body: dict[str, Any] | None = None, timeout: float = 4.0) -> dict[str, Any]:
        return self.fetch(self.url + path, self.token, body, timeout)

    def ready(self) -> bool:
        try:
            health = self.call("/health", timeout=3.0)
        except (OSError, ValueError, urllib.error.URLError):
            return False
        return health.get("ready") is True and motor_safe(health)

    def status(self) -> dict[str, Any]:
        return {
            "companion": True,
            "service": "herbie-desk",
            "brain": bool(self.token),
            "herbie": bool(self.token),
            "brain_ready": self.ready() if self.token else False,
            "grok": False,
            "voice": self.voice,
            "motor_authority": False,
            "safe_motion_state": "STOP",
        }

    def expression(self) -> dict[str, Any]:
        try:
            snap = self.call("/v1/expression", timeout=2.0)
        except (OSError, ValueError, urllib.error.URLError):
            return {"herbie": False}
        snap = dict(snap)
        snap["herbie"] = True
        with self.lock:
            if self.clock() < self.speaking_until:
                snap["speaking"] = True
        return snap

    def chat(self, text: str) -> list[dict[str, Any]]:
        if not self.token:
            return [{"type": "error", "error": "no_brain_token"}]
        try:
            result = self.call("/v1/chat", {"message": text, "max_tokens": 160}, timeout=180.0)
        except urllib.error.HTTPError as exc:
            return [{"type": "error", "error": f"brain_http_{exc.code}"}]
        except (OSError, ValueError, urllib.error.URLError):
            return [{"type": "error", "error": "brain_unreachable"}]
        if not motor_safe(result):
            return [{"type": "error", "error": "motor_safety_check_failed"}]
        reply = result.get("text")
        if not isinstance(reply, str) or not reply.strip():
            return [{"type": "error", "error": "empty_reply"}]
        reply = reply.strip()
        spoken_by = "screen"
        if self.voice == "galaxy":
            try:
                self.call("/v1/speak", {"text": reply[:MAX_MESSAGE_CHARS]}, timeout=8.0)
                with self.lock:
                    self.speaking_until = self.clock() + speaking_seconds(reply)
                spoken_by = "galaxy"
            except (OSError, ValueError, urllib.error.URLError):
                spoken_by = "screen"  # the face says it instead of going silent
        expression = self.expression().get("expression")
        return [{
            "type": "done",
            "text": reply,
            "herbie_expression": expression,
            "spoken_by": spoken_by,
        }]


def make_handler(brain: Brain, face_dir: Path = FACE_DIR) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "HerbieDesk/1"

        def log_message(self, format_string: str, *args: Any) -> None:
            return

        def send_bytes(self, status: int, data: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, status: int, payload: dict[str, Any]) -> None:
            self.send_bytes(status, json.dumps(payload).encode("utf-8"),
                            "application/json; charset=utf-8")

        def send_face_file(self, relative: str) -> None:
            if ".." in relative.split("/"):
                self.send_json(404, {"error": "not_found"})
                return
            target = (face_dir / (relative or "index.html")).resolve()
            try:
                target.relative_to(face_dir.resolve())
            except ValueError:
                self.send_json(404, {"error": "not_found"})
                return
            if not target.is_file():
                self.send_json(404, {"error": "not_found"})
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix == ".html":
                content_type = "text/html; charset=utf-8"
            self.send_bytes(200, target.read_bytes(), content_type)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/health":
                self.send_json(200, {"ready": True, "service": "herbie-desk",
                                     "motor_authority": False, "safe_motion_state": "STOP"})
            elif path == "/status":
                self.send_json(200, brain.status())
            elif path == "/v1/expression":
                self.send_json(200, brain.expression())
            elif path in {"/", "/face", "/face/"}:
                self.send_face_file("")
            elif path.startswith("/face/"):
                self.send_face_file(path[len("/face/"):])
            else:
                self.send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/v1/chat":
                self.send_json(404, {"error": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_json(400, {"error": "invalid_content_length"})
                return
            if length < 0 or length > MAX_BODY_BYTES:
                self.send_json(413, {"error": "payload_too_large"})
                return
            try:
                request = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json(400, {"error": "invalid_json"})
                return
            text = request.get("text") if isinstance(request, dict) else None
            if not isinstance(text, str) or not text.strip() or len(text) > MAX_MESSAGE_CHARS:
                self.send_json(400, {"error": "invalid_text"})
                return
            events = brain.chat(text.strip())
            body = "".join(json.dumps(event) + "\n" for event in events).encode("utf-8")
            self.send_bytes(200, body, "application/x-ndjson; charset=utf-8")

    return Handler


def connect_over_adb() -> str:
    """Forward the Galaxy brain to the PC exactly as herbie_presence does."""
    sys.path.insert(0, str(REPO / "tools"))
    import herbie_presence  # noqa: E402  (Windows-side helper in tools/)

    return herbie_presence.connect()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--brain", default=DEFAULT_BRAIN,
                        help="Galaxy brain URL (default: the PC's ADB forward)")
    parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_FILE)
    parser.add_argument("--no-adb", action="store_true",
                        help="do not set up the ADB forward; --brain is reachable already")
    parser.add_argument("--voice", choices=VOICES, default="galaxy",
                        help="galaxy: replies play from the phone; screen: the face's own speech")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    token = ""
    if args.brain == DEFAULT_BRAIN and not args.no_adb:
        try:
            token = connect_over_adb()
        except Exception as exc:  # face still comes up; it just can't think
            print(f"Galaxy brain not connected: {exc}", file=sys.stderr)
            print("The face will show, but Herbie can't answer until this is fixed.",
                  file=sys.stderr)
    if not token and args.token_file.is_file():
        token = args.token_file.read_text(encoding="utf-8").strip()

    brain = Brain(args.brain, token, voice=args.voice)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(brain))
    print(f"Herbie's desk face: http://{args.host}:{args.port}/face/?kiosk=1", flush=True)
    print(f"Brain: {args.brain} ({'token loaded' if token else 'no token'}), voice: {args.voice}",
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
