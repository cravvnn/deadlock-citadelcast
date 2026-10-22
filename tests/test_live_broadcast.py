"""Offline sequencing checks for the synthetic broadcast fixture."""
import ast
from pathlib import Path
import unittest

from dolly_live.broadcast import (BroadcastConsumer, DEFAULT_FRAGMENT_DELAY, FRAGMENT_TICKS,
                                 MAX_CATCH_UP_FRAGMENTS, SYNTHETIC_PROTOCOL, TICK_RATE,
                                 SyntheticRelay)
from dolly_live.presets import MAP


class RelayTests(unittest.TestCase):
    def test_sync_waits_for_the_configured_buffer(self):
        relay = SyntheticRelay()
        relay.publish(3)
        info = relay.sync()
        self.assertEqual((info.fragment, info.latest, info.tick), (0, 2, 0))
        self.assertEqual((info.delay, info.tps, info.protocol, info.map_name),
                         (DEFAULT_FRAGMENT_DELAY, TICK_RATE, SYNTHETIC_PROTOCOL, MAP))
        relay.publish(6)
        self.assertEqual(relay.sync().fragment, 0)
        relay.publish(1)
        self.assertEqual((relay.sync().fragment, relay.sync().tick), (1, FRAGMENT_TICKS))

    def test_fragments_are_continuous_and_deterministic(self):
        first, second = SyntheticRelay(), SyntheticRelay()
        first.publish(12)
        second.publish(12)
        for fragment in range(12):
            self.assertEqual(first.read(fragment), second.read(fragment))
            start, full, delta = first.read(fragment)
            self.assertEqual(start.fragment, fragment)
            self.assertEqual(delta.start_tick, fragment * FRAGMENT_TICKS)
            self.assertEqual(delta.end_tick, delta.start_tick + FRAGMENT_TICKS)
            self.assertEqual(full.tick, delta.start_tick)
            self.assertEqual((start.tps, start.protocol, start.map_name),
                             (TICK_RATE, SYNTHETIC_PROTOCOL, MAP))
            self.assertFalse(delta.final)

    def test_destroyed_walker_removed_by_delta_not_teleported(self):
        relay = SyntheticRelay()
        relay.publish(17)
        start, full, delta = relay.read(9)
        self.assertEqual(delta.deleted, ("walker-blue",))
        start, full, delta = relay.read(10)
        self.assertNotIn("walker-blue", {entity.id for entity in full.entities})
        self.assertEqual(len(full.entities), 3)
        for entity in full.entities:
            if entity.id.startswith("hero"):
                self.assertLessEqual(abs(entity.x), 40.001)
                self.assertLessEqual(abs(entity.y), 40.001)

    def test_end_marks_only_the_latest_fragment_final(self):
        relay = SyntheticRelay()
        relay.publish(5)
        relay.end()
        self.assertTrue(relay.read(4)[2].final)
        self.assertFalse(relay.read(3)[2].final)
        with self.assertRaises(ValueError):
            relay.publish(1)
        relay.end()

    def test_drop_disconnect_and_reconnect(self):
        relay = SyntheticRelay()
        relay.publish(5)
        relay.drop(2)
        with self.assertRaisesRegex(ValueError, "missing"):
            relay.read(2)
        relay.disconnect()
        with self.assertRaisesRegex(ValueError, "disconnected"):
            relay.sync()
        relay.reconnect()
        self.assertEqual((relay.latest, relay.epoch), (-1, 2))
        with self.assertRaisesRegex(ValueError, "not produced"):
            relay.sync()
        relay.publish(2)
        self.assertEqual(relay.read(0)[0].fragment, 0)

    def test_tamper_validates_its_change(self):
        relay = SyntheticRelay()
        relay.publish(3)
        with self.assertRaises(ValueError):
            relay.tamper(0)
        with self.assertRaises(ValueError):
            relay.tamper(0, end_tick=0)
        with self.assertRaises(ValueError):
            relay.tamper(9, start_tick=1)
        relay.tamper(0, start_tick=45)
        self.assertEqual(relay.read(0)[2].start_tick, 45)

    def test_invalid_relay_parameters(self):
        for delay in (-1, 121, True, 8.0):
            with self.subTest(delay=delay), self.assertRaises(ValueError):
                SyntheticRelay(delay=delay)
        for name in ("", " " * 200, None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                SyntheticRelay(map_name=name)
        relay = SyntheticRelay()
        for count in (0, -1, 10_001, True, 1.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                relay.publish(count)
        for fragment in (-1, 10_000_001, True, 1.5):
            with self.subTest(fragment=fragment), self.assertRaises(ValueError):
                relay.read(fragment)


class ConsumerTests(unittest.TestCase):
    def live(self, publish=9, delay=DEFAULT_FRAGMENT_DELAY):
        relay = SyntheticRelay(delay=delay)
        relay.publish(publish)
        return relay, BroadcastConsumer(relay).connect()

    def test_connect_applies_snapshot_with_its_own_delta(self):
        relay, consumer = self.live()
        self.assertEqual(consumer.state, "live")
        self.assertEqual((consumer.resyncs, consumer.cursor, consumer.last_tick), (1, 1, FRAGMENT_TICKS))
        self.assertEqual(list(consumer.applied), [(0, FRAGMENT_TICKS)])
        self.assertEqual(len(consumer.entities), 4)
        self.assertEqual(len(consumer.positions()), 4)
        self.assertEqual(consumer.lag(), 8)

    def test_advance_applies_new_fragments_once(self):
        relay, consumer = self.live()
        relay.publish(1)
        self.assertEqual(consumer.advance(), "live")
        self.assertEqual((consumer.last_tick, consumer.cursor), (2 * FRAGMENT_TICKS, 2))
        applied = list(consumer.applied)
        consumer.advance()
        self.assertEqual(list(consumer.applied), applied)
        self.assertEqual(consumer.state, "live")

    def test_no_work_while_the_buffer_has_not_moved(self):
        relay, consumer = self.live(publish=3, delay=0)
        applied = list(consumer.applied)
        self.assertEqual((consumer.cursor, consumer.last_tick), (3, 3 * FRAGMENT_TICKS))
        self.assertEqual(consumer.advance(), "live")
        self.assertEqual(list(consumer.applied), applied)

    def test_deletion_applies_at_the_right_fragment(self):
        relay, consumer = self.live(publish=17)
        self.assertIn("walker-blue", consumer.entities)
        self.assertEqual(list(consumer.applied)[-1], (8 * FRAGMENT_TICKS, 9 * FRAGMENT_TICKS))
        relay.publish(2)
        consumer.advance()
        self.assertNotIn("walker-blue", consumer.entities)
        self.assertEqual(relay.read(9)[2].deleted, ("walker-blue",))
        self.assertEqual(list(consumer.applied)[-2], (9 * FRAGMENT_TICKS, 10 * FRAGMENT_TICKS))
        self.assertEqual(consumer.last_tick, 11 * FRAGMENT_TICKS)

    def test_catch_up_resyncs_instead_of_replaying_unbounded_deltas(self):
        relay, consumer = self.live()
        relay.publish(13)
        consumer.advance()
        self.assertEqual(consumer.resyncs, 2)
        self.assertEqual(consumer.cursor, 14)
        self.assertEqual(list(consumer.applied)[-1], (13 * FRAGMENT_TICKS, 14 * FRAGMENT_TICKS))
        self.assertEqual(consumer.state, "live")

    def test_end_drains_to_the_final_fragment(self):
        relay, consumer = self.live(publish=5)
        relay.end()
        self.assertEqual(consumer.advance(), "ended")
        self.assertEqual(consumer.last_tick, 5 * FRAGMENT_TICKS)
        self.assertEqual(len(consumer.applied), 5)
        self.assertEqual(consumer.advance(), "ended")
        self.assertIn("ended", consumer.reason)

    def test_lag_tracks_delivery_against_the_latest_fragment(self):
        relay, consumer = self.live(publish=21)
        self.assertEqual(consumer.lag(), 8)
        relay.publish(1)
        self.assertEqual(consumer.lag(), 9)
        consumer.advance()
        self.assertEqual(consumer.lag(), 8)

    def test_consumer_rejects_non_synthetic_relays(self):
        class Impostor:
            def sync(self):
                return None
        for relay in (object(), Impostor(), None):
            with self.subTest(relay=relay), self.assertRaises(TypeError):
                BroadcastConsumer(relay)


class FaultTests(unittest.TestCase):
    def live(self, publish=9):
        relay = SyntheticRelay()
        relay.publish(publish)
        return relay, BroadcastConsumer(relay).connect()

    def test_missing_fragment_faults_and_requires_a_fresh_session(self):
        relay, consumer = self.live()
        relay.drop(2)
        relay.publish(4)
        self.assertEqual(consumer.advance(), "fault")
        self.assertIn("missing", consumer.reason)
        self.assertIsNone(consumer.cursor)
        self.assertEqual(consumer.entities, {})
        applied = list(consumer.applied)
        self.assertEqual(applied, [(0, FRAGMENT_TICKS), (FRAGMENT_TICKS, 2 * FRAGMENT_TICKS)])
        self.assertEqual(consumer.advance(), "fault")
        self.assertEqual(list(consumer.applied), applied)
        consumer.connect()
        self.assertEqual(consumer.state, "live")
        self.assertEqual(list(consumer.applied), [(4 * FRAGMENT_TICKS, 5 * FRAGMENT_TICKS)])

    def test_discontinuous_ticks_fault(self):
        relay, consumer = self.live()
        relay.tamper(1, start_tick=12_345, end_tick=12_435)
        relay.publish(1)
        self.assertEqual(consumer.advance(), "fault")
        self.assertIn("Discontinuous", consumer.reason)
        self.assertFalse(consumer.entities)

    def test_reconnect_faults_and_a_fresh_session_starts_clean(self):
        relay, consumer = self.live()
        relay.disconnect()
        self.assertEqual(consumer.advance(), "fault")
        self.assertIn("disconnected", consumer.reason)
        with self.assertRaises(ValueError):
            consumer.connect()
        self.assertEqual(consumer.state, "fault")
        relay.reconnect()
        with self.assertRaises(ValueError):
            consumer.connect()
        relay.publish(9)
        consumer.connect()
        self.assertEqual(consumer.state, "live")
        self.assertEqual((consumer.resyncs, list(consumer.applied)), (1, [(0, FRAGMENT_TICKS)]))

    def test_session_epoch_change_is_not_resumed(self):
        relay, consumer = self.live()
        relay.disconnect()
        relay.reconnect()
        relay.publish(9)
        self.assertEqual(consumer.advance(), "fault")
        self.assertIn("fresh session", consumer.reason)

    def test_map_and_protocol_changes_fault(self):
        relay, consumer = self.live()
        relay.set_map("wrong-map")
        self.assertEqual(consumer.advance(), "fault")
        self.assertIn("Map/build", consumer.reason)
        with self.assertRaises(ValueError):
            consumer.connect()
        self.assertEqual(consumer.state, "fault")
        relay.reconnect()
        relay.publish(9)
        consumer.connect()
        self.assertEqual(consumer.state, "live")
        self.assertEqual(consumer.map_name, "wrong-map")
        relay.set_protocol("other-protocol")
        self.assertEqual(consumer.advance(), "fault")
        self.assertIn("Protocol", consumer.reason)
        self.assertIsNone(consumer.cursor)


class BoundaryTests(unittest.TestCase):
    def test_broadcast_module_is_offline_only(self):
        allowed = {"__future__", "collections", "dataclasses", "math"}
        root = Path(__file__).resolve().parents[1] / "dolly_live"
        added = 0
        for node in ast.walk(ast.parse((root / "broadcast.py").read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                for name in node.names:
                    self.assertIn(name.name, allowed)
                    added += 1
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                self.assertIn(node.module, allowed)
                added += 1
        self.assertGreater(added, 0)

    def test_constant_contract(self):
        self.assertEqual((TICK_RATE, FRAGMENT_TICKS), (30, 90))
        self.assertEqual(DEFAULT_FRAGMENT_DELAY, 8)
        self.assertEqual(MAX_CATCH_UP_FRAGMENTS, 4)
        self.assertTrue(SYNTHETIC_PROTOCOL.startswith("synthetic"))
        self.assertTrue(MAP.startswith("synthetic"))


if __name__ == "__main__":
    unittest.main()
