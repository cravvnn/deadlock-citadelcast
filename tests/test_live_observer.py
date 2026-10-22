"""Behavioural checks for the live observer adapter contract.

Everything here is offline: no game, no window, no process, no network. The
adapter produces console command text and gate decisions from verified static
analysis; these tests pin that contract and its fail-closed behaviour.
"""
import ast
import unittest
from pathlib import Path

from dolly_live.observer import (
    CONSOLE_MAX_HZ,
    CONSOLE_SAFE_HZ,
    GOTO_ARGC,
    LAYOUT,
    OBSERVER_SLOT,
    PITCH_MAX_DEG,
    PITCH_MIN_DEG,
    SETANG_ARGC,
    SETPOS_ARGC,
    VERIFIED_CLIENT_SHA256,
    VERIFIED_CLIENT_SIZE,
    ConsoleObserverAdapter,
    Frame,
    Gates,
    NativeBackendRefused,
    ObserverLayout,
    ObserverPose,
    clamp_pitch,
    command_argc,
    console_rate_warning,
    native_backend,
    obs_spec_goto,
    spec_setang,
    spec_setpos,
)
from dolly_live._vendor.dolly.path import Keyframe, Project
from dolly_live.presets import defaults
from dolly_live.runtime import CueRunner, MockCamera, SyntheticScene


def open_gates(**overrides):
    gates = {
        "observer_attached": True,
        "slot": OBSERVER_SLOT,
        "replay_playing": False,
        "pawn_gate_0x290": True,
        "pawn_gate_0x298": True,
    }
    gates.update(overrides)
    return Gates(**gates)


def shot():
    return defaults().get("walker").project


def pose(**overrides):
    values = {"x": -100.0, "y": -80.0, "z": 70.0, "pitch": 12.0, "yaw": 30.0, "roll": 0.0}
    values.update(overrides)
    return ObserverPose(**values)


class LayoutTests(unittest.TestCase):
    def test_layout_is_pinned_to_the_verified_build(self):
        self.assertEqual(LAYOUT.client_sha256, VERIFIED_CLIENT_SHA256)
        self.assertEqual(LAYOUT.client_size, VERIFIED_CLIENT_SIZE)
        self.assertEqual(LAYOUT.image_base, 0x180000000)
        self.assertEqual((LAYOUT.set_origin_rva, LAYOUT.set_angles_rva),
                         (0x16B1E70, 0x16B19D0))
        self.assertEqual(LAYOUT.camera_state_rva, 0x36384B0)
        self.assertEqual(LAYOUT.camera_vtable_rva, 0x26514F8)
        self.assertEqual((LAYOUT.services_offset, LAYOUT.pending_angles_offset),
                         (0x330, 0x522))
        self.assertEqual((LAYOUT.desired_angles_offset, LAYOUT.applied_angles_offset),
                         (0x44, 0x114))
        self.assertEqual(LAYOUT.hold_window_offset, 0x1A4)

    def test_layout_refuses_a_different_build(self):
        for field, value in (("client_sha256", "0" * 64),
                             ("client_size", VERIFIED_CLIENT_SIZE + 1),
                             ("image_base", 0x140000000)):
            with self.assertRaises(ValueError):
                ObserverLayout(**{**LAYOUT.__dict__, field: value}).validate()

    def test_layout_rejects_addresses_outside_the_module(self):
        with self.assertRaises(ValueError):
            ObserverLayout(**{**LAYOUT.__dict__,
                              "set_origin_rva": VERIFIED_CLIENT_SIZE}).validate()
        with self.assertRaises(ValueError):
            ObserverLayout(**{**LAYOUT.__dict__, "set_origin_rva": 0}).validate()

    def test_layout_rejects_implausible_offsets_and_slots(self):
        with self.assertRaises(ValueError):
            ObserverLayout(**{**LAYOUT.__dict__,
                              "services_offset": 0x100000}).validate()
        with self.assertRaises(ValueError):
            ObserverLayout(**{**LAYOUT.__dict__,
                              "gate_vtable_0x290": 0x1000}).validate()

    def test_layout_rejects_non_integer_fields(self):
        with self.assertRaises(ValueError):
            ObserverLayout(**{**LAYOUT.__dict__, "camera_state_rva": 0}).validate()
        with self.assertRaises(ValueError):
            ObserverLayout(**{**LAYOUT.__dict__,
                              "camera_state_rva": True}).validate()


