"""Monotonic, latest-due playback into an in-memory trace ONLY."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
import math
import time

from .motion import ACTIONS, MotionPlan
from .presets import number


@dataclass
class MockOutput:
    """No device handle, transport, callbacks or route to a game."""

    held: tuple[str, ...] = ()
    mouse_x: int = 0
    mouse_y: int = 0
    trace: list = field(default_factory=list)

    def emit(self, frame):
        self.trace.append({"time": frame.time, "commands": frame.commands,
                           "released": tuple(k for k in self.held if k not in frame.held),
                           "pressed": tuple(k for k in frame.held if k not in self.held),
                           "mouse_delta": (frame.mouse_x - self.mouse_x, frame.mouse_y - self.mouse_y)})
        self.held = frame.held
        self.mouse_x, self.mouse_y = frame.mouse_x, frame.mouse_y

    def release(self):
        # All modeled movement controls, even if an interrupted emission was partial.
        self.trace.append({"release_all": ACTIONS})
        self.held = ()


class TraceRunner:
    """Explicit arm/run/hold/release/abort; no resume and no stale-frame bursts.

    Foreground and operator takeover are caller-supplied simulated observations.
    This is not a global hotkey, foreground monitor or real input implementation.
    """

    def __init__(self, output, *, stall_seconds=0.05):
        if type(output) is not MockOutput:
            raise TypeError("Phase 0 playback accepts only MockOutput")
        self.output = output
        self.stall_seconds = number(stall_seconds, "stall budget", 0.001, 2)
        self.state, self.reason = "manual", "Released"
        self.plan = None
        self.last_time = None
        self.last_index = -1
        self.skipped = 0

    def arm(self, plan):
        if self.state in ("running", "held"):
            raise ValueError("Release before arming another shot")
        if type(plan) is not MotionPlan or not plan.frames:
            raise ValueError("Expected a compiled MotionPlan")
        self.release()
        self.plan, self.times = plan, plan.times
        self.last_time, self.last_index, self.skipped = None, -1, 0
        self.state, self.reason = "ready", "Prepared; manual rebase required"

    def run(self, now, *, rebase_confirmed=False, foreground=True):
        if self.state != "ready":
            raise ValueError("Arm before run; interrupted shots cannot resume")
        try:
            self.started = number(now, "monotonic time", 0, 1e12)
            if rebase_confirmed is not True:
                raise ValueError("Confirm manual off-air rebase before running")
            if foreground is not True:
                raise ValueError("Foreground lost")
            self.state, self.reason = "running", "Mock playback running"
            self.update(now, foreground=foreground)
        except BaseException as error:
            self._fault(error)
            raise

    def update(self, now, *, foreground=True, operator_override=False):
        if self.state not in ("running", "held"):
            return
        try:
            now = number(now, "monotonic time", 0, 1e12)
            if now < self.started or (self.last_time is not None and now < self.last_time):
                raise ValueError("Monotonic clock moved backwards")
            if foreground is not True or operator_override is not False:
                raise ValueError("Foreground lost or operator took over")
            if self.state == "held":
                return
            if self.last_time is not None and now - self.last_time > self.stall_seconds:
                raise ValueError("Playback stalled; rebase and arm again")
            self.last_time = now
            elapsed = min(now - self.started, self.plan.duration)
            index = bisect_right(self.times, elapsed + 1e-9) - 1
            if index <= self.last_index:
                return
            self.skipped += max(0, index - self.last_index - 1)
            self.output.emit(self.plan.frames[index])
            self.last_index = index
            if elapsed >= self.plan.duration:
                self.hold()
        except BaseException as error:
            self._fault(error)
            raise

    def hold(self):
        if self.state != "running":
            raise ValueError("Only running playback can hold")
        self.output.release()
        self.state, self.reason = "held", "Motion released; no automatic resume"

    def release(self):
        self.output.release()
        self.plan = None
        self.state, self.reason = "manual", "Released; arm again to run"

    def abort(self):
        self._fault(ValueError("Operator abort"))

    def _fault(self, error):
        try:
            self.output.release()
        finally:
            self.plan = None
            self.state, self.reason = "fault", str(error)


def deadline_ticks(rate_hz, duration, *, clock=time.perf_counter, sleep=time.sleep):
    """Absolute deadlines, skip expired ticks, no catch-up burst or busy spin."""
    rate = number(rate_hz, "clock rate Hz", 1, 500)
    duration = number(duration, "clock probe duration", 0.1, 30)
    started = clock()
    index, final = 0, math.ceil(duration * rate)
    while index <= final:
        deadline = min(index / rate, duration)
        remaining = started + deadline - clock()
        if remaining > 0:
            sleep(remaining)
        elapsed = max(0., clock() - started)
        latest = min(final, math.floor(elapsed * rate + 1e-8))
        if elapsed >= duration:
            latest = final
        # A sleep may return early; sleep again instead of emitting early.
        if latest < index:
            continue
        index = max(index, latest)
        intended = min(index / rate, duration)
        yield {"index": index, "deadline": intended, "elapsed": elapsed,
               "lateness_ms": max(0., elapsed - intended) * 1000}
        index += 1


def clock_probe(rate_hz=120, duration=2):
    """Actual host scheduling only. No windows, input, game or network."""
    ticks = tuple(deadline_ticks(rate_hz, duration))
    lateness = sorted(tick["lateness_ms"] for tick in ticks)
    gaps = [(b["elapsed"] - a["elapsed"]) * 1000 for a, b in zip(ticks, ticks[1:])]
    expected = math.ceil(duration * rate_hz) + 1
    return {"evidence": "MEASURED HOST CLOCK ONLY; game application rate unknown",
            "requested_hz": rate_hz, "duration_seconds": duration,
            "emitted_ticks": len(ticks), "skipped_deadlines": expected - len(ticks),
            "p95_lateness_ms": lateness[min(len(lateness) - 1, math.ceil(len(lateness) * .95) - 1)],
            "max_gap_ms": max(gaps, default=0.), "ticks": ticks}
