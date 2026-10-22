"""Narrow build identity for external mouse presets, not native compatibility.

Reviewed against the installed files and canonical HANDOFF-LIVE-6810.md on
2026-10-21. The client matches its owned paused-replay finding; engine bytes
are unchanged from the prior Live review. This helper uses no client offsets,
native bridge, hooks, console transport or camera-memory access. Live input
acceptance and visual quality still require the operator's private-session test.
The old Test2 console and Test3 build gates remain untouched.
"""
import hashlib

from normal_console_probe import EXE

BUILD = 6810
PINS = {
    "client.dll": "5c50c21e71a976161968da71c4ed8f69ddfacda2aa035108a2dbfc2f2c149354",
    "engine2.dll": "f7dd5763050e203361809360b4354ef3f768753bb6e43fb314d4822065d28da6",
}


def verify_input_modules():
    paths = {"client.dll": EXE.parents[2] / "citadel/bin/win64/client.dll",
             "engine2.dll": EXE.parent / "engine2.dll"}
    found = {}
    for name, path in paths.items():
        with path.open("rb") as stream:
            found[name] = hashlib.file_digest(stream, "sha256").hexdigest()
        if found[name] != PINS[name]:
            raise ValueError(f"Installed {name} differs from the Live input review for build {BUILD}; no input sent")
    return found
