"""Held-key translation/release owner. No test emits real Windows input."""
import ctypes
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from mouse_trial import Input
from travel_fixture import FakeTravelEnvironment
from travel_trial import KeyLatch, Travel, TravelEnvironment, TravelSession, execute_travel, key_packet
import travel_trial


class KeyboardTests(unittest.TestCase):
    def test_scan_code_allowlist_and_single_event_api_failure(self):
        for key, scan in (("w", 0x11), ("shift", 0x2A), ("ctrl", 0x1D)):
            for down, flags in ((True, 8), (False, 10)):
                event = key_packet(key, down)
                self.assertEqual((event.type, event.ki.wVk, event.ki.wScan, event.ki.dwFlags), (1, 0, scan, flags))
                self.assertEqual((event.ki.time, event.ki.dwExtraInfo), (0, 0))
        for key, down in (("enter", True), ("space", True), ("w", 1)):
            with self.assertRaises(ValueError): key_packet(key, down)
        api = MagicMock()
        api.SendInput.return_value = 1
        with patch.object(travel_trial.ctypes, "WinDLL", return_value=api):
            TravelEnvironment().key("ctrl", False)
        args = api.SendInput.call_args.args
        event = ctypes.cast(args[1], ctypes.POINTER(Input)).contents
        self.assertEqual((args[0], args[2], event.ki.wScan, event.ki.dwFlags), (1, ctypes.sizeof(Input), 0x1D, 10))
        api.SendInput.reset_mock()
        api.SendInput.return_value = 0
        with patch.object(travel_trial.ctypes, "WinDLL", return_value=api), self.assertRaises(ValueError):
            TravelEnvironment().key("w", True)
        self.assertEqual(api.SendInput.call_count, 1)

    def test_active_guard_requires_idle_controls_then_ignores_owned_keys_only(self):
        api = MagicMock()
        pressed = {0x57, 0x10}
        api.GetAsyncKeyState.side_effect = lambda key: 0x8000 if key in pressed else 0
        with patch.object(travel_trial.ctypes, "WinDLL", return_value=api), \
                patch.object(travel_trial, "foreground_pid", return_value=4242):
            env = TravelEnvironment()
            self.assertFalse(env.travel_active(4242, ()))
            self.assertTrue(env.travel_active(4242, ("w", "shift")))
            pressed.add(0x53)  # Physical S remains an unconditional stop.
            self.assertFalse(env.travel_active(4242, ("w", "shift")))
            pressed.clear()
            self.assertFalse(env.travel_active(9999, ()))


