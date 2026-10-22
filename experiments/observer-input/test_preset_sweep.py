"""Preset input/lifecycle boundaries. All output is fake or API-mocked."""
import ctypes
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from mouse_trial import Input
from preset_fixture import FakeSweepEnvironment
from preset_sweep import Sweep, SweepEnvironment, SweepSession, execute_sweep, xy_packet
import preset_sweep
import input_build


class PresetMotionTests(unittest.TestCase):
    def test_changed_build_refuses_before_process_read_and_uses_real_hashing(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            exe = root / "bin/win64/deadlock.exe"
            client = root / "citadel/bin/win64/client.dll"
            engine = exe.parent / "engine2.dll"
            client.parent.mkdir(parents=True)
            engine.parent.mkdir(parents=True)
            client.write_bytes(b"fixture-client")
            engine.write_bytes(b"fixture-engine")
            pins = {"client.dll": hashlib.sha256(client.read_bytes()).hexdigest(),
                    "engine2.dll": hashlib.sha256(engine.read_bytes()).hexdigest()}
            with patch.object(input_build, "EXE", exe), patch.object(input_build, "PINS", pins):
                self.assertEqual(input_build.verify_input_modules(), pins)
                for target in (client, engine):
                    original = target.read_bytes()
                    target.write_bytes(original + b"-changed")
                    with patch.object(preset_sweep, "normal_identity") as identity, self.assertRaises(ValueError):
                        SweepEnvironment().inspect()
                    identity.assert_not_called()
                    target.write_bytes(original)

    def test_signed_xy_packets_are_mouse_only_and_api_failure_never_retries(self):
        for dx, dy in ((-8, 8), (0, -1), (1, 0)):
            event = xy_packet(dx, dy)
            self.assertEqual((event.type, event.mi.dx, event.mi.dy, event.mi.dwFlags), (0, dx, dy, 1))
            self.assertEqual((event.mi.mouseData, event.mi.time, event.mi.dwExtraInfo), (0, 0, 0))
        for dx, dy in ((0, 0), (9, 0), (0, -9), (True, 1), (1, 1.5)):
            with self.subTest(step=(dx, dy)), self.assertRaises(ValueError):
                xy_packet(dx, dy)
        api = MagicMock()
        api.SendInput.return_value = 1
        with patch.object(preset_sweep.ctypes, "WinDLL", return_value=api):
            SweepEnvironment().send_xy(-2, 3)
        args = api.SendInput.call_args.args
        event = ctypes.cast(args[1], ctypes.POINTER(Input)).contents
        self.assertEqual((args[0], args[2]), (1, ctypes.sizeof(Input)))
        self.assertEqual((event.mi.dx, event.mi.dy, event.mi.dwFlags), (-2, 3, 1))
        api.SendInput.reset_mock()
        api.SendInput.return_value = 0
        with patch.object(preset_sweep.ctypes, "WinDLL", return_value=api), self.assertRaises(ValueError):
            SweepEnvironment().send_xy(1, 1)
        self.assertEqual(api.SendInput.call_count, 1)

    def test_presets_have_exact_endpoints_and_eased_start_finish(self):
        cases = ((Sweep(), (480, 0)),
                 (Sweep(shot="reveal"), (360, 240)),
                 (Sweep(shot="reveal", size="large", direction="left", invert_y=True), (-540, -360)),
                 (Sweep(shot="tilt_check", size="large"), (0, 40)))
        for selection, endpoint in cases:
            with self.subTest(selection=selection):
                env, evidence = FakeSweepEnvironment(), {}
                execute_sweep(env, 4242, threading.Event(), evidence, selection)
                self.assertEqual(tuple(map(sum, zip(*env.moves))), endpoint)
                self.assertEqual(evidence["inserted_relative_xy"], list(endpoint))
                self.assertIsNone(evidence["actual_world_position"])
                self.assertIsNone(evidence["actual_camera_angles"])
                self.assertTrue(all(max(abs(x), abs(y)) <= 8 for x, y in env.moves))
        shot = Sweep()
        # Independent quarter-curve reference: smoothstep(1/4) = 53/512.
        self.assertEqual(shot.position(180), (50, 0))
        self.assertEqual(shot.position(360), (240, 0))
        self.assertEqual(shot.position(540), (430, 0))
        self.assertEqual(shot.position(1), (0, 0))
        self.assertEqual(shot.position(719), (480, 0))

    def test_all_menu_combinations_remain_bounded_and_finish_at_endpoint(self):
        for shot in ("lane", "reveal", "tilt_check"):
            for duration in (4, 6, 8):
                for size in ("small", "medium", "large"):
                    selection = Sweep(shot, size, duration)
                    env, evidence = FakeSweepEnvironment(), {}
                    execute_sweep(env, 4242, threading.Event(), evidence, selection)
                    self.assertEqual(tuple(evidence["inserted_relative_xy"]), selection.endpoint())
                    self.assertEqual(evidence["skipped"], 0)

    def test_skip_is_coalesced_but_faults_stop_without_reset_or_burst(self):
        env, evidence = FakeSweepEnvironment(), {}
        env.ticks = lambda rate, duration: ({"index": i, "elapsed": i / rate, "lateness_ms": 0}
                                           for i in [0, 2, *range(3, 721)])
        execute_sweep(env, 4242, threading.Event(), evidence, Sweep())
        self.assertEqual(evidence["inserted_relative_xy"], [480, 0])
        self.assertEqual(evidence["skipped"], 1)
        for fault in ("focus", "cancel", "stall", "oversize", "repeat", "partial", "rejected", "nan"):
            with self.subTest(fault=fault):
                env, evidence, cancel = FakeSweepEnvironment(), {}, threading.Event()
                if fault == "focus": env.focus = False
                if fault == "cancel": cancel.set()
                if fault == "rejected": env.fail_send = True
                if fault in ("stall", "oversize", "repeat", "partial", "nan"):
                    rows = [{"index": 180, "elapsed": 1.5, "lateness_ms": 0}]
                    if fault == "stall": rows[0]["lateness_ms"] = 60
                    if fault == "oversize": rows[0]["elapsed"] = 0  # Invalid large delta must also refuse.
                    if fault == "nan": rows[0]["elapsed"] = float("nan")
                    if fault in ("repeat", "partial"):
                        rows = [{"index": i, "elapsed": i / 120, "lateness_ms": 0} for i in range(181)]
                    if fault == "repeat": rows.append(rows[-1])
                    env.ticks = lambda rate, duration, rows=rows: iter(rows)
                with self.assertRaises(ValueError):
                    execute_sweep(env, 4242, cancel, evidence, Sweep())
                self.assertEqual(len(evidence["sent"]), len(env.moves))
                if fault not in ("repeat", "partial"):
                    self.assertEqual(env.moves, [])

    def test_mid_take_focus_loss_or_cancel_prevents_every_later_event(self):
        for fault in ("focus", "cancel"):
            env, evidence, cancel = FakeSweepEnvironment(), {}, threading.Event()
            def emit(dx, dy):
                env.moves.append((dx, dy))
                if fault == "focus": env.focus = False
                else: cancel.set()
            env.send_xy = emit
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                execute_sweep(env, 4242, cancel, evidence, Sweep(shot="reveal"))
            self.assertEqual(len(env.moves), 1)
            self.assertEqual(len(evidence["sent"]), 1)


class PresetSessionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = FakeSweepEnvironment()
        self.session = SweepSession(self.folder.name, self.env)

    def action(self, mode, data=None):
        self.session.start(mode, data or {})
        self.session.worker.join(2)
        self.assertFalse(self.session.worker.is_alive())
        return self.session.snapshot()

    def test_inert_inspection_exact_schema_and_frozen_selection(self):
        self.assertEqual(self.action("inspect")["result"], "completed")
        self.assertEqual(self.env.moves, [])
        for data in ({}, {"off_air": True, "dx": 10}, {"off_air": True, "shot": "teleport"},
                     {"off_air": True, "duration": True}, {"off_air": True, "duration": 60},
                     {"off_air": True, "invert_y": 1}, {"off_air": True, "shot": []}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.session.start("pan", data)
        self.assertEqual(self.env.moves, [])
        state = self.action("pan", {"off_air": True, "shot": "reveal", "direction": "left"})
        report = json.loads(Path(state["report"]).read_text(encoding="utf-8"))
        self.assertEqual(state["result"], "completed")
        self.assertEqual(report["preset"]["shot"], "reveal")
        self.assertEqual(report["inserted_relative_xy"], [-360, 240])
        self.assertIsNone(report["observed_camera_response"])
        self.assertIsNone(report["actual_angle_degrees"])

    def test_modules_identity_countdown_and_stop_keep_input_disabled(self):
        for fault in ("modules", "identity", "countdown", "stop", "identity_after_countdown"):
            with self.subTest(fault=fault):
                self.env = FakeSweepEnvironment()
                self.session = SweepSession(self.folder.name, self.env)
                self.action("inspect")
                if fault == "modules": self.env.module_error = True
                if fault == "identity": self.env.version += 1
                if fault == "countdown": self.env.stop_countdown = True
                if fault == "identity_after_countdown":
                    self.env.countdown = lambda cancel, note: setattr(self.env, "version", 2)
                if fault == "stop":
                    self.session.stop()
                    with self.assertRaises(ValueError): self.session.start("pan", {"off_air": True})
                else:
                    self.assertEqual(self.action("pan", {"off_air": True})["result"], "stopped")
                self.assertEqual(self.env.moves, [])


if __name__ == "__main__":
    unittest.main()
