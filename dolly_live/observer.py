"""Live observer camera contract for Deadlock Dolly Live.

Everything in this module was read out of one reviewed ``client.dll`` by offline
static analysis. No game was launched, no process was attached, and nothing here
opens a socket, spawns a process or touches the game. The module turns verified
engine facts into gate decisions and console command *text*.

Provenance
----------
Verified against::

    citadel/bin/win64/client.dll
    sha256 948260612c9b7243964e4a0d5f0f6252ae846ceaa6e8c0e95b83bd5eba4caf60
    58293912 bytes, image base 0x180000000

This is a historical static contract copied from the Dolly Live worktree.
It does not describe the currently installed client. Any other build invalidates
every address below. The original research remains in the local continuity
archive; these constants are not a live compatibility or authorization gate.

What the engine actually does
-----------------------------
The observer camera is a ``CCitadel_ThirdPersonCamera`` behind an ``ICamera``
interface. Per rendered frame its update:

1. hard-copies the desired angles onto the applied angles (so an absolute pose
   set from outside is **snapped**, never eased);
2. clamps pitch into ``citadel_camera_pitch_min/_max``;
3. adds camera *wobble* noise scaled by ``citadel_camera_wobble_angle_scale``;
4. publishes and quantizes the result.

This reviewed setter did not provide timed easing. That does not establish
whether another engine interface can provide it. Replay Dolly interpolates
shot keys separately; ``dolly_live`` only models such writes offline here.
The three gates below describe this historical decompiled setter.

Deliberately absent
-------------------
The in-process backend is **not** implemented. :func:`native_backend` exists only
to refuse loudly. Nothing in this module can be substituted for
``dolly_live.runtime.MockCamera``, and :class:`ConsoleObserverAdapter` refuses
any camera object it did not construct.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from dolly_live._vendor.dolly.path import Project

from .presets import number


VERIFIED_CLIENT_SHA256 = (
    "948260612c9b7243964e4a0d5f0f6252ae846ceaa6e8c0e95b83bd5eba4caf60"
)
VERIFIED_CLIENT_SIZE = 58293912

# citadel_camera_pitch_min / _max, read from the registration defaults at
# rva 0x2654fe0 and 0x2654fbc. The engine clamps authored pitch to this range,
# so Dolly must pre-clamp or the engine will silently alter a shot.
PITCH_MIN_DEG = -89.0
PITCH_MAX_DEG = 89.0

# FUN_1805b4260 / FUN_1805ab6b0 return the roaming observer state only for
# player slot 0 and null for every other slot.
OBSERVER_SLOT = 0

# spec_setang rejects a single argument (FUN_1805aca80 requires argc >= 3
# including the command name, i.e. two numbers).
SETANG_ARGC = 2
# spec_goto only forwards pitch/yaw when argc > 5, i.e. five numbers.
GOTO_ARGC = 5
# spec_setpos takes three numbers here so z is never defaulted from the pawn.
SETPOS_ARGC = 3

# Legacy typed-command adapter policy, NOT a measured engine/transport ceiling.
# The separate offline motion compiler can request higher emission rates for
# feasibility experiments; this never establishes live application throughput.
CONSOLE_MAX_HZ = 20.0
CONSOLE_SAFE_HZ = 4.0


class NativeBackendRefused(RuntimeError):
    """Raised by :func:`native_backend`. No in-process backend exists."""


def native_backend(*_args, **_kwargs):
    """Always refuse. The in-process SetOrigin/SetAngles path is unimplemented.

    Present so that callers aiming at smooth per-frame writes get an explicit
    error naming the missing work, instead of silently degrading to the console
    path and believing they got render-rate motion.
    """
    raise NativeBackendRefused(
        "In-process observer backend is not implemented. Smooth per-frame rails "
        "need SetOrigin/SetAngles on observerPawn+0x330 from inside the client; "
        "this build refuses rather than pretending. See "
        "analysis/LIVE-OBSERVER-CAMERA-RE-20261003.md."
    )


@dataclass(frozen=True)
class ObserverLayout:
    """Verified client.dll offsets. Meaningless against any other build."""

    client_sha256: str
    client_size: int
    image_base: int
    # CCitadelObserver_MovementServices accessors.
    set_origin_rva: int
    set_angles_rva: int
    # ICamera wrapper object reachable from the observer state global.
    camera_state_rva: int
    camera_vtable_rva: int
    # Fields on the observer pawn.
    services_offset: int
    pending_angles_offset: int
    # Fields on the camera object.
    desired_angles_offset: int
    applied_angles_offset: int
    hold_window_offset: int
    # Virtual slots the wrappers check before writing.
    gate_vtable_0x290: int
    gate_vtable_0x298: int

    RVA_FIELDS = ("set_origin_rva", "set_angles_rva",
                  "camera_state_rva", "camera_vtable_rva")
    OFFSET_FIELDS = ("services_offset", "pending_angles_offset",
                     "desired_angles_offset", "applied_angles_offset",
                     "hold_window_offset")
    SLOT_FIELDS = ("gate_vtable_0x290", "gate_vtable_0x298")

    def validate(self):
        if self.client_sha256 != VERIFIED_CLIENT_SHA256:
            raise ValueError("Layout was verified against a different client build")
        if self.client_size != VERIFIED_CLIENT_SIZE:
            raise ValueError("Layout was verified against a different client size")
        if self.image_base != 0x180000000:
            raise ValueError("Layout was verified against a different image base")
        for name in self.RVA_FIELDS + self.OFFSET_FIELDS + self.SLOT_FIELDS:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
        for name in self.RVA_FIELDS:
            value = getattr(self, name)
            # An RVA has to land inside the module image, above the PE headers.
            if not 0x1000 <= value < self.client_size:
                raise ValueError(f"{name} is outside the verified module image")
        for name in self.OFFSET_FIELDS:
            # The camera object is ~17 KiB; nothing legitimate is near 1 MiB.
            if not 0 <= getattr(self, name) < 0x100000:
                raise ValueError(f"{name} is not a plausible struct offset")
        for name in self.SLOT_FIELDS:
            if not 0 <= getattr(self, name) < 0x1000:
                raise ValueError(f"{name} is not a plausible vtable slot")


LAYOUT = ObserverLayout(
    client_sha256=VERIFIED_CLIENT_SHA256,
    client_size=VERIFIED_CLIENT_SIZE,
    image_base=0x180000000,
    set_origin_rva=0x16B1E70,      # FUN_1816b1e70, rejects non-finite xyz
    set_angles_rva=0x16B19D0,      # FUN_1816b19d0, early-returns if unchanged
    camera_state_rva=0x36384B0,    # DAT_1836384b0, slot 0 only
    camera_vtable_rva=0x26514F8,   # CCitadel_ThirdPersonCamera primary vtable
    services_offset=0x330,         # observerPawn + 0x330
    pending_angles_offset=0x522,   # observerPawn + 0x522
    desired_angles_offset=0x44,    # snapped onto applied every frame
    applied_angles_offset=0x114,
    hold_window_offset=0x1A4,      # now + arg3; suppresses the update, not a blend
    gate_vtable_0x290=0x290,
    gate_vtable_0x298=0x298,
)
LAYOUT.validate()


@dataclass(frozen=True)
class Gates:
    """The four conditions the decompiled client checks before accepting a write.

    Every field is an observation supplied by the caller. This module never
    probes anything itself, so an unknown observation must be False, not True.
    """

    observer_attached: bool
    slot: int
    replay_playing: bool
    pawn_gate_0x290: bool
    pawn_gate_0x298: bool

    def validate(self):
        for name in ("observer_attached", "replay_playing",
                     "pawn_gate_0x290", "pawn_gate_0x298"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a bool")
        if isinstance(self.slot, bool) or not isinstance(self.slot, int):
            raise ValueError("slot must be an integer")
        if not -1 <= self.slot <= 64:
            raise ValueError("slot must be between -1 and 64")

    def refusal(self):
        """Return None when every gate passes, else the reason to refuse."""
        self.validate()
        if not self.observer_attached:
            return "observer not attached"
        if self.replay_playing:
            # FUN_180866bd0 and FUN_1805a5580 both bail while a replay plays.
            return "replay/demo playing; observer writes are refused"
        if self.slot != OBSERVER_SLOT:
            # FUN_1805b4260 returns null for any slot but 0.
            return f"observer is in slot {self.slot}; only slot {OBSERVER_SLOT} has roaming state"
        if not self.pawn_gate_0x290:
            return "pawn gate vtable[0x290] refused"
        if not self.pawn_gate_0x298:
            return "pawn angle gate vtable[0x298] refused"
        return None


@dataclass(frozen=True)
class ObserverPose:
    """Camera pose. Matches the engine's x y z pitch yaw roll channel order."""

    x: float
    y: float
    z: float
    pitch: float
    yaw: float
    roll: float

    def validate(self):
        for key, value in vars(self).items():
            number(value, key)

    @property
    def position(self):
        return (self.x, self.y, self.z)

    @property
    def angles(self):
        return (self.pitch, self.yaw, self.roll)


