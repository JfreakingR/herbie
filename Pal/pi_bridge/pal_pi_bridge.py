#!/usr/bin/env python3
"""Minimal, safety-bounded coordinator service for Pal's Raspberry Pi 3B."""

from __future__ import annotations

import json
import mimetypes
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SERVICE_VERSION = "0.2.0"
HERE = Path(__file__).resolve().parent
FACE_DIR = HERE / "face"
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
            "service": "pal-pi-bridge",
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
            "face": (FACE_DIR / "index.html").is_file(),
        }


class PalHandler(BaseHTTPRequestHandler):
    server_version = "PalPiBridge/0.1"

    def log_message(self, format_string: str, *args: Any) -> None:
        print(f"{self.client_address[0]} - {format_string % args}", flush=True)

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def send_file(self, path: Path) -> None:
        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_json(200, snapshot())
            return
        if parsed.path in {"/face", "/face/"}:
            index = FACE_DIR / "index.html"
            if index.is_file():
                self.send_file(index)
                return
            self.send_json(404, {"error": "face_missing"})
            return
        if parsed.path.startswith("/face/"):
            relative = parsed.path[len("/face/") :]
            if not relative or ".." in relative.split("/"):
                self.send_json(404, {"error": "not_found"})
                return
            target = (FACE_DIR / relative).resolve()
            try:
                target.relative_to(FACE_DIR.resolve())
            except ValueError:
                self.send_json(404, {"error": "not_found"})
                return
            if target.is_file():
                self.send_file(target)
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
    host = os.environ.get("PAL_PI_HOST", "127.0.0.1")
    port = int(os.environ.get("PAL_PI_PORT", "8766"))
    server = ThreadingHTTPServer((host, port), PalHandler)
    print(f"Pal Pi bridge {SERVICE_VERSION} listening on {host}:{port}", flush=True)
    print("Motor authority: disabled; safe motion state: STOP", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
