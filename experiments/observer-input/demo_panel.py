"""Local operator UI for the finite, reviewed angle-only console experiment."""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

from demo_clipboard import copy_text

from demo_core import (PINS, SHOTS, Selection, check_process, execute_angles,
                       foreground_pid, perform_probe, self_check, verify_modules)
from normal_console_probe import EXE
from dolly_live._vendor.dolly.console import ConsoleClient

HERE = Path(__file__).resolve().parent


def inventory():
    script = ("@(Get-CimInstance Win32_Process -Filter \"Name = 'deadlock.exe'\" | "
              "Select-Object ProcessId,ExecutablePath) | ConvertTo-Json -Compress")
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                            capture_output=True, text=True, check=True, timeout=8,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    rows = json.loads(result.stdout) if result.stdout.strip() else []
    rows = rows if isinstance(rows, list) else [rows]
    return [int(row["ProcessId"]) for row in rows if row.get("ExecutablePath") and
            Path(row["ExecutablePath"]).resolve() == EXE.resolve()]


def manual_stop_key():
    api = ctypes.WinDLL("user32", use_last_error=True)
    api.GetAsyncKeyState.argtypes = [ctypes.c_int]
    api.GetAsyncKeyState.restype = ctypes.c_short
    # State queries only. No hooks, key registration, keyboard/mouse synthesis.
    return any(api.GetAsyncKeyState(key) & 0x8000 for key in (0x1b, 0x57, 0x41, 0x53, 0x44))


