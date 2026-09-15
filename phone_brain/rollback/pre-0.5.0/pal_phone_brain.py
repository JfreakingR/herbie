#!/data/data/com.termux/files/usr/bin/python
"""Persistent, safety-bounded service for Herbie's Galaxy S21 Ultra brain."""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

import herbie_memory
import herbie_voice


SERVICE_VERSION = "0.4.0"
MAX_BODY_BYTES = 16_384
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
            "service_current": "herbie-phone-brain",
            "identity_name": "Herbie",
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
            "persistent_memory": True,
            "memory_count": herbie_memory.count_memories(),
            "motor_authority": False,
            "safe_motion_state": "STOP",
        }


class PalHandler(BaseHTTPRequestHandler):
    server_version = "HerbiePhoneBrain/0.4"

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
        parsed = urlsplit(self.path)
        if parsed.path == "/health":
            self.send_json(200, snapshot())
            return
        if parsed.path == "/v1/self":
            self.send_json(200, herbie_memory.self_snapshot())
            return
        if parsed.path == "/v1/expression":
            self.send_json(200, herbie_memory.expression_snapshot())
            return
        if parsed.path == "/v1/privacy":
            self.send_json(200, herbie_memory.privacy_snapshot())
            return
        if parsed.path == "/v1/memories":
            params = parse_qs(parsed.query)
            try:
                limit = int(params.get("limit", ["20"])[0])
            except ValueError:
                self.send_json(400, {"error": "invalid_limit"})
                return
            query = params.get("q", [""])[0]
            if len(query) > 200:
                self.send_json(400, {"error": "query_too_long"})
                return
            self.send_json(200, {"memories": herbie_memory.recent(limit, query)})
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path not in {
            "/v1/heartbeat",
            "/v1/remember",
            "/v1/experience",
            "/v1/expression",
            "/v1/privacy",
            "/v1/speak",
        }:
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

        if self.path == "/v1/heartbeat":
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
        elif self.path == "/v1/remember":
            try:
                response = herbie_memory.remember(request)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
                return
            response.update({"motor_authority": False, "safe_motion_state": "STOP"})
        elif self.path == "/v1/experience":
            try:
                response = herbie_memory.experience(request)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
                return
            response.update({"motor_authority": False, "safe_motion_state": "STOP"})
        elif self.path == "/v1/expression":
            try:
                response = herbie_memory.set_expression(request)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
                return
            response.update({"motor_authority": False, "safe_motion_state": "STOP"})
        elif self.path == "/v1/privacy":
            try:
                response = herbie_memory.set_privacy(request)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
                return
            response.update({"motor_authority": False, "safe_motion_state": "STOP"})
        else:
            try:
                response = herbie_voice.speak(request)
            except (ValueError, RuntimeError) as exc:
                self.send_json(400, {"error": str(exc)})
                return
            response.update({"motor_authority": False, "safe_motion_state": "STOP"})
        self.send_json(200, response)


def main() -> None:
    herbie_memory.initialize()
    host = os.environ.get("HERBIE_PHONE_HOST", os.environ.get("PAL_PHONE_HOST", "127.0.0.1"))
    port = int(os.environ.get("HERBIE_PHONE_PORT", os.environ.get("PAL_PHONE_PORT", "8765")))
    server = ThreadingHTTPServer((host, port), PalHandler)
    print(f"Herbie phone brain {SERVICE_VERSION} listening on {host}:{port}", flush=True)
    print(f"Persistent memory: {herbie_memory.DB_PATH}", flush=True)
    print("Motor authority: disabled; safe motion state: STOP", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
