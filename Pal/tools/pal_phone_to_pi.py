import json
import urllib.request

req = urllib.request.Request(
    "http://127.0.0.1:18767/v1/heartbeat",
    data=b'{"source":"phone-brain"}',
    method="POST",
)
req.add_header("Content-Type", "application/json")
body = json.loads(urllib.request.urlopen(req, timeout=5).read().decode())
print("PHONE_TO_PI_ACK=" + str(body.get("acknowledged")))
print("MOTOR=" + str(body.get("motor_authority")))
print("SAFE=" + str(body.get("safe_motion_state")))
print("SERVICE=" + str(body.get("service")))
if not (
    body.get("acknowledged") is True
    and body.get("motor_authority") is False
    and body.get("safe_motion_state") == "STOP"
    and body.get("service") == "pal-pi-bridge"
):
    raise SystemExit(2)
