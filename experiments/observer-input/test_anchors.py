"""Offline authoring contracts; synthetic coordinates never reach a game."""
from dataclasses import asdict
import http.client
import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import patch

from anchors import Anchor, AnchorBank, dolly_keyframe, load_dolly_keyframe, unique_json
from anchor_web import AnchorDesk, APP
from demo_web import make_server


def example(**changes):
    return Anchor(**{**dict(name="SYNTHETIC test", map_label="Fixture only", x=123.125,
                           y=-456.5, z=789, pitch=22.5, yaw=370), **changes})


class AnchorTests(unittest.TestCase):
    def test_numeric_only_command_and_finite_validation(self):
        point = example(name='Quoted " ; name', x=-0.0000001)
        self.assertEqual(point.command(), "spec_goto 0.000000 -456.500000 789.000000 22.500000 10.000000")
        self.assertEqual(point.display()["live_status"], "unverified")
        for field, values in {"x": [True, "1;quit", float("nan"), float("inf"), 1e7, 10**1000],
                              "pitch": [90, -90, 180], "name": ["", "a\nb"], "origin": ["verified"]}.items():
            for value in values:
                with self.subTest(field=field, value=str(value)[:40]), self.assertRaises(ValueError):
                    example(**{field: value})
        with self.assertRaises(ValueError):
            Anchor.from_dict({**asdict(point), "command": "quit"})

    def test_free_key_import_is_pose_only_and_refuses_relative_or_rolled_sources(self):
        key = {k: getattr(example(), k) for k in ("x", "y", "z", "pitch", "yaw")}
        raw = {"format": "deadlock-dolly", "version": 12, "keyframes": [key],
               "setup_values": {"unrelated": "never interpreted"}}
        point = dolly_keyframe(raw, 0, "Imported", "Operator map label")
        self.assertEqual(point.command(), "spec_goto 123.125000 -456.500000 789.000000 22.500000 10.000000")
        self.assertEqual(point.origin, "dolly-keyframe")
        for change in ({"source": "game"}, {"source": "attach"}, {"attach": {}},
                       {"source_blend": True}, {"roll": 1}, {"pitch": float("nan")}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                dolly_keyframe({**raw, "keyframes": [{**key, **change}]}, 0, "Test", "Map")
        for change in ({"format": "other"}, {"version": 13}, {"version": True}, {"keyframes": []}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                dolly_keyframe({**raw, **change}, 0, "Test", "Map")
        with self.assertRaises(ValueError):
            dolly_keyframe(raw, True, "Test", "Map")
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "project.json"
            path.write_text(json.dumps(raw), encoding="utf-8-sig")
            self.assertEqual(load_dolly_keyframe(path, 0, "Imported", "Operator map label"), point)

    def test_duplicate_and_nonfinite_json_are_refused(self):
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '[', '[[[['):
            with self.subTest(text=text), self.assertRaises(ValueError):
                unique_json(text)

    def test_saved_dolly_producer_uses_effective_rotation_curve_values(self):
        from dolly_live._vendor.dolly.path import Keyframe, Project
        project = Project(name="SYNTHETIC source", keyframes=[
            Keyframe(0, 123.125, -456.5, 789, 22.5, 370, 0, curve_yaw=400)])
        point = dolly_keyframe(project.to_dict(), 0, "Imported", "Synthetic map")
        self.assertEqual(point.command(), "spec_goto 123.125000 -456.500000 789.000000 22.500000 40.000000")
        project.keyframes[0].curve_roll = 10
        with self.assertRaises(ValueError):
            dolly_keyframe(project.to_dict(), 0, "Imported", "Synthetic map")

    def test_persistence_is_add_only_idempotent_and_survives_write_failure(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "points.json"
            bank = AnchorBank(path)
            first = bank.add(example())
            self.assertEqual(bank.add(example()), first)
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                bank.add(example(name="synthetic TEST", x=200))
            with patch("anchors.os.replace", side_effect=OSError("synthetic failure")), self.assertRaises(ValueError):
                bank.add(example(name="Second point"))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(bank.snapshot(), [first])
            self.assertEqual(AnchorBank(path).snapshot(), [first])
            path.write_bytes(b'{"broken":true}')
            with self.assertRaises(ValueError): bank.add(example(name="External change"))
            with self.assertRaises(ValueError): AnchorBank(path)
            self.assertEqual(path.read_bytes(), b'{"broken":true}')


class AnchorHttpTests(unittest.TestCase):
    def test_real_loopback_authoring_boundaries_and_no_game_actions(self):
        with tempfile.TemporaryDirectory() as root:
            desk = AnchorDesk(AnchorBank(Path(root) / "points.json"))
            server = make_server(desk, page="anchor_web.html", app=APP, actions=desk.actions())
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
            thread.start()
            def request(method, path, data=None, extra=None):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
                try:
                    headers = {"Content-Type": "application/json", **(extra or {})}
                    connection.request(method, path, json.dumps(data) if data is not None else None, headers)
                    reply = connection.getresponse()
                    return reply.status, reply.read().decode("utf-8")
                finally:
                    connection.close()
            try:
                status, html = request("GET", "/")
                self.assertEqual(status, 200)
                token = re.search("const token='([^']+)'", html).group(1)
                headers = {"Origin": f"http://127.0.0.1:{server.server_port}", "X-Dolly-Token": token}
                data = asdict(example())
                self.assertEqual(request("POST", "/anchors/preview", data, headers)[0], 200)
                self.assertEqual(desk.snapshot()["anchors"], [])
                imported = {"format": "deadlock-dolly", "version": 12, "key": data,
                            "name": "Imported preview", "map_label": "Synthetic map"}
                code, result = request("POST", "/anchors/import", imported, headers)
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(result)["command"],
                                 "spec_goto 123.125000 -456.500000 789.000000 22.500000 10.000000")
                self.assertEqual(desk.snapshot()["anchors"], [])
                self.assertEqual(request("POST", "/anchors/save", data, headers)[0], 200)
                for extra in ({"Origin": "https://other.example"}, {"X-Dolly-Token": "wrong"}):
                    self.assertEqual(request("POST", "/anchors/save", asdict(example(name="Rejected")),
                                             {**headers, **extra})[0], 403)
                self.assertEqual(len(desk.snapshot()["anchors"]), 1)
                for route in ("/prepare", "/inspect", "/pan"):
                    self.assertEqual(request("POST", route, {}, headers)[0], 400)
                self.assertEqual(request("POST", "/anchors/execute", data, headers)[0], 404)
                self.assertEqual(request("POST", "/anchors/save", {**data, "x": "0;quit"}, headers)[0], 400)
                _, state = request("GET", "/state")
                self.assertFalse(json.loads(state)["live_teleport"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(2)
