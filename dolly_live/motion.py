"""Offline motion compilation and explicitly hypothetical camera consumption.

No sockets, process access, native offsets or OS input. Neither compilation nor
simulation establishes that a live observer accepts the resulting commands.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product
import math

from dolly_live._vendor.dolly.path import Project

from .observer import ObserverPose, spec_goto, spec_setang, spec_setpos
from .presets import number


AXES = ("x", "y", "z", "pitch", "yaw", "roll")
ACTIONS = ("forward", "back", "left", "right", "up", "down")


@dataclass(frozen=True)
class InputModel:
    """Assumptions to measure off-air, never a compatibility certificate.

    Pitch-positive-down, forward follows look, strafe is horizontal, vertical
    is world Z, combined axes normalize, immediate speed/no inertia. These
    semantics and the signed degrees/count MUST be checked on the observer PC.
    """

    speed: float = 600.0
    yaw_degrees_per_count: float = 0.02
    pitch_degrees_per_count: float = 0.02

    def validate(self):
        number(self.speed, "model speed", 0.001, 1000)
        for name in ("yaw_degrees_per_count", "pitch_degrees_per_count"):
            value = number(getattr(self, name), name, -10, 10)
            if abs(value) < 0.000001:
                raise ValueError(f"{name} must be nonzero")


@dataclass(frozen=True)
class MotionFrame:
    time: float
    pose: ObserverPose
    commands: tuple[str, ...] = ()
    held: tuple[str, ...] = ()
    # Cumulative counts let a paced runner coalesce missed samples safely.
    mouse_x: int = 0
    mouse_y: int = 0


@dataclass(frozen=True)
class MotionPlan:
    kind: str
    duration: float
    rate_hz: float
    start: ObserverPose
    frames: tuple[MotionFrame, ...]
    warnings: tuple[str, ...]
    model: InputModel | None = None

    @property
    def times(self):
        return tuple(frame.time for frame in self.frames)

    @property
    def rebase_commands(self):
        return (spec_goto(self.start), spec_setpos(self.start), spec_setang(self.start))


def _shot(project, duration, rate_hz):
    if not isinstance(project, Project):
        raise TypeError("Expected a dolly_live._vendor.dolly.path.Project")
    project = Project.from_dict(project.to_dict())  # Own an authored snapshot.
    duration = number(project.duration if duration is None else duration,
                      "helper duration", 0.1, 30)
    rate_hz = number(rate_hz, "requested emission rate", 1, 500)
    if not 2 <= len(project.keyframes) <= 256 or project.keyframes[0].time != 0:
        raise ValueError("Helper shots need 2-256 keys starting at zero")
    if project.tracks or project.setup_values or project.objects or project.confetti_enabled:
        raise ValueError("Helper shots cannot contain replay effects, objects or cvar tracks")
    for key in project.keyframes:
        if key.source != "free" or key.attach or key.source_blend:
            raise ValueError("Helper shots accept free camera poses only")
        if (abs(key.roll) > 1e-9 or key.fov != 90 or key.aspect_ratio != 16 / 9
                or key.lens_scale is not None
                or any(getattr(key, "curve_" + axis) is not None
                       for axis in ("pitch", "yaw", "roll"))):
            raise ValueError("Helper cannot reproduce roll, zoom, lens or rotation overrides")
    return project, duration, rate_hz


def sample_pose(project, time, duration):
    raw = project.evaluate(time / duration * project.duration)
    pose = ObserverPose(**{name: raw[name] for name in AXES})
    pose.validate()
    if not -89 <= pose.pitch <= 89 or abs(pose.roll) > 1e-9:
        raise ValueError("Evaluated shot exceeds observer pitch/roll support")
    return pose


def _times(duration, rate_hz):
    # Exact endpoint, including shots not divisible by the requested interval.
    return (*[i / rate_hz for i in range(math.ceil(duration * rate_hz))], duration)


def compile_console(project, *, duration=None, rate_hz=120):
    """Sample Dolly curves into one five-number command per intended deadline.

    This has no typing-derived cap: a prospective console transport must prove
    its throughput and live access separately. The engine still receives snaps.
    """
    project, duration, rate_hz = _shot(project, duration, rate_hz)
    frames = []
    for time in _times(duration, rate_hz):
        command = spec_goto(sample_pose(project, time, duration))
        # Model the two-decimal formatter in the reviewed command path.
        pose = ObserverPose(*map(float, command.split()[1:]), 0.0)
        frames.append(MotionFrame(time, pose, (command,)))
    return MotionPlan("console", duration, rate_hz, frames[0].pose, tuple(frames), (
        "OFFLINE: requested emission Hz is not measured application Hz.",
        "Absolute pose commands snap; no engine blending has been established.",
        "Console access, command processing cadence and live behavior remain unverified.",
    ))


def input_velocity(held, pitch, yaw, model):
    """Digital-key velocity for the hypothetical model, not recovered engine code."""
    forward = int("forward" in held) - int("back" in held)
    side = int("right" in held) - int("left" in held)
    vertical = int("up" in held) - int("down" in held)
    p, y = math.radians(pitch), math.radians(yaw)
    velocity = (forward * math.cos(p) * math.cos(y) + side * math.sin(y),
                forward * math.cos(p) * math.sin(y) - side * math.cos(y),
                -forward * math.sin(p) + vertical)
    length = math.dist((0, 0, 0), velocity)
    return tuple(v * model.speed / length for v in velocity) if length > 1e-9 else (0., 0., 0.)


_KEY_CHOICES = tuple(tuple((("back", "forward"), ("left", "right"),
                            ("down", "up"))[axis][int(value > 0)]
                          for axis, value in enumerate(choice) if value)
                     for choice in product((0, -1, 1), repeat=3))


def compile_input(project, *, duration=None, rate_hz=120, model=None):
    """Dead-reckoned digital flight with independent authored look direction.

    Selects the key chord minimizing next-sample position error. Fractional
    speeds require temporal pulsing; this is exposed rather than called smooth.
    Never aims the camera along the path in place of the authored framing.
    """
    project, duration, rate_hz = _shot(project, duration, rate_hz)
    model = InputModel() if model is None else model
    if type(model) is not InputModel:
        raise TypeError("Expected an InputModel")
    model.validate()
    times = _times(duration, rate_hz)
    start = sample_pose(project, 0, duration)
    position = start.position
    frames, peak_error, pulsed = [], 0.0, False
    for index, time in enumerate(times):
        target = sample_pose(project, time, duration)
        dx = round((target.yaw - start.yaw) / model.yaw_degrees_per_count)
        dy = round((target.pitch - start.pitch) / model.pitch_degrees_per_count)
        yaw = start.yaw + dx * model.yaw_degrees_per_count
        pitch = max(-89, min(89, start.pitch + dy * model.pitch_degrees_per_count))
        believed = ObserverPose(*position, pitch, yaw, 0.)
        peak_error = max(peak_error, math.dist(position, target.position))
        held = ()
        if index + 1 < len(times):
            dt = times[index + 1] - time
            next_target = sample_pose(project, times[index + 1], duration)
            desired_speed = math.dist(target.position, next_target.position) / dt
            if desired_speed > model.speed + 1e-6:
                raise ValueError("Shot exceeds the hypothetical input-model speed; lengthen it")
            candidates = [(keys, input_velocity(keys, pitch, yaw, model)) for keys in _KEY_CHOICES]
            held, velocity = min(candidates, key=lambda item: math.dist(
                tuple(p + v * dt for p, v in zip(position, item[1])), next_target.position))
            pulsed |= 1e-6 < desired_speed < model.speed - 1e-6
            next_position = tuple(p + v * dt for p, v in zip(position, velocity))
        frames.append(MotionFrame(time, believed, held=held, mouse_x=dx, mouse_y=dy))
        if index + 1 < len(times):
            position = next_position
    warnings = ["OFFLINE INPUT MODEL: synthetic constants, instant velocity, no collision/inertia.",
                "Mouse acceptance, signs, sensitivity, axis semantics and consumption Hz need calibration.",
                f"Model tracking error at helper samples: {peak_error:.6f} world units."]
    if pulsed:
        warnings.append("Fractional digital speed uses key pulsing: lower input consumption may alias or lose pulses.")
    return MotionPlan("input", duration, rate_hz, start, tuple(frames), tuple(warnings), model)


def simulate_render(plan, *, render_hz=120, consume_hz=120, phase_seconds=0):
    """Optimistic latest-state consumption at a specified, ASSUMED game cadence.

    Console: latest pose wins, zero-order hold, no queue/network delay. Input:
    latest held chord and accumulated mouse counts sampled by the consumer;
    continuous velocity integration between consumption times. Fast key pulses
    can alias. Real prediction/interpolation, queues and input plumbing unknown.
    """
    render_hz = number(render_hz, "render Hz", 1, 500)
    consume_hz = number(consume_hz, "assumed consumption Hz", 1, 500)
    phase = number(phase_seconds, "consumer phase", 0, 1 / consume_hz)
    pending = {}
    for frame in plan.frames:
        arrival = phase + max(0, math.ceil((frame.time - phase) * consume_hz - 1e-9)) / consume_hz
        pending[round(arrival, 12)] = frame
    events = sorted(pending.items())
    index, event_time = 0, 0.
    current = plan.start
    velocity = (0., 0., 0.)
    samples = []
    for i in range(math.ceil(plan.duration * render_hz)):
        time = (i + 0.5) / render_hz  # Sample frame centers, exclude final held shot.
        if time >= plan.duration:
            break
        while index < len(events) and events[index][0] <= time + 1e-12:
            arrival, frame = events[index]
            if plan.kind == "console":
                current = frame.pose
            else:
                current = replace(current, **dict(zip(("x", "y", "z"),
                    (p + v * (arrival - event_time) for p, v in zip(current.position, velocity)))))
                current = replace(current,
                    yaw=plan.start.yaw + frame.mouse_x * plan.model.yaw_degrees_per_count,
                    pitch=max(-89, min(89, plan.start.pitch + frame.mouse_y * plan.model.pitch_degrees_per_count)))
                velocity = input_velocity(frame.held, current.pitch, current.yaw, plan.model)
            event_time = arrival
            index += 1
        rendered = current if plan.kind == "console" else replace(current, **dict(zip(
            ("x", "y", "z"), (p + v * (time - event_time) for p, v in zip(current.position, velocity)))))
        samples.append((time, rendered))
    return tuple(samples)


def render_metrics(samples):
    """Visible held frames/jumps, not a perceptual pass/fail or game observation."""
    pairs = list(zip(samples, samples[1:]))
    unchanged = sum(a == b for (_, a), (_, b) in pairs)
    position_jumps = [math.dist(a.position, b.position) for (_, a), (_, b) in pairs]
    angle_jumps = [max(abs(a.pitch - b.pitch), abs(a.yaw - b.yaw)) for (_, a), (_, b) in pairs]
    return {"rendered_samples": len(samples),
            "unchanged_frame_percent": 100 * unchanged / len(pairs) if pairs else 0.,
            "max_position_jump_units": max(position_jumps, default=0.),
            "max_angle_jump_degrees": max(angle_jumps, default=0.)}
