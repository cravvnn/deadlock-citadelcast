"""Guided finite console trial, separate from any UI or replay launcher."""
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import subprocess
import threading
import time

from demo_core import Selection, check_process, execute_angles, perform_probe, verify_modules
from demo_panel import inventory, manual_stop_key
from normal_console_probe import foreground_pid
from dolly_live._vendor.dolly.console import ConsoleClient
from dolly_live.playback import deadline_ticks


class Environment:
    simulated = False

    def generate_password(self):
        return secrets.token_urlsafe(24)

    def modules(self):
        return verify_modules()

    def pids(self):
        return inventory()

    def identity(self, pid, port, password):
        return check_process(pid, port, password)

    def connect(self, port):
        client = ConsoleClient(protocol="netcon")
        try:
            client.connect("127.0.0.1", port, timeout=2)
        except BaseException:
            client.close()
            raise
        return client

    def active(self, pid):
        return foreground_pid() == pid and not manual_stop_key()

    def countdown(self, cancel, note):
        for remaining in range(5, 0, -1):
            note(f"Starts in {remaining}s. Focus Deadlock, close its console/menu and release WASD.")
            if cancel.wait(1):
                raise ValueError("Countdown stopped; no camera commands sent")

    def ticks(self, rate, duration):
        return deadline_ticks(rate, duration)


