"""Session and actual loopback HTTP checks. All game endpoints are simulated."""
import http.client
import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import patch

from demo_session import Session
from demo_web import make_server
from demo_web_fixture import FixtureEnvironment
import normal_console_probe


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = FixtureEnvironment()
        self.session = Session(Path(self.folder.name), self.env)

    def action(self, mode, data=None):
        self.session.start(mode, data or {})
        self.session.worker.join(2)
        self.assertFalse(self.session.worker.is_alive())
        return self.session.snapshot()

    def ready(self):
        self.session.prepare()
        self.action("inspect")
        self.action("echo")

    def test_prepare_is_repeatable_and_state_does_not_expose_credentials(self):
        first = self.session.prepare()
        self.assertEqual(self.session.prepare(), first)
        self.assertNotIn(self.session.password, json.dumps(self.session.snapshot()))
        self.assertEqual(self.env.clients, [])
        self.assertIn("-netconport 29090 -netconpassword ", first["options"])

    def test_echo_needs_inspection_pan_needs_echo_and_off_air(self):
        self.session.prepare()
        with self.assertRaises(ValueError):
            self.session.start("echo", {})
        self.action("inspect")
        self.assertEqual(self.env.clients, [])
        with self.assertRaises(ValueError):
            self.session.start("pan", {"off_air": True})
        self.action("echo")
        with self.assertRaises(ValueError):
            self.session.start("pan", {})
        self.assertFalse(any(c.startswith("spec_") for x in self.env.clients for c in x.commands))

    def test_finite_pan_and_evidence_keep_actual_observation_unknown(self):
        self.ready()
        state = self.action("pan", {"off_air": True})
        report = json.loads(Path(state["report"]).read_text(encoding="utf-8"))
        self.assertEqual(report["result"], "completed")
        self.assertEqual(report["mode"], "pan")
        self.assertEqual(len(report["sent"]), 121)
        self.assertEqual(report["sent"][-1]["command"], "spec_setang 0.00 12.00")
        self.assertIsNone(report["observed_camera_response"])
        for path in Path(self.folder.name).glob("*.json"):
            self.assertNotIn(self.session.password, path.read_text(encoding="utf-8"))
        self.assertTrue(all(client.closed for client in self.env.clients))

    def test_auth_spoof_module_change_identity_focus_and_countdown_stop(self):
        for fault in ("auth", "module", "identity", "focus", "countdown"):
            with self.subTest(fault=fault):
                self.env = FixtureEnvironment()
                self.session = Session(Path(self.folder.name), self.env)
                self.ready()
                if fault == "auth": self.env.allow_auth = False
                if fault == "module": self.env.module_error = True
                if fault == "identity": self.env.identity_version += 1
                if fault == "focus": self.env.allow_focus = False
                if fault == "countdown": self.env.cancel_countdown = True
                state = self.action("pan", {"off_air": True})
                self.assertEqual(state["result"], "stopped")
                self.assertFalse(state["verified"])
                self.assertFalse(any(c.startswith("spec_") for x in self.env.clients for c in x.commands))

    def test_stop_and_port_change_invalidate_connection(self):
        self.ready()
        self.session.stop()
        with self.assertRaises(ValueError):
            self.session.start("pan", {"off_air": True})
        self.ready()
        self.session.prepare(29091)
        self.assertFalse(self.session.snapshot()["inspected"])
        self.assertFalse(self.session.snapshot()["verified"])

    def test_console_close_error_preserves_evidence_and_releases_busy_state(self):
        self.session.prepare()
        self.action("inspect")
        connect = self.env.connect
        def failing_close(port):
            client = connect(port)
            def close():
                client.closed = True
                raise OSError("synthetic cleanup failure")
            client.close = close
            return client
        with patch.object(self.env, "connect", side_effect=failing_close):
            state = self.action("echo")
        self.assertFalse(state["busy"])
        self.assertFalse(state["verified"])
        report = json.loads(Path(state["report"]).read_text(encoding="utf-8"))
        self.assertEqual(report["result"], "stopped")
        self.assertEqual(report["cleanup_error_type"], "OSError")

    def test_process_queries_do_not_spawn_visible_console_windows(self):
        process = type("Result", (), {"stdout": json.dumps({"CreationDate": "fixture"})})()
        listener = type("Result", (), {"stdout": json.dumps({"LocalAddress": "127.0.0.1", "LocalPort": 29090})})()
        with patch.object(normal_console_probe.subprocess, "run", side_effect=[process, listener]) as run, \
                patch.object(normal_console_probe, "validate_record"):
            identity = normal_console_probe.check_process(4242, 29090, "synthetic_fixture_password")
        self.assertEqual(identity["pid"], 4242)
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["creationflags"],
                             getattr(normal_console_probe.subprocess, "CREATE_NO_WINDOW", 0))


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.session = Session(Path(self.folder.name), FixtureEnvironment())
        self.server = make_server(self.session)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        code, html = self.request("GET", "/")
        self.assertEqual(code, 200)
        self.token = re.search("const token='([^']+)'", html).group(1)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, method, path, data=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        try:
            connection.request(method, path, body=json.dumps(data) if data is not None else None,
                               headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read().decode("utf-8")
        finally:
            connection.close()

    def headers(self, **extra):
        return {"Origin": self.origin, "X-Dolly-Token": self.token, "Content-Type": "application/json", **extra}

    def test_actual_http_setup_and_same_origin_boundary(self):
        self.assertEqual(self.request("POST", "/prepare", {}, self.headers())[0], 200)
        for headers in ({}, self.headers(Origin="https://unrelated.example"),
                        self.headers(**{"X-Dolly-Token": "wrong"}),
                        self.headers(Host="unrelated.example")):
            self.assertEqual(self.request("POST", "/prepare", {}, headers)[0], 403)
        self.assertEqual(self.request("GET", "/", headers={"Host": "unrelated.example"})[0], 403)
        self.assertEqual(self.request("POST", "/arbitrary", {}, self.headers())[0], 404)
        self.assertEqual(self.request("POST", "/inspect", {"command": "arbitrary"}, self.headers())[0], 400)
        code, state = self.request("GET", "/state")
        self.assertNotIn(self.session.password, state)


if __name__ == "__main__":
    unittest.main()
