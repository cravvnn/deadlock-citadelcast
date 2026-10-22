"""Offline named camera starts. No process/game/input/transport access.

Values come from the operator or a selected free-camera Dolly project keyframe.
Command generation does not prove map compatibility or live relocation.
"""
from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import secrets
import threading

FIELDS = ("x", "y", "z", "pitch", "yaw")
MAX_FILE = 8 * 1024 * 1024
MAX_ANCHORS = 32


def label(value, field):
    if (not isinstance(value, str) or not value.strip() or len(value) > 80 or
            any(ord(char) < 32 for char in value)):
        raise ValueError(f"{field} must be a short, nonempty label without control characters")
    return value.strip()


def number(value, field, limit):
    if type(value) not in (int, float):
        raise ValueError(f"{field} must be a finite number")
    try:
        result = float(value)
    except (ValueError, OverflowError):
        raise ValueError(f"{field} must be a finite number") from None
    if not math.isfinite(result) or abs(result) > limit:
        raise ValueError(f"{field} is outside the finite anchor bound")
    return result


def unique_json(text):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON fields are not allowed")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Nonfinite JSON numbers are not allowed")
    try:
        return json.loads(text, object_pairs_hook=unique, parse_constant=constant)
    except (json.JSONDecodeError, UnicodeError, RecursionError):
        raise ValueError("Invalid anchor/project JSON") from None


@dataclass(frozen=True)
class Anchor:
    name: str
    map_label: str
    x: float
    y: float
    z: float
    pitch: float
    yaw: float
    origin: str = "manual"

    def __post_init__(self):
        object.__setattr__(self, "name", label(self.name, "Anchor name"))
        object.__setattr__(self, "map_label", label(self.map_label, "Map/version label"))
        if self.origin not in ("manual", "dolly-keyframe"):
            raise ValueError("Anchor origin must be manual or dolly-keyframe")
        for field in ("x", "y", "z"):
            object.__setattr__(self, field, number(getattr(self, field), field.upper(), 1_000_000))
        pitch = number(self.pitch, "Pitch", 360_000)
        pitch = (pitch + 180) % 360 - 180
        if not -89 <= pitch <= 89:
            raise ValueError("Use a camera pitch within -89 to 89 degrees")
        yaw = number(self.yaw, "Yaw", 360_000)
        object.__setattr__(self, "pitch", pitch)
        object.__setattr__(self, "yaw", (yaw + 180) % 360 - 180)

    def command(self):
        def formatted(value):
            return f"{0. if abs(value) < .0000005 else value:.6f}"
        return "spec_goto " + " ".join(formatted(getattr(self, key)) for key in FIELDS)

    @classmethod
    def from_dict(cls, raw):
        if not isinstance(raw, dict) or set(raw) != set(cls.__dataclass_fields__):
            raise ValueError("Anchor fields must be name, map_label, XYZ, pitch, yaw and origin")
        try:
            return cls(**raw)
        except TypeError:
            raise ValueError("Invalid anchor fields") from None

    def display(self):
        return {**asdict(self), "command": self.command(), "live_status": "unverified"}


def dolly_keyframe(raw, index, name, map_label):
    """Import exactly one absolute free key; never interpret attach/game offsets."""
    if (not isinstance(raw, dict) or raw.get("format") != "deadlock-dolly" or
            type(raw.get("version")) is not int or not 1 <= raw["version"] <= 12):
        raise ValueError("Choose a saved Deadlock Dolly project in reviewed format 1 through 12")
    keys = raw.get("keyframes")
    if (not isinstance(keys, list) or len(keys) > 100_000 or type(index) is not int or
            not 0 <= index < len(keys)):
        raise ValueError("Choose an existing camera keyframe")
    key = keys[index]
    if (not isinstance(key, dict) or key.get("source", "free") != "free" or
            key.get("attach") is not None or key.get("source_blend")):
        raise ValueError("Choose an absolute free-camera key, without attachment or source blending")
    def angle(field):
        override = key.get("curve_" + field)
        return override if override is not None else key.get(field, 0)
    if abs(number(angle("roll"), "Roll", 360_000)) > .000001:
        raise ValueError("spec_goto has no roll argument; choose a zero-roll starting key")
    if any(field not in key for field in FIELDS):
        raise ValueError("The camera key must contain XYZ, pitch and yaw")
    return Anchor(name, map_label, *(key[field] for field in ("x", "y", "z")),
                  angle("pitch"), angle("yaw"), origin="dolly-keyframe")


def load_dolly_keyframe(path, index, name, map_label):
    path = Path(path)
    with path.open("rb") as stream:
        blob = stream.read(MAX_FILE + 1)
    if len(blob) > MAX_FILE:
        raise ValueError("Project exceeds the 8 MiB import bound")
    try:
        raw = unique_json(blob.decode("utf-8-sig"))
    except UnicodeError:
        raise ValueError("Project must be UTF-8 JSON") from None
    return dolly_keyframe(raw, index, name, map_label)


class AnchorBank:
    """Add-only persistent authoring data; invalid existing data is never reset."""
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.anchors = []
        self.serialized = None
        if self.path.exists():
            with self.path.open("rb") as stream:
                blob = stream.read(256 * 1024 + 1)
            if len(blob) > 256 * 1024:
                raise ValueError("Anchor bank exceeds its size bound; existing file preserved")
            raw = unique_json(blob.decode("utf-8-sig"))
            if (not isinstance(raw, dict) or set(raw) != {"format", "version", "anchors"} or
                    raw["format"] != "dolly-live-anchors" or type(raw["version"]) is not int or raw["version"] != 1 or
                    not isinstance(raw["anchors"], list) or len(raw["anchors"]) > MAX_ANCHORS):
                raise ValueError("Invalid anchor bank; existing file preserved")
            self.anchors = [Anchor.from_dict(item) for item in raw["anchors"]]
            names = [item.name.casefold() for item in self.anchors]
            if len(set(names)) != len(names):
                raise ValueError("Duplicate anchor names; existing file preserved")
            self.serialized = blob

    def snapshot(self):
        with self.lock:
            return [anchor.display() for anchor in self.anchors]

    def add(self, anchor):
        if type(anchor) is not Anchor:
            raise ValueError("Expected a validated anchor")
        with self.lock:
            try:
                with self.path.open("rb") as stream:
                    current = stream.read(256 * 1024 + 1)
            except FileNotFoundError:
                current = None
            except OSError:
                raise ValueError("Could not check the saved bank; existing data preserved") from None
            if current != self.serialized:
                raise ValueError("Saved bank changed outside this desk; close and reopen before saving")
            for previous in self.anchors:
                if previous.name.casefold() == anchor.name.casefold():
                    if previous == anchor:
                        return previous.display()
                    raise ValueError("Anchor name already exists; use a new name to preserve the saved point")
            if len(self.anchors) >= MAX_ANCHORS:
                raise ValueError("This authoring bank is limited to 32 anchors")
            updated = self.anchors + [anchor]
            raw = {"format": "dolly-live-anchors", "version": 1, "anchors": [asdict(x) for x in updated]}
            blob = (json.dumps(raw, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(self.path.name + "." + secrets.token_hex(8) + ".tmp")
            try:
                with temporary.open("xb") as stream:
                    stream.write(blob)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            except OSError:
                # Preserve prior file and any temporary evidence; memory changes
                # only after the complete atomic replacement succeeded.
                raise ValueError("Could not save the anchor; previous bank preserved") from None
            self.anchors = updated
            self.serialized = blob
            return anchor.display()
