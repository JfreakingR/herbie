#!/usr/bin/env python3
"""Computer-primary lease coordinator for Herbie.

The Galaxy remains the only memory writer and becomes active automatically when
this process stops renewing its short lease.

With --neck it also drives Herbie's neck (the camera wheel on his head): each
cycle it tells the phone which way the head faces and takes any look a brain
asked for, then turns the wheel through tools/Herbie-Look.py. That is the only
actuator it can reach. The wheels stay off - there is no drive path here.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import ipaddress
import json
import os
import socket
import importlib.util
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_PORT = 8765
DEFAULT_BRAIN_PORT = 18766
DEFAULT_INTERVAL = 5.0
DEFAULT_LEASE = 15
SOURCE = "windows-computer"
LOOK_TOOL = Path(__file__).resolve().parent.parent / "tools" / "Herbie-Look.py"


def private_directory() -> Path:
    profile = os.environ.get("USERPROFILE") or str(Path.home())
    return Path(profile) / ".herbie"


def token_path() -> Path:
    return private_directory() / "api-token"


def endpoint_path() -> Path:
    return private_directory() / "phone-endpoint.json"


def load_token(path: Path | None = None) -> str:
    candidate = path or token_path()
    token = candidate.read_text(encoding="utf-8").strip()
    if len(token) < 8:
        raise RuntimeError(f"Herbie API token is invalid: {candidate}")
    return token


def normalized_endpoint(value: str) -> str:
    endpoint = value.strip().rstrip("/")
    if not endpoint.startswith(("http://", "https://")):
        endpoint = "http://" + endpoint
    return endpoint


def request_json(
    endpoint: str,
    path: str,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 2.0,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint + path,
        data=body,
        method="GET" if payload is None else "POST",
    )
    if body is not None:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def is_herbie(endpoint: str, timeout: float = 0.4) -> bool:
    try:
        health = request_json(endpoint, "/health", timeout=timeout)
    except (OSError, ValueError, urllib.error.URLError):
        return False
    return health.get("service_current") == "herbie-phone-brain" and bool(
        health.get("ready")
    )


def cached_endpoint(path: Path | None = None) -> str | None:
    candidate = path or endpoint_path()
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
        return normalized_endpoint(data["endpoint"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def save_endpoint(endpoint: str, path: Path | None = None) -> None:
    candidate = path or endpoint_path()
    candidate.parent.mkdir(parents=True, exist_ok=True)
    temporary = candidate.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {"endpoint": endpoint, "verified_at": time.time()}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(candidate)


def local_ipv4() -> str | None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        return probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()


def discover_phone(explicit: str | None = None) -> str:
    candidates: list[str] = []
    if explicit:
        candidates.append(normalized_endpoint(explicit))
    cached = cached_endpoint()
    if cached and cached not in candidates:
        candidates.append(cached)
    for endpoint in candidates:
        if is_herbie(endpoint, timeout=1.5):
            save_endpoint(endpoint)
            return endpoint

    address = local_ipv4()
    if not address:
        raise RuntimeError("No active IPv4 network was found for Herbie discovery.")
    network = ipaddress.ip_network(f"{address}/24", strict=False)
    urls = [f"http://{host}:{DEFAULT_PORT}" for host in network.hosts() if str(host) != address]
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        checks = {pool.submit(is_herbie, url): url for url in urls}
        for future in concurrent.futures.as_completed(checks):
            if future.result():
                endpoint = checks[future]
                save_endpoint(endpoint)
                return endpoint
    raise RuntimeError("Herbie was not found on the local /24 network.")


def inference_url(port: int = DEFAULT_BRAIN_PORT) -> str:
    address = local_ipv4()
    if not address:
        raise RuntimeError("No active IPv4 address is available for PC inference.")
    return f"http://{address}:{port}"


def renew_lease(
    endpoint: str,
    token: str,
    lease_seconds: int,
    brain_url: str | None = None,
) -> dict[str, Any]:
    return request_json(
        endpoint,
        "/v1/heartbeat",
        token=token,
        payload={
            "source": SOURCE,
            "role": "computer-primary",
            "lease_seconds": lease_seconds,
            "inference_url": brain_url or inference_url(),
        },
        timeout=4.0,
    )


class NeckController:
    """Turns the neck for the phone, one look at a time, in a background thread.

    A look takes up to a couple of minutes, so it never blocks lease renewal.
    While one is running the controller reports busy and the phone keeps any
    newer request until it is free.
    """

    def __init__(self, look_module: Any | None = None) -> None:
        self._look = look_module
        self._thread: threading.Thread | None = None

    @property
    def look(self) -> Any:
        if self._look is None:
            spec = importlib.util.spec_from_file_location("herbie_look", LOOK_TOOL)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._look = module
        return self._look

    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def facing(self) -> float | None:
        step = self.look.read_step()
        if step is None:
            return None
        return step * self.look.vava.NECK_DEGREES_PER_STEP

    def poll(self, endpoint: str, token: str) -> int | None:
        """Check in with the phone; start a turn if a look was waiting."""
        busy = self.busy()
        facing = self.facing()
        response = request_json(
            endpoint,
            "/v1/neck/claim",
            token=token,
            payload={"facing": facing, "busy": busy},
            timeout=4.0,
        )
        claimed = response.get("look")
        if not claimed or busy:
            return None
        degrees = int(claimed["degrees"])
        if facing is None:
            print("neck: asked to look but heading unknown - face him forward "
                  "and run `python tools/Herbie-Look.py home`", file=sys.stderr, flush=True)
            return None
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} neck: look {degrees}", flush=True)
        self._thread = threading.Thread(
            target=self.look.main, args=(["herbie-look", str(degrees)],),
            name="herbie-neck", daemon=True,
        )
        self._thread.start()
        return degrees


def run_once(
    endpoint: str | None,
    lease_seconds: int,
    brain_url: str | None = None,
) -> dict[str, Any]:
    token = load_token()
    verified = discover_phone(endpoint)
    response = renew_lease(verified, token, lease_seconds, brain_url)
    coordination = response["coordination"]
    return {
        "endpoint": verified,
        "active_brain": coordination["active_brain"],
        "phone_fallback_ready": coordination["phone_fallback_ready"],
        "memory_writer": coordination["memory_writer"],
        "motor_authority": coordination["motor_authority"],
        "safe_motion_state": coordination["safe_motion_state"],
    }


def run_forever(
    endpoint: str | None,
    interval: float,
    lease_seconds: int,
    brain_url: str | None = None,
    neck: NeckController | None = None,
) -> None:
    token = load_token()
    current = endpoint
    while True:
        try:
            current = discover_phone(current)
            response = renew_lease(current, token, lease_seconds, brain_url)
            coordination = response["coordination"]
            if neck is not None:
                try:
                    neck.poll(current, token)
                except Exception as exc:
                    # A neck hiccup must never cost the lease.
                    print(f"neck: check-in failed: {exc}", file=sys.stderr, flush=True)
            print(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} connected={current} "
                f"active={coordination['active_brain']} fallback=ready",
                flush=True,
            )
            time.sleep(interval)
        except KeyboardInterrupt:
            return
        except Exception as exc:
            # Do not claim the phone is down. The expired lease deliberately
            # makes it independent while this computer retries discovery.
            print(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} computer-disconnected "
                f"phone-fallback=expected error={exc}",
                file=sys.stderr,
                flush=True,
            )
            current = None
            time.sleep(max(interval, 5.0))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phone", help="Herbie phone URL or IP; otherwise discover it")
    parser.add_argument("--once", action="store_true", help="renew one lease and exit")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    parser.add_argument("--lease", type=int, default=DEFAULT_LEASE)
    parser.add_argument(
        "--brain-url",
        help="private-LAN PC inference base URL; defaults to this PC and port 18766",
    )
    parser.add_argument(
        "--neck",
        action="store_true",
        help="let Herbie's brains turn his neck (the camera wheel) through this PC",
    )
    args = parser.parse_args()
    if not 1.0 <= args.interval <= 30.0:
        parser.error("--interval must be between 1 and 30 seconds")
    if not 5 <= args.lease <= 60:
        parser.error("--lease must be between 5 and 60 seconds")

    if args.once:
        print(json.dumps(run_once(args.phone, args.lease, args.brain_url), indent=2))
        return 0
    neck = NeckController() if args.neck else None
    if neck is not None:
        print(f"neck: enabled, facing {neck.facing()}", flush=True)
    run_forever(args.phone, args.interval, args.lease, args.brain_url, neck)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
