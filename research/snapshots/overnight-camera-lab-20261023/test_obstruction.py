import math
import unittest
from obstruction import Box, BoxWorld, Config, Frame, Hit, Resolver, near_plane_radius

def frame(t=0, desired=(260,0,48), focus=(0,0,48), epoch=1, target=7, allowed=True):
    return Frame(t,epoch,target,focus,desired,(focus,(focus[0],focus[1],focus[2]+24),
        (focus[0],focus[1],focus[2]-24)),allowed)

class GeometryTests(unittest.TestCase):
    def test_box_sweep_accounts_for_volume_and_contact(self):
        w=BoxWorld([Box((100,-20,0),(110,20,100))])
        self.assertAlmostEqual(w.sweep((0,0,48),(200,0,48),8).fraction,.46)
        self.assertAlmostEqual(w.sweep((0,0,48),(200,0,48),0).fraction,.5)
        self.assertTrue(w.sweep((92,0,48),(0,0,48),8).start_solid)
    def test_parallel_miss_and_thin_wall_no_tunnelling(self):
        w=BoxWorld([Box((100,-20,0),(100.01,20,100))])
        self.assertFalse(w.sweep((0,40,48),(1000,40,48),8).obstacle)
        self.assertAlmostEqual(w.sweep((0,0,48),(1000,0,48),8).fraction,.092)
    def test_diagonal_sweep(self):
        w=BoxWorld([Box((100,100,0),(200,200,100))])
        h=w.sweep((0,0,48),(300,300,48),10)
        self.assertAlmostEqual(h.fraction,.3)
    def test_bad_geometry_and_numbers_refuse(self):
        with self.assertRaises(ValueError): Box((1,1,1),(0,0,0))
        self.assertFalse(BoxWorld().sweep((math.nan,0,0),(1,0,0),1).valid)
    def test_near_plane_envelope_covers_wide_aspect_and_bank(self):
        # 90deg vertical, near10, aspect2 -> corner=(10,20,10), radius sqrt600.
        self.assertAlmostEqual(near_plane_radius(10,90,2),math.sqrt(600))
        self.assertGreater(near_plane_radius(10,90,2),near_plane_radius(10,60,2))
        with self.assertRaises(ValueError): near_plane_radius(10,180,2)

