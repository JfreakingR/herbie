#!/data/data/com.termux/files/usr/bin/python
"""Persistent, safety-bounded service for Herbie's Galaxy S21 Ultra brain."""

from __future__ import annotations

import hmac
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import herbie_autonomic
import herbie_memory
import herbie_voice


SERVICE_VERSION = "0.7.0"
AUTONOMIC = herbie_autonomic.AutonomicLoop()
TOKEN_PATH = Path(
    os.environ.get(
        "HERBIE_TOKEN_FILE",
        Path(__file__).resolve().parent / "herbie-api-token",
    )
)


def load_api_token() -> str:
    """Return the shared secret callers must present, creating one if needed.

    Binding to loopback is not access control on Android: any app on the phone
    can reach 127.0.0.1, and `adb forward` republishes this port on the
    workstation's loopback too. Without a token, anything local could rewrite
    personality, insert memories, or switch privacy mode off.
    """
    from_env = os.environ.get("HERBIE_API_TOKEN", "").strip()
    if from_env:
        return from_env
    if TOKEN_PATH.exists():
        existing = TOKEN_PATH.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    token = secrets.token_urlsafe(32)
    TOKEN_PATH.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(TOKEN_PATH, 0o600)
    except OSError:
        pass
    return token


API_TOKEN = load_api_token()
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

    def authenticated(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        return hmac.compare_digest(header[7:].strip(), API_TOKEN)

    def require_auth(self) -> bool:
        """Send 401 and return False when the caller has no valid token."""
        if self.authenticated():
            return True
        encoded = json.dumps({"error": "unauthorized"}).encode("utf-8")
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Bearer realm="herbie"')
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
        return False

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
            # Liveness stays reachable without a token so existing monitoring
            # keeps working, but unauthenticated callers get only the minimum.
            if self.authenticated():
                self.send_json(200, snapshot())
            else:
                self.send_json(
                    200,
                    {
                        "service": "pal-phone-brain",
                        "service_current": "herbie-phone-brain",
                        "identity_name": "Herbie",
                        "version": SERVICE_VERSION,
                        "ready": True,
                        "authenticated": False,
                        "motor_authority": False,
                        "safe_motion_state": "STOP",
                    },
                )
            return
        if not self.require_auth():
            return
        if parsed.path == "/v1/export":
            include_inactive = parse_qs(parsed.query).get(
                "include_inactive", ["true"]
            )[0].lower() not in {"false", "0", "no"}
            self.send_json(200, herbie_memory.export_all(include_inactive))
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
        if parsed.path == "/v1/mood":
            self.send_json(200, herbie_autonomic.mood_snapshot())
            return
        if parsed.path == "/v1/voice":
            # Preview how Herbie would sound right now, without speaking.
            params = herbie_voice.voice_params()
            params.update(
                {
                    "engine": "termux-tts-speak",
                    "local_only": True,
                    "cost": "none",
                    "motor_authority": False,
                    "safe_motion_state": "STOP",
                }
            )
            self.send_json(200, params)
            return
        if parsed.path == "/v1/urge":
            # Peek without claiming, so a poller cannot silently swallow one.
            state = herbie_memory.autonomic_snapshot()
            self.send_json(
                200,
                {
                    "pending_urge": state["pending_urge"] or None,
                    "pending_since": state["pending_urge_at"],
                    "motor_authority": False,
                    "safe_motion_state": "STOP",
                },
            )
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
            order = params.get("order", [""])[0]
            try:
                memories = herbie_memory.recent(limit, query, order)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
                return
            self.send_json(
                200,
                {
                    "memories": memories,
                    "search": "fts5" if herbie_memory.FTS_AVAILABLE else "substring",
                },
            )
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
            "/v1/forget",
            "/v1/restore",
            "/v1/correct",
            "/v1/interact",
            "/v1/urge",
            "/v1/autonomic",
            "/v1/speak/stop",
        }:
            self.send_json(404, {"error": "not_found"})
            return

        if not self.require_auth():
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
            herbie_autonomic.note_interaction()
            response.update({"motor_authority": False, "safe_motion_state": "STOP"})
        elif self.path == "/v1/experience":
            try:
                response = herbie_memory.experience(request)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
                return
            herbie_autonomic.note_interaction()
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
        elif self.path == "/v1/interact":
            # Someone engaged with Herbie: discharge the drives that satisfies.
            source = request.get("source", "unknown")
            if not isinstance(source, str) or not 1 <= len(source) <= 64:
                self.send_json(400, {"error": "invalid_source"})
                return
            response = {
                "acknowledged": True,
                "drives": herbie_autonomic.note_interaction(),
                "motor_authority": False,
                "safe_motion_state": "STOP",
            }
        elif self.path == "/v1/speak/stop":
            response = herbie_voice.stop()
        elif self.path == "/v1/urge":
            # Claim the pending urge. Returns words and a face, never motion.
            urge = herbie_autonomic.take_urge()
            if urge is None:
                self.send_json(200, {"urge": None, "motor_authority": False,
                                     "safe_motion_state": "STOP"})
                return
            try:
                herbie_memory.set_expression({"expression": urge["expression"]})
            except ValueError:
                pass
            # Close the loop: an impulse that only appears in an HTTP response
            # is not initiative. Silent night-time urges change the face only.
            urge["spoken"] = False
            if urge.get("text") and not urge.get("silent"):
                try:
                    herbie_voice.speak(
                        {"text": urge["text"], "expression": urge["expression"]}
                    )
                    urge["spoken"] = True
                except (ValueError, RuntimeError):
                    pass  # No TTS on this device; the face still changes.
            response = urge
        elif self.path == "/v1/autonomic":
            enabled = request.get("enabled")
            if not isinstance(enabled, bool):
                self.send_json(400, {"error": "invalid_enabled"})
                return
            herbie_memory.autonomic_update(enabled=enabled)
            response = {
                "autonomic_enabled": enabled,
                "motor_authority": False,
                "safe_motion_state": "STOP",
            }
        elif self.path in {"/v1/forget", "/v1/restore", "/v1/correct"}:
            action = {
                "/v1/forget": herbie_memory.forget,
                "/v1/restore": herbie_memory.restore,
                "/v1/correct": herbie_memory.correct,
            }[self.path]
            try:
                response = action(request)
            except ValueError as exc:
                status = 404 if str(exc) == "memory_not_found" else 400
                self.send_json(status, {"error": str(exc)})
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
    print(
        "Memory search: "
        + ("FTS5" if herbie_memory.FTS_AVAILABLE else "substring fallback"),
        flush=True,
    )
    # Never print the token itself - only where to find it.
    print(f"API token file: {TOKEN_PATH} (send as: Authorization: Bearer <token>)", flush=True)
    print("Motor authority: disabled; safe motion state: STOP", flush=True)
    AUTONOMIC.start()
    print(
        f"Autonomic layer: ticking every {herbie_autonomic.TICK_SECONDS:g}s "
        "(mood, drives, circadian rhythm, initiative)",
        flush=True,
    )
    print(
        "Voice: local Android TTS, prosody from mood, no API key, no cost",
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        AUTONOMIC.stop()
        server.server_close()


if __name__ == "__main__":
    main()
