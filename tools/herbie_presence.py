#!/usr/bin/env python3
"""Talk to Herbie's existing Galaxy brain without touching the motor controller."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


PHONE_SERIAL = "R5CR11QCHPY"
LOCAL_URL = "http://127.0.0.1:18765"
TOKEN_FILE = Path.home() / ".herbie" / "api-token"
REPO = Path(__file__).resolve().parents[1]
ADB_CANDIDATES = (
    REPO / "tools" / "scrcpy-win64-v4.1" / "scrcpy-win64-v4.1" / "adb.exe",
    Path.home() / "Desktop" / "Herbie" / ".tools" / "platform-tools" / "adb.exe",
)


def request(path: str, token: str = "", body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(LOCAL_URL + path, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=180 if path == "/v1/chat" else 8) as response:
        return json.load(response)


def connect() -> str:
    adb = next((p for p in ADB_CANDIDATES if p.is_file()), None)
    if adb is None:
        raise RuntimeError("ADB is missing from the known Herbie tool locations")
    if not TOKEN_FILE.is_file():
        raise RuntimeError("Galaxy API token missing; export it with tools/Export-Herbie-Token.ps1")
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError("Galaxy API token file is empty")
    devices = subprocess.run([str(adb), "devices"], capture_output=True, text=True,
                             timeout=12, check=True).stdout
    if not any(line.split()[:2] == [PHONE_SERIAL, "device"] for line in devices.splitlines()):
        raise RuntimeError("Galaxy S21 is not connected and authorized over ADB")
    subprocess.run([str(adb), "-s", PHONE_SERIAL, "forward", "tcp:18765", "tcp:8765"],
                   capture_output=True, text=True, timeout=12, check=True)
    health = request("/health", token)
    if (health.get("ready") is not True
            or health.get("motor_authority") is not False
            or health.get("safe_motion_state") != "STOP"):
        raise RuntimeError("Galaxy brain is not ready in its motor disabled state")
    return token


def talk(token: str, message: str) -> str:
    result = request("/v1/chat", token, {"message": message, "max_tokens": 128})
    if result.get("motor_authority") is not False or result.get("safe_motion_state") != "STOP":
        raise RuntimeError("Chat response failed the motor safety check")
    reply = result.get("text")
    if not isinstance(reply, str) or not reply.strip():
        raise RuntimeError("Galaxy model returned no reply")
    reply = reply.strip()
    request("/v1/speak", token, {"text": reply[:1000]})
    return reply


def main() -> int:
    try:
        token = connect()
        print("Herbie is ready. Type a message; Ctrl+C or an empty line exits.")
        while True:
            try:
                message = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not message:
                break
            try:
                print("Herbie:", talk(token, message))
            except urllib.error.HTTPError as exc:
                print(f"Herbie could not answer (HTTP {exc.code}).", file=sys.stderr)
            except (OSError, ValueError, RuntimeError) as exc:
                print(f"Herbie could not answer: {exc}", file=sys.stderr)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError,
            urllib.error.URLError) as exc:
        print(f"Herbie is unavailable: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