class ResolverTests(unittest.TestCase):
    def test_clear_world_leaves_requested_pose(self):
        r=Resolver();d=r.step(frame(),BoxWorld(epoch=1),(260,0,48))
        self.assertEqual(d.action,"publish-proposal");self.assertEqual(d.camera,(260,0,48))
        self.assertEqual(d.queries,6)
    def test_recovery_limit_does_not_slow_ordinary_hero_translation(self):
        r=Resolver();w=BoxWorld(epoch=1)
        r.step(frame(),w,(260,0,48))
        # 300 units/sec exceeds recovery speed, but is continuous valid tracking.
        for i in range(1,21):
            x=i*30
            d=r.step(frame(i*.1,focus=(x,0,48),desired=(x+260,0,48)),w)
            self.assertEqual(d.action,"publish-proposal")
            self.assertAlmostEqual(d.camera[0],x+260)
            self.assertAlmostEqual(d.distance,260)
    def test_wall_contracts_without_camera_penetration(self):
        # Camera is already on the hero side of a wall; requested wide view is not.
        r=Resolver();w=BoxWorld([Box((150,-100,-50),(170,100,200))],1)
        d=r.step(frame(),w,(130,0,48))
        self.assertEqual(d.action,"publish-proposal")
        self.assertLessEqual(d.camera[0],140)
        self.assertEqual(d.reason,"contracted")
    def test_recovery_waits_then_has_a_speed_limit(self):
        r=Resolver();wall=BoxWorld([Box((150,-100,-50),(170,100,200))],1)
        d=r.step(frame(),wall,(140,0,48));self.assertEqual(d.distance,140)
        w=BoxWorld(epoch=1)
        self.assertEqual(r.step(frame(.1),w).distance,140)
        self.assertEqual(r.step(frame(.2),w).distance,140)
        self.assertAlmostEqual(r.step(frame(.3),w).distance,152)
    def test_endpoint_clear_does_not_permit_crossing_wall(self):
        r=Resolver();w=BoxWorld([Box((100,-100,-50),(110,100,200))],1)
        d=r.step(frame(desired=(80,0,48)),w,(180,0,48))
        self.assertEqual(d.reason,"camera travel blocked");self.assertIsNone(d.camera)
    def test_head_visibility_independent_of_camera_clearance(self):
        w=BoxWorld([Box((50,-5,62),(70,5,80))],1)
        d=Resolver().step(frame(),w,(260,0,48))
        self.assertEqual(d.reason,"hero sightline blocked")
    def test_non_solid_visual_obstruction_is_still_a_blocked_shot(self):
        w=BoxWorld([Box((100,-30,0),(110,30,100),"curtain",solid=False)],1)
        d=Resolver().step(frame(),w,(260,0,48))
        self.assertEqual(d.reason,"hero sightline blocked")
    def test_transparent_solid_still_blocks_camera_travel(self):
        w=BoxWorld([Box((100,-30,0),(110,30,100),"glass",occludes=False)],1)
        d=Resolver().step(frame(desired=(80,0,48)),w,(180,0,48))
        self.assertEqual(d.reason,"camera travel blocked")
    def test_no_distance_in_narrow_space(self):
        w=BoxWorld([Box((60,-100,-50),(80,100,200))],1)
        d=Resolver().step(frame(),w,(40,0,48))
        self.assertEqual(d.reason,"no usable camera distance")
    def test_prop_appearing_at_camera_requires_return(self):
        r=Resolver();r.step(frame(),BoxWorld(epoch=1),(260,0,48))
        d=r.step(frame(.1),BoxWorld([Box((250,-10,30),(270,10,70))],1))
        self.assertEqual(d.action,"return-native")
    def test_target_swap_gap_focus_loss_and_teleport_cancel(self):
        for next_frame in (frame(.1,target=8),frame(.3),frame(.1,allowed=False),
                           frame(.1,focus=(600,0,48),desired=(860,0,48))):
            with self.subTest(next_frame=next_frame):
                r=Resolver();w=BoxWorld(epoch=1);r.step(frame(),w,(260,0,48))
                self.assertEqual(r.step(next_frame,w).action,"return-native")
                self.assertEqual(r.step(frame(.2),w).reason,"already stopped")
    def test_stale_epoch_refuses_without_using_query(self):
        d=Resolver().step(frame(),BoxWorld(epoch=0),(260,0,48))
        self.assertEqual(d.reason,"stale world query");self.assertEqual(d.queries,0)
    def test_epoch_change_inside_query_refuses(self):
        class Changing(BoxWorld):
            def sweep(self,*args): self.epoch+=1;return Hit(True)
        d=Resolver().step(frame(),Changing(epoch=1),(260,0,48))
        self.assertEqual(d.reason,"world changed during query")
    def test_invalid_result_and_budget_refuse(self):
        class Bad(BoxWorld):
            def sweep(self,*args): return Hit(True,math.nan)
        self.assertEqual(Resolver().step(frame(),Bad(epoch=1),(260,0,48)).reason,"invalid world query")
        d=Resolver(Config(query_budget=5)).step(frame(),BoxWorld(epoch=1),(260,0,48))
        self.assertEqual(d.reason,"query budget exhausted");self.assertEqual(d.queries,5)
    def test_one_second_entry_is_not_implicitly_safe(self):
        w=BoxWorld([Box((100,-100,-20),(120,100,140))],1)
        # Interpolation across a wall cannot be made safe by taking smaller steps.
        d=Resolver().step(frame(desired=(80,0,48)),w,(180,0,48))
        self.assertEqual(d.action,"return-native")
    def test_invalid_configuration(self):
        with self.assertRaises(ValueError): Resolver(Config(recover_speed=0))

if __name__ == '__main__': unittest.main()
