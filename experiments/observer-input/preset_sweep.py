"""Finite relative mouse presets. No XYZ telemetry, keyboard input or teleport.

Uses the Test3 normal-process, build, cancellation and countdown lifecycle.
Presets describe input deltas, not world coordinates or calibrated angles.
"""
import ctypes
from ctypes import wintypes
from dataclasses import asdict, dataclass
import math

from mouse_trial import Input, MouseEnvironment, MouseInput, MouseSession, normal_identity, verify_abi
from input_build import verify_input_modules

SHOTS = {"lane": ("Lane panorama", 480, 0),
         "reveal": ("Walker / lane reveal", 360, 240),
         "tilt_check": ("Small tilt direction check", 0, 40)}
SIZES = {"small": .5, "medium": 1., "large": 1.5}


@dataclass(frozen=True)
class Sweep:
    shot: str = "lane"
    size: str = "medium"
    duration: int = 6
    direction: str = "right"
    invert_y: bool = False

    def __post_init__(self):
        if (self.shot not in SHOTS or self.size not in SIZES or
                type(self.duration) is not int or self.duration not in (4, 6, 8) or
                self.direction not in ("left", "right") or type(self.invert_y) is not bool):
            raise ValueError("Select a listed preset, size, duration and direction")

    @property
    def seconds(self):
        return 2 if self.shot == "tilt_check" else self.duration

    def endpoint(self):
        _, dx, dy = SHOTS[self.shot]
        scale = 1 if self.shot == "tilt_check" else SIZES[self.size]
        return (round(dx * scale) * (-1 if self.direction == "left" else 1),
                round(dy * scale) * (-1 if self.invert_y else 1))

    def position(self, index):
        final = self.seconds * 120
        if type(index) is not int or not 0 <= index <= final:
            raise ValueError("Preset schedule index is outside its finite bounds")
        u = index / final
        # Quintic easing has zero velocity and acceleration at both endpoints.
        blend = u ** 3 * (10 + u * (-15 + 6 * u))
        return tuple(round(value * blend) for value in self.endpoint())


def xy_packet(dx, dy):
    if (type(dx) is not int or type(dy) is not int or
            not -8 <= dx <= 8 or not -8 <= dy <= 8 or (dx == 0 and dy == 0)):
        raise ValueError("Relative mouse step exceeds the finite preset bound")
    result = Input()
    result.type = 0
    result.mi = MouseInput(dx, dy, 0, 0x0001, 0, 0)
    return result


class SweepEnvironment(MouseEnvironment):
    def inspect(self):
        return {"modules": verify_input_modules(), "process": normal_identity(), "abi": verify_abi()}

    def send_xy(self, dx, dy):
        verify_abi()
        event = xy_packet(dx, dy)
        api = ctypes.WinDLL("user32", use_last_error=True)
        api.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
        api.SendInput.restype = wintypes.UINT
        if api.SendInput(1, ctypes.byref(event), ctypes.sizeof(Input)) != 1:
            raise ValueError("Windows did not accept the preset mouse event; stopped without retry")


def execute_sweep(environment, pid, cancel, evidence, selection):
    endpoint = selection.endpoint()
    evidence.update(preset=asdict(selection), requested_send_hz=120,
                    duration_seconds=selection.seconds, planned_relative_xy=list(endpoint),
                    inserted_relative_xy=[0, 0], sent=[], skipped=0,
                    actual_world_position=None, actual_camera_angles=None)
    previous, position, complete = -1, (0, 0), False
    final = selection.seconds * 120
    for tick in environment.ticks(120, selection.seconds):
        if cancel.is_set() or not environment.active(pid):
            raise ValueError("Stopped by Escape/WASD/mouse button, focus loss or operator Stop")
        index = tick["index"]
        if type(index) is not int or not previous < index <= final or index < 0:
            raise ValueError("Invalid or repeated preset schedule sample")
        if (not math.isfinite(tick["elapsed"]) or not math.isfinite(tick["lateness_ms"]) or
                tick["lateness_ms"] > 50 or
                tick["elapsed"] - min((previous + 1) / 120, selection.seconds) > .05):
            raise ValueError("Scheduling stall; stopped without a catch-up burst")
        target = selection.position(index)
        dx, dy = target[0] - position[0], target[1] - position[1]
        if dx or dy:
            xy_packet(dx, dy)  # Validate fixtures identically; no silent clamping.
            environment.send_xy(dx, dy)
            evidence["sent"].append({"elapsed": tick["elapsed"], "deadline": index / 120,
                "lateness_ms": tick["lateness_ms"], "relative_dx": dx, "relative_dy": dy})
            evidence["inserted_relative_xy"][0] += dx
            evidence["inserted_relative_xy"][1] += dy
        evidence["skipped"] += max(0, index - previous - 1)
        previous, position, complete = index, target, index == final
    if not complete:
        raise ValueError("Preset ended before its endpoint; partial trace retained")


class SweepSession(MouseSession):
    ready_message = "Game found. Place the camera manually, choose a preset and confirm the starting view."

    def __init__(self, output, environment=None):
        super().__init__(output, environment or SweepEnvironment())

    def selection(self, mode, data):
        if mode not in ("inspect", "pan") or not isinstance(data, dict):
            raise ValueError("Select Inspect or a listed preset")
        if mode == "inspect":
            if data:
                raise ValueError("Inspection takes no preset fields")
            return None
        if set(data) - {"off_air", "shot", "size", "duration", "direction", "invert_y"}:
            raise ValueError("Unexpected preset fields; arbitrary input and console commands are unavailable")
        if data.get("off_air") is not True:
            raise ValueError("Confirm off-air observer fly cam and a manually staged starting view")
        try:
            return Sweep(**{key: value for key, value in data.items() if key != "off_air"})
        except (TypeError, KeyError):
            raise ValueError("Select the listed preset settings") from None

    def execute(self, pid, evidence, selection):
        self.note(f"{SHOTS[selection.shot][0]} running for {selection.seconds}s. Escape or Alt-Tab stops it.")
        execute_sweep(self.env, pid, self.cancel, evidence, selection)
        self.note("Preset finished. Manually stage the view again before another take; no automatic return.")
