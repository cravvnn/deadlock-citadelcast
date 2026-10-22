"""Finite held-key movement with optional relative pan. No hooks/pose access.

Andrew confirmed smooth translation on6812; combined shots await visual testing.
Only helper-owned movement keys are released; no arbitrary key endpoint exists.
"""
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import math
import threading
import time

from mouse_trial import Input, KeyboardInput, MouseSession, verify_abi
from normal_console_probe import foreground_pid
from preset_sweep import SweepEnvironment, xy_packet

# Andrew verified these actual live fly-cam bindings on6810 in this session:
# W forward, left Shift up, left Ctrl down. Shift is not added as a speed boost.
KEYS = {"w": (0x57, 0x11), "ctrl": (0x11, 0x1D), "shift": (0x10, 0x2A)}
PATTERNS = {"forward": "Forward", "up": "Up", "down": "Down",
            "forward_up": "Forward + up", "forward_down": "Forward + down"}
PAN_RATES = {"slow": 60, "standard": 120, "wide": 240}  # Relative units/s, not degrees.


@dataclass(frozen=True)
class Travel:
    pattern: str = "forward"
    duration: float = 1
    pan: str = "none"
    pace: str = "standard"

    def __post_init__(self):
        if (self.pattern not in PATTERNS or type(self.duration) not in (int, float) or
                self.duration not in (.5, 1, 2, 3, 4, 6) or
                self.pan not in ("none", "left", "right") or self.pace not in PAN_RATES):
            raise ValueError("Choose the listed movement, pan, pace and duration settings")
        if self.pan == "none" and self.duration > 3:
            raise ValueError("Translation-only checks stay within three seconds; longer takes require a selected pan")

    def mouse_position(self, index):
        if type(index) is not int or not 0 <= index <= round(self.duration * 120):
            raise ValueError("Pan sample is outside the finite shot bounds")
        if self.pan == "none":
            return 0
        # Integer division gives a uniform cadence at60/120/240units/s;
        # round(index/2) would alternate one- and three-tick packet gaps.
        amount = PAN_RATES[self.pace] * index // 120
        return -amount if self.pan == "left" else amount

    @property
    def held(self):
        keys = ["w"] if "forward" in self.pattern else []
        if "up" in self.pattern:
            keys.append("shift")
        if "down" in self.pattern:
            keys.append("ctrl")
        return tuple(keys)


def key_packet(key, down):
    if key not in KEYS or type(down) is not bool:
        raise ValueError("Only the listed finite movement keys are available")
    event = Input()
    event.type = 1  # INPUT_KEYBOARD, physical scan code, no text or modifiers added.
    event.ki = KeyboardInput(0, KEYS[key][1], 0x0008 | (0 if down else 0x0002), 0, 0)
    return event


class TravelEnvironment(SweepEnvironment):
    def key(self, key, down):
        verify_abi()
        event = key_packet(key, down)
        api = ctypes.WinDLL("user32", use_last_error=True)
        api.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
        api.SendInput.restype = wintypes.UINT
        if api.SendInput(1, ctypes.byref(event), ctypes.sizeof(Input)) != 1:
            raise ValueError("Windows rejected a movement key event")

    def travel_active(self, pid, held):
        if foreground_pid() != pid:
            return False
        api = ctypes.WinDLL("user32", use_last_error=True)
        api.GetAsyncKeyState.argtypes = [ctypes.c_int]
        api.GetAsyncKeyState.restype = ctypes.c_short
        ignored = {KEYS[key][0] for key in held}
        # A selected held key cannot also be a manual takeover signal. All
        # remaining movement controls, Escape/buttons/Alt/Win/Tab stop the take.
        controls = {0x1B, 0x01, 0x02, 0x04, 0x12, 0x5B, 0x5C, 0x09,
                    0x57, 0x41, 0x53, 0x44, 0x20, 0x10, 0x11, 0x51, 0x45}
        return not any(api.GetAsyncKeyState(key) & 0x8000 for key in controls - ignored)

    def countdown(self, cancel, note):
        for remaining in range(5, 0, -1):
            note(f"Focus Deadlock. Movement follows in {remaining}s after a final identity check. Release all movement keys.")
            if cancel.wait(1):
                raise ValueError("Countdown stopped; no movement keys pressed")


class KeyLatch:
    """Serialize Stop against presses; retain failed key-up ownership for recovery."""
    def __init__(self, environment, cancel):
        self.environment, self.cancel = environment, cancel
        self.lock = threading.RLock()
        self.owned = []
        self.evidence = None

    def pending(self):
        with self.lock:
            return tuple(self.owned)

    def detach_evidence(self):
        with self.lock:
            self.evidence = None  # Later Stop recovery must not mutate a saved raw report.
            return tuple(self.owned)

    def press(self, key, evidence):
        with self.lock:
            if self.cancel.is_set():
                raise ValueError("Stopped before movement key press")
            if key in self.owned:
                raise ValueError("Movement key already owned")
            self.evidence = evidence
            self.owned.append(key)  # Cleanup also covers uncertain/failed insertion.
            self.environment.key(key, True)
            evidence["key_events"].append({"key": key, "down": True,
                                           "host_insertion_return": time.perf_counter()})

    def move(self, dx, evidence, tick):
        with self.lock:
            if self.cancel.is_set():
                raise ValueError("Stopped before mouse pan input")
            xy_packet(dx, 0)
            self.environment.send_xy(dx, 0)
            evidence["sent"].append({"elapsed": tick["elapsed"], "deadline": tick["index"] / 120,
                "lateness_ms": tick["lateness_ms"], "relative_dx": dx, "relative_dy": 0,
                "host_insertion_return": time.perf_counter()})
            evidence["inserted_relative_xy"][0] += dx

    def release(self, evidence=None):
        failures = []
        with self.lock:
            evidence = evidence if evidence is not None else self.evidence
            for key in tuple(reversed(self.owned)):
                try:
                    self.environment.key(key, False)  # Key-up even after foreground loss.
                    self.owned.remove(key)
                    if evidence is not None:
                        evidence["key_events"].append({"key": key, "down": False,
                                                       "host_insertion_return": time.perf_counter()})
                except BaseException:
                    failures.append(key)
            if evidence is not None:
                evidence["release_pending"] = list(self.owned)
            if not self.owned:
                self.evidence = None
        if failures:
            raise ValueError("Key release was rejected. Release these physically and use Stop: " + ", ".join(failures))