class TravelExecutionTests(unittest.TestCase):
    def run_trial(self, selection, env=None):
        env = env or FakeTravelEnvironment()
        cancel, evidence = threading.Event(), {}
        latch = KeyLatch(env, cancel)
        execute_travel(env, 4242, cancel, evidence, selection, latch)
        return env, evidence, latch

    def test_every_pattern_holds_continuously_with_one_down_and_one_up_per_key(self):
        expected = {"forward": ("w",), "up": ("shift",), "down": ("ctrl",),
                    "forward_up": ("w", "shift"), "forward_down": ("w", "ctrl")}
        for pattern, keys in expected.items():
            for duration in (.5, 1, 2, 3):
                with self.subTest(pattern=pattern, duration=duration):
                    env, report, latch = self.run_trial(Travel(pattern, duration))
                    self.assertEqual(env.key_events, [(key, True) for key in keys] +
                                     [(key, False) for key in reversed(keys)])
                    self.assertEqual(report["checks"], round(duration * 120) + 1)
                    self.assertEqual(report["release_pending"], [])
                    self.assertEqual(latch.pending(), ())
                    self.assertEqual(env.keys_down, set())
                    self.assertEqual(env.moves, [])  # View is held, never rotated.
                    self.assertIsNone(report["actual_world_position"])

    def test_every_mid_take_fault_releases_all_claimed_keys(self):
        for fault in ("focus", "manual", "cancel", "stall", "index", "iterator", "partial"):
            env, cancel, report = FakeTravelEnvironment(), threading.Event(), {}
            latch = KeyLatch(env, cancel)
            def ticks(rate, duration):
                yield {"index": 0, "elapsed": 0, "lateness_ms": 0}
                if fault == "focus": env.focus = False
                if fault == "manual": env.manual = {"s"}
                if fault == "cancel": cancel.set()
                if fault == "iterator": raise RuntimeError("fixture tick failure")
                if fault == "partial": return
                yield {"index": 0 if fault == "index" else 1, "elapsed": .2 if fault == "stall" else 1 / rate,
                       "lateness_ms": 60 if fault == "stall" else 0}
            env.ticks = ticks
            with self.subTest(fault=fault), self.assertRaises((ValueError, RuntimeError)):
                execute_travel(env, 4242, cancel, report, Travel("forward_down"), latch)
            self.assertEqual(env.key_events, [("w", True), ("ctrl", True), ("ctrl", False), ("w", False)])
            self.assertEqual(latch.pending(), ())
            self.assertEqual(env.keys_down, set())

    def test_rejected_second_key_press_still_releases_first_and_uncertain_second(self):
        env, cancel, report = FakeTravelEnvironment(), threading.Event(), {}
        env.reject_down.add("shift")
        latch = KeyLatch(env, cancel)
        with self.assertRaises(ValueError):
            execute_travel(env, 4242, cancel, report, Travel("forward_up"), latch)
        self.assertEqual(env.key_events, [("w", True), ("shift", False), ("w", False)])
        self.assertEqual(env.keys_down, set())
        self.assertEqual(report["release_pending"], [])

    def test_cancel_between_presses_never_sends_second_key(self):
        env, cancel, report = FakeTravelEnvironment(), threading.Event(), {}
        original = env.key
        def key(name, down):
            original(name, down)
            if down: cancel.set()
        env.key = key
        latch = KeyLatch(env, cancel)
        with self.assertRaises(ValueError):
            execute_travel(env, 4242, cancel, report, Travel("forward_down"), latch)
        self.assertEqual(env.key_events, [("w", True), ("w", False)])

    def test_preexisting_physical_key_or_unfocused_game_is_never_released_by_helper(self):
        for fault in ("manual", "focus", "cancel"):
            env, cancel, report = FakeTravelEnvironment(), threading.Event(), {}
            if fault == "manual": env.manual.add("w")
            if fault == "focus": env.focus = False
            if fault == "cancel": cancel.set()
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                execute_travel(env, 4242, cancel, report, Travel(), KeyLatch(env, cancel))
            self.assertEqual(env.key_events, [])


