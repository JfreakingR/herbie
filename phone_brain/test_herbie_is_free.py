"""Herbie must cost nothing to run. This asserts it, rather than assuming it.

Owner requirement: no paid API, no subscription, no metered service. Everything
runs on hardware already owned — Android's built-in TTS, the phone's own
microphone and camera, SQLite, and the Python standard library.

The risk this guards against is drift: a future session reaching for a hosted
model "just for now" and quietly introducing a bill and an outbound data path.
A failing test is a much better guard than a note in a handoff.
"""

import ast
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PI_BRIDGE = HERE.parent / "pi_bridge"

# Modules that make up the running system. Tests and parked experiments are
# checked too, so nothing sneaks in through a helper.
def source_files():
    # This file is excluded: it necessarily contains the very markers it looks
    # for, and scanning itself would make the audit fail on its own vocabulary.
    for folder in (HERE, PI_BRIDGE):
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.py")):
            if path.name == Path(__file__).name:
                continue
            yield path


PAID_SERVICE_MARKERS = [
    "api.openai.com",
    "openai",
    "anthropic",
    "api.elevenlabs",
    "elevenlabs",
    "azure.cognitiveservices",
    "speech.googleapis",
    "texttospeech.googleapis",
    "aws_access_key",
    "boto3",
    "polly",
    "watsonplatform",
    "deepgram",
    "assemblyai",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
]

# Standard library only. Anything else is a dependency someone has to install,
# and a chance for a paid SDK to arrive.
ALLOWED_THIRD_PARTY: set[str] = set()


class CostTests(unittest.TestCase):
    def test_no_paid_service_appears_anywhere(self):
        for path in source_files():
            source = path.read_text(encoding="utf-8").lower()
            for marker in PAID_SERVICE_MARKERS:
                self.assertNotIn(
                    marker.lower(),
                    source,
                    f"{path.name} references {marker}; Herbie must stay free",
                )

    def test_no_api_keys_or_tokens_for_external_services(self):
        for path in source_files():
            source = path.read_text(encoding="utf-8")
            # The local bearer token is Herbie's own and is generated on device;
            # it is not a credential for any paid service.
            for marker in ("sk-", "Bearer sk", "apikey=", "api_key="):
                self.assertNotIn(
                    marker, source, f"{path.name} looks like it carries a credential"
                )

    def test_runtime_modules_import_only_the_standard_library(self):
        runtime = [
            HERE / "pal_phone_brain.py",
            HERE / "herbie_memory.py",
            HERE / "herbie_voice.py",
            HERE / "herbie_autonomic.py",
        ]
        local = {path.stem for path in source_files()}
        stdlib = set(getattr(__import__("sys"), "stdlib_module_names", ()))

        for path in runtime:
            if not path.exists():
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    names = [node.module.split(".")[0]]
                for name in names:
                    if name in local or name in ALLOWED_THIRD_PARTY:
                        continue
                    self.assertIn(
                        name,
                        stdlib,
                        f"{path.name} imports non-stdlib '{name}'; that is a new "
                        "dependency and a possible cost",
                    )

    def test_the_only_external_command_is_the_phones_own_tts(self):
        """Subprocess calls must stay on tools already present on the device."""
        allowed = {
            "termux-tts-speak",
            "termux-wake-lock",
            "termux-wake-unlock",
            "termux-microphone-record",
            "termux-camera-photo",
        }
        for path in source_files():
            if path.name.startswith("test_"):
                continue
            source = path.read_text(encoding="utf-8")
            for line in source.splitlines():
                if "termux-" not in line:
                    continue
                for raw in line.replace('"', " ").replace("'", " ").split():
                    if not raw.startswith("termux-"):
                        continue
                    # Strip prose punctuation: these names appear in comments
                    # and docstrings as well as in argument lists.
                    token = raw.strip(",()[]`.:;")
                    self.assertIn(
                        token,
                        allowed,
                        f"{path.name} calls unexpected tool {token}",
                    )

    def test_no_outbound_network_calls_in_runtime_code(self):
        """Herbie's brain talks to loopback only; nothing phones home."""
        for path in source_files():
            if path.name.startswith("test_"):
                continue
            source = path.read_text(encoding="utf-8")
            for marker in ("urllib.request.urlopen", "http.client", "socket.create_connection"):
                self.assertNotIn(
                    marker,
                    source,
                    f"{path.name} makes outbound calls; the brain should stay local",
                )


if __name__ == "__main__":
    unittest.main()