class GateTests(unittest.TestCase):
    def test_all_gates_open_admits_the_write(self):
        self.assertIsNone(open_gates().refusal())

    def test_every_single_failure_is_named(self):
        cases = {
            "observer_attached": False,
            "replay_playing": True,
            "slot": 1,
            "pawn_gate_0x290": False,
            "pawn_gate_0x298": False,
        }
        for field, value in cases.items():
            refusal = open_gates(**{field: value}).refusal()
            self.assertIsNotNone(refusal, field)
            self.assertTrue(refusal)

    def test_replay_playing_is_refused_first_because_the_client_does_that(self):
        refusal = open_gates(replay_playing=True, slot=7).refusal()
        self.assertIn("replay", refusal)

    def test_gates_reject_non_bool_observations(self):
        for field in ("observer_attached", "replay_playing",
                      "pawn_gate_0x290", "pawn_gate_0x298"):
            with self.assertRaises(ValueError):
                open_gates(**{field: 1}).refusal()

    def test_gates_reject_a_non_integer_slot(self):
        with self.assertRaises(ValueError):
            open_gates(slot=0.0).refusal()

    def test_no_observer_means_no_way_in(self):
        self.assertIn("observer", open_gates(observer_attached=False).refusal())


class CommandTests(unittest.TestCase):
    def test_setpos_sends_three_numbers(self):
        command = spec_setpos(pose())
        self.assertTrue(command.startswith("spec_setpos "))
        self.assertEqual(command_argc(command), SETPOS_ARGC)

    def test_setang_sends_exactly_two_numbers(self):
        command = spec_setang(pose())
        self.assertTrue(command.startswith("spec_setang "))
        self.assertEqual(command_argc(command), SETANG_ARGC)

    def test_goto_sends_five_numbers(self):
        command = obs_spec_goto(pose())
        self.assertTrue(command.startswith("obs_spec_goto "))
        self.assertEqual(command_argc(command), GOTO_ARGC)

    def test_commands_match_the_engine_two_decimal_format(self):
        self.assertEqual(spec_setpos(pose(x=-100.005, y=1.0, z=2.0)),
                         "spec_setpos -100.00 1.00 2.00")
        self.assertEqual(spec_setang(pose(pitch=12.345, yaw=-4.0)),
                         "spec_setang 12.35 -4.00")

    def test_pitch_is_clamped_to_the_engine_range(self):
        self.assertEqual((PITCH_MIN_DEG, PITCH_MAX_DEG), (-89.0, 89.0))
        value, clamped = clamp_pitch(120.0)
        self.assertEqual((value, clamped), (PITCH_MAX_DEG, True))
        value, clamped = clamp_pitch(-120.0)
        self.assertEqual((value, clamped), (PITCH_MIN_DEG, True))
        value, clamped = clamp_pitch(45.0)
        self.assertEqual((value, clamped), (45.0, False))

    def test_clamped_pitch_reaches_the_command_text(self):
        command = spec_setang(pose(pitch=120.0))
        self.assertEqual(command, "spec_setang 89.00 30.00")
        self.assertEqual(command_argc(obs_spec_goto(pose(pitch=-200.0))), GOTO_ARGC)

    def test_commands_reject_a_foreign_pose_type(self):
        class Foreign:
            x = y = z = pitch = yaw = roll = 0.0

        with self.assertRaises(TypeError):
            spec_setpos(Foreign())
        with self.assertRaises(TypeError):
            spec_setpos(object())

    def test_commands_reject_non_finite_and_non_numeric(self):
        for bad in (float("nan"), float("inf"), "0", None, True):
            with self.assertRaises(ValueError):
                spec_setpos(pose(x=bad))

    def test_command_argc_validates_its_input(self):
        for bad in ("", None, 5):
            with self.assertRaises(ValueError):
                command_argc(bad)


