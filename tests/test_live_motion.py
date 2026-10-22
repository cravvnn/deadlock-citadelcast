"""Offline contracts: rate aliasing, framing preservation and fail-closed pacing.

These tests never run a game and cannot establish live compatibility.
"""
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dolly_live._vendor.dolly.path import Keyframe, Project
from dolly_live.helper import main, rate_report
from dolly_live.motion import (InputModel, compile_console, compile_input,
                              render_metrics, simulate_render)
from dolly_live.playback import MockOutput, TraceRunner, deadline_ticks


def rail(distance=600, duration=1, yaw=0, end_yaw=None):
    return Project(name="SYNTHETIC rate fixture", interpolation="linear", keyframes=[
        Keyframe(0, 0, 0, 0, 0, yaw, 0),
        Keyframe(duration, distance, 0, 0, 0, yaw if end_yaw is None else end_yaw, 0)])


class MotionCompilationTests(unittest.TestCase):
    def test_console_commands_keep_position_facing_and_exact_partial_endpoint(self):
        project = rail(distance=78, duration=.13, yaw=170, end_yaw=-170)
        plan = compile_console(project, rate_hz=30)
        self.assertEqual(len(plan.frames), 5)
        self.assertEqual(plan.frames[-1].time, .13)
        self.assertEqual(plan.frames[-1].commands, ("spec_goto 78.00 0.00 0.00 0.00 190.00",))
        self.assertTrue(all(len(f.commands[0].split()) == 6 for f in plan.frames))
        self.assertEqual(plan.rebase_commands, ("spec_goto 0.00 0.00 0.00 0.00 170.00",
                         "spec_setpos 0.00 0.00 0.00", "spec_setang 0.00 170.00"))
        project.keyframes[-1].x = 999
        self.assertEqual(plan.frames[-1].pose.x, 78)

    def test_unsupported_channels_and_invalid_bounds_refuse_instead_of_disappearing(self):
        for compiler in (compile_console, compile_input):
            for attribute, value in (("roll", 1), ("pitch", 90), ("fov", 80),
                                     ("curve_yaw", 10), ("lens_scale", 1.0)):
                with self.subTest(compiler=compiler.__name__, attribute=attribute):
                    project = rail()
                    setattr(project.keyframes[-1], attribute, value)
                    with self.assertRaises(ValueError):
                        compiler(project)
            for options in ({"rate_hz": math.nan}, {"rate_hz": 0}, {"rate_hz": True},
                            {"duration": 31}, {"duration": .01}):
                with self.assertRaises(ValueError):
                    compiler(rail(), **options)

    def test_full_speed_held_input_integrates_without_repeated_key_presses(self):
        plan = compile_input(rail(), rate_hz=120)
        self.assertEqual({f.held for f in plan.frames[:-1]}, {("forward",)})
        self.assertEqual(plan.frames[-1].held, ())
        self.assertAlmostEqual(plan.frames[-1].pose.x, 600)
        samples = simulate_render(plan, render_hz=120, consume_hz=16)
        for time, pose in samples:
            self.assertAlmostEqual(pose.x, 600 * time)
        self.assertAlmostEqual(render_metrics(samples)["max_position_jump_units"], 5)

    def test_strafe_preserves_authored_facing_instead_of_aiming_along_path(self):
        plan = compile_input(rail(yaw=90), rate_hz=60)
        self.assertEqual({f.held for f in plan.frames[:-1]}, {("right",)})
        self.assertTrue(all(f.pose.yaw == 90 and f.mouse_x == 0 for f in plan.frames))
        self.assertAlmostEqual(plan.frames[-1].pose.x, 600)

    def test_fractional_speed_pulses_and_is_labeled_as_a_risk(self):
        plan = compile_input(rail(distance=300))
        self.assertEqual({f.held for f in plan.frames[:-1]}, {(), ("forward",)})
        self.assertTrue(any("pulsing" in text for text in plan.warnings))
        self.assertAlmostEqual(plan.frames[-1].pose.x, 300)
        # Same helper rate, lower consumption samples one parity of the pulses.
        rendered = simulate_render(plan, render_hz=120, consume_hz=60)
        self.assertGreater(abs(rendered[-1][1].x - 300 * rendered[-1][0]), 100)

    def test_mouse_quantization_preserves_total_signed_counts_across_yaw_wrap(self):
        model = InputModel(yaw_degrees_per_count=-.03)
        plan = compile_input(rail(distance=0, yaw=170, end_yaw=-170), model=model)
        self.assertEqual(plan.frames[-1].mouse_x, -667)
        self.assertAlmostEqual(plan.frames[-1].pose.yaw, 190.01)
        self.assertTrue(all(f.held == () for f in plan.frames))
        with self.assertRaisesRegex(ValueError, "speed"):
            compile_input(rail(distance=601))
        with self.assertRaises(ValueError):
            compile_input(rail(), model=InputModel(yaw_degrees_per_count=0))


