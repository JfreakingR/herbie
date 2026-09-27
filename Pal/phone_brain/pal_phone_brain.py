#!/data/data/com.termux/files/usr/bin/python
"""Persistent, safety-bounded service for Herbie's Galaxy S21 Ultra brain."""

from __future__ import annotations

import hmac
import ipaddress
import json
import os
import secrets
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import herbie_autonomic
import herbie_chat
import herbie_memory
import herbie_voice


SERVICE_VERSION = "0.11.0"
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
CONVERSATION_LOCK = threading.Lock()
RECENT_DIALOGUE: deque[dict[str, str]] = deque(maxlen=12)
STATE: dict[str, Any] = {
    "heartbeat_count": 0,
    "last_heartbeat_monotonic": None,
    "last_source": None,
    "primary_source": None,
    "primary_last_seen_monotonic": None,
    "primary_lease_seconds": 15,
    "primary_inference_url": None,
}
NETWORK_SCOPE = "device-only"


def is_local_network_address(address: str) -> bool:
    """Return whether a client address belongs to this device or a local LAN."""
    try:
        parsed = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped:
        parsed = parsed.ipv4_mapped
    return parsed.is_loopback or parsed.is_link_local or parsed.is_private


def snapshot() -> dict[str, Any]:
    with STATE_LOCK:
        last_heartbeat = STATE["last_heartbeat_monotonic"]
        return {
            "service": "pal-phone-brain",
            "service_current": "herbie-phone-brain",
            "identity_name": "Herbie",
            "version": SERVICE_VERSION,
            "network_scope": NETWORK_SCOPE,
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


def coordination_snapshot(now: float | None = None) -> dict[str, Any]:
    """Report who is coordinating without moving memory off the phone."""
    current = time.monotonic() if now is None else now
    with STATE_LOCK:
        source = STATE["primary_source"]
        last_seen = STATE["primary_last_seen_monotonic"]
        lease = STATE["primary_lease_seconds"]
        age = None if last_seen is None else max(0.0, current - last_seen)
        primary_available = bool(source and age is not None and age <= lease)
        return {
            "active_brain": source if primary_available else "phone-local",
            "computer_primary_available": primary_available,
            "phone_fallback_ready": True,
            "lease_seconds": lease,
            "seconds_since_primary": None if age is None else round(age, 3),
            "memory_writer": "phone",
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

    def require_local_client(self) -> bool:
        if is_local_network_address(self.client_address[0]):
            return True
        self.send_json(403, {"error": "local_network_only"})
        return False

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
        if not self.require_local_client():
            return
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
                        "network_scope": NETWORK_SCOPE,
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
        if parsed.path == "/v1/coordination":
            self.send_json(200, coordination_snapshot())
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
        if not self.require_local_client():
            return
        if self.path not in {
            "/v1/chat",
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
            role = request.get("role", "observer")
            if role not in {"observer", "computer-primary"}:
                self.send_json(400, {"error": "invalid_role"})
                return
            lease_seconds = request.get("lease_seconds", 15)
            if not isinstance(lease_seconds, int) or not 5 <= lease_seconds <= 60:
                self.send_json(400, {"error": "invalid_lease_seconds"})
                return
            inference_url = request.get("inference_url")
            if role == "computer-primary" and inference_url is not None:
                try:
                    inference_url = herbie_chat.validate_local_url(inference_url)
                except ValueError as exc:
                    self.send_json(400, {"error": str(exc)})
                    return
            with STATE_LOCK:
                STATE["heartbeat_count"] += 1
                STATE["last_heartbeat_monotonic"] = time.monotonic()
                STATE["last_source"] = source
                if role == "computer-primary":
                    STATE["primary_source"] = source
                    STATE["primary_last_seen_monotonic"] = STATE["last_heartbeat_monotonic"]
                    STATE["primary_lease_seconds"] = lease_seconds
                    if inference_url is not None:
                        STATE["primary_inference_url"] = inference_url
            response = snapshot()
            response["acknowledged"] = True
            response["coordination"] = coordination_snapshot()
        elif self.path == "/v1/chat":
            coordination = coordination_snapshot()
            with STATE_LOCK:
                computer_url = STATE["primary_inference_url"]
            identity = herbie_memory.self_snapshot()
            relevant_memories = herbie_memory.recent(
                2,
                request.get("message", "")[:500],
                "relevance",
            )
            with CONVERSATION_LOCK:
                recent_dialogue = list(RECENT_DIALOGUE)[-6:]
            trait_text = ", ".join(
                f"{name}={float(value):.2f}"
                for name, value in identity.get("personality", {}).items()
            )
            context_lines = [
                f"Identity: {identity.get('name', 'Herbie')}.",
                f"Personality: {trait_text}.",
            ]
            if relevant_memories:
                context_lines.append("Relevant long-term memory:")
                context_lines.extend(
                    f"- {memory['content'][:300]}" for memory in relevant_memories
                )
            if recent_dialogue:
                context_lines.append("Recent conversation:")
                context_lines.extend(
                    f"{turn['role'].title()}: {turn['content'][:400]}"
                    for turn in recent_dialogue
                )
            context = "\n".join(context_lines)
            try:
                response = herbie_chat.route_chat(
                    request,
                    computer_available=coordination["computer_primary_available"],
                    computer_url=computer_url,
                    computer_token=API_TOKEN,
                    context=context,
                )
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
                return
            except herbie_chat.ChatUnavailable as exc:
                self.send_json(503, {"error": str(exc), "coordination": coordination})
                return
            with CONVERSATION_LOCK:
                RECENT_DIALOGUE.append(
                    {"role": "user", "content": request["message"].strip()}
                )
                RECENT_DIALOGUE.append(
                    {"role": "assistant", "content": response["text"].strip()}
                )
            herbie_autonomic.note_interaction()
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
    global NETWORK_SCOPE
    herbie_memory.initialize()
    host = os.environ.get("HERBIE_PHONE_HOST", os.environ.get("PAL_PHONE_HOST", "127.0.0.1"))
    port = int(os.environ.get("HERBIE_PHONE_PORT", os.environ.get("PAL_PHONE_PORT", "8765")))
    NETWORK_SCOPE = "device-only" if host in {"127.0.0.1", "::1", "localhost"} else "local-network"
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