class AdapterTests(unittest.TestCase):
    def test_arm_writes_nothing(self):
        adapter = ConsoleObserverAdapter()
        adapter.arm(shot(), 4.0)
        self.assertEqual(adapter.state, "ready")
        self.assertEqual(adapter.index, 0)

    def test_step_emits_position_then_facing(self):
        adapter = ConsoleObserverAdapter()
        adapter.arm(shot(), 4.0)
        frame = adapter.step(open_gates())
        self.assertIsInstance(frame, Frame)
        frame.validate()
        self.assertEqual(len(frame.commands), 2)
        self.assertTrue(frame.commands[0].startswith("spec_setpos "))
        self.assertTrue(frame.commands[1].startswith("spec_setang "))
        self.assertEqual(adapter.index, 1)

    def test_frames_are_deterministic_for_a_fixed_rate(self):
        first = ConsoleObserverAdapter(rate_hz=4)
        first.arm(shot(), 4.0)
        one = [first.step(open_gates()) for _ in range(6)]
        second = ConsoleObserverAdapter(rate_hz=4)
        second.arm(shot(), 4.0)
        two = [second.step(open_gates()) for _ in range(6)]
        self.assertEqual([f.pose for f in one], [f.pose for f in two])
        self.assertEqual([f.commands for f in one], [f.commands for f in two])

    def test_shot_holds_at_the_end_and_refuses_to_keep_emitting(self):
        adapter = ConsoleObserverAdapter(rate_hz=CONSOLE_SAFE_HZ)
        adapter.arm(shot(), 0.5)
        for _ in range(40):
            if adapter.state == "held":
                break
            adapter.step(open_gates())
        self.assertEqual(adapter.state, "held")
        # A completed shot must not silently extend itself.
        with self.assertRaises(ValueError) as caught:
            adapter.step(open_gates())
        self.assertIn("already complete", str(caught.exception))
        self.assertEqual(adapter.state, "held")
        adapter.release()
        self.assertEqual(adapter.state, "manual")

    def test_gate_refusal_releases_and_requires_rearm(self):
        adapter = ConsoleObserverAdapter()
        adapter.arm(shot(), 4.0)
        with self.assertRaises(ValueError):
            adapter.step(open_gates(slot=3))
        self.assertEqual(adapter.state, "fault")
        self.assertIn("slot", adapter.reason)
        with self.assertRaises(ValueError):
            adapter.step(open_gates())
        adapter.arm(shot(), 4.0)
        self.assertEqual(adapter.state, "ready")

    def test_replay_playing_refuses_without_emitting(self):
        adapter = ConsoleObserverAdapter()
        adapter.arm(shot(), 4.0)
        with self.assertRaises(ValueError):
            adapter.step(open_gates(replay_playing=True))
        self.assertIn("replay", adapter.reason)

    def test_non_gates_argument_is_refused(self):
        adapter = ConsoleObserverAdapter()
        adapter.arm(shot(), 4.0)
        for bad in (None, True, {"slot": 0}, MockCamera()):
            with self.assertRaises(ValueError):
                adapter.step(bad)
            self.assertEqual(adapter.state, "fault")
            adapter.arm(shot(), 4.0)

    def test_step_before_arm_is_refused(self):
        adapter = ConsoleObserverAdapter()
        with self.assertRaises(ValueError):
            adapter.step(open_gates())

    def test_arming_twice_without_release_is_refused(self):
        adapter = ConsoleObserverAdapter()
        adapter.arm(shot(), 4.0)
        adapter.step(open_gates())
        with self.assertRaises(ValueError):
            adapter.arm(shot(), 4.0)

    def test_release_clears_ownership(self):
        adapter = ConsoleObserverAdapter()
        adapter.arm(shot(), 4.0)
        adapter.release()
        self.assertEqual(adapter.state, "manual")
        self.assertIsNone(adapter.project)
        self.assertIn("arm again", adapter.reason)

    def test_arm_rejects_a_foreign_project_and_bad_durations(self):
        adapter = ConsoleObserverAdapter()
        for bad in (None, object(), "project"):
            with self.assertRaises(TypeError):
                adapter.arm(bad, 4.0)
        for bad in (0.0, -1.0, 1000.0, "4", True, float("nan")):
            with self.assertRaises(ValueError):
                adapter.arm(shot(), bad)
            self.assertEqual(adapter.state, "fault")

    def test_clamped_pitch_is_reported(self):
        steep = Project(name="steep", keyframes=[
            Keyframe(0.0, 0.0, 0.0, 0.0, 120.0, 0.0, 0.0),
            Keyframe(2.0, 0.0, 0.0, 0.0, -120.0, 0.0, 0.0),
        ])
        adapter = ConsoleObserverAdapter(rate_hz=8)
        adapter.arm(steep, 2.0)
        seen = [adapter.step(open_gates()) for _ in range(8)]
        self.assertTrue(any(frame.clamped for frame in seen))
        self.assertTrue(all(PITCH_MIN_DEG <= frame.pose.pitch <= PITCH_MAX_DEG
                            for frame in seen))
        self.assertIn("pitch clamped", adapter.status())

    def test_rate_is_bounded_to_something_a_console_could_ever_do(self):
        for bad in (0, -1, CONSOLE_MAX_HZ + 1, "4", True, None):
            with self.assertRaises(ValueError):
                ConsoleObserverAdapter(rate_hz=bad)

    def test_rate_warning_is_honest_about_the_console_ceiling(self):
        self.assertIsNone(console_rate_warning(CONSOLE_SAFE_HZ))
        warning = console_rate_warning(60.0)
        self.assertIn("framing", warning)
        self.assertIn("smooth rails", warning)


