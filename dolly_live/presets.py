"""Strict synthetic shot library; reuses only Dolly's pure path mathematics."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re

from dolly_live._vendor.dolly.path import Keyframe, Project


MAP = "synthetic-stage-v1"
MAX_BYTES = 1024 * 1024
POSE_FIELDS = ("x", "y", "z", "pitch", "yaw", "roll")


def number(value, label, low=-1_000_000, high=1_000_000):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be finite and between {low:g} and {high:g}")
    return value


def text(value, label):
    if not isinstance(value, str) or not value or len(value) > 160 or any(ord(c) < 32 for c in value):
        raise ValueError(f"{label} must be 1–160 printable characters")
    return value


@dataclass
class Preset:
    id: str
    name: str
    landmark: str
    side: str
    project: Project
    mode: str = "rail"
    target: str | None = None
    map_revision: str = MAP
    synthetic: bool = True

    def validate(self):
        if not isinstance(self.id, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", self.id):
            raise ValueError("Preset ID needs lowercase letters, numbers or hyphens")
        for field in ("name", "landmark", "side", "map_revision"):
            text(getattr(self, field), field)
        if self.synthetic is not True or self.map_revision != MAP:
            raise ValueError("This prototype accepts only synthetic-stage-v1 synthetic presets")
        if self.mode not in ("rail", "look-at", "follow"):
            raise ValueError("Mode must be rail, look-at or follow")
        if self.mode == "rail" and self.target is not None:
            raise ValueError("A rail cannot have a tracking target")
        if self.mode != "rail":
            text(self.target, "target")
        self.project.validate()
        keys = self.project.keyframes
        if not 2 <= len(keys) <= 256 or keys[0].time != 0:
            raise ValueError("A shot needs 2–256 keys starting at time zero")
        number(self.project.duration, "duration", 0.1, 120)
        if self.project.tracks or self.project.setup_values:
            raise ValueError("Offline shots cannot contain console/CVAR tracks or setup values")
        if self.project.rotation_mode != "shortest" or self.project.start_tick != 0:
            raise ValueError("Offline shots use shortest rotations and no replay start tick")
        for key in keys:
            if key.fov != 90 or key.aspect_ratio != 16 / 9:
                raise ValueError("Lens animation is not supported by this offline pose format")
            if key.source != "free" or key.attach or key.source_blend or any(
                getattr(key, "curve_" + axis) is not None for axis in ("pitch", "yaw", "roll")
            ):
                raise ValueError("Offline keys contain plain camera poses only")
            for field in POSE_FIELDS:
                number(getattr(key, field), field)

    def to_dict(self):
        self.validate()
        return {
            "id": self.id, "name": self.name, "landmark": self.landmark,
            "side": self.side, "map_revision": self.map_revision, "synthetic": True,
            "mode": self.mode, "target": self.target,
            "interpolation": self.project.interpolation,
            "keys": [{"time": k.time, **{f: getattr(k, f) for f in POSE_FIELDS}}
                     for k in self.project.keyframes],
        }

    @classmethod
    def from_dict(cls, raw):
        fields = {"id", "name", "landmark", "side", "map_revision", "synthetic",
                  "mode", "target", "interpolation", "keys"}
        if not isinstance(raw, dict) or set(raw) != fields:
            raise ValueError("Preset fields are missing or unknown")
        keys = raw["keys"]
        if not isinstance(keys, list) or not 2 <= len(keys) <= 256:
            raise ValueError("A shot needs 2–256 keys")
        parsed = []
        for key in keys:
            if not isinstance(key, dict) or set(key) != {"time", *POSE_FIELDS}:
                raise ValueError("A key needs time, x, y, z, pitch, yaw and roll")
            parsed.append(Keyframe(**{k: number(v, k) for k, v in key.items()}))
        preset = cls(raw["id"], raw["name"], raw["landmark"], raw["side"],
                     Project(name=raw["name"], keyframes=parsed, interpolation=raw["interpolation"]),
                     raw["mode"], raw["target"], raw["map_revision"], raw["synthetic"])
        preset.validate()
        return preset


class Library:
    def __init__(self, presets):
        self._presets = {}
        for preset in presets:
            preset.validate()
            if preset.id in self._presets:
                raise ValueError(f"Duplicate preset: {preset.id}")
            self._presets[preset.id] = preset.to_dict()
        if not 1 <= len(self._presets) <= 128:
            raise ValueError("Library needs 1–128 presets")

    def __iter__(self):
        return (Preset.from_dict(raw) for raw in self._presets.values())

    def get(self, name):
        try:
            return Preset.from_dict(self._presets[name])
        except KeyError:
            raise ValueError(f"Unknown preset: {name}") from None

    def save(self, path):
        # Exclusive create protects existing authored work; save to a new filename.
        raw = {"format": "deadlock-dolly-live-offline", "version": 1,
               "presets": list(self._presets.values())}
        data = (json.dumps(raw, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if len(data) > MAX_BYTES:
            raise ValueError("Preset library exceeds 1 MiB")
        with Path(path).open("xb") as stream:
            stream.write(data)

    @classmethod
    def load(cls, path):
        with Path(path).open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Preset library exceeds 1 MiB")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"Duplicate JSON field: {key}")
                result[key] = value
            return result
        try:
            raw = json.loads(data, object_pairs_hook=unique)
        except (UnicodeError, RecursionError) as error:
            raise ValueError("Invalid library encoding or nesting") from error
        if not isinstance(raw, dict) or set(raw) != {"format", "version", "presets"}:
            raise ValueError("Invalid library envelope")
        if raw["format"] != "deadlock-dolly-live-offline" or type(raw["version"]) is not int or raw["version"] != 1:
            raise ValueError("Unsupported library format/version")
        if not isinstance(raw["presets"], list) or not 1 <= len(raw["presets"]) <= 128:
            raise ValueError("Library needs 1–128 presets")
        return cls(Preset.from_dict(preset) for preset in raw["presets"])


def defaults():
    """Made-up coordinates, not an extraction or approximation of the game map."""
    def shot(id, label, points, mode="rail", target=None):
        keys = [Keyframe(i * 2.0, *point) for i, point in enumerate(points)]
        return Preset(id, "SYNTHETIC — " + label, label, "demo side",
                      Project(name=label, keyframes=keys), mode, target)
    return Library([
        shot("walker", "Blue-lane top-Walker sweep", [(-100, -80, 70, 12, 30, 0),
             (-40, -100, 65, 10, 65, 0), (40, -80, 60, 8, 115, 0), (90, -30, 60, 8, 150, 0)]),
        shot("mid-boss", "Mid-boss reveal", [(-60, -100, 90, 30, 60, 0),
             (0, -70, 65, 25, 90, 0), (60, -40, 55, 20, 135, 0)]),
        shot("bridge", "Bridge-buff sweep", [(-100, 30, 40, 5, 0, 0),
             (0, 30, 55, 12, 45, 0), (100, 70, 65, 15, 90, 0)]),
        shot("rollout", "Opening rollout", [(-160, -120, 80, 10, 30, 0),
             (-80, -80, 65, 8, 40, 0), (20, -20, 50, 6, 50, 0), (120, 80, 70, 15, 70, 0)]),
        shot("hero-pan", "Hero tracking rail", [(-100, -100, 50, 0, 0, 0),
             (0, -90, 60, 0, 0, 0), (100, -60, 50, 0, 0, 0)], "look-at", "hero-a"),
        shot("hero-follow", "Hero follow", [(-70, -50, 40, 0, 0, 0),
             (-70, -50, 40, 0, 0, 0)], "follow", "hero-a"),
    ])