def clamp_pitch(pitch, low=PITCH_MIN_DEG, high=PITCH_MAX_DEG):
    """Clamp to the engine's own pitch range. Returns (pitch, was_clamped)."""
    pitch = number(pitch, "pitch", -360, 360)
    if not low <= high:
        raise ValueError("pitch clamp range is inverted")
    clamped = min(max(pitch, low), high)
    return clamped, clamped != pitch


def _fmt(value):
    # The engine formats with %.2f (FUN_1805ac8b0), so match it exactly rather
    # than emitting more precision than the parser will read back.
    return f"{value:.2f}"


def spec_setpos(pose):
    """`spec_setpos x y z` -- three numbers, so z is never defaulted."""
    pose = _pose(pose)
    return "spec_setpos " + " ".join(_fmt(v) for v in pose.position)


def spec_setang(pose):
    """`spec_setang pitch yaw` -- exactly two; the engine rejects one."""
    pose = _pose(pose)
    pitch, clamped = clamp_pitch(pose.pitch)
    if clamped:
        pose = replace(pose, pitch=pitch)
    return "spec_setang " + " ".join((_fmt(pitch), _fmt(pose.yaw)))


def spec_goto(pose):
    """Public five-number rebase/pose command, not an engine interpolation API."""
    pose = _pose(pose)
    pitch, _ = clamp_pitch(pose.pitch)
    return "spec_goto " + " ".join(_fmt(v) for v in pose.position + (pitch, pose.yaw))


