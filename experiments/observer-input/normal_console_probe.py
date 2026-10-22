"""Private, explicit normal-client console trial; no launch/injection/OS input.

Default execution mode is authenticated ECHO ONLY. Camera mode is a separately
selected two-second, twelve-degree stationary pan. No game position is sent.
This file does not modify replay Dolly or connect the mock desk to a game.
The operator must review/authorize the mode before this script is executed.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import getpass
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dolly_live._vendor.dolly.console import ConsoleClient
from dolly_live._vendor.dolly.path import Keyframe, Project
from dolly_live.motion import compile_console
from dolly_live.observer import spec_setang
from dolly_live.playback import deadline_ticks

EXE = Path(r"B:/SteamLibrary/steamapps/common/Deadlock/game/bin/win64/deadlock.exe")
CLIENT_SHA256 = "d61348c564ce931e969996af18dbdec8544643810f28f3d330fb94b33231c460"
ENGINE_SHA256 = "44bb357a1baf4765043042de3234112e18ea0db7e0b637f18385bb21f8338707"


def pan_frames(rate):
    if type(rate) is not int or rate not in (16, 60, 120):
        raise ValueError("Only reviewed 16/60/120 Hz trials are accepted")
    project = Project(name="OFF-AIR stationary pan", interpolation="linear", keyframes=[
        Keyframe(0, 0, 0, 0, 0, 0, 0), Keyframe(2, 0, 0, 0, 0, 12, 0)])
    plan = compile_console(project, rate_hz=rate)
    return tuple((frame.time, spec_setang(frame.pose)) for frame in plan.frames)


def argv_tokens(command):
    # Windows-native quoting rules, no shell interpretation or substring flags.
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    count = ctypes.c_int()
    pointer = shell32.CommandLineToArgvW(command, ctypes.byref(count))
    if not pointer:
        raise OSError("Could not parse process command line")
    try:
        return [pointer[i] for i in range(count.value)]
    finally:
        kernel32.LocalFree(pointer)


def validate_record(record, *, pid, port, password):
    if int(record["ProcessId"]) != pid or Path(record["ExecutablePath"]).resolve() != EXE.resolve():
        raise ValueError("Wrong process identity; refusing console access")
    tokens = argv_tokens(record["CommandLine"])
    validate_tokens(tokens, port=port, password=password)


def validate_tokens(tokens, *, port, password):
    lower = [token.casefold() for token in tokens]
    if any(token in lower for token in ("-insecure", "-dev", "-tools", "-concommandpipe")):
        raise ValueError("This probe requires a normal client, not a replay/development launch")
    if any("citadel_dolly_" in token for token in lower):
        raise ValueError("Dolly replay overlay is not a normal observer client")
    for option, wanted in (("-netconport", str(port)), ("-netconpassword", password)):
        if lower.count(option) != 1:
            raise ValueError(f"Exactly one {option} argument is required")
        index = lower.index(option)
        if index + 1 >= len(tokens) or tokens[index + 1] != wanted:
            raise ValueError(f"The reviewed {option} configuration does not match")


def check_process(pid, port, password):
    if type(pid) is not int or pid < 1 or type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("Invalid explicit PID or port")
    script = (f"$p = Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; "
              "if (!$p) { exit 4 }; "
              "$p | Select-Object ProcessId,ExecutablePath,CommandLine,CreationDate | ConvertTo-Json -Compress")
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                            capture_output=True, text=True, timeout=5, check=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    record = json.loads(result.stdout)
    validate_record(record, pid=pid, port=port, password=password)
    # No command line/password is returned or written to evidence.
    listener = subprocess.run(["powershell", "-NoProfile", "-Command",
        f"$p = Get-NetTCPConnection -OwningProcess {pid} -LocalPort {port} -State Listen "
        "-ErrorAction SilentlyContinue; if (!$p) { exit 5 }; "
        "$p | Select-Object LocalAddress,LocalPort | ConvertTo-Json -Compress"],
        capture_output=True, text=True, timeout=5, check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return {"pid": pid, "created": record["CreationDate"],
            "listeners": json.loads(listener.stdout)}


def foreground_pid():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value


def perform_probe(client, *, password, mode, rate, active, ticks, token, evidence=None):
    """Explicit authentication, echo barrier, then optional fixed angle allowlist.

    Caller has already verified the target PID/port/launch tokens. No arbitrary
    command inputs, position commands, cheat commands or automatic reset.
    """
    if mode not in ("echo", "pan"):
        raise ValueError("Unknown mode")
    if not re.fullmatch(r"[A-Za-z0-9]{1,32}", token):
        raise ValueError("Invalid echo nonce")
    frames = pan_frames(rate)
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", password):
        raise ValueError("Use a temporary 16-64 character alphanumeric/underscore/hyphen password")
    marker = "DOLLY_LIVE_ECHO_" + token
    client.send("PASS " + password)
    output = client.request("echo " + marker, timeout=2)
    # Password rejection may print an echoed command rather than execute it.
    # Require a standalone marker line, not a substring of 'echo <marker>'.
    marker_line = re.compile(r"^(?:\[[^\]\r\n]+\]\s*)*" + re.escape(marker) + r"$")
    if not any(marker_line.fullmatch(line.strip()) for line in output.splitlines()):
        raise ValueError("No authenticated echo acknowledgement; no camera commands sent")
    evidence = {} if evidence is None else evidence
    evidence.update({"mode": mode, "authenticated_echo": True, "sent": [], "skipped": 0})
    if mode == "echo":
        return evidence
    if not active():
        raise ValueError("Game is not foreground; no camera commands sent")
    last_index = -1
    for tick in ticks(rate, 2):
        if not active():
            raise ValueError("Foreground lost: stopped without resetting the camera")
        # 50 ms BEYOND the next intended deadline: a normal 16 Hz interval is
        # itself 62.5 ms. A raw 50 ms inter-send limit incorrectly rejects it.
        overdue = tick["elapsed"] - min((last_index + 1) / rate, 2.)
        if tick["lateness_ms"] > 50 or overdue > .05:
            raise ValueError("Scheduling stall: stopped without a catch-up burst/reset")
        index = tick["index"]
        evidence["skipped"] += max(0, index - last_index - 1)
        intended, command = frames[index]
        if not re.fullmatch(r"spec_setang 0\.00 (?:\d|1[012])\.\d{2}", command):
            raise ValueError("Command outside the fixed pan allowlist")
        before = time.perf_counter()
        client.send(command)
        evidence["sent"].append({"deadline": intended, "elapsed": tick["elapsed"],
                                 "lateness_ms": tick["lateness_ms"],
                                 "send_duration_ms": (time.perf_counter() - before) * 1000,
                                 "command": command})
        last_index = index
    return evidence


def self_check():
    class FakeConsole:
        def __init__(self, accepted=True):
            self.commands = []
            self.accepted = accepted
        def send(self, command):
            self.commands.append(command)
        def request(self, command, timeout):
            self.commands.append(command)
            return command[5:] if self.accepted else "password required"
    password, token = "synthetic_fixture_password", "fixture"
    tokens = [str(EXE), "-netconport", "29090", "-netconpassword", password]
    validate_tokens(tokens, port=29090, password=password)
    for bad in (tokens + ["-insecure"], tokens + ["-dev"], tokens + ["-netconport", "29090"],
                tokens[:-1] + ["different_password"], tokens[:-4]):
        try:
            validate_tokens(bad, port=29090, password=password)
            raise AssertionError("Process argument refusal was lost")
        except ValueError:
            pass
    fake = FakeConsole()
    proof = perform_probe(fake, password=password, mode="echo", rate=120,
                          active=lambda: False, ticks=None, token=token)
    assert proof["authenticated_echo"] and not proof["sent"]
    assert all(not command.startswith("spec_") for command in fake.commands)
    fake = FakeConsole(False)
    try:
        perform_probe(fake, password=password, mode="pan", rate=120,
                      active=lambda: True, ticks=None, token=token)
        raise AssertionError("Authentication refusal was lost")
    except ValueError:
        assert not any(command.startswith("spec_") for command in fake.commands)
    class PrefixedConsole(FakeConsole):
        def request(self, command, timeout):
            self.commands.append(command)
            return "[Console] " + command[5:]
    proof = perform_probe(PrefixedConsole(), password=password, mode="echo", rate=120,
                          active=lambda: False, ticks=None, token=token)
    assert proof["authenticated_echo"]
    class CommandEchoConsole(FakeConsole):
        def request(self, command, timeout):
            self.commands.append(command)
            return command
    fake = CommandEchoConsole()
    try:
        perform_probe(fake, password=password, mode="pan", rate=120,
                      active=lambda: True, ticks=None, token=token)
        raise AssertionError("A command echo was accepted as an executed acknowledgement")
    except ValueError:
        assert not any(command.startswith("spec_") for command in fake.commands)
    fake = FakeConsole()
    proof = {}
    try:
        perform_probe(fake, password=password, mode="pan", rate=120,
            active=iter([True, True, False]).__next__,
            ticks=lambda r, d: iter([{"index": 0, "elapsed": 0, "lateness_ms": 0},
                                     {"index": 1, "elapsed": 1 / 120, "lateness_ms": 0}]),
            token=token, evidence=proof)
        raise AssertionError("Foreground refusal was lost")
    except ValueError:
        assert len(proof["sent"]) == 1  # Preserve the partial trace, no reset command.
        assert fake.commands[-1] == "spec_setang 0.00 0.00"
    for rate in (16, 60, 120):
        fake = FakeConsole()
        ticks = lambda r, d: ({"index": i, "elapsed": i / r, "lateness_ms": 0}
                              for i in range(2 * r + 1))
        proof = perform_probe(fake, password=password, mode="pan", rate=rate,
                              active=lambda: True, ticks=ticks, token=token)
        assert len(proof["sent"]) == 2 * rate + 1 and proof["skipped"] == 0
        assert proof["sent"][0]["command"] == "spec_setang 0.00 0.00"
        assert proof["sent"][-1]["command"] == "spec_setang 0.00 12.00"
        assert not any(command.startswith("spec_goto") for command in fake.commands)
    fake = FakeConsole()
    try:
        perform_probe(fake, password=password, mode="pan", rate=120,
            active=lambda: True, ticks=lambda r, d: iter([{"index": 12, "elapsed": .1,
                                                          "lateness_ms": 60}]), token=token)
        raise AssertionError("Stall refusal was lost")
    except ValueError:
        assert not any(command.startswith("spec_") for command in fake.commands)
    print("PASS: simulated auth/echo-only/three bounded pans/stall refusal. No OS/game/network access.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--port", type=int)
    parser.add_argument("--mode", choices=("echo", "pan"), default="echo")
    parser.add_argument("--rate", type=int, choices=(16, 60, 120), default=60)
    parser.add_argument("--observer-confirmed", action="store_true")
    parser.add_argument("--off-air", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return 0
    if not args.pid or not args.port or not args.out or not args.observer_confirmed or not args.off_air:
        parser.error("Explicit PID/port/new output path and observer/off-air confirmations are required")
    password = getpass.getpass("Temporary netconsole password (not logged): ")
    client = ConsoleClient(protocol="netcon")
    evidence = {"evidence": "ACTUAL CONSOLE TRANSPORT PROBE; camera acceptance requires user observation",
                "mode": args.mode, "result": "not started"}
    try:
        with args.out.open("x", encoding="utf-8") as log:
            try:
                client_path = EXE.parents[2] / "citadel/bin/win64/client.dll"
                digest = hashlib.sha256(client_path.read_bytes()).hexdigest()
                if digest != CLIENT_SHA256:
                    raise ValueError("Client differs from reviewed command implementation")
                if hashlib.sha256((EXE.parent / "engine2.dll").read_bytes()).hexdigest() != ENGINE_SHA256:
                    raise ValueError("Engine differs from the reviewed netconsole implementation")
                if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", password):
                    raise ValueError("Password does not meet the probe's reviewed format")
                identity = check_process(args.pid, args.port, password)
                evidence["identity"] = identity
                client.connect("127.0.0.1", args.port, timeout=2)
                if args.mode == "pan":
                    print("Two-second pan: starts at pitch/yaw 0/0, ends 0/12. Focus the game within 5 seconds.")
                    time.sleep(5)
                if args.mode == "pan" and check_process(args.pid, args.port, password) != identity:
                    raise ValueError("Process/listener identity changed before the pan")
                perform_probe(client, password=password, mode=args.mode, rate=args.rate,
                    active=lambda: foreground_pid() == args.pid, ticks=deadline_ticks,
                    token=secrets.token_hex(8), evidence=evidence)
                evidence["result"] = "completed"
            except BaseException as error:
                evidence["result"] = "stopped"
                # Do not store raw exception text: transport/process errors may include secrets.
                evidence["error_type"] = type(error).__name__
                raise
            finally:
                client.close()
                json.dump(evidence, log, indent=2, allow_nan=False)
                log.write("\n")
    except Exception as error:
        print(f"Probe stopped ({type(error).__name__}); no automatic retry/reset/relaunch.", file=sys.stderr)
        return 1
    print(f"Probe completed ({args.mode}); evidence: {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