class Panel:
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.closing = False
        self.client = None
        self.cancel = threading.Event()
        self.messages = queue.Queue()
        self.verified = None
        self.inspected = None
        self.pid = tk.StringVar()
        self.port = tk.StringVar(value="29090")
        self.password = tk.StringVar()
        self.off_air = tk.BooleanVar()
        self.shot = tk.StringVar(value="comparison")
        self.rate = tk.StringVar(value="60")
        self.pitch = tk.StringVar(value="0")
        self.yaw = tk.StringVar(value="0")
        self.status = tk.StringVar(value="Not connected. Set launch options, start the normal game, then verify echo.")
        self.detail = tk.StringVar(value="Current review: build 6807. No injection, game launch or game-file edits.")
        self.binding = tk.StringVar(value="Console listener binding: not inspected")
        self.copy_feedback = tk.StringVar(value="Enter a password above, then click Copy.")
        for variable in (self.pid, self.port, self.password):
            variable.trace_add("write", self.configuration_changed)
        for variable in (self.shot, self.rate, self.pitch, self.yaw, self.off_air):
            variable.trace_add("write", self.selection_changed)
        root.title("Dolly Live — camera demo (setup fix)")
        root.minsize(670, 660)
        root.geometry("790x760")
        scroller = ttk.Frame(root)
        scroller.pack(fill="both", expand=True)
        canvas = tk.Canvas(scroller, highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroller, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        outer = ttk.Frame(canvas, padding=22)
        window = canvas.create_window(0, 0, window=outer, anchor="nw")
        outer.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        root.bind("<MouseWheel>", lambda event: canvas.yview_scroll(-int(event.delta / 120), "units"))
        ttk.Label(outer, text="DOLLY LIVE", font=("Segoe UI", 23, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Off-air console camera trial · live smoothness still unverified",
                  font=("Segoe UI", 11)).pack(anchor="w", pady=(0, 16))
        setup = ttk.LabelFrame(outer, text="1  Normal-client setup", padding=12)
        setup.pack(fill="x")
        for row, (label, variable) in enumerate((("Game PID", self.pid), ("Console port", self.port),
                                                ("Temporary password", self.password))):
            ttk.Label(setup, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
            ttk.Entry(setup, textvariable=variable, show="•" if row == 2 else "", width=38).grid(
                row=row, column=1, sticky="ew", pady=4)
        setup.columnconfigure(1, weight=1)
        buttons = ttk.Frame(setup)
        buttons.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 4))
        self.action_buttons = []
        self.button(buttons, "Find game PID", self.refresh).pack(side="left", padx=(0, 8))
        self.button(buttons, "Copy temporary launch options", self.copy_options).pack(side="left")
        self.button(buttons, "Show for manual copy", self.show_options).pack(side="left", padx=(8, 0))
        ttk.Label(setup, textvariable=self.copy_feedback, wraplength=620,
                  font=("Segoe UI", 10, "bold")).grid(row=4, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Label(setup, text="Password: 16–64 letters, digits, _ or -. Enter locally; never send it in chat.\n"
                  "Copy explicitly places it on your clipboard. Paste options into Steam before starting;\n"
                  "preserve existing options and remove only these two temporary options afterward.",
                  wraplength=650).grid(row=5, column=0, columnspan=2, sticky="w", pady=(5, 0))
        self.button(outer, "2  Inspect setup and listener — no connection", lambda: self.submit("inspect")).pack(
            anchor="w", pady=(12, 4))
        ttk.Label(outer, textvariable=self.binding, wraplength=650).pack(anchor="w")
        self.button(outer, "3  Verify authenticated echo — no camera movement", self.echo).pack(
            anchor="w", pady=10)
        motion = ttk.LabelFrame(outer, text="4  One finite shot", padding=12)
        motion.pack(fill="x")
        labels = (("Shot", self.shot, list(SHOTS)), ("Requested send Hz", self.rate, ["16", "60", "120"]))
        for row, (label, var, values) in enumerate(labels):
            ttk.Label(motion, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Combobox(motion, textvariable=var, values=values, state="readonly", width=28).grid(
                row=row, column=1, sticky="w", padx=12, pady=4)
        angles = ttk.Frame(motion)
        angles.grid(row=2, column=0, columnspan=2, sticky="w", pady=6)
        for text, var in (("Start pitch", self.pitch), ("Start yaw", self.yaw)):
            ttk.Label(angles, text=text).pack(side="left", padx=(0, 8))
            ttk.Entry(angles, textvariable=var, width=9).pack(side="left", padx=(0, 16))
        ttk.Label(motion, text="comparison: 2 s / +12° yaw · cinematic: 6 s / eased +45° yaw\n"
                  "reveal: 4 s / eased +20° yaw and −15° pitch\n"
                  "The first command sets the entered angles immediately. Position stays where you put it.\n"
                  "No automatic reset or resume; set up each shot off-air.", wraplength=650).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Checkbutton(motion, text="I am currently an observer in a private test, off-air, in roaming/freecam",
                        variable=self.off_air).grid(row=4, column=0, columnspan=2, sticky="w", pady=5)
        self.button(motion, "Start selected shot — 5 second focus countdown", self.pan).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        footer = ttk.Frame(root, padding=(22, 0, 22, 14))
        footer.pack(fill="x")
        ttk.Button(footer, text="STOP / RELEASE  ·  Escape or WASD in-game also stops future commands",
                   command=self.stop).pack(fill="x", pady=12)
        ttk.Label(footer, textvariable=self.status, font=("Segoe UI", 11, "bold"),
                  wraplength=710).pack(anchor="w", pady=(2, 5))
        ttk.Label(footer, textvariable=self.detail, wraplength=710).pack(anchor="w")
        ttk.Label(footer, text="Alt-Tab stops motion. Already accepted commands cannot be retracted.\n"
                  "Send logs are not measured camera Hz. This experiment has no Valve risk guarantee.",
                  wraplength=710).pack(anchor="w", pady=(10, 0))
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Escape>", lambda event: self.stop())
        root.after(50, self.poll)

    def button(self, parent, text, command):
        widget = ttk.Button(parent, text=text, command=command)
        self.action_buttons.append(widget)
        return widget

    def fields(self):
        import re
        password = self.password.get()
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", password):
            raise ValueError("Enter a temporary password with 16–64 letters, digits, _ or -")
        try:
            port = int(self.port.get())
        except ValueError:
            raise ValueError("Console port must be a number between 1024 and 65535") from None
        if not 1024 <= port <= 65535:
            raise ValueError("Console port must be 1024–65535")
        return port, password

    def configuration_changed(self, *_):
        self.verified = None
        self.inspected = None
        self.binding.set("Console listener binding: not inspected")
        self.copy_feedback.set("Settings changed. Copy the launch options again before starting the game.")
        if self.busy:
            self.stop()

    def selection_changed(self, *_):
        if self.busy:
            self.stop()

    def copy_options(self):
        try:
            port, password = self.fields()
            copy_text(self.root.winfo_id(), f"-netconport {port} -netconpassword {password}")
            self.copy_feedback.set("Copied and checked. Paste into Steam’s Launch Options with Ctrl+V.")
            self.status.set("Temporary options copied. Paste in Steam, then start the normal game yourself.")
        except ValueError as error:
            self.copy_feedback.set(str(error))
            self.status.set(str(error))
        except OSError:
            self.copy_feedback.set("Clipboard copy failed. Click Show for manual copy, then select the text and press Ctrl+C.")
            self.status.set("Clipboard could not be verified; use Show for manual copy.")

    def show_options(self):
        try:
            port, password = self.fields()
        except ValueError as error:
            self.copy_feedback.set(str(error))
            return
        window = tk.Toplevel(self.root)
        window.title("Steam launch options — contains your temporary password")
        window.transient(self.root)
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Select the text below and press Ctrl+C. Paste into Steam → Deadlock →\n"
                  "Properties → General → Launch Options. Preserve existing options.").pack(anchor="w", pady=(0, 10))
        entry = ttk.Entry(frame, width=95)
        entry.insert(0, f"-netconport {port} -netconpassword {password}")
        entry.configure(state="readonly")
        entry.pack(fill="x", pady=(0, 12))
        entry.select_range(0, "end")
        entry.focus_set()
        ttk.Button(frame, text="Close", command=window.destroy).pack(anchor="e")
        self.copy_feedback.set("Launch options opened for manual copy on your PC.")

    def refresh(self):
        self.start_worker("inventory", None)

    def echo(self):
        self.submit("echo")

    def pan(self):
        self.submit("pan")

    def submit(self, mode):
        try:
            port, password = self.fields()
            pid = int(self.pid.get())
            selection = Selection(self.shot.get(), int(self.rate.get()), float(self.pitch.get()), float(self.yaw.get()))
            selection.frames()
            if mode == "echo":
                if not self.inspected or self.inspected[:3] != (pid, port, password):
                    raise ValueError("Inspect setup first and review the displayed listener binding")
                if time.monotonic() - self.inspected[4] > 180:
                    raise ValueError("Setup inspection expired; inspect again")
            if mode == "pan":
                if not self.off_air.get():
                    raise ValueError("Confirm the current off-air observer setup before a camera shot")
                if not self.verified or self.verified[:3] != (pid, port, password):
                    raise ValueError("Verify authenticated echo for this exact setup first")
                if time.monotonic() - self.verified[4] > 180:
                    raise ValueError("Echo is older than 3 minutes; verify again")
            prior = self.verified if mode == "pan" else self.inspected
            self.start_worker(mode, (pid, port, password, selection, prior))
        except ValueError as error:
            self.status.set(str(error))

    def start_worker(self, mode, arguments):
        if self.busy:
            return
        self.busy = True
        self.cancel.clear()
        for button in self.action_buttons:
            button.state(["disabled"])
        self.status.set("Checking…" if mode != "inventory" else "Finding the installed game…")
        threading.Thread(target=self.work, args=(mode, arguments), daemon=False).start()

    def work(self, mode, arguments):
        evidence = {"evidence": "ACTUAL CONSOLE SEND LOG; visible camera response not yet observed",
                    "mode": mode, "result": "not started", "build_review": 6807,
                    "observed_camera_response": None, "smoothness_verdict": "UNMEASURED"}
        stage, output = "inventory", None
        try:
            if mode == "inventory":
                pids = inventory()
                self.messages.put(("inventory", pids))
                return
            pid, port, password, selection, prior = arguments
            stage = "module review"
            evidence["modules"] = verify_modules()
            stage = "process and listener identity"
            identity = check_process(pid, port, password)
            evidence["identity"] = identity
            if mode in ("echo", "pan") and identity != prior[3]:
                raise ValueError("Process/listener changed; inspect setup and verify echo again")
            if self.cancel.is_set():
                raise ValueError("Stopped before connection")
            listeners = identity["listeners"]
            listeners = listeners if isinstance(listeners, list) else [listeners]
            exposure = ", ".join(sorted({item["LocalAddress"] for item in listeners}))
            self.messages.put(("binding", f"Listener binding: {exposure}. Password required; do not forward this port."))
            if mode == "inspect":
                self.messages.put(("inspected", (pid, port, password, identity, time.monotonic())))
                self.messages.put(("status", "Setup inspected without a connection. Review binding, then verify echo."))
                return
            logs = HERE / "demo-evidence"
            logs.mkdir(exist_ok=True)
            output = logs / (datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + secrets.token_hex(4) + ".json")
            with output.open("x", encoding="utf-8") as log:
                try:
                    stage = "authenticated echo"
                    self.client = ConsoleClient(protocol="netcon")
                    self.client.connect("127.0.0.1", port, timeout=2)
                    perform_probe(self.client, password=password, mode="echo", rate=60,
                                  active=lambda: False, ticks=None, token=secrets.token_hex(8), evidence=evidence)
                    if self.cancel.is_set():
                        raise ValueError("Stopped after echo; no camera writes")
                    if mode == "echo":
                        self.messages.put(("verified", (pid, port, password, identity, time.monotonic())))
                    else:
                        stage = "focus countdown"
                        for remaining in range(5, 0, -1):
                            self.messages.put(("status", f"Shot starts in {remaining}s. Focus the game; release WASD. Hold Escape to stop."))
                            if self.cancel.wait(1):
                                raise ValueError("Countdown stopped; no camera writes")
                        stage = "last identity check"
                        if check_process(pid, port, password) != identity:
                            raise ValueError("Process/listener changed before camera writes")
                        stage = "finite angle shot"
                        self.messages.put(("status", "Running finite shot. Escape, WASD or Alt-Tab stops future sends."))
                        execute_angles(self.client, selection, evidence=evidence,
                            active=lambda: not self.cancel.is_set() and foreground_pid() == pid and not manual_stop_key())
                    evidence["result"] = "completed"
                except BaseException as error:
                    evidence.update(result="stopped", error_type=type(error).__name__, stage=stage)
                    raise
                finally:
                    if self.client:
                        self.client.close()
                        self.client = None
                    json.dump(evidence, log, indent=2, allow_nan=False)
                    log.write("\n")
            self.messages.put(("status", "Authenticated echo passed. No camera movement sent." if mode == "echo"
                               else f"Shot sent: {len(evidence['sent'])} samples, {evidence['skipped']} skipped. Inspect the game result."))
        except Exception as error:
            # No subprocess stdout/stderr, command line, password or raw transport logs.
            reason = str(error) if type(error) is ValueError else type(error).__name__
            if arguments and arguments[2] in reason:
                reason = type(error).__name__
            self.messages.put(("failed", f"Stopped at {stage}: {reason}. No automatic retry/reset."))
        finally:
            if output:
                self.messages.put(("detail", "Evidence: " + str(output)))
            self.messages.put(("done", None))

    def stop(self):
        self.cancel.set()
        self.status.set("Stop requested. Future sends stop; no reset command is sent.")

    def close(self):
        self.closing = True
        self.stop()
        if not self.busy:
            self.password.set("")
            self.root.destroy()

    def poll(self):
        while not self.messages.empty():
            kind, value = self.messages.get_nowait()
            if kind == "inventory":
                self.verified = None
                self.pid.set(str(value[0]) if len(value) == 1 else "")
                self.status.set("Found game PID " + str(value[0]) if len(value) == 1 else
                                "Start the normal game first." if not value else "Multiple game clients; choose the intended PID explicitly.")
            elif kind == "verified":
                self.verified = value
            elif kind == "inspected":
                self.inspected = value
            elif kind == "failed":
                self.verified = None
                self.status.set(value)
            elif kind in ("status", "detail", "binding"):
                getattr(self, kind).set(value)
            elif kind == "done":
                self.busy = False
                for button in self.action_buttons:
                    button.state(["!disabled"])
        if self.closing and not self.busy:
            self.password.set("")
            self.root.destroy()
            return
        self.root.after(50, self.poll)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--ui-smoke", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    root = tk.Tk()
    panel = Panel(root)
    if args.ui_smoke:
        # Layout only: no process query, game connection or UI action.
        root.update_idletasks()
        panel.verified = ("fixture",)
        panel.pid.set("123")
        assert panel.verified is None
        panel.busy = True
        panel.off_air.set(True)
        assert panel.cancel.is_set()
        panel.busy = False
        panel.password.set("short")
        panel.copy_options()
        assert "16–64" in panel.copy_feedback.get()
        panel.password.set("synthetic_fixture_password")
        panel.show_options()
        assert any(isinstance(child, tk.Toplevel) for child in root.winfo_children())
        print(f"UI layout: {root.winfo_width()}x{root.winfo_height()}, requested {root.winfo_reqwidth()}x{root.winfo_reqheight()}; no game/network access")
        root.after(100, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
