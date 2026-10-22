"""Ordinary-input owner checks: no actual OS input or live game control."""
import ctypes
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from mouse_fixture import FakeMouseEnvironment
from mouse_trial import Input, MouseEnvironment, MouseSession, execute_mouse, packet, verify_abi
import mouse_trial


class MousePacketTests(unittest.TestCase):
    def test_exact_windows_layout_and_relative_mouse_only(self):
        self.assertEqual(verify_abi()["input_bytes"], 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
        event = packet(3)
        self.assertEqual((event.type, event.mi.dx, event.mi.dy, event.mi.dwFlags), (0, 3, 0, 1))
        self.assertEqual((event.mi.mouseData, event.mi.time, event.mi.dwExtraInfo), (0, 0, 0))
        for dx in (False, 0, -1, 9, 1.5):
            with self.subTest(dx=dx), self.assertRaises(ValueError):
                packet(dx)

    def test_sendinput_exact_single_packet_and_zero_return_refuses_without_retry(self):
        api = MagicMock()
        api.SendInput.return_value = 1
        with patch.object(mouse_trial.ctypes, "WinDLL", return_value=api):
            MouseEnvironment().send(2)
        args = api.SendInput.call_args.args
        self.assertEqual((args[0], args[2]), (1, ctypes.sizeof(Input)))
        event = ctypes.cast(args[1], ctypes.POINTER(Input)).contents
        self.assertEqual((event.mi.dx, event.mi.dy, event.mi.dwFlags), (2, 0, 1))
        api.SendInput.reset_mock()
        api.SendInput.return_value = 0
        with patch.object(mouse_trial.ctypes, "WinDLL", return_value=api), self.assertRaises(ValueError):
            MouseEnvironment().send(2)
        self.assertEqual(api.SendInput.call_count, 1)


class MouseScheduleTests(unittest.TestCase):
    def test_two_seconds_exact_total_and_skipped_ticks_coalesce_within_bound(self):
        for indices in (range(241), [0, 1, 4, *range(5, 241)]):
            env, evidence = FakeMouseEnvironment(), {}
            env.ticks = lambda rate, duration: ({"index": i, "elapsed": i / rate, "lateness_ms": 0}
                                               for i in indices)
            execute_mouse(env, 4242, threading.Event(), evidence)
            self.assertEqual(sum(env.moves), 240)
            self.assertLessEqual(max(env.moves), 8)
            self.assertEqual(evidence["sent"][-1]["deadline"], 2)
            self.assertEqual(evidence["inserted_relative_dx"], 240)

    def test_focus_cancel_stall_rejection_and_partial_schedule_stop(self):
        for fault in ("focus", "cancel", "stall", "rejected", "partial"):
            env, evidence, cancel = FakeMouseEnvironment(), {}, threading.Event()
            if fault == "focus": env.focus = False
            if fault == "cancel": cancel.set()
            if fault == "stall":
                env.ticks = lambda rate, duration: iter([{"index": 12, "elapsed": .1, "lateness_ms": 60}])
            if fault == "rejected": env.fail_send = True
            if fault == "partial":
                env.ticks = lambda rate, duration: iter([{"index": 1, "elapsed": 1 / 120, "lateness_ms": 0}])
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                execute_mouse(env, 4242, cancel, evidence)
            self.assertEqual(len(env.moves), 1 if fault == "partial" else 0)
            self.assertEqual(len(evidence["sent"]), len(env.moves))


class MouseSessionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = FakeMouseEnvironment()
        self.session = MouseSession(self.folder.name, self.env)

    def action(self, mode, data=None):
        self.session.start(mode, data or {})
        self.session.worker.join(2)
        self.assertFalse(self.session.worker.is_alive())
        return self.session.snapshot()

    def test_inspection_is_inert_and_explicit_confirmation_required(self):
        with self.assertRaises(ValueError): self.session.start("pan", {"off_air": True})
        state = self.action("inspect")
        self.assertTrue(state["inspected"])
        self.assertEqual(self.env.moves, [])
        with self.assertRaises(ValueError): self.session.start("pan", {})
        with self.assertRaises(ValueError): self.session.start("pan", {"off_air": True, "dx": 999})
        with self.assertRaises(ValueError): self.session.start("echo", {})
        with self.assertRaises(ValueError): self.session.prepare()

    def test_complete_input_trial_records_insertion_only_without_reset(self):
        self.action("inspect")
        state = self.action("pan", {"off_air": True})
        self.assertEqual(state["result"], "completed")
        report = json.loads(Path(state["report"]).read_text(encoding="utf-8"))
        self.assertEqual(report["inserted_relative_dx"], 240)
        self.assertIsNone(report["actual_angle_degrees"])
        self.assertIsNone(report["observed_camera_response"])
        self.assertTrue(all(dx > 0 for dx in self.env.moves))

    def test_changed_identity_countdown_stop_and_module_error_send_nothing(self):
        for fault in ("identity", "countdown", "module"):
            with self.subTest(fault=fault):
                self.env = FakeMouseEnvironment()
                self.session = MouseSession(self.folder.name, self.env)
                self.action("inspect")
                if fault == "identity": self.env.version += 1
                if fault == "countdown": self.env.stop_countdown = True
                if fault == "module": self.env.module_error = True
                self.assertEqual(self.action("pan", {"off_air": True})["result"], "stopped")
                self.assertEqual(self.env.moves, [])

    def test_normal_identity_accepts_unused_netcon_options_without_retaining_secrets(self):
        row = {"ProcessId": 4242, "ExecutablePath": str(mouse_trial.EXE),
               "CommandLine": "synthetic command", "CreationDate": "fixture"}
        result = type("Result", (), {"stdout": json.dumps([row])})()
        for flags, accepted in ((["-netconport", "29090", "-netconpassword", "synthetic_fixture_only"], True),
                                (["-insecure"], False), (["-dev"], False), (["-tools"], False),
                                (["-game", "citadel_dolly_fixture"], False)):
            with self.subTest(flags=flags), patch.object(mouse_trial.subprocess, "run", return_value=result), \
                    patch.object(mouse_trial, "argv_tokens", return_value=[str(mouse_trial.EXE), *flags]):
                if accepted:
                    identity = mouse_trial.normal_identity()
                    self.assertEqual(set(identity), {"pid", "created", "executable"})
                    self.assertNotIn("synthetic_fixture_only", json.dumps(identity))
                else:
                    with self.assertRaises(ValueError): mouse_trial.normal_identity()


if __name__ == "__main__":
    unittest.main()