class Session:
    def __init__(self, output, environment=None):
        self.env = environment or Environment()
        self.output = Path(output)
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.worker = None
        self.password = ""
        self.port = 29090
        self.inspected = None
        self.verified = None
        self.state = {"simulated": self.env.simulated, "busy": False, "prepared": False,
                      "inspected": False, "verified": False, "message": "Create your launch options to begin.",
                      "binding": "Not inspected", "result": "not tested", "report": None, "events": []}

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.state))

    def note(self, message):
        with self.lock:
            self.state["message"] = message
            self.state["events"] = (self.state["events"] + [message])[-20:]

    def prepare(self, port=29090):
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("Choose a console port between 1024 and 65535")
        with self.lock:
            if self.state["busy"]:
                raise ValueError("Stop the current check before changing setup")
            if not self.password or port != self.port:
                self.password = self.env.generate_password()
                self.port = port
                self.inspected = self.verified = None
                self.state.update(prepared=True, inspected=False, verified=False, binding="Not inspected")
            self.note("Launch options ready. Paste them into Steam, then start Deadlock normally.")
            return {"options": f"-netconport {self.port} -netconpassword {self.password}"}

    def start(self, mode, data):
        if mode not in ("inspect", "echo", "pan"):
            raise ValueError("Unknown action")
        allowed = {"shot", "rate", "pitch", "yaw", "off_air"} if mode == "pan" else set()
        if not isinstance(data, dict) or set(data) - allowed:
            raise ValueError("Unexpected action fields")
        selection = Selection()
        if mode == "pan":
            if data.get("off_air") is not True:
                raise ValueError("Confirm you are currently an off-air roaming observer")
            selection = Selection(data.get("shot", "comparison"), data.get("rate", 60),
                                  data.get("pitch", 0.), data.get("yaw", 0.))
            selection.frames()
        with self.lock:
            if not self.password:
                raise ValueError("Create launch options first")
            if self.state["busy"]:
                raise ValueError("A check is already running")
            prior = self.verified if mode == "pan" else self.inspected if mode == "echo" else None
            if mode != "inspect" and (not prior or time.monotonic() - prior[1] > 180):
                self.verified = None
                self.state["verified"] = False
                raise ValueError("Inspect setup first" if mode == "echo" else "Run the connection check first")
            self.cancel.clear()
            self.state.update(busy=True, result="checking")
            self.note("Checking installed game and configured process…")
            self.worker = threading.Thread(target=self._run, args=(mode, selection, prior), daemon=False)
            self.worker.start()

    def stop(self):
        with self.lock:
            self.cancel.set()
            self.verified = None
            self.state["verified"] = False
            self.note("Stop requested. No reset or automatic resume.")

    def _run(self, mode, selection, prior):
        evidence = {"evidence": "SIMULATED UI/WORKFLOW TEST" if self.env.simulated else
                    "ACTUAL CONSOLE SEND LOG; application cadence and smoothness unmeasured",
                    "mode": mode, "result": "not started", "reviewed_build": 6807,
                    "observed_camera_response": None, "smoothness_verdict": "UNMEASURED", "sent": []}
        client, stage, path = None, "module review", None
        try:
            self.output.mkdir(parents=True, exist_ok=True)
            path = self.output / (datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + secrets.token_hex(4) + ".json")
            evidence["modules"] = self.env.modules()
            stage = "finding game"
            pids = self.env.pids()
            if len(pids) != 1:
                raise ValueError("Start Deadlock normally with the copied options first" if not pids else
                                 "Multiple Deadlock clients are open; close the extra client before testing")
            stage = "process and listener inspection"
            pid = pids[0]
            identity = self.env.identity(pid, self.port, self.password)
            evidence["identity"] = identity
            if prior and identity != prior[0]:
                raise ValueError("Game or listener changed; inspect setup and check connection again")
            if self.cancel.is_set():
                raise ValueError("Stopped before connection")
            listeners = identity["listeners"]
            listeners = listeners if isinstance(listeners, list) else [listeners]
            binding = ", ".join(sorted({item["LocalAddress"] for item in listeners}))
            with self.lock:
                self.state["binding"] = binding
            if mode == "inspect":
                with self.lock:
                    if self.cancel.is_set():
                        raise ValueError("Setup check stopped")
                    self.inspected = (identity, time.monotonic())
                    self.verified = None
                    self.state.update(inspected=True, verified=False)
                self.note("Setup found. Review the listener binding, then click Check connection. No connection made yet.")
            else:
                stage = "authenticated connection"
                client = self.env.connect(self.port)
                perform_probe(client, password=self.password, mode="echo", rate=60,
                              active=lambda: False, ticks=None, token=secrets.token_hex(8), evidence=evidence)
                evidence["mode"] = mode
                if self.cancel.is_set():
                    raise ValueError("Stopped after echo; no camera commands sent")
                if mode == "echo":
                    with self.lock:
                        if self.cancel.is_set():
                            raise ValueError("Connection check stopped")
                        self.verified = (identity, time.monotonic())
                        self.state["verified"] = True
                    self.note("Connection passed. Authenticated echo received; no camera movement sent.")
                else:
                    stage = "focus countdown"
                    self.env.countdown(self.cancel, self.note)
                    if self.cancel.is_set():
                        raise ValueError("Stopped before motion")
                    stage = "last process check"
                    if self.env.identity(pid, self.port, self.password) != identity:
                        raise ValueError("Game or listener changed before camera movement")
                    stage = "finite pan"
                    self.note("Sending finite camera shot. Escape, WASD or Alt-Tab stops future commands.")
                    execute_angles(client, selection, evidence=evidence, ticks=self.env.ticks,
                        active=lambda: not self.cancel.is_set() and self.env.active(pid))
                    self.note(f"Shot sent: {len(evidence['sent'])} samples, {evidence['skipped']} skipped. Did it visibly turn smoothly?")
            evidence["result"] = "completed"
        except BaseException as error:
            evidence.update(result="stopped", stage=stage, error_type=type(error).__name__)
            reason = str(error) if type(error) is ValueError else (
                "Process or listener inspection failed. Check that the copied options were applied before restarting Deadlock."
                if isinstance(error, subprocess.CalledProcessError) else type(error).__name__)
            if self.password and self.password in reason:
                reason = type(error).__name__
            with self.lock:
                self.verified = None
                self.state["verified"] = False
            self.note(f"Stopped at {stage}: {reason}")
        finally:
            try:
                if client:
                    client.close()
            except Exception as error:
                evidence.update(result="stopped", cleanup_error_type=type(error).__name__)
                with self.lock:
                    self.verified = None
                    self.state["verified"] = False
                self.note("Console cleanup failed. No automatic retry; inspect the saved evidence.")
            try:
                if path:
                    with path.open("x", encoding="utf-8") as stream:
                        json.dump(evidence, stream, indent=2, allow_nan=False)
                        stream.write("\n")
            except OSError:
                evidence["result"] = "stopped"
                self.note("Evidence could not be saved; stop this test and check the output folder.")
                path = None
            finally:
                with self.lock:
                    self.state.update(busy=False, result=evidence["result"], report=str(path) if path else None)