class CombinedShotTests(unittest.TestCase):
    def test_constant_pan_has_exact_uniform_cadence_while_keys_stay_held(self):
        for pace, units, gap in (("slow", 60, 2), ("standard", 120, 1), ("wide", 240, 1)):
            for pan, sign in (("left", -1), ("right", 1)):
                with self.subTest(pace=pace, pan=pan):
                    env, cancel, report = FakeTravelEnvironment(), threading.Event(), {}
                    original = env.send_xy
                    def send(dx, dy):
                        self.assertEqual(env.keys_down, {"w", "shift"})
                        original(dx, dy)
                    env.send_xy = send
                    execute_travel(env, 4242, cancel, report, Travel("forward_up", 3, pan, pace), KeyLatch(env, cancel))
                    self.assertEqual(sum(dx for dx, dy in env.moves), sign * units * 3)
                    self.assertTrue(all(dy == 0 for dx, dy in env.moves))
                    deadlines = [round(row["deadline"] * 120) for row in report["sent"]]
                    self.assertEqual(deadlines, list(range(gap, 361, gap)))
                    self.assertEqual(report["inserted_relative_xy"], [sign * units * 3, 0])
                    self.assertEqual(report["planned_relative_xy"], report["inserted_relative_xy"])
                    self.assertEqual(env.key_events, [("w", True), ("shift", True), ("shift", False), ("w", False)])
                    self.assertEqual(env.keys_down, set())

    def test_extended_takes_and_pan_schema_are_finite_and_default_motion_is_preserved(self):
        for data in ({"duration": 6}, {"duration": 8, "pan": "right"}, {"pan": "up"},
                     {"pan": True}, {"pace": 120}, {"pace": "unbounded"}):
            with self.subTest(data=data), self.assertRaises(ValueError): Travel(**data)
        env, cancel, report = FakeTravelEnvironment(), threading.Event(), {}
        execute_travel(env, 4242, cancel, report, Travel("forward_down", 6, "left"), KeyLatch(env, cancel))
        self.assertEqual(report["inserted_relative_xy"], [-720, 0])
        self.assertEqual(report["translation"], {"pattern": "forward_down", "duration": 6})
        self.assertEqual(report["rotation"], {"pan": "left", "pace": "standard", "shape": "steady"})
        self.assertIsNone(report["actual_world_position"])
        self.assertIsNone(report["actual_camera_angles"])
        self.assertEqual(env.keys_down, set())

    def test_mouse_failure_focus_loss_and_cancel_after_mouse_release_all_keys(self):
        for fault in ("reject", "focus", "cancel"):
            env, cancel, report = FakeTravelEnvironment(), threading.Event(), {}
            original = env.send_xy
            if fault == "reject": env.fail_send = True
            def send(dx, dy):
                original(dx, dy)
                if fault == "focus": env.focus = False
                if fault == "cancel": cancel.set()
            env.send_xy = send
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                execute_travel(env, 4242, cancel, report, Travel("forward_down", 3, "right"), KeyLatch(env, cancel))
            self.assertEqual(len(env.moves), 0 if fault == "reject" else 1)
            self.assertEqual(len(report["sent"]), len(env.moves))
            self.assertEqual(env.keys_down, set())
            self.assertEqual(report["release_pending"], [])

    def test_cancel_after_foreground_guard_is_rechecked_before_mouse_insertion(self):
        env, cancel, report = FakeTravelEnvironment(), threading.Event(), {}
        checks = 0
        def active(pid, held):
            nonlocal checks
            checks += 1
            # Preflight, before W, watchdog index0, watchdog index1.
            if checks == 4: cancel.set()
            return True
        env.travel_active = active
        with self.assertRaises(ValueError):
            execute_travel(env, 4242, cancel, report, Travel("forward", 3, "right"), KeyLatch(env, cancel))
        self.assertEqual(env.moves, [])
        self.assertEqual(env.key_events, [("w", True), ("w", False)])

    def test_skips_preserve_pan_endpoint_but_large_catchup_releases_without_mouse_burst(self):
        env, cancel, report = FakeTravelEnvironment(), threading.Event(), {}
        env.ticks = lambda rate, duration: ({"index": i, "elapsed": i / rate, "lateness_ms": 0}
                                           for i in [0, 1, 4, *range(5, 361)])
        execute_travel(env, 4242, cancel, report, Travel("forward", 3, "right"), KeyLatch(env, cancel))
        self.assertEqual(report["inserted_relative_xy"], [360, 0])
        self.assertEqual(report["skipped"], 2)
        env, cancel, report = FakeTravelEnvironment(), threading.Event(), {}
        env.ticks = lambda rate, duration: ({"index": i, "elapsed": i / rate, "lateness_ms": 0} for i in (0, 5))
        with self.assertRaises(ValueError):
            execute_travel(env, 4242, cancel, report, Travel("forward", 3, "right", "wide"), KeyLatch(env, cancel))
        self.assertEqual(env.moves, [])
        self.assertEqual(env.keys_down, set())


class TravelSessionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = FakeTravelEnvironment()
        self.session = TravelSession(self.folder.name, self.env)

    def action(self, mode, data=None):
        self.session.start(mode, data or {})
        self.session.worker.join(2)
        self.assertFalse(self.session.worker.is_alive())
        return self.session.snapshot()

    def test_inspection_and_schema_gates_then_completed_evidence(self):
        self.assertEqual(self.action("inspect")["result"], "completed")
        self.assertEqual(self.env.key_events, [])
        for data in ({}, {"off_air": True, "key": "enter"}, {"off_air": True, "duration": 60},
                     {"off_air": True, "duration": True}, {"off_air": True, "duration": float("nan")},
                     {"off_air": True, "pattern": "backward"}):
            with self.subTest(data=data), self.assertRaises(ValueError): self.session.start("pan", data)
        state = self.action("pan", {"off_air": True, "pattern": "forward_down", "duration": .5})
        report = json.loads(Path(state["report"]).read_text(encoding="utf-8"))
        self.assertEqual(state["result"], "completed")
        self.assertEqual(report["translation"], {"pattern": "forward_down", "duration": .5})
        self.assertEqual([(x["key"], x["down"]) for x in report["key_events"]], self.env.key_events)
        self.assertIsNone(report["observed_camera_response"])
        self.assertEqual(report["release_pending"], [])

    def test_release_failure_retains_ownership_blocks_rearm_and_stop_recovers(self):
        self.action("inspect")
        self.env.reject_up.add("ctrl")
        state = self.action("pan", {"off_air": True, "pattern": "forward_down"})
        self.assertEqual(state["result"], "stopped")
        self.assertEqual(state["release_pending"], ["ctrl"])
        self.assertEqual(self.env.keys_down, {"ctrl"})
        self.assertIn(("w", False), self.env.key_events)  # Other releases still attempted.
        for mode, data in (("inspect", {}), ("pan", {"off_air": True})):
            with self.assertRaises(ValueError): self.session.start(mode, data)
        self.env.reject_up.clear()
        self.session.stop()
        self.assertEqual(self.session.snapshot()["release_pending"], [])
        self.assertEqual(self.env.keys_down, set())
        self.assertFalse(self.session.snapshot()["inspected"])

    def test_stop_releases_immediately_while_worker_waits_and_records_keyup(self):
        self.action("inspect")
        waiting, resume = threading.Event(), threading.Event()
        def ticks(rate, duration):
            yield {"index": 0, "elapsed": 0, "lateness_ms": 0}
            waiting.set()
            resume.wait(1)
            yield {"index": 1, "elapsed": 1 / rate, "lateness_ms": 0}
        self.env.ticks = ticks
        self.session.start("pan", {"off_air": True, "pattern": "forward_up", "pan": "right"})
        try:
            self.assertTrue(waiting.wait(1))
            self.assertEqual(self.env.keys_down, {"w", "shift"})
            self.session.stop()
            self.assertEqual(self.env.keys_down, set())  # Before unblocking the worker.
        finally:
            resume.set()
            self.session.worker.join(2)
        state = self.session.snapshot()
        report = json.loads(Path(state["report"]).read_text(encoding="utf-8"))
        self.assertEqual(state["result"], "stopped")
        self.assertEqual([(x["key"], x["down"]) for x in report["key_events"]], self.env.key_events)
        self.assertEqual(self.env.key_events, [("w", True), ("shift", True), ("shift", False), ("w", False)])
        self.assertEqual(self.env.moves, [])

    def test_identity_module_and_countdown_refusals_never_press_keys(self):
        for fault in ("identity", "module", "countdown", "after_countdown"):
            with self.subTest(fault=fault):
                self.env = FakeTravelEnvironment()
                self.session = TravelSession(self.folder.name, self.env)
                self.action("inspect")
                if fault == "identity": self.env.version += 1
                if fault == "module": self.env.module_error = True
                if fault == "countdown": self.env.stop_countdown = True
                if fault == "after_countdown": self.env.countdown = lambda cancel, note: setattr(self.env, "version", 2)
                self.assertEqual(self.action("pan", {"off_air": True})["result"], "stopped")
                self.assertEqual(self.env.key_events, [])


if __name__ == "__main__":
    unittest.main()