def obs_spec_goto(pose):
    """`obs_spec_goto x y z pitch yaw` -- five numbers, position and facing."""
    pose = _pose(pose)
    pitch, clamped = clamp_pitch(pose.pitch)
    if clamped:
        pose = replace(pose, pitch=pitch)
    values = pose.position + (pitch, pose.yaw)
    return "obs_spec_goto " + " ".join(_fmt(v) for v in values)


def _pose(pose):
    if not isinstance(pose, ObserverPose):
        raise TypeError("Expected an ObserverPose built by this module")
    pose.validate()
    return pose


def command_argc(command):
    """Argument count the engine will see, excluding the command name."""
    if not isinstance(command, str) or not command:
        raise ValueError("command must be a non-empty string")
    return len(command.split()) - 1


@dataclass(frozen=True)
class Frame:
    """One adapter step: the pose written and the exact console text."""

    index: int
    time: float
    pose: ObserverPose
    clamped: bool
    commands: tuple

    def validate(self):
        number(self.time, "time", 0)
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
            raise ValueError("index must be a non-negative integer")
        self.pose.validate()
        if type(self.clamped) is not bool:
            raise ValueError("clamped must be a bool")
        if not isinstance(self.commands, tuple) or not self.commands:
            raise ValueError("commands must be a non-empty tuple")


