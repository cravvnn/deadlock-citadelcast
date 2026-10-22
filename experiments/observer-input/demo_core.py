"""Private bounded angle-only demo. No launcher, injection or memory access.

Camera writes require the caller's current normal-client identity, authenticated
echo and off-air observer confirmation. Host timestamps do not prove application.
"""
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
import time

from normal_console_probe import (EXE, check_process, foreground_pid, perform_probe)
from dolly_live.playback import deadline_ticks

PINS = {
    "client.dll": "96ee2a334a93a6a0f40ed56c0cedf441b882681b9605deeb46d83d62d4a3e4b9",
    "engine2.dll": "f7dd5763050e203361809360b4354ef3f768753bb6e43fb314d4822065d28da6",
}
SHOTS = {
    "comparison": ("Rate comparison", 2., 12., 0., False),
    "cinematic": ("Eased panorama", 6., 45., 0., True),
    "reveal": ("Eased tilt and pan", 4., 20., -15., True),
}


@dataclass(frozen=True)
class Selection:
    shot: str = "comparison"
    rate: int = 60
    pitch: float = 0.
    yaw: float = 0.

    def frames(self):
        if self.shot not in SHOTS or type(self.rate) is not int or self.rate not in (16, 60, 120):
            raise ValueError("Select a listed shot and 16/60/120 Hz")
        for value in (self.pitch, self.yaw):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Angles must be finite numbers")
        _, duration, dyaw, dpitch, eased = SHOTS[self.shot]
        if not -360 <= self.yaw <= 360 or not -89 <= self.pitch <= 89 or not -89 <= self.pitch + dpitch <= 89:
            raise ValueError("Pitch must stay within -89..89 and start yaw within -360..360")
        result = []
        for i in range(round(duration * self.rate) + 1):
            t = i / self.rate
            u = t / duration
            blend = u * u * u * (10 + u * (-15 + 6 * u)) if eased else u
            command = f"spec_setang {self.pitch + dpitch * blend:.2f} {self.yaw + dyaw * blend:.2f}"
            result.append((t, command))
        return tuple(result)


def verify_modules():
    paths = {"client.dll": EXE.parents[2] / "citadel/bin/win64/client.dll",
             "engine2.dll": EXE.parent / "engine2.dll"}
    found = {}
    for name, path in paths.items():
        with path.open("rb") as stream:
            found[name] = hashlib.file_digest(stream, "sha256").hexdigest()
        if found[name] != PINS[name]:
            raise ValueError("Installed " + name + " differs from the reviewed build 6807; no connection")
    return found


def execute_angles(client, selection, *, active, evidence, ticks=deadline_ticks, clock=time.perf_counter):
    """No raw text inputs. Frozen finite schedule; no resetting on completion/fault."""
    frames = selection.frames()
    duration = frames[-1][0]
    evidence.update({"shot": selection.shot, "requested_send_hz": selection.rate,
                     "duration_seconds": duration, "sent": [], "skipped": 0})
    last = -1
    complete = False
    for tick in ticks(selection.rate, duration):
        if not active():
            raise ValueError("Operator stop, foreground loss or manual movement key")
        if tick["lateness_ms"] > 50 or tick["elapsed"] - min((last + 1) / selection.rate, duration) > .05:
            raise ValueError("Scheduling stall; no catch-up burst")
        index = tick["index"]
        if type(index) is not int or not last < index < len(frames):
            raise ValueError("Invalid or repeated scheduling index")
        intended, command = frames[index]
        if not re.fullmatch(r"spec_setang -?\d+\.\d{2} -?\d+\.\d{2}", command):
            raise ValueError("Command outside angle-only allowlist")
        evidence["skipped"] += index - last - 1
        before = clock()
        client.send(command)
        evidence["sent"].append({"command": command, "deadline": intended,
            "elapsed": tick["elapsed"], "lateness_ms": tick["lateness_ms"],
            "send_duration_ms": (clock() - before) * 1000})
        last = index
        complete = index == len(frames) - 1
    if not complete:
        raise ValueError("Schedule ended before the endpoint; partial trace retained")


def self_check():
    class Console:
        def __init__(self):
            self.commands = []
        def send(self, command):
            self.commands.append(command)
    def ticks(rate, duration):
        return ({"index": i, "elapsed": i / rate, "lateness_ms": 0.}
                for i in range(round(rate * duration) + 1))
    for shot in SHOTS:
        for rate in (16, 60, 120):
            selection = Selection(shot, rate, 10., 90.)
            client, evidence = Console(), {}
            execute_angles(client, selection, active=lambda: True, evidence=evidence, ticks=ticks)
            _, duration, yaw, pitch, _ = SHOTS[shot]
            assert len(client.commands) == round(duration * rate) + 1
            assert client.commands[0] == "spec_setang 10.00 90.00"
            assert client.commands[-1] == f"spec_setang {10 + pitch:.2f} {90 + yaw:.2f}"
            assert evidence["skipped"] == 0
            assert not any(";" in c or "spec_goto" in c for c in client.commands)
    for selection in (Selection("arbitrary"), Selection(rate=240), Selection(pitch=float("nan")),
                      Selection(pitch=90), Selection("reveal", pitch=-80)):
        try:
            selection.frames()
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid shot accepted")
    for active, stream, expected in (
        (lambda: False, [{"index": 0, "elapsed": 0, "lateness_ms": 0}], 0),
        (iter([True, False]).__next__, list(ticks(60, 2)), 1),
        (lambda: True, [{"index": 12, "elapsed": .2, "lateness_ms": 60}], 0),
        (lambda: True, [{"index": 0, "elapsed": 0, "lateness_ms": 0}], 1),
    ):
        client, evidence = Console(), {}
        try:
            execute_angles(client, Selection(), active=active, evidence=evidence,
                           ticks=lambda rate, duration: iter(stream))
        except ValueError:
            assert len(client.commands) == expected
            assert len(evidence["sent"]) == expected
        else:
            raise AssertionError("Interrupted schedule reported complete")
    # Independent midpoint/quarter reference for quintic easing, including tilt.
    frames = Selection("reveal", 60, 10, 90).frames()
    assert frames[60][1] == "spec_setang 8.45 92.07"
    assert frames[120][1] == "spec_setang 2.50 100.00"
    print("PASS: 9 finite angle schedules, endpoint/easing/allowlist/abort/stall/partial traces; simulated only.")
