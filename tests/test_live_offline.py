"""Behavioral checks for the disconnected desk, without windows or game access."""
import ast
import io
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dolly_live.desk import Desk, main
from dolly_live.presets import Library, MAP, Preset, defaults
from dolly_live.runtime import CueRunner, MockCamera, Pose, SyntheticScene, look_at


class LibraryTests(unittest.TestCase):
    def test_every_builtin_is_labeled_synthetic(self):
        bank = list(defaults())
        self.assertEqual({p.id for p in bank},
                         {"walker", "mid-boss", "bridge", "rollout", "hero-pan", "hero-follow"})
        for p in bank:
            self.assertTrue(p.synthetic)
            self.assertEqual(p.map_revision, MAP)
            self.assertIn("SYNTHETIC", p.name)
            p.validate()

    def test_save_load_preserves_motion_and_never_overwrites(self):
        library = defaults()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "presets with spaces.json"
            library.save(path)
            loaded = Library.load(path)
            for a, b in zip(library, loaded):
                self.assertEqual(a.to_dict(), b.to_dict())
                self.assertEqual(a.project.evaluate(1.234), b.project.evaluate(1.234))
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                library.save(path)
            self.assertEqual(path.read_bytes(), before)

    def test_bank_get_is_a_snapshot(self):
        library = defaults()
        p = library.get("walker")
        p.project.keyframes[0].x = 12345
        self.assertNotEqual(library.get("walker").project.keyframes[0].x, 12345)

    def test_bad_envelopes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            for raw in ('{}', '[]', '{"version":1,"version":1}',
                        '{"format":"deadlock-dolly-live-offline","version":true,"presets":[]}'):
                path.write_text(raw)
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    Library.load(path)
            path.write_bytes(b" " * (1024 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, "1 MiB"):
                Library.load(path)

    def test_invalid_presets_are_rejected(self):
        for field, value in (("synthetic", False), ("map_revision", "real-map"),
                             ("mode", "native"), ("id", "../bad"), ("target", "hero-a")):
            raw = defaults().get("walker").to_dict()
            raw[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                Preset.from_dict(raw)

    def test_bad_keys_and_extra_fields_rejected(self):
        for field, value in (("time", float("nan")), ("x", True), ("yaw", float("inf"))):
            raw = defaults().get("walker").to_dict()
            raw["keys"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                Preset.from_dict(raw)
        raw = defaults().get("walker").to_dict()
        raw["command"] = "playdemo whatever"
        with self.assertRaises(ValueError):
            Preset.from_dict(raw)
        raw.pop("command")
        raw["keys"][1]["time"] = 0
        with self.assertRaises(ValueError):
            Preset.from_dict(raw)

    def test_duplicate_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            Library([defaults().get("walker"), defaults().get("walker")])

    def test_cvar_and_attachment_payloads_never_enter_live_library(self):
        p = defaults().get("walker")
        p.project.setup_values = {"r_drawviewmodel": 0}
        with self.assertRaises(ValueError):
            p.validate()
        p.project.setup_values = {}
        p.project.keyframes[0].source_blend = 1
        with self.assertRaises(ValueError):
            p.validate()

    def test_unsupported_lens_is_not_silently_lost_on_save(self):
        p = defaults().get("walker")
        p.project.keyframes[0].aspect_ratio = 2
        with self.assertRaisesRegex(ValueError, "Lens"):
            p.to_dict()


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.camera = MockCamera()
        self.scene = SyntheticScene()
        self.runner = CueRunner(self.camera, self.scene)

    def start(self, name="walker", now=0, duration=None):
        self.runner.cue(defaults().get(name), now, duration)
        self.runner.run(now)

    def test_cue_does_not_move_camera(self):
        self.runner.cue(defaults().get("walker"), 45)
        self.assertEqual(self.runner.state, "ready")
        self.assertFalse(self.camera.active)
        self.assertIsNone(self.camera.pose)

    def test_relative_clock_and_duration_override(self):
        self.start(now=100, duration=12)
        self.runner.update(106)
        expected = defaults().get("walker").project.evaluate(3)
        self.assertAlmostEqual(self.camera.pose.x, expected["x"])
        self.assertEqual(self.runner.elapsed, 6)
        self.runner.update(112)
        self.assertEqual(self.runner.state, "held")
        self.assertAlmostEqual(self.camera.pose.x, 90)

    def test_cued_path_is_immutable_snapshot(self):
        preset = defaults().get("walker")
        self.runner.cue(preset, 0)
        preset.project.keyframes[0].x = 999
        self.runner.run(0)
        self.assertEqual(self.camera.pose.x, -100)

    def test_large_step_clamps_to_endpoint(self):
        self.start()
        self.runner.update(100)
        self.assertEqual(self.runner.elapsed, 6)
        self.assertEqual(self.camera.pose.x, 90)
        self.assertEqual(self.runner.state, "held")

    def test_hold_freezes_camera_not_world(self):
        self.start("hero-follow", duration=10)
        self.runner.update(1)
        self.runner.hold(1)
        before = self.camera.pose
        target = self.scene.sample("hero-a", 1)
        self.runner.update(2)
        self.assertEqual(self.camera.pose, before)
        self.assertNotEqual(self.scene.sample("hero-a", 2).position, target.position)
        self.assertEqual(self.runner.elapsed, 1)

    def test_cancel_releases_immediately_and_cannot_restart(self):
        self.start()
        self.runner.release()
        before = len(self.camera.trace)
        self.runner.update(2)
        self.assertFalse(self.camera.active)
        self.assertEqual(len(self.camera.trace), before)
        with self.assertRaises(ValueError):
            self.runner.run(2)

    def test_disconnect_reconnect_requires_fresh_cue(self):
        self.start()
        self.camera.connect(False)
        self.camera.connect(True)
        self.runner.update(1)
        self.assertEqual(self.runner.state, "fault")
        self.assertFalse(self.camera.active)
        self.runner.update(2)
        self.assertEqual(self.runner.state, "fault")
        self.runner.cue(defaults().get("walker"), 2)
        self.runner.run(2)
        self.assertTrue(self.camera.active)

    def test_map_mismatch_rejects_and_map_change_releases(self):
        self.camera.set_map("wrong")
        with self.assertRaisesRegex(ValueError, "Map revision"):
            self.runner.cue(defaults().get("walker"), 0)
        self.assertFalse(self.camera.active)
        self.camera.set_map(MAP)
        self.start()
        self.camera.set_map("wrong")
        self.runner.update(1)
        self.assertEqual(self.runner.state, "fault")

    def test_lost_target_releases_without_writing(self):
        self.start("hero-pan")
        count = len(self.camera.trace)
        self.scene.change("hero-a", "lose", 0)
        self.runner.update(0.1)
        self.assertEqual(self.runner.state, "fault")
        self.assertEqual(len(self.camera.trace), count)
        self.assertFalse(self.camera.active)

    def test_stale_and_replaced_targets_release(self):
        for action in ("freeze", "restore"):
            self.setUp()
            self.start("hero-follow")
            self.scene.change("hero-a", action, 0)
            self.runner.update(0.3)
            self.assertEqual(self.runner.state, "fault")
            self.assertFalse(self.camera.active)

    def test_missing_target_at_cue_rejected(self):
        self.scene.change("hero-a", "lose", 0)
        with self.assertRaisesRegex(ValueError, "missing"):
            self.runner.cue(defaults().get("hero-pan"), 0)

    def test_look_at_tracks_from_rail_position(self):
        self.start("hero-pan")
        self.runner.update(1)
        position = defaults().get("hero-pan").project.evaluate(1)
        self.assertAlmostEqual(self.camera.pose.x, position["x"])
        self.assertAlmostEqual(self.camera.pose.y, position["y"])
        target = self.scene.sample("hero-a", 1)
        dx = target.position[0] - self.camera.pose.x
        dy = target.position[1] - self.camera.pose.y
        self.assertAlmostEqual(math.sin(math.radians(self.camera.pose.yaw)), dy / math.hypot(dx, dy))

    def test_follow_keeps_world_offset_and_aims_at_target(self):
        self.start("hero-follow")
        for now in (0.5, 1, 1.5):
            self.runner.update(now)
            target = self.scene.sample("hero-a", now)
            self.assertAlmostEqual(self.camera.pose.x - target.position[0], -70)
            self.assertAlmostEqual(self.camera.pose.y - target.position[1], -50)
            self.assertAlmostEqual(self.camera.pose.z - target.position[2], 40)

    def test_invalid_clock_fails_closed(self):
        for now in (-1, float("nan"), float("inf")):
            self.setUp()
            self.start()
            self.runner.update(now)
            self.assertEqual(self.runner.state, "fault")
            self.assertFalse(self.camera.active)
        self.setUp()
        self.start(now=10)
        self.runner.update(9)
        self.assertEqual(self.runner.state, "fault")

    def test_invalid_durations_and_recue_while_active(self):
        for duration in (0, -1, 121, True, float("nan")):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                self.runner.cue(defaults().get("walker"), 0, duration)
        self.start()
        with self.assertRaises(ValueError):
            self.runner.cue(defaults().get("bridge"), 0)
        self.assertEqual(self.runner.state, "running")

    def test_coincident_lookat_fails_instead_of_bad_angles(self):
        with self.assertRaises(ValueError):
            look_at(Pose(1, 2, 3, 0, 0, 0), (1, 2, 3))

    def test_mock_trace_is_bounded(self):
        for i in range(600):
            self.camera.write(Pose(i, 0, 0, 0, 0, 0))
        self.assertEqual(len(self.camera.trace), 512)

    def test_every_preset_reaches_same_pose_with_different_step_sizes(self):
        for preset in defaults():
            direct = CueRunner(MockCamera(), SyntheticScene())
            sampled = CueRunner(MockCamera(), SyntheticScene())
            for runner in (direct, sampled):
                runner.cue(preset, 50)
                runner.run(50)
            direct.update(51.5)
            for i in range(1, 91):
                sampled.update(50 + i / 60)
            with self.subTest(preset=preset.id):
                for key in ("x", "y", "z", "pitch", "roll"):
                    self.assertAlmostEqual(getattr(direct.camera.pose, key), getattr(sampled.camera.pose, key))
                self.assertAlmostEqual(math.sin(math.radians(direct.camera.pose.yaw)),
                                       math.sin(math.radians(sampled.camera.pose.yaw)))

    def test_held_target_loss_releases_and_new_identity_does_not_resume(self):
        self.start("hero-follow")
        self.runner.hold(1)
        self.scene.change("hero-a", "lose", 1)
        self.runner.update(1)
        self.assertEqual(self.runner.state, "fault")
        self.scene.change("hero-a", "restore", 1)
        self.runner.update(2)
        self.assertFalse(self.camera.active)
        self.assertEqual(self.runner.state, "fault")


class DeskTests(unittest.TestCase):
    def test_operator_workflow_and_actor_selection(self):
        desk = Desk()
        desk.execute("cue hero-follow 10 hero-b")
        desk.execute("run")
        desk.execute("step 2")
        self.assertEqual(desk.runner.preset.target, "hero-b")
        self.assertEqual(desk.runner.elapsed, 2)
        pose = desk.camera.pose
        desk.execute("hold")
        desk.execute("step 2")
        self.assertEqual(desk.time, 4)
        self.assertEqual(desk.camera.pose, pose)
        self.assertIn("SYNTHETIC", desk.execute("view"))
        desk.execute("cancel")
        self.assertFalse(desk.camera.active)

    def test_load_is_atomic_and_requires_released_camera(self):
        desk = Desk()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bank with spaces.json"
            desk.execute(f'save "{path}"')
            desk.execute(f'load "{path}"')
            before = desk.library
            path.write_text("{}")
            with self.assertRaises(ValueError):
                desk.execute(f'load "{path}"')
            self.assertIs(desk.library, before)
            desk.execute("cue walker")
            with self.assertRaisesRegex(ValueError, "Release"):
                desk.execute(f'load "{path}"')

    def test_cli_demo_no_windows(self):
        output = io.StringIO()
        self.assertEqual(main(["--demo"], stdout=output), 0)
        self.assertIn("Camera held", output.getvalue())
        self.assertIn("SYNTHETIC", output.getvalue())

    def test_script_file_and_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "commands.txt"
            path.write_text("# comment\n\ncue bridge\nrun\nstep 2\nrelease\nquit\n", encoding="utf-8")
            self.assertEqual(main(["--script", str(path)], stdout=io.StringIO()), 0)
            self.assertEqual(main(["--script", str(path) + ".missing"], stdout=io.StringIO()), 1)

    def test_stdin_script_and_eof_release(self):
        desk = Desk()
        with patch("dolly_live.desk.Desk", return_value=desk):
            self.assertEqual(main([], io.StringIO("cue walker\nrun\nstep 1\n"), io.StringIO()), 0)
        self.assertFalse(desk.camera.active)

    def test_script_fault_is_nonzero_and_releases(self):
        desk = Desk()
        with patch("dolly_live.desk.Desk", return_value=desk):
            result = main([], io.StringIO("cue hero-pan\nrun\ntarget hero-a lose\n"), io.StringIO())
        self.assertEqual(result, 1)
        self.assertFalse(desk.camera.active)

    def test_invalid_command_step_and_args(self):
        desk = Desk()
        for command in ("launch", "run extra", "step nan", "step -1", "step 31", 'load "unterminated'):
            with self.subTest(command=command), self.assertRaises(ValueError):
                desk.execute(command)
        self.assertEqual(desk.time, 0)

    def test_runtime_import_boundary(self):
        # The offline package may use standard-library math/files/terminal helpers
        # and dolly_live._vendor.dolly.path only. No launcher, GUI, transport or process access.
        allowed = {"__future__", "dataclasses", "json", "math", "pathlib", "re",
                   "collections", "argparse", "shlex", "sys", "dolly_live._vendor.dolly.path"}
        # Pure key-chord enumeration and host-only timing for Phase 0. Keep
        # clock access confined to the paced trace player; the desk stays on
        # explicit simulation time. No OS input, sockets or process modules.
        scoped = {"motion.py": {"itertools"}, "playback.py": {"bisect", "time"}}
        root = Path(__file__).resolve().parents[1] / "dolly_live"
        for path in root.glob("*.py"):
            module_allowed = allowed | scoped.get(path.name, set())
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        self.assertIn(name.name, module_allowed, str(path))
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    self.assertIn(node.module, module_allowed, str(path))


if __name__ == "__main__":
    unittest.main()