class ConsoleObserverAdapter:
    """Turns an authored shot into gate-checked console command text.

    State discipline mirrors ``dolly_live.runtime.CueRunner``: a write needs a
    fresh arm, any gate failure releases ownership, and there is no auto-resume.
    The adapter owns no camera and reads no game state -- the caller supplies
    ``Gates`` observations for every frame.
    """

    def __init__(self, rate_hz=CONSOLE_SAFE_HZ):
        if isinstance(rate_hz, bool) or not isinstance(rate_hz, (int, float)):
            raise ValueError("rate must be a number")
        rate = float(rate_hz)
        if not 0 < rate <= CONSOLE_MAX_HZ:
            raise ValueError(f"rate must be greater than 0 and at most {CONSOLE_MAX_HZ:g} Hz")
        self.rate_hz = rate
        self.state = "manual"
        self.reason = "Camera released"
        self.project = None
        self.duration = 0.0
        self.elapsed = 0.0
        self.started = None
        self.index = 0
        self.clamped_any = False
        self.frames = 0

    def arm(self, project, duration):
        """Validate a shot and take ownership without writing anything."""
        if self.state == "running":
            raise ValueError("Release the current shot before arming another")
        if not isinstance(project, Project):
            raise TypeError("Expected a dolly_live._vendor.dolly.path.Project")
        self.release()
        try:
            if isinstance(duration, bool) or not isinstance(duration, (int, float)):
                raise ValueError("duration must be a number")
            duration = number(duration, "duration", 0.1, 120)
            project.validate()
        except (ValueError, ArithmeticError) as error:
            self._fault(error)
            raise
        self.project = project
        self.duration = duration
        self.state = "ready"
        self.reason = "Armed off-air; call step() to emit console text"
        return self.state

    def step(self, gates):
        """Emit one frame of console text, or raise after releasing ownership."""
        if self.state == "held":
            # A finished shot must not silently extend itself; the operator
            # decides whether to release or re-arm.
            raise ValueError("Shot already complete; release it before stepping again")
        if self.state not in ("ready", "running"):
            raise ValueError("Arm a shot before stepping")
        refusal = gates.refusal() if isinstance(gates, Gates) else None
        if refusal is None and not isinstance(gates, Gates):
            self._fault(ValueError("gates must be a Gates observation"))
            raise ValueError("gates must be a Gates observation")
        if refusal is not None:
            self._fault(ValueError(refusal))
            raise ValueError(refusal)
        step_time = self.index / self.rate_hz
        self.elapsed = min(step_time, self.duration)
        shot_time = self.elapsed / self.duration * self.project.duration
        sample = self.project.evaluate(shot_time)
        raw_pitch = sample["pitch"]
        pitch, clamped = clamp_pitch(raw_pitch)
        pose = ObserverPose(sample["x"], sample["y"], sample["z"],
                            pitch, sample["yaw"], sample["roll"])
        commands = (spec_setpos(pose), spec_setang(pose))
        frame = Frame(self.index, self.elapsed, pose, clamped, commands)
        frame.validate()
        self.index += 1
        self.frames += 1
        self.clamped_any = self.clamped_any or clamped
        self.state = "held" if self.elapsed >= self.duration else "running"
        self.reason = ("Shot complete; holding final pose"
                       if self.state == "held" else "Console text emitted")
        return frame

    def release(self):
        self.project = None
        self.duration = 0.0
        self.elapsed = 0.0
        self.index = 0
        self.clamped_any = False
        self.state = "manual"
        self.reason = "Camera released; arm again to emit"

    def status(self):
        rate = f"{self.rate_hz:g} Hz"
        return (f"{self.state}: {self.index} frames at {rate}, "
                f"{'pitch clamped' if self.clamped_any else 'pitch in range'} "
                f"({self.reason})")

    def _fault(self, error):
        self.project = None
        self.duration = 0.0
        self.elapsed = 0.0
        self.index = 0
        self.state = "fault"
        self.reason = str(error)


def console_rate_warning(rate_hz):
    """Honest note about what the console path can and cannot deliver."""
    rate = number(rate_hz, "rate", 0.001, 1000)
    if rate > CONSOLE_SAFE_HZ:
        return (f"{rate:g} Hz is above the {CONSOLE_SAFE_HZ:g} Hz console-safe rate; "
                "typed commands will not keep up, so this path is for framing, "
                "not for smooth rails.")
    return None
