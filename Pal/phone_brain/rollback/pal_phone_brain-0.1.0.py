#!/data/data/com.termux/files/usr/bin/python
"""Minimal, safety-bounded service for Pal's Galaxy S21 Ultra brain."""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


SERVICE_VERSION = "0.1.0"
MAX_BODY_BYTES = 4096
STARTED_AT = time.monotonic()
STATE_LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "heartbeat_count": 0,
    "last_heartbeat_monotonic": None,
    "last_source": None,
}


def snapshot() -> dict[str, Any]:
    with STATE_LOCK:
        last_heartbeat = STATE["last_heartbeat_monotonic"]
        return {
            "service": "pal-phone-brain",
            "version": SERVICE_VERSION,
            "ready": True,
            "uptime_seconds": round(time.monotonic() - STARTED_AT, 3),
            "heartbeat_count": STATE["heartbeat_count"],
            "seconds_since_heartbeat": (
                None
                if last_heartbeat is None
                else round(time.monotonic() - last_heartbeat, 3)
            ),
            "last_source": STATE["last_source"],
            "motor_authority": False,
            "safe_motion_state": "STOP",
        }


class PalHandler(BaseHTTPRequestHandler):
    server_version = "PalPhoneBrain/0.1"

    def log_message(self, format_string: str, *args: Any) -> None:
        # Keep logs concise and do not record request bodies.
        print(f"{self.client_address[0]} - {format_string % args}", flush=True)

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(200, snapshot())
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/v1/heartbeat":
            self.send_json(404, {"error": "not_found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"error": "invalid_content_length"})
            return

        if content_length < 0 or content_length > MAX_BODY_BYTES:
            self.send_json(413, {"error": "payload_too_large"})
            return

        try:
            body = self.rfile.read(content_length)
            request = json.loads(body.decode("utf-8")) if body else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "invalid_json"})
            return

        source = request.get("source", "unknown")
        if not isinstance(source, str) or not 1 <= len(source) <= 64:
            self.send_json(400, {"error": "invalid_source"})
            return

        with STATE_LOCK:
            STATE["heartbeat_count"] += 1
            STATE["last_heartbeat_monotonic"] = time.monotonic()
            STATE["last_source"] = source

        response = snapshot()
        response["acknowledged"] = True
        self.send_json(200, response)


def main() -> None:
    host = os.environ.get("PAL_PHONE_HOST", "127.0.0.1")
    port = int(os.environ.get("PAL_PHONE_PORT", "8765"))
    server = ThreadingHTTPServer((host, port), PalHandler)
    print(f"Pal phone brain {SERVICE_VERSION} listening on {host}:{port}", flush=True)
    print("Motor authority: disabled; safe motion state: STOP", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

