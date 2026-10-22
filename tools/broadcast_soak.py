"""Deterministic soak for the synthetic broadcast fixture.

Run from the repository root: python -B tools/broadcast_soak.py [--iterations N] [--seed S]
The fixture is entirely in-memory: no network, game, process or file access.
A nonzero exit means an invariant was violated; seed and iteration are printed.
"""
import argparse
from pathlib import Path
import random
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dolly_live.broadcast import BroadcastConsumer, FRAGMENT_TICKS, SyntheticRelay


DELAYS = (0, 1, 2, 4, 8, 12)
MAPS = ("synthetic-stage-v1", "other-map")
PROTOCOLS = ("synthetic-broadcast-v1", "other-protocol")
ACTIONS = ("publish", "advance", "drop", "tamper", "disconnect", "reconnect",
           "map", "protocol", "end", "connect")
WEIGHTS = (30, 30, 4, 2, 2, 2, 2, 2, 2, 10)


class Violation(AssertionError):
    pass


def check(consumer, seed, iteration, step):
    applied = list(consumer.applied)
    for start, end in applied:
        if end - start != FRAGMENT_TICKS:
            raise Violation(f"range width {start}-{end}")
    if applied:
        if applied != sorted(applied):
            raise Violation("applied ranges out of order")
        if len(set(applied)) != len(applied):
            raise Violation("applied range repeated")
    if consumer.state in ("live", "ended"):
        if not applied:
            raise Violation("no applied range while active")
        if consumer.last_tick != applied[-1][1]:
            raise Violation(f"last tick {consumer.last_tick} vs {applied[-1][1]}")
        if consumer.state == "live" and consumer.cursor != applied[-1][1] // FRAGMENT_TICKS:
            raise Violation(f"cursor {consumer.cursor} disagrees with applied range")
        if not 3 <= len(consumer.entities) <= 4:
            raise Violation(f"entity count {len(consumer.entities)}")
        for entity in consumer.entities.values():
            if entity.id.startswith("hero") and (abs(entity.x) > 40.001 or abs(entity.y) > 40.001):
                raise Violation(f"hero position out of bounds: {entity}")
    if consumer.state == "fault":
        if consumer.cursor is not None or consumer.last_tick is not None or consumer.entities:
            raise Violation("fault state retained session data")
        if not consumer.reason:
            raise Violation(f"empty fault reason for seed {seed} iteration {iteration} step {step}")


def run(iterations, seed, progress):
    rng = random.Random(seed)
    stats = {"fragments": 0, "applied": 0, "faults": 0, "resyncs": 0, "ended": 0}
    for iteration in range(iterations):
        relay = SyntheticRelay(delay=rng.choice(DELAYS))
        relay.publish(rng.randint(1, 5))
        consumer = BroadcastConsumer(relay)
        try:
            consumer.connect()
        except ValueError:
            pass
        for step in range(rng.randint(1, 60)):
            previous = (consumer.state, consumer.cursor, consumer.last_tick, len(consumer.applied))
            action = rng.choices(ACTIONS, WEIGHTS)[0]
            if action == "publish":
                if not relay.ended:
                    relay.publish(rng.randint(1, 6))
            elif action == "advance":
                consumer.advance()
                if previous[0] in ("fault", "ended", "disconnected"):
                    after = (consumer.state, consumer.cursor, consumer.last_tick, len(consumer.applied))
                    if after != previous:
                        raise Violation(f"advance changed state after {previous[0]}")
            elif action == "drop":
                if relay.latest >= 0:
                    relay.drop(rng.randint(0, relay.latest))
            elif action == "tamper":
                if relay.latest >= 0:
                    fragment = rng.randint(0, relay.latest)
                    try:
                        delta = relay.read(fragment)[2]
                        shift = FRAGMENT_TICKS * rng.randint(1, 3)
                        relay.tamper(fragment, start_tick=delta.start_tick + shift,
                                     end_tick=delta.end_tick + shift)
                    except ValueError:
                        pass
            elif action == "disconnect":
                relay.disconnect()
            elif action == "reconnect":
                if not relay.connected:
                    relay.reconnect()
            elif action == "map":
                relay.set_map(rng.choice(MAPS))
            elif action == "protocol":
                relay.set_protocol(rng.choice(PROTOCOLS))
            elif action == "end":
                if relay.latest >= 0 and not relay.ended:
                    relay.end()
            else:
                if relay.connected and relay.latest >= 0:
                    try:
                        consumer.connect()
                    except ValueError:
                        pass
            if previous[0] != "fault" and consumer.state == "fault":
                stats["faults"] += 1
            check(consumer, seed, iteration, step)
        stats["fragments"] += relay.latest + 1
        stats["applied"] += len(consumer.applied)
        stats["resyncs"] += consumer.resyncs
        if consumer.state == "ended":
            stats["ended"] += 1
        if progress and (iteration + 1) % progress == 0:
            print(f"{iteration + 1} iterations; {stats['faults']} faults; {stats['resyncs']} resyncs")
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--progress", type=int, default=500)
    args = parser.parse_args(argv)
    if not 1 <= args.iterations <= 100_000_000:
        raise SystemExit("--iterations must be between 1 and 100000000")
    if args.progress < 0:
        raise SystemExit("--progress cannot be negative")
    stats = run(args.iterations, args.seed, args.progress)
    print(f"seed {args.seed}: {args.iterations} iterations, "
          f"{stats['fragments']} fragments, {stats['applied']} deltas, "
          f"{stats['resyncs']} resyncs, {stats['faults']} fault states observed, "
          f"{stats['ended']} ended sessions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
