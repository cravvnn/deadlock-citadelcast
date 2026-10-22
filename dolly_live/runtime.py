"""Deterministic simulation. No console, native bridge, network or game access."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import math

from .presets import MAP, Preset, number


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    z: float
    pitch: float
    yaw: float
    roll: float

    def validate(self):
        for key, value in vars(self).items():
            number(value, key)


@dataclass(frozen=True)
class Target:
    id: str
    generation: int
    position: tuple[float, float, float]
    time: float


class SyntheticScene:
    """Two deterministic actors. IDs are synthetic and never match player slots."""
    def __init__(self):
        self.generations = {"hero-a": 1, "hero-b": 1}
        self.missing = set()
        self.frozen_at = {}

    def sample(self, target_id, now):
        if target_id not in self.generations or target_id in self.missing:
            return None
        time = self.frozen_at.get(target_id, now)
        phase = time / 3 + (math.pi if target_id == "hero-b" else 0)
        return Target(target_id, self.generations[target_id],
                      (40 * math.cos(phase), 40 * math.sin(phase), 20.0), time)

    def change(self, target_id, action, now):
        if target_id not in self.generations:
            raise ValueError("Unknown synthetic actor")
        if action == "lose":
            self.missing.add(target_id)
        elif action == "restore":
            self.missing.discard(target_id)
            self.frozen_at.pop(target_id, None)
            self.generations[target_id] += 1
        elif action == "freeze":
            self.frozen_at.setdefault(target_id, now)
        else:
            raise ValueError("Target action must be lose, restore or freeze")


class MockCamera:
    """In-memory poses only; bounded trace, no callbacks into a game backend."""
    def __init__(self):
        self.connected = True
        self.map_revision = MAP
        self.epoch = 0
        self.active = False
        self.pose = None
        self.trace = deque(maxlen=512)

    def connect(self, connected):
        if connected != self.connected:
            self.epoch += 1
            self.connected = connected
            self.release()

    def set_map(self, revision):
        if revision != self.map_revision:
            self.epoch += 1
            self.map_revision = revision
            self.release()

    def write(self, pose):
        if not self.connected:
            raise ValueError("Mock camera disconnected")
        pose.validate()
        self.pose = pose
        self.active = True
        self.trace.append(pose)

    def release(self):
        self.active = False


def look_at(pose, position):
    delta = tuple(b - a for a, b in zip((pose.x, pose.y, pose.z), position))
    if math.dist((0, 0, 0), delta) < 0.001:
        raise ValueError("Camera coincides with target; framing is undefined")
    pitch = -math.degrees(math.atan2(delta[2], math.hypot(delta[0], delta[1])))
    yaw = math.degrees(math.atan2(delta[1], delta[0]))
    return replace(pose, pitch=pitch, yaw=yaw)


class CueRunner:
    """Manual -> ready -> running -> held; faults always release ownership.

    A held pose is static even though simulation time and targets keep moving.
    Every interruption requires a fresh cue and run; there is no auto-resume.
    """
    def __init__(self, camera, scene):
        if type(camera) is not MockCamera or type(scene) is not SyntheticScene:
            raise TypeError("Offline runner accepts only the mock camera and synthetic scene")
        self.camera = camera
        self.scene = scene
        self.state = "manual"
        self.reason = "Camera released"
        self.preset = None
        self.duration = 0.0
        self.elapsed = 0.0
        self.last_time = 0.0
        self.started = 0.0
        self.epoch = 0
        self.target_generation = None

    def _clock(self, now):
        now = number(now, "simulation time", 0, 1_000_000)
        if now < self.last_time:
            raise ValueError("Simulation clock cannot move backwards")
        self.last_time = now
        return now

    def _target(self, now):
        target = self.scene.sample(self.preset.target, now)
        if target is None:
            raise ValueError("Synthetic target missing")
        if target.generation != self.target_generation:
            raise ValueError("Target identity changed; cue again")
        age = now - number(target.time, "target timestamp", 0)
        if not 0 <= age <= 0.25:
            raise ValueError("Target data stale or from the future")
        for component in target.position:
            number(component, "target position")
        return target

    def _check(self, now):
        if not self.camera.connected:
            raise ValueError("Mock camera disconnected")
        if self.camera.epoch != self.epoch:
            raise ValueError("Mock connection/map changed; cue again")
        if self.camera.map_revision != self.preset.map_revision:
            raise ValueError("Map revision mismatch")
        return self._target(now) if self.preset.mode != "rail" else None

    def _fault(self, error):
        self.camera.release()
        self.state = "fault"
        self.reason = str(error)

    def cue(self, preset, now, duration=None):
        if self.state in ("running", "held"):
            raise ValueError("Release the current shot before cueing another")
        self.camera.release()
        self.state = "manual"
        self.preset = None
        try:
            now = self._clock(now)
            snapshot = Preset.from_dict(preset.to_dict())
            selected_duration = snapshot.project.duration if duration is None else number(duration, "duration", 0.1, 120)
            self.preset = snapshot
            self.duration = selected_duration
            self.elapsed = 0.0
            self.epoch = self.camera.epoch
            target = self.scene.sample(snapshot.target, now)
            self.target_generation = target.generation if target else None
            self._check(now)
            self.state = "ready"
            self.reason = "Prepared off-air; run explicitly to position the mock camera"
        except ValueError as error:
            self._fault(error)
            raise

    def run(self, now):
        if self.state != "ready":
            raise ValueError("Cue a shot before running")
        try:
            self.started = self._clock(now)
            self._check(now)
            self.state = "running"
            self.reason = "Synthetic shot running"
            self.update(now)
        except ValueError as error:
            self._fault(error)
            raise

    def update(self, now):
        try:
            now = self._clock(now)
            if self.state not in ("ready", "running", "held"):
                return
            target = self._check(now)
            if self.state != "running":
                return
            self.elapsed = min(now - self.started, self.duration)
            shot_time = self.elapsed / self.duration * self.preset.project.duration
            sample = self.preset.project.evaluate(shot_time)
            pose = Pose(**{name: sample[name] for name in Pose.__dataclass_fields__})
            if self.preset.mode == "follow":
                # World-axis offset, deliberately independent of animated joint/aim rotation.
                pose = replace(pose, x=pose.x + target.position[0],
                               y=pose.y + target.position[1], z=pose.z + target.position[2])
            if target:
                pose = look_at(pose, target.position)
                if self.camera.pose is not None:
                    previous = self.camera.pose.yaw
                    pose = replace(pose, yaw=previous + (pose.yaw - previous + 180) % 360 - 180)
            self.camera.write(pose)
            if self.elapsed >= self.duration:
                self.state = "held"
                self.reason = "Shot complete; holding final camera pose"
        except (ValueError, ArithmeticError) as error:
            self._fault(error)

    def hold(self, now):
        if self.state != "running":
            raise ValueError("Only a running shot can be held")
        self.update(now)
        if self.state != "fault":
            self.state = "held"
            self.reason = "Camera held; synthetic actors continue moving"

    def release(self):
        self.camera.release()
        self.state = "manual"
        self.preset = None
        self.duration = 0.0
        self.elapsed = 0.0
        self.reason = "Camera released; cue again to run"
