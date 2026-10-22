"""Phase 0 CLI: offline motion plans, rate experiments and host-clock probes.

python -B -m dolly_live.helper --out analysis/helper-phase0
python -B -m dolly_live.helper --clock-probe --rate 240 --out analysis/helper-clock
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path

from dolly_live._vendor.dolly.path import Project

from .motion import (InputModel, compile_console, compile_input, render_metrics,
                     sample_pose, simulate_render)
from .playback import MockOutput, TraceRunner, clock_probe, deadline_ticks
from .presets import Library, defaults, number


def rate_report(project, *, duration=None, render_hz=120, consume_hz=120, model=None):
    rows = []
    for rate in (16, 30, 60, 120, 240):
        for compiler in (compile_console, compile_input):
            options = {"model": model} if compiler is compile_input else {}
            try:
                plan = compiler(project, duration=duration, rate_hz=rate, **options)
            except ValueError as error:
                if compiler is compile_console:
                    raise
                rows.append({"kind": "input", "emission_hz": rate, "refused": str(error)})
                continue
            samples = simulate_render(plan, render_hz=render_hz, consume_hz=consume_hz)
            errors = [math.dist(pose.position, sample_pose(project, t, plan.duration).position)
                      for t, pose in samples]
            rows.append({"kind": plan.kind, "emission_hz": rate,
                         **render_metrics(samples),
                         "max_tracking_error_units": max(errors, default=0.)})
    return {"evidence": "SIMULATION ONLY; no live or native replay observation",
            "render_hz": render_hz, "assumed_consumption_hz": consume_hz,
            "model": asdict(model or InputModel()),
            "assumptions": ["Latest state wins; no network latency, backlog, jitter or collision.",
                "Console poses hold between application times; no engine blending.",
                "Input model integrates velocity continuously; no inertia or render prediction.",
                "Input chords are sampled and mouse counts accumulated at consumption times.",
                "Unchanged frames and errors are diagnostics, not a perceptual quality verdict."],
            "rows": rows}


def calibration_plan():
    """Instructions/data only; never executed or routed to an input API."""
    probes = []
    for rate in (60, 120, 240):
        for axis in ("yaw", "pitch"):
            probes.append({"kind": "mouse-" + axis, "rate_hz": rate,
                "requires_manual_rebase": True,
                "events": [{"time": i / rate,
                            "cumulative_counts": round(720 * i / (2 * rate))}
                           for i in range(2 * rate + 1)],
                "note": "Reset cumulative count origin each trial; both signs must be measured."})
        probes.append({"kind": "half-speed-digital", "rate_hz": rate,
            "requires_manual_rebase": True,
            "events": [{"time": i / rate,
                        "held_actions": ["forward"] if i % 2 == 0 and i < 2 * rate else []}
                       for i in range(2 * rate + 1)]})
    for action in ("forward", "right", "up", "down"):
        probes.append({"kind": "hold-" + action, "requires_manual_rebase": True,
                       "events": [{"time": 0, "held_actions": [action]},
                                  {"time": 2, "held_actions": []}]})
    return {"evidence": "UNEXECUTED OFF-AIR TEST DESIGN",
        "requires": ["Separately authorized supported observer setup; no live client attachment.",
                     "Operator-authored real poses/binds; built-in coordinates are synthetic.",
                     "Record observer FPS and high-frame-rate local video, not only a stream.",
                     "Identical baseline settings/rebase each trial; manual override available."],
        "measure": ["Physical-input baseline vs helper: does ordinary input reach freecam?",
                    "Signed yaw/pitch degrees per mouse count at multiple rates and sensitivities.",
                    "Forward, strafe, vertical, diagonal speed; acceleration, coast and collisions.",
                    "Actual applied-pose intervals, duplicated video frames and uneven jumps.",
                    "Repeatability and endpoint drift; focus loss, abort and manual takeover."],
        "trials": [
            {"kind": "held-forward", "seconds": 2,
             "note": "One key down then one key up. No need to re-press at helper Hz."},
            {"kind": "mouse-yaw", "seconds": 2, "total_counts": 720,
             "emission_hz": [60, 120, 240], "note": "Same total counts; compare consumption pacing."},
            {"kind": "half-speed-digital", "seconds": 2, "emission_hz": [60, 120, 240],
             "note": "Alternate held/released: check pulsing and aliasing against baseline."},
            {"kind": "pose-stream", "seconds": 2, "emission_hz": [16, 30, 60, 120, 240],
             "note": "Only after console transport is verified; compare straight rail and pan."}],
        "timestamped_input_probes": probes,
        "commands": {
            "combined_pose": "spec_goto <x> <y> <z> <pitch> <yaw>",
            "position": "spec_setpos <x> <y> <z>",
            "angles": "spec_setang <pitch> <yaw>",
            "speed_candidate": "citadel_observer_roaming_speed <measured-value>",
            "notes": "Static current-build evidence, not a live availability guarantee. No duration/ease argument found. Query/record the original speed before edits; restore it manually. Pose readback commands found so far are cheat-gated."}}


def _write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--library", type=Path, help="Synthetic offline shot bank")
    source.add_argument("--project", type=Path, help="Dolly JSON project, free poses only")
    parser.add_argument("--shot", default="bridge")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--rate", type=float, default=120)
    parser.add_argument("--render-hz", type=float, default=120)
    parser.add_argument("--consume-hz", type=float, default=120, help="ASSUMED, not detected")
    parser.add_argument("--model", type=Path, help="JSON speed/signed degrees per count; still unverified")
    parser.add_argument("--out", type=Path, required=True, help="New output directory; never overwrite")
    parser.add_argument("--clock-probe", action="store_true", help="Measure host timer only")
    parser.add_argument("--mock-play", choices=("console", "input"), help="Paced in-memory playback only")
    args = parser.parse_args(argv)
    try:
        number(args.rate, "rate", 1, 500)
        if args.clock_probe:
            report = clock_probe(args.rate, args.duration if args.duration is not None else 2)
            args.out.mkdir(parents=True, exist_ok=False)
            _write(args.out / "clock.json", report)
            print(f"HOST CLOCK ONLY: {report['emitted_ticks']} ticks, "
                  f"{report['skipped_deadlines']} skipped, max gap {report['max_gap_ms']:.3f} ms")
            return 0
        if args.project:
            if args.project.stat().st_size > 1024 * 1024:
                raise ValueError("Project exceeds 1 MiB")
            project = Project.from_dict(json.loads(args.project.read_text(encoding="utf-8-sig")))
            synthetic = False  # User-authored, not a statement that coordinates are verified.
        else:
            preset = (Library.load(args.library) if args.library else defaults()).get(args.shot)
            if preset.mode != "rail":
                raise ValueError("Phase 0 helper accepts static authored rails, not live target tracking")
            project, synthetic = preset.project, True
        model = InputModel(**json.loads(args.model.read_text(encoding="utf-8-sig"))) if args.model else InputModel()
        model.validate()
        console = compile_console(project, duration=args.duration, rate_hz=args.rate)
        try:
            flight = compile_input(project, duration=args.duration, rate_hz=args.rate, model=model)
            input_error = None
        except ValueError as error:
            flight, input_error = None, str(error)
        report = rate_report(project, duration=args.duration, render_hz=args.render_hz,
                             consume_hz=args.consume_hz, model=model)
        report.update({"name": project.name, "synthetic": synthetic,
                       "live_compatibility": "UNVERIFIED", "input_refusal": input_error})
        playback = None
        if args.mock_play:
            plan = console if args.mock_play == "console" else flight
            if plan is None:
                raise ValueError(input_error)
            output = MockOutput()
            runner = TraceRunner(output, stall_seconds=max(.05, 1.5 / args.rate))
            runner.arm(plan)
            try:
                runner.run(0., rebase_confirmed=True)
                for tick in deadline_ticks(args.rate, plan.duration):
                    runner.update(tick["elapsed"])
                playback = {"state": runner.state, "skipped": runner.skipped, "trace": output.trace}
            finally:
                runner.release()
        args.out.mkdir(parents=True, exist_ok=False)
        _write(args.out / "report.json", report)
        _write(args.out / "console-timeline.json", {"synthetic": synthetic, **asdict(console)})
        if flight:
            _write(args.out / "input-timeline.json", {"synthetic": synthetic, **asdict(flight)})
        _write(args.out / "calibration-plan.json", calibration_plan())
        if playback:
            _write(args.out / "mock-playback.json", playback)
        print("PHASE 0 OFFLINE ONLY; live compatibility UNVERIFIED")
        print(f"{'method':8} {'send Hz':>7} {'held frames %':>14} {'max step u':>12} {'max step deg':>13}")
        for row in report["rows"]:
            if "refused" in row:
                print(f"input {row['emission_hz']:>10}: refused: {row['refused']}")
            else:
                print(f"{row['kind']:8} {row['emission_hz']:7g} "
                      f"{row['unchanged_frame_percent']:14.2f} "
                      f"{row['max_position_jump_units']:12.3f} {row['max_angle_jump_degrees']:13.3f}")
        print(f"Artifacts: {args.out.resolve()}")
        return 0
    except (ValueError, TypeError, OSError, KeyError) as error:
        parser.exit(2, f"Phase 0: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
