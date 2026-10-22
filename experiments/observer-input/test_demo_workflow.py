"""Private integration checks with fake console/process/clock; never uses a game."""
import json
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch

import demo_core
import demo_panel


class Value:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class ClipboardButtonTests(unittest.TestCase):
    def panel(self, password="synthetic_fixture_password", port="29090"):
        panel = object.__new__(demo_panel.Panel)
        panel.password, panel.port = Value(password), Value(port)
        panel.status, panel.copy_feedback = Value(), Value()
        panel.root = type("Root", (), {"winfo_id": lambda self: 123})()
        return panel

    def test_invalid_password_and_port_explain_next_to_copy_without_touching_clipboard(self):
        for password, port in (("short", "29090"), ("", "29090"), ("synthetic_fixture_password", "wrong")):
            with self.subTest(port=port), patch.object(demo_panel, "copy_text") as copy:
                panel = self.panel(password, port)
                panel.copy_options()
                copy.assert_not_called()
                self.assertTrue(panel.copy_feedback.get())
                self.assertNotIn("copied", panel.copy_feedback.get().lower())

    def test_success_transfers_exact_options_and_only_then_reports_checked(self):
        panel = self.panel()
        with patch.object(demo_panel, "copy_text") as copy:
            panel.copy_options()
            copy.assert_called_once_with(123, "-netconport 29090 -netconpassword synthetic_fixture_password")
        self.assertIn("Copied and checked", panel.copy_feedback.get())
        self.assertNotIn("synthetic_fixture_password", panel.copy_feedback.get())

    def test_clipboard_failure_exposes_manual_copy_instead_of_claiming_success(self):
        panel = self.panel()
        with patch.object(demo_panel, "copy_text", side_effect=OSError("fixture write failure")):
            panel.copy_options()
        self.assertIn("Show for manual copy", panel.copy_feedback.get())
        self.assertNotIn("Copied and checked", panel.copy_feedback.get())


class FakeConsole:
    instances = []
    authenticated = True

    def __init__(self, **kwargs):
        self.commands = []
        self.closed = False
        self.instances.append(self)

    def connect(self, host, port, timeout):
        assert host == "127.0.0.1" and port == 29090

    def send(self, command):
        assert not self.closed
        self.commands.append(command)

    def request(self, command, timeout):
        self.commands.append(command)
        return command[5:] if self.authenticated else command

    def close(self):
        self.closed = True


class FastCancel:
    def __init__(self, stop_countdown=False):
        self.cancelled = False
        self.stop_countdown = stop_countdown

    def is_set(self):
        return self.cancelled

    def wait(self, seconds):
        self.cancelled = self.stop_countdown
        return self.cancelled


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        FakeConsole.instances = []
        FakeConsole.authenticated = True
        self.identity = {"pid": 123, "created": "fixture", "listeners": {
            "LocalAddress": "127.0.0.1", "LocalPort": 29090}}

    def run_trial(self, mode="pan", *, identities=None, modules=None, countdown_stop=False,
                  manual=False, focus=123):
        panel = object.__new__(demo_panel.Panel)
        panel.messages, panel.cancel = queue.Queue(), FastCancel(countdown_stop)
        panel.client = None
        password = "fixture_password_not_real"
        prior = (123, 29090, password, self.identity, 0)
        arguments = (123, 29090, password, demo_core.Selection(), prior)
        def paced(client, selection, **kwargs):
            return demo_core.execute_angles(client, selection, **kwargs,
                ticks=lambda rate, duration: ({"index": i, "elapsed": i / rate, "lateness_ms": 0}
                                             for i in range(round(rate * duration) + 1)))
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(demo_panel, "HERE", Path(folder)), \
                patch.object(demo_panel, "verify_modules", side_effect=modules or [demo_core.PINS]), \
                patch.object(demo_panel, "check_process", side_effect=identities or [self.identity, self.identity]), \
                patch.object(demo_panel, "ConsoleClient", FakeConsole), \
                patch.object(demo_panel, "execute_angles", side_effect=paced), \
                patch.object(demo_panel, "manual_stop_key", return_value=manual), \
                patch.object(demo_panel, "foreground_pid", return_value=focus):
            panel.work(mode, arguments)
            paths = list(Path(folder).rglob("*.json"))
            raw = paths[0].read_text(encoding="utf-8") if paths else ""
            self.assertNotIn(password, raw)
            self.assertNotIn("PASS ", raw)
            report = json.loads(raw) if raw else None
        messages = list(panel.messages.queue)
        return report, messages, [c for instance in FakeConsole.instances for c in instance.commands]

    def test_echo_never_moves_and_returns_verified_identity(self):
        report, messages, commands = self.run_trial("echo")
        self.assertEqual(report["result"], "completed")
        self.assertEqual(report["sent"], [])
        self.assertTrue(any(kind == "verified" for kind, value in messages))
        self.assertFalse(any(c.startswith("spec_") for c in commands))
        self.assertTrue(all(instance.closed for instance in FakeConsole.instances))

    def test_inspection_reports_binding_without_constructing_transport(self):
        report, messages, commands = self.run_trial("inspect")
        self.assertIsNone(report)
        self.assertEqual(FakeConsole.instances, [])
        self.assertTrue(any(kind == "binding" and "127.0.0.1" in value for kind, value in messages))
        self.assertTrue(any(kind == "inspected" for kind, value in messages))

    def test_pan_authenticates_then_sends_finite_endpoint_without_reset(self):
        report, messages, commands = self.run_trial()
        self.assertEqual(report["result"], "completed")
        self.assertEqual(len(report["sent"]), 121)
        self.assertEqual(commands[-1], "spec_setang 0.00 12.00")
        self.assertIsNone(report["observed_camera_response"])
        self.assertEqual(report["smoothness_verdict"], "UNMEASURED")

    def test_auth_spoof_countdown_identity_focus_and_takeover_refuse_camera(self):
        FakeConsole.authenticated = False
        report, messages, commands = self.run_trial()
        self.assertEqual(report["result"], "stopped")
        self.assertFalse(any(c.startswith("spec_") for c in commands))
        FakeConsole.authenticated = True
        for kwargs in ({"countdown_stop": True}, {"manual": True}, {"focus": 999},
                       {"identities": [self.identity, dict(self.identity, created="different")]}):
            with self.subTest(kwargs=kwargs):
                FakeConsole.instances = []
                report, messages, commands = self.run_trial(**kwargs)
                self.assertEqual(report["result"], "stopped")
                self.assertFalse(any(c.startswith("spec_") for c in commands))
                self.assertTrue(all(instance.closed for instance in FakeConsole.instances))

    def test_module_mismatch_never_constructs_transport(self):
        report, messages, commands = self.run_trial(modules=[ValueError("unreviewed module")])
        self.assertIsNone(report)
        self.assertEqual(FakeConsole.instances, [])
        self.assertTrue(any(kind == "failed" for kind, value in messages))


if __name__ == "__main__":
    unittest.main()
