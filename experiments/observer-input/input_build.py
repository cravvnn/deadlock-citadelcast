"""Current narrow external-input build review, not native compatibility.

6812: see analysis/LIVE-UPDATE-6812-20261021.md and review-6812-*.json.
Installed engine bytes match6810; named spectator registrations were compared
on disk against the retained6810 client. This helper uses Windows input and no
game offsets, native bridge, console transport, hooks or pose access. Updated
live acceptance/quality is pending; this does not certify the replay backend.
Frozen6810 evidence remains in input_build_6810.py, which is no longer imported.
"""
import hashlib

from normal_console_probe import EXE

BUILD = 6812
PINS = {
    "client.dll": "23b89cd1834420e6e8e593d4205c64ee79c4a712bfffef93c7abbacc0dc19041",
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