def execute_travel(environment, pid, cancel, evidence, selection, latch):
    evidence.update(evidence="SIMULATED MOVEMENT/PAN TRIAL" if environment.simulated else
                    "WINDOWS KEY/MOUSE INSERTION LOG; game consumption and camera path unmeasured",
                    translation={"pattern": selection.pattern, "duration": selection.duration},
                    rotation={"pan": selection.pan, "pace": selection.pace, "shape": "steady"},
                    duration_seconds=selection.duration,
                    requested_watchdog_hz=120, key_events=[], checks=0, skipped=0,
                    sent=[], planned_relative_xy=[selection.mouse_position(round(selection.duration * 120)), 0],
                    inserted_relative_xy=[0, 0],
                    release_pending=[], actual_world_position=None, actual_camera_angles=None)
    if selection.pan != "none":
        evidence["requested_mouse_hz"] = 120
    # Refuse already-held physical movement keys before claiming any ownership.
    if cancel.is_set() or not environment.travel_active(pid, ()):
        raise ValueError("Focus the game, release all movement keys and close menus before the test")
    previous, previous_mouse, complete = -1, 0, False
    final = round(selection.duration * 120)
    try:
        for key in selection.held:
            if not environment.travel_active(pid, latch.pending()):
                raise ValueError("Focus loss or manual takeover before movement key press")
            latch.press(key, evidence)
        for tick in environment.ticks(120, selection.duration):
            if cancel.is_set() or not environment.travel_active(pid, latch.pending()):
                raise ValueError("Stopped by Escape/button/opposing key, focus loss or operator Stop")
            index = tick["index"]
            if type(index) is not int or not previous < index <= final or index < 0:
                raise ValueError("Invalid movement watchdog sample")
            if (not math.isfinite(tick["elapsed"]) or not math.isfinite(tick["lateness_ms"]) or
                    tick["lateness_ms"] > 50 or
                    tick["elapsed"] - min((previous + 1) / 120, selection.duration) > .05):
                raise ValueError("Movement watchdog stalled; releasing keys without catch-up")
            target_mouse = selection.mouse_position(index)
            if target_mouse != previous_mouse:
                latch.move(target_mouse - previous_mouse, evidence, tick)
            previous_mouse = target_mouse
            evidence["checks"] += 1
            evidence["skipped"] += max(0, index - previous - 1)
            evidence["last_elapsed_seconds"] = tick["elapsed"]
            previous, complete = index, index == final
        if not complete:
            raise ValueError("Movement schedule ended early")
    except BaseException as error:
        evidence["movement_error_type"] = type(error).__name__
        if type(error) is ValueError:
            evidence["movement_error"] = str(error)
        raise
    finally:
        latch.release(evidence)


class TravelSession(MouseSession):
    ready_message = "Game found. Stage the view in clear space, then try the three-second Dolly push + pan. Inspection sends no input."

    def __init__(self, output, environment=None):
        super().__init__(output, environment or TravelEnvironment())
        self.latch = KeyLatch(self.env, self.cancel)

    def selection(self, mode, data):
        if self.latch.pending():
            raise ValueError("A movement-key release is pending. Release the keys physically and use Stop before another test")
        if mode not in ("inspect", "pan") or not isinstance(data, dict):
            raise ValueError("Select Inspect or a listed translation test")
        if mode == "inspect":
            if data:
                raise ValueError("Inspection takes no movement fields")
            return None
        if set(data) - {"off_air", "pattern", "duration", "pan", "pace"}:
            raise ValueError("Unexpected translation fields")
        if data.get("off_air") is not True:
            raise ValueError("Confirm off-air fly cam, clear space and a manually staged starting view")
        try:
            return Travel(**{key: value for key, value in data.items() if key != "off_air"})
        except (TypeError, KeyError):
            raise ValueError("Choose the listed translation settings") from None

    def execute(self, pid, evidence, selection):
        look = "fixed view" if selection.pan == "none" else f"pan {selection.pan}, {selection.pace} pace"
        self.note(f"{PATTERNS[selection.pattern]} for {selection.duration:g}s, {look}. Escape or Alt-Tab stops it.")
        try:
            execute_travel(self.env, pid, self.cancel, evidence, selection, self.latch)
        finally:
            pending = self.latch.detach_evidence()
            with self.lock:
                self.state["release_pending"] = list(pending)
        self.note("Shot finished; movement keys released. Stage the view again before another take; no automatic return.")

    def stop(self):
        super().stop()
        try:
            self.latch.release()
        except ValueError as error:
            self.note(str(error))
        finally:
            with self.lock:
                self.state["release_pending"] = list(self.latch.pending())
