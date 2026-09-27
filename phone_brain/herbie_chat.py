"""Route one bounded Herbie reply: cloud first, then the PC, then the phone model."""

from __future__ import annotations

import ipaddress
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import herbie_cloud


PHONE_BRIDGE_URL = "http://127.0.0.1:8766"
MAX_MESSAGE_CHARS = 4_000
MAX_CONTEXT_CHARS = 8_000
MAX_OUTPUT_TOKENS = 256
PHONE_CONTEXT_CHARS = 2_000


class ChatUnavailable(RuntimeError):
    pass


def bridge_token_path() -> Path:
    return Path(
        os.environ.get(
            "HERBIE_MODEL_BRIDGE_TOKEN_FILE",
            Path(__file__).resolve().parent / "herbie-model-bridge-token",
        )
    )


def load_bridge_token() -> str:
    value = os.environ.get("HERBIE_MODEL_BRIDGE_TOKEN", "").strip()
    if not value:
        try:
            value = bridge_token_path().read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
    if len(value) < 16:
        raise ChatUnavailable("phone_model_bridge_not_provisioned")
    return value


def validate_local_url(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid_inference_url")
    parsed = urlsplit(value.strip().rstrip("/"))
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("invalid_inference_url")
    try:
        address = ipaddress.ip_address(parsed.hostname.split("%", 1)[0])
    except ValueError as exc:
        raise ValueError("inference_url_must_use_ip_address") from exc
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    if not (address.is_loopback or address.is_link_local or address.is_private):
        raise ValueError("inference_url_must_be_local")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("invalid_inference_url")
    if parsed.port is None:
        raise ValueError("inference_url_requires_port")
    return value.strip().rstrip("/")


def validate_request(payload: dict[str, Any]) -> tuple[str, int]:
    message = payload.get("message", "")
    max_tokens = payload.get("max_tokens", 96)
    if not isinstance(message, str) or not message.strip():
        raise ValueError("invalid_message")
    if len(message) > MAX_MESSAGE_CHARS:
        raise ValueError("message_too_long")
    if not isinstance(max_tokens, int) or isinstance(max_tokens, bool):
        raise ValueError("invalid_max_tokens")
    if not 1 <= max_tokens <= MAX_OUTPUT_TOKENS:
        raise ValueError("invalid_max_tokens")
    return message.strip(), max_tokens


def post_local_chat(
    endpoint: str,
    token: str,
    message: str,
    context: str,
    max_tokens: int,
    timeout: float,
) -> dict[str, Any]:
    endpoint = validate_local_url(endpoint)
    body = json.dumps(
        {"message": message, "context": context[:MAX_CONTEXT_CHARS], "max_tokens": max_tokens},
        separators=(",", ":"),
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint + "/v1/chat",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read())
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise ChatUnavailable(str(exc)) from exc
    if not isinstance(result, dict) or not isinstance(result.get("text"), str):
        raise ChatUnavailable("model_bridge_returned_no_text")
    result["motor_authority"] = False
    result["safe_motion_state"] = "STOP"
    return result


def post_bridge_voice(path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """Ask the on-phone bridge app to speak (/v1/speak) or hush (/v1/speak/stop).

    The bridge owns Android's TTS because Termux:API's hung on this phone. It
    answers /v1/speak once the utterance has finished playing.
    """
    if path not in ("/v1/speak", "/v1/speak/stop"):
        raise ValueError("invalid_voice_path")
    request = urllib.request.Request(
        PHONE_BRIDGE_URL + path,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {load_bridge_token()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read())
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise ChatUnavailable(str(exc)) from exc
    if not isinstance(result, dict):
        raise ChatUnavailable("model_bridge_returned_no_result")
    return result


def wait_for_phone_bridge(timeout: float = 20.0) -> bool:
    """Allow Android to restore the sticky foreground model service after pressure."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(PHONE_BRIDGE_URL + "/health", timeout=1.0) as response:
                health = json.loads(response.read())
            if health.get("ready") is True and health.get("motor_authority") is False:
                return True
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    return False


def route_chat(
    payload: dict[str, Any],
    *,
    computer_available: bool,
    computer_url: str | None,
    computer_token: str,
    context: str,
) -> dict[str, Any]:
    message, max_tokens = validate_request(payload)
    primary_error = None
    # Cloud first when provisioned and online; any failure or refusal falls
    # through, so Herbie keeps talking with no network.
    try:
        return herbie_cloud.chat(message, context, max_tokens)
    except herbie_cloud.CloudUnavailable:
        pass
    if computer_available and computer_url:
        try:
            return post_local_chat(
                computer_url,
                computer_token,
                message,
                context,
                max_tokens,
                timeout=180.0,
            )
        except ChatUnavailable as exc:
            primary_error = str(exc)
    try:
        if not wait_for_phone_bridge():
            raise ChatUnavailable("phone_model_bridge_not_ready")
        result = post_local_chat(
            PHONE_BRIDGE_URL,
            load_bridge_token(),
            message,
            # Enough memory for the small offline model without slowing it much.
            context[:PHONE_CONTEXT_CHARS],
            min(max_tokens, 128),
            timeout=300.0,
        )
    except ChatUnavailable as exc:
        detail = "phone_fallback_unavailable"
        if primary_error:
            detail = "computer_and_phone_models_unavailable"
        raise ChatUnavailable(detail) from exc
    result["brain"] = "phone-local"
    if primary_error:
        result["fell_back_from_computer"] = True
    return result