class BoundaryTests(unittest.TestCase):
    def test_observer_module_is_offline_only(self):
        allowed = {"__future__", "dataclasses", "math", "dolly_live._vendor.dolly.path",
                   "dolly_live.presets"}
        root = Path(__file__).resolve().parents[1] / "dolly_live"
        added = 0
        for node in ast.walk(ast.parse((root / "observer.py").read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                for name in node.names:
                    self.assertIn(name.name, allowed)
                    added += 1
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                self.assertIn(node.module, allowed)
                added += 1
        self.assertGreater(added, 0)

    def test_module_grants_no_process_or_network_access(self):
        # Check the syntax tree, not the prose: docstrings legitimately say
        # "no socket" and a substring scan would flag its own disclaimer.
        banned = {"subprocess", "socket", "ctypes", "win32api", "win32con",
                  "pywintypes", "multiprocessing", "shutil", "urllib", "http"}
        root = Path(__file__).resolve().parents[1] / "dolly_live" / "observer.py"
        tree = ast.parse(root.read_text(encoding="utf-8"))
        seen = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    self.assertNotIn(name.name.split(".")[0], banned)
                    seen += 1
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                self.assertNotIn((node.module or "").split(".")[0], banned)
                seen += 1
            elif isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, banned)
            elif isinstance(node, ast.Name):
                self.assertNotIn(node.id, banned)
                seen += 1
        self.assertGreater(seen, 0)

    def test_native_backend_refuses_loudly_instead_of_degrading(self):
        for args in ((), ("anything",), ()):
            with self.assertRaises(NativeBackendRefused):
                native_backend(*args)
        with self.assertRaises(NativeBackendRefused):
            native_backend()

    def test_adapter_cannot_be_passed_where_a_mock_camera_is_required(self):
        runner = CueRunner(MockCamera(), SyntheticScene())
        self.assertIs(runner.camera.__class__, MockCamera)
        for impostor in (ConsoleObserverAdapter(), native_backend, LAYOUT):
            with self.assertRaises(TypeError):
                CueRunner(impostor, SyntheticScene())

    def test_adapter_owns_no_camera_object(self):
        adapter = ConsoleObserverAdapter()
        for attribute in vars(adapter):
            self.assertNotIsInstance(getattr(adapter, attribute), MockCamera)


if __name__ == "__main__":
    unittest.main()
