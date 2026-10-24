"""Current narrow external-input build review, not native compatibility.

6819: reviewed2026-10-22 after the exact6817 gate refused the updated client.
Named spectator/lens registrations and pitch/angle callbacks retain their
instruction structure. Selected orientation getters and the old ThirdPerson
roll-zero output remain unchanged; moved external targets are recorded locally.
This does not undo the separate positive file-camera bank result. Engine, tier0,
network and Steam Input manifest bytes are unchanged. Disk and Windows INPUT ABI
checks are not live compatibility or complete callee/native qualification.

This Windows-input helper has no game offsets, hooks, pose access or console
transport. Dev/insecure refusal, cancellation and key-release guards persist.
Changed modules refuse before input. Prior exact gates/reviews are retained.
"""
import hashlib

from normal_console_probe import EXE

BUILD = 6819
PINS = {
    "client.dll": "c09143cf9cd722909404c64e3ffa05157afc15e8a3519b49a1396a627af8ca85",
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