class RateModelTests(unittest.TestCase):
    def test_sixteen_pose_updates_produce_expected_stairs_at_120_render_fps(self):
        plan = compile_console(rail(), rate_hz=16)
        metrics = render_metrics(simulate_render(plan, render_hz=120, consume_hz=120))
        self.assertAlmostEqual(metrics["max_position_jump_units"], 37.5)
        self.assertGreater(metrics["unchanged_frame_percent"], 85)

    def test_sending_240_hz_does_not_overcome_16_hz_consumption(self):
        plan = compile_console(rail(), rate_hz=240)
        metrics = render_metrics(simulate_render(plan, render_hz=120, consume_hz=16))
        self.assertAlmostEqual(metrics["max_position_jump_units"], 37.5)
        self.assertGreater(metrics["unchanged_frame_percent"], 85)
        fast = render_metrics(simulate_render(plan, render_hz=120, consume_hz=120))
        self.assertAlmostEqual(fast["max_position_jump_units"], 5)
        self.assertEqual(fast["unchanged_frame_percent"], 0)

    def test_relative_mouse_events_accumulate_when_consumption_is_slower(self):
        plan = compile_input(rail(distance=0, yaw=0, end_yaw=30), rate_hz=240)
        samples = simulate_render(plan, render_hz=120, consume_hz=30)
        self.assertAlmostEqual(samples[-1][1].yaw, 29)
        self.assertAlmostEqual(render_metrics(samples)["max_angle_jump_degrees"], 1, places=2)


class PlaybackTests(unittest.TestCase):
    def runner(self, kind="input"):
        plan = (compile_input if kind == "input" else compile_console)(rail(), rate_hz=120)
        output = MockOutput()
        runner = TraceRunner(output)
        runner.arm(plan)
        runner.run(10, rebase_confirmed=True)
        return runner, output

    def test_latest_deadline_skips_old_commands_without_bursting(self):
        runner, output = self.runner("console")
        before = len(output.trace)
        runner.update(10.03)
        self.assertEqual(len(output.trace), before + 1)
        self.assertEqual(runner.skipped, 2)
        self.assertEqual(output.trace[-1]["commands"], ("spec_goto 15.00 0.00 0.00 0.00 0.00",))

    def test_focus_takeover_backwards_clock_stall_abort_and_hold_release_all(self):
        cases = ((10.01, {"foreground": False}), (10.01, {"operator_override": True}),
                 (9.99, {}), (10.1, {}), (math.nan, {}))
        for now, options in cases:
            with self.subTest(now=now, options=options):
                runner, output = self.runner()
                self.assertEqual(output.held, ("forward",))
                with self.assertRaises(ValueError):
                    runner.update(now, **options)
                self.assertEqual((runner.state, output.held), ("fault", ()))
                with self.assertRaises(ValueError):
                    runner.run(11, rebase_confirmed=True)
        for action in ("hold", "abort", "release"):
            runner, output = self.runner()
            getattr(runner, action)()
            self.assertEqual(output.held, ())
            self.assertIn("release_all", output.trace[-1])

    def test_completion_and_partial_output_error_release_controls(self):
        runner, output = self.runner()
        for i in range(1, 101):
            runner.update(10 + i / 100)
        self.assertEqual((runner.state, output.held), ("held", ()))
        runner, output = self.runner()
        with patch.object(output, "emit", side_effect=OSError("mock output fault")):
            with self.assertRaises(OSError):
                runner.update(10.01)
        self.assertEqual((runner.state, output.held), ("fault", ()))

    def test_manual_rebase_is_required_and_nonmock_output_is_rejected(self):
        runner = TraceRunner(MockOutput())
        runner.arm(compile_input(rail()))
        with self.assertRaisesRegex(ValueError, "rebase"):
            runner.run(10)
        with self.assertRaises(TypeError):
            TraceRunner(object())

    def test_absolute_clock_deadlines_do_not_drift_or_burst_after_stall(self):
        now = [100.]
        waits = []
        def sleep(seconds):
            waits.append(seconds)
            now[0] += seconds + (.025 if len(waits) == 1 else 0)
        ticks = list(deadline_ticks(100, .1, clock=lambda: now[0], sleep=sleep))
        self.assertEqual([t["index"] for t in ticks], [0, 3, 4, 5, 6, 7, 8, 9, 10])
        self.assertAlmostEqual(ticks[2]["elapsed"], .04)
        self.assertAlmostEqual(ticks[-1]["elapsed"], .1)


class HelperOutputTests(unittest.TestCase):
    def test_cli_exports_labeled_data_and_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "phase0"
            with patch("builtins.print"), patch("sys.stderr"):
                self.assertEqual(main(["--out", str(path)]), 0)
                report = json.loads((path / "report.json").read_text())
                self.assertTrue(report["synthetic"])
                self.assertEqual(report["live_compatibility"], "UNVERIFIED")
                self.assertEqual(len(report["rows"]), 10)
                before = (path / "report.json").read_bytes()
                with self.assertRaises(SystemExit):
                    main(["--out", str(path)])
                self.assertEqual((path / "report.json").read_bytes(), before)
            calibration = json.loads((path / "calibration-plan.json").read_text())
            self.assertIn("UNEXECUTED", calibration["evidence"])
            for probe in calibration["timestamped_input_probes"]:
                self.assertEqual(probe["events"][-1]["time"], 2)
                if probe["kind"].startswith("mouse-"):
                    self.assertEqual(probe["events"][-1]["cumulative_counts"], 720)
                else:
                    self.assertEqual(probe["events"][-1]["held_actions"], [])

    def test_infeasible_input_does_not_hide_viable_console_compilation(self):
        report = rate_report(rail(distance=1000))
        self.assertEqual(sum("refused" in row for row in report["rows"]), 5)
        self.assertEqual(sum(row["kind"] == "console" for row in report["rows"]), 5)


if __name__ == "__main__":
    unittest.main()
