"""Operator-started, finite mouse-look acceptance test. No game transport/hooks.

Only the real environment's send method calls SendInput. Import, inspection,
ABI checks and fixture tests never send OS input. No keyboard/button events.
"""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import subprocess
import threading
import time

from demo_core import verify_modules
from normal_console_probe import EXE, argv_tokens, foreground_pid
from dolly_live.playback import deadline_ticks


class MouseInput(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KeyboardInput(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class InputUnion(ctypes.Union):
    _fields_ = [("mi", MouseInput), ("ki", KeyboardInput), ("hi", HardwareInput)]


class Input(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", wintypes.DWORD), ("data", InputUnion)]


def packet(dx):
    if type(dx) is not int or not 1 <= dx <= 8:
        raise ValueError("Mouse step exceeds the finite test bound")
    result = Input()
    result.type = 0  # INPUT_MOUSE
    result.mi = MouseInput(dx, 0, 0, 0x0001, 0, 0)  # relative MOVE only
    return result


def verify_abi():
    expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    if ctypes.sizeof(Input) != expected:
        raise ValueError("Windows INPUT layout does not match this interpreter")
    return {"input_bytes": ctypes.sizeof(Input), "mouse_bytes": ctypes.sizeof(MouseInput),
            "pointer_bytes": ctypes.sizeof(ctypes.c_void_p)}


def normal_identity():
    """Read process metadata only. Password/other launch values never returned."""
    script = ("@(Get-CimInstance Win32_Process -Filter \"Name = 'deadlock.exe'\" | "
              "Select-Object ProcessId,ExecutablePath,CommandLine,CreationDate) | ConvertTo-Json -Compress")
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True, check=True, timeout=6,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    rows = json.loads(result.stdout) if result.stdout.strip() else []
    rows = rows if isinstance(rows, list) else [rows]
    if len(rows) != 1:
        raise ValueError("Exactly one normal Deadlock client must be running")
    row = rows[0]
    if not row.get("ExecutablePath") or Path(row["ExecutablePath"]).resolve() != EXE.resolve():
        raise ValueError("Game executable differs from the intended installed client")
    tokens = [token.casefold() for token in argv_tokens(row.get("CommandLine") or "")]
    if any(flag in tokens for flag in ("-dev", "-insecure", "-tools", "-concommandpipe", "-dedicated")):
        raise ValueError("This test requires the normal observer client")
    if any("citadel_dolly_" in token for token in tokens):
        raise ValueError("Replay overlays cannot be used for this live observer test")
    if not row.get("CreationDate"):
        raise ValueError("Game creation identity is unavailable")
    return {"pid": int(row["ProcessId"]), "created": row["CreationDate"], "executable": str(EXE)}


class MouseEnvironment:
    simulated = False

    def inspect(self):
        return {"modules": verify_modules(), "process": normal_identity(), "abi": verify_abi()}

    def identity(self):
        return normal_identity()

    def active(self, pid):
        if foreground_pid() != pid:
            return False
        api = ctypes.WinDLL("user32", use_last_error=True)
        api.GetAsyncKeyState.argtypes = [ctypes.c_int]
        api.GetAsyncKeyState.restype = ctypes.c_short
        return not any(api.GetAsyncKeyState(key) & 0x8000
                       for key in (0x1b, 0x57, 0x41, 0x53, 0x44, 0x01, 0x02, 0x04))

    def countdown(self, cancel, note):
        for remaining in range(5, 0, -1):
            note(f"Focus Deadlock now. Test begins after {remaining}s; keep the mouse still and release WASD.")
            if cancel.wait(1):
                raise ValueError("Countdown stopped; no mouse input sent")

    def ticks(self, rate, duration):
        return deadline_ticks(rate, duration)

    def send(self, dx):
        verify_abi()
        event = packet(dx)
        api = ctypes.WinDLL("user32", use_last_error=True)
        api.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
        api.SendInput.restype = wintypes.UINT
        if api.SendInput(1, ctypes.byref(event), ctypes.sizeof(Input)) != 1:
            raise ValueError("Windows did not accept the mouse event; stopped without retry")


def execute_mouse(environment, pid, cancel, evidence):
    """Fixed 240 positive relative units over 2s, requested120Hz; no reset."""
    evidence.update(requested_send_hz=120, duration_seconds=2, planned_relative_dx=240,
                    sent=[], skipped=0, inserted_relative_dx=0)
    previous = 0
    complete = False
    for tick in environment.ticks(120, 2):
        if cancel.is_set() or not environment.active(pid):
            raise ValueError("Stopped by Escape/WASD/mouse button, focus loss or operator Stop")
        index = tick["index"]
        if type(index) is not int or not 0 <= index <= 240 or (evidence["sent"] and index <= previous):
            raise ValueError("Invalid or repeated mouse schedule sample")
        if tick["lateness_ms"] > 50 or tick["elapsed"] - min((previous + 1) / 120, 2.) > .05:
            raise ValueError("Scheduling stall; stopped without a catch-up burst")
        if index == 0:
            continue
        dx = index - previous
        packet(dx)  # Validate even simulated output; bounds remain identical.
        environment.send(dx)
        evidence["sent"].append({"elapsed": tick["elapsed"], "deadline": index / 120,
                                 "lateness_ms": tick["lateness_ms"], "relative_dx": dx})
        evidence["skipped"] += max(0, index - previous - 1)
        evidence["inserted_relative_dx"] += dx
        previous = index
        complete = index == 240
    if not complete:
        raise ValueError("Mouse test ended before its endpoint; partial trace retained")


class MouseSession:
    def __init__(self, output, environment=None):
        self.env = environment or MouseEnvironment()
        self.output = Path(output)
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.worker = None
        self.checked = None
        self.state = {"simulated": self.env.simulated, "busy": False, "inspected": False,
                      "message": "Helper online. Inspect the current game to begin.", "result": "not tested",
                      "report": None, "events": []}

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.state))

    def note(self, message):
        with self.lock:
            self.state["message"] = message
            self.state["events"] = (self.state["events"] + [message])[-20:]

    def prepare(self, *args):
        raise ValueError("The mouse-only test uses no password or console port")

    def start(self, mode, data):
        selection = self.selection(mode, data)
        with self.lock:
            if self.state["busy"]:
                raise ValueError("A check or test is already running")
            if mode == "pan" and (not self.checked or time.monotonic() - self.checked[1] > 180):
                self.state["inspected"] = False
                raise ValueError("Inspect the current game first")
            self.cancel.clear()
            self.state.update(busy=True, result="checking")
            self.note("Checking the current normal game process...")
            self.worker = threading.Thread(target=self._run, args=(mode, selection), daemon=False)
            self.worker.start()

    def selection(self, mode, data):
        if mode not in ("inspect", "pan") or not isinstance(data, dict):
            raise ValueError("Select Inspect or the fixed mouse test")
        if set(data) - ({"off_air"} if mode == "pan" else set()):
            raise ValueError("Unexpected mouse-test fields")
        if mode == "pan" and data.get("off_air") is not True:
            raise ValueError("Confirm the current off-air fly-cam and physical-input baseline")

    def execute(self, pid, evidence, selection):
        self.note("Mouse test running for two seconds. Hold Escape or Alt-Tab to stop.")
        execute_mouse(self.env, pid, self.cancel, evidence)
        self.note("Mouse test finished. Did the game view turn, and did it look smooth? No automatic return move.")

    ready_message = "Game found. No mouse input sent. Confirm fly cam below, then start the two-second test."

    def stop(self):
        with self.lock:
            self.cancel.set()
            self.checked = None
            self.state["inspected"] = False
            self.note("Stopped. No reset or automatic resume; inspect again before another test.")

    def _run(self, mode, selection=None):
        evidence = {"evidence": "SIMULATED MOUSE TRIAL" if self.env.simulated else
                    "WINDOWS INPUT INSERTION LOG; game consumption and camera movement unverified",
                    "mode": mode, "result": "not started", "sent": [],
                    "observed_camera_response": None, "actual_angle_degrees": None}
        path, stage = None, "game inspection"
        try:
            self.output.mkdir(parents=True, exist_ok=True)
            path = self.output / (datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + secrets.token_hex(4) + ".json")
            inspection = self.env.inspect()
            evidence["inspection"] = inspection
            identity = inspection["process"]
            if self.cancel.is_set():
                raise ValueError("Stopped during inspection")
            if mode == "inspect":
                with self.lock:
                    if self.cancel.is_set():
                        raise ValueError("Stopped during inspection")
                    self.checked = (identity, time.monotonic())
                    self.state["inspected"] = True
                self.note(self.ready_message)
            else:
                if identity != self.checked[0]:
                    raise ValueError("Game identity changed; inspect the current client again")
                stage = "focus countdown"
                self.env.countdown(self.cancel, self.note)
                if self.cancel.is_set():
                    raise ValueError("Stopped before mouse input")
                stage = "last game identity check"
                self.note("Rechecking game identity. Keep Deadlock focused; the mouse test follows immediately.")
                if self.env.identity() != identity:
                    raise ValueError("Game identity changed during countdown")
                stage = "finite mouse test"
                self.execute(identity["pid"], evidence, selection)
            evidence["result"] = "completed"
        except BaseException as error:
            evidence.update(result="stopped", stage=stage, error_type=type(error).__name__)
            with self.lock:
                self.checked = None
                self.state["inspected"] = False
            reason = str(error) if type(error) is ValueError else type(error).__name__
            self.note(f"Stopped at {stage}: {reason}")
        finally:
            try:
                if path:
                    with path.open("x", encoding="utf-8") as stream:
                        json.dump(evidence, stream, indent=2, allow_nan=False)
                        stream.write("\n")
            except OSError:
                evidence["result"] = "stopped"
                self.note("Evidence could not be saved. Stop this test and check the output folder.")
                path = None
            finally:
                with self.lock:
                    self.state.update(busy=False, result=evidence["result"], report=str(path) if path else None)
