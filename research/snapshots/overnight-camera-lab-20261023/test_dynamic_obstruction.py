"""New batch2 contracts, not repetitions of the static wall fixture."""
from dataclasses import replace
import math
import unittest
from obstruction import Box, BoxWorld, Projection, Resolver, subjects_in_frame
from test_obstruction import frame

class DynamicCases(unittest.TestCase):
    def test_door_crossing_view_ends_take_before_obscured_proposal(self):
        r=Resolver();r.step(frame(),BoxWorld(epoch=1),(260,0,48))
        # Curtain is visual-only; movement clearance alone would miss it.
        d=r.step(frame(.1,epoch=2),BoxWorld([Box((100,-20,0),(110,20,100),'door',solid=False)],2))
        self.assertEqual(d.reason,'hero sightline blocked');self.assertIsNone(d.camera)
    def test_new_wall_between_previous_camera_and_subject_does_not_teleport(self):
        r=Resolver();r.step(frame(),BoxWorld(epoch=1),(260,0,48))
        d=r.step(frame(.1,epoch=2),BoxWorld([Box((150,-30,-20),(170,30,120),'moving wall')],2))
        self.assertEqual(d.reason,'camera travel blocked');self.assertIsNone(d.camera)
    def test_clear_new_world_generation_continues(self):
        r=Resolver();r.step(frame(),BoxWorld(epoch=1),(260,0,48))
        d=r.step(frame(.1,epoch=2),BoxWorld(epoch=2))
        self.assertEqual(d.action,'publish-proposal')
    def test_corner_endpoints_are_clear_but_transition_is_not(self):
        w=BoxWorld([Box((45,45,-20),(160,160,130),'corner')],1)
        f=frame(desired=(0,200,48));r=Resolver()
        d=r.step(f,w,(200,0,48))
        self.assertEqual(d.reason,'camera travel blocked')
    def test_clearance_does_not_mean_narrow_lens_fits_hero(self):
        w=BoxWorld(epoch=1)
        tight=replace(frame(desired=(100,0,48)),projection=Projection(20,16/9,4))
        d=Resolver().step(tight,w,(100,0,48))
        self.assertEqual(d.reason,'hero leaves frame')
        wider=replace(tight,projection=Projection(55,16/9,4))
        self.assertEqual(Resolver().step(wider,w,(100,0,48)).action,'publish-proposal')
    def test_wide_lens_requires_more_wall_clearance(self):
        w=BoxWorld([Box((160,-100,-50),(180,100,180),'wall')],1)
        radii=[]
        for fov in (30,100):
            r=Resolver()
            for i in range(21):
                f=replace(frame(i*.1),projection=Projection(fov,16/9,10))
                d=r.step(f,w,(100,0,48) if i==0 else None)
                self.assertEqual(d.action,'publish-proposal',d)
            radii.append(d.distance)
        self.assertLess(radii[1],radii[0]-10)
    def test_bank_rotates_landmarks_toward_narrow_frame_edge(self):
        f=frame(desired=(100,0,48));p=Projection(55,.4,4)
        self.assertTrue(subjects_in_frame(f.desired,f.focus,f.landmarks,p,0))
        self.assertFalse(subjects_in_frame(f.desired,f.focus,f.landmarks,p,90))
    def test_missing_measured_projection_does_not_claim_framing(self):
        f=frame(desired=(100,0,48))
        self.assertIsNone(f.projection)
        self.assertEqual(Resolver().step(f,BoxWorld(epoch=1),(100,0,48)).action,'publish-proposal')
    def test_invalid_projection_refuses_before_any_world_query(self):
        for p in (Projection(180,1,4),Projection(55,0,4),Projection(55,1,math.nan),Projection(55,1,4,1)):
            d=Resolver().step(replace(frame(),projection=p),BoxWorld(epoch=1),(260,0,48))
            self.assertEqual(d.reason,'invalid projection');self.assertEqual(d.queries,0)

if __name__=='__main__':unittest.main()
