"""Synthetic Source 2 broadcast fragments. No sockets, files, processes or game access.

This is a simplified offline model of the relay contract documented by the
community hltv-relay project: numbered fragments, each with a start frame, a
full snapshot and a delta update, served a fixed number of fragments behind the
latest ingested data. It is not the real protocol and carries no match data.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import math

from .presets import MAP, text


SYNTHETIC_PROTOCOL = "synthetic-broadcast-v1"
TICK_RATE = 30
FRAGMENT_TICKS = TICK_RATE * 3
DEFAULT_FRAGMENT_DELAY = 8
MAX_CATCH_UP_FRAGMENTS = 4


def _fragment_number(value, label="fragment"):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if not 0 <= value <= 10_000_000:
        raise ValueError(f"{label} must be between 0 and 10000000")
    return value


def _tick(value, label):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if not 0 <= value <= 100_000_000:
        raise ValueError(f"{label} must be between 0 and 100000000")
    return value


def _world(tick):
    time = tick / TICK_RATE
    phase = time / 3
    entities = [
        Entity("hero-a", 40 * math.cos(phase), 40 * math.sin(phase), 20.0, 100),
        Entity("hero-b", 40 * math.cos(phase + math.pi), 40 * math.sin(phase + math.pi), 20.0, 100),
        Entity("mid-boss", 0.0, 120.0, 25.0, 2400 - tick // 2),
    ]
    if tick < 900:
        entities.append(Entity("walker-blue", -60.0, -60.0, 22.0, 4000 - tick))
    return {entity.id: entity for entity in entities}


@dataclass(frozen=True)
class Entity:
    id: str
    x: float
    y: float
    z: float
    health: int


@dataclass(frozen=True)
class SyncInfo:
    fragment: int
    latest: int
    tick: int
    tps: int
    protocol: str
    map_name: str
    delay: int


@dataclass(frozen=True)
class StartFrame:
    fragment: int
    tps: int
    protocol: str
    map_name: str


@dataclass(frozen=True)
class FullSnapshot:
    fragment: int
    tick: int
    entities: tuple


@dataclass(frozen=True)
class DeltaUpdate:
    fragment: int
    start_tick: int
    end_tick: int
    final: bool
    created: tuple
    updated: tuple
    deleted: tuple


class SyntheticRelay:
    """In-memory fragment cache with a fixed delay and explicit fault injection."""
    def __init__(self, delay=DEFAULT_FRAGMENT_DELAY, map_name=MAP, protocol=SYNTHETIC_PROTOCOL):
        if isinstance(delay, bool) or not isinstance(delay, int) or not 0 <= delay <= 120:
            raise ValueError("Fragment delay must be an integer between 0 and 120")
        self.delay = delay
        self.map_name = text(map_name, "map name")
        self.protocol = text(protocol, "protocol")
        self.connected = True
        self.epoch = 0
        self.latest = -1
        self.ended = False
        self._fragments = {}
        self._dropped = set()

    def publish(self, count=1):
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 10_000:
            raise ValueError("Publish count must be an integer between 1 and 10000")
        if self.ended:
            raise ValueError("Broadcast already ended")
        for _ in range(count):
            fragment = self.latest + 1
            start_tick = fragment * FRAGMENT_TICKS
            end_tick = start_tick + FRAGMENT_TICKS
            before = _world(start_tick)
            after = _world(end_tick)
            created = tuple(entity for key, entity in after.items() if key not in before)
            updated = tuple(entity for key, entity in after.items()
                            if key in before and before[key] != entity)
            deleted = tuple(key for key in before if key not in after)
            self._fragments[fragment] = (
                StartFrame(fragment, TICK_RATE, self.protocol, self.map_name),
                FullSnapshot(fragment, start_tick, tuple(before.values())),
                DeltaUpdate(fragment, start_tick, end_tick, False, created, updated, deleted),
            )
            self.latest = fragment

    def end(self):
        if self.latest < 0:
            raise ValueError("Nothing has been published")
        start, full, delta = self._fragments[self.latest]
        self._fragments[self.latest] = (start, full, replace(delta, final=True))
        self.ended = True

    def sync(self):
        if not self.connected:
            raise ValueError("Synthetic relay disconnected")
        if self.latest < 0:
            raise ValueError("Broadcast has not produced any fragments")
        fragment = max(0, self.latest - self.delay)
        return SyncInfo(fragment, self.latest, fragment * FRAGMENT_TICKS,
                        TICK_RATE, self.protocol, self.map_name, self.delay)

    def read(self, fragment):
        _fragment_number(fragment)
        if not self.connected:
            raise ValueError("Synthetic relay disconnected")
        if fragment in self._dropped:
            raise ValueError("Fragment missing")
        if fragment not in self._fragments:
            raise ValueError("Fragment not yet available")
        return self._fragments[fragment]

    def drop(self, fragment):
        _fragment_number(fragment)
        if fragment not in self._fragments:
            raise ValueError("Fragment not yet available")
        self._dropped.add(fragment)

    def tamper(self, fragment, start_tick=None, end_tick=None):
        start, full, delta = self.read(fragment)
        changes = {}
        if start_tick is not None:
            changes["start_tick"] = _tick(start_tick, "start tick")
        if end_tick is not None:
            changes["end_tick"] = _tick(end_tick, "end tick")
        if not changes:
            raise ValueError("Tamper needs a start or end tick")
        if changes.get("end_tick", delta.end_tick) <= changes.get("start_tick", delta.start_tick):
            raise ValueError("Delta end tick must follow its start tick")
        self._fragments[fragment] = (start, full, replace(delta, **changes))

    def disconnect(self):
        self.connected = False
        self.epoch += 1

    def reconnect(self):
        self.connected = True
        self.epoch += 1
        self.latest = -1
        self.ended = False
        self._fragments = {}
        self._dropped = set()

    def set_map(self, name):
        self.map_name = text(name, "map name")

    def set_protocol(self, name):
        self.protocol = text(name, "protocol")


class BroadcastConsumer:
    """Explicit cursor over synthetic fragments. Any fault requires a fresh session.

    A full snapshot is always applied together with its own fragment's delta, so
    applied tick ranges stay continuous. Missing, duplicated, reordered or
    mismatched data fails closed instead of being extrapolated.
    """
    def __init__(self, relay):
        if type(relay) is not SyntheticRelay:
            raise TypeError("Offline consumer accepts only the synthetic relay")
        self.relay = relay
        self.state = "disconnected"
        self.reason = "No session"
        self.epoch = None
        self.map_name = None
        self.protocol = None
        self.cursor = None
        self.last_tick = None
        self.entities = {}
        self.resyncs = 0
        self.applied = deque(maxlen=512)

    def connect(self):
        try:
            info = self.relay.sync()
            self.epoch = self.relay.epoch
            self.map_name = info.map_name
            self.protocol = info.protocol
            self.resyncs = 0
            self.applied = deque(maxlen=512)
            self._snapshot(info.fragment)
        except ValueError as error:
            self._fault(error)
            raise
        return self

    def advance(self):
        if self.state in ("disconnected", "fault", "ended"):
            return self.state
        try:
            info = self.relay.sync()
            self._check(info)
            target = info.latest if self.relay.ended else info.fragment
            if target < self.cursor:
                return self.state
            if target - self.cursor + 1 > MAX_CATCH_UP_FRAGMENTS:
                self._snapshot(target)
                return self.state
            for fragment in range(self.cursor, target + 1):
                start, full, delta = self.relay.read(fragment)
                self._check_start(start)
                if delta.start_tick != self.last_tick:
                    raise ValueError("Discontinuous tick range")
                self._apply(delta)
                self.cursor = fragment + 1
                if delta.final:
                    self.state = "ended"
                    self.reason = "Synthetic broadcast ended"
                    return self.state
            self.state = "live"
            self.reason = "Synthetic fragments applied"
        except ValueError as error:
            self._fault(error)
        return self.state

    def release(self):
        self.epoch = None
        self.cursor = None
        self.last_tick = None
        self.entities = {}
        self.state = "disconnected"
        self.reason = "Session released"

    def lag(self):
        if self.cursor is None or self.relay.latest < 0:
            return None
        return self.relay.latest - (self.cursor - 1)

    def positions(self):
        return {key: (entity.x, entity.y, entity.z) for key, entity in self.entities.items()}

    def status(self):
        return (f"{self.state}: cursor {self.cursor} tick {self.last_tick} "
                f"entities {len(self.entities)} resyncs {self.resyncs} ({self.reason})")

    def _snapshot(self, fragment):
        start, full, delta = self.relay.read(fragment)
        self._check_start(start)
        if full.tick != fragment * FRAGMENT_TICKS:
            raise ValueError("Snapshot tick does not match its fragment")
        self.entities = {entity.id: entity for entity in full.entities}
        self.last_tick = full.tick
        self.resyncs += 1
        if delta.start_tick != self.last_tick:
            raise ValueError("Snapshot and delta disagree")
        self._apply(delta)
        self.cursor = fragment + 1
        if delta.final:
            self.state = "ended"
            self.reason = "Synthetic broadcast ended"
        else:
            self.state = "live"
            self.reason = "Synthetic snapshot applied"

    def _apply(self, delta):
        for entity in delta.created + delta.updated:
            self.entities[entity.id] = entity
        for key in delta.deleted:
            self.entities.pop(key, None)
        self.applied.append((delta.start_tick, delta.end_tick))
        self.last_tick = delta.end_tick

    def _check_start(self, start):
        if start.protocol != self.protocol:
            raise ValueError("Protocol mismatch")
        if start.map_name != self.map_name:
            raise ValueError("Map/build mismatch")
        if start.tps != TICK_RATE:
            raise ValueError("Tick rate mismatch")

    def _check(self, info):
        if not self.relay.connected:
            raise ValueError("Synthetic relay disconnected")
        if self.relay.epoch != self.epoch:
            raise ValueError("Relay session changed; fresh session required")
        if info.protocol != self.protocol:
            raise ValueError("Protocol mismatch")
        if info.map_name != self.map_name:
            raise ValueError("Map/build mismatch")
        if info.fragment < self.cursor - 1:
            raise ValueError("Broadcast moved backwards")

    def _fault(self, error):
        self.cursor = None
        self.last_tick = None
        self.entities = {}
        self.state = "fault"
        self.reason = str(error)
