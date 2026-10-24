"""Deterministic adversarial fixtures and an independent sampled oracle.

This is not an exhaustive geometry proof. Thin-wall crossing is also tested
analytically in the unit suite; sampling alone could miss thin surfaces.
"""
from dataclasses import asdict
from pathlib import Path
import json
import math
import random
import time
from obstruction import Box, BoxWorld, Frame, Resolver
from shot_lab import obstruction_scenario

HERE=Path(__file__).resolve().parent

def inside(p,box,extent):
    return all(a-extent <= v <= b+extent for v,a,b in zip(p,box.low,box.high))

def inspect_segment(a,b,boxes,extent,visibility=False):
    n=max(1,math.ceil(math.dist(a,b)))
    for i in range(n+1):
        p=tuple(x+(y-x)*i/n for x,y in zip(a,b))
        for box in boxes:
            if not (box.occludes if visibility else box.solid): continue
            if inside(p,box,extent):
                return {'position':p,'obstacle':box.name,'extent':extent,'visibility':visibility}
    return None

def run():
    began=time.perf_counter();rng=random.Random(681923)
    reasons={};accepted=0;failures=[];queries=[]
    for case in range(1200):
        angle=rng.uniform(-math.pi,math.pi)
        desired=(260*math.cos(angle),260*math.sin(angle),rng.uniform(32,100))
        focus=(0,0,48);landmarks=(focus,(0,0,24),(0,0,72));boxes=[]
        for n in range(rng.randrange(6)):
            x,y=rng.uniform(-300,300),rng.uniform(-300,300)
            w,d=rng.uniform(.1,70),rng.uniform(.1,70)
            boxes.append(Box((x,y,-20),(x+w,y+d,rng.uniform(60,160)),f'case{case}-box{n}',
                             solid=rng.random()>.1,occludes=rng.random()>.1))
        world=BoxWorld(boxes,1);r=Resolver()
        f=Frame(0,1,7,focus,desired,landmarks)
        decision=r.step(f,world,desired);queries.append(decision.queries)
        reasons[decision.reason]=reasons.get(decision.reason,0)+1
        if decision.camera is None: continue
        accepted+=1
        errors=[inspect_segment(desired,decision.camera,boxes,8)]
        errors.extend(inspect_segment(decision.camera,p,boxes,0,True) for p in landmarks)
        errors=[e for e in errors if e]
        if errors:failures.append({'case':case,'boxes':[asdict(b) for b in boxes],'decision':asdict(decision),'errors':errors})
    moving=obstruction_scenario()
    moving_boxes=[Box(**b) for b in moving['boxes']]
    last=(260,0,48)
    for i,f in enumerate(moving['frames']):
        errors=[inspect_segment(last,f['camera'],moving_boxes,8)]
        target=f['target']
        errors.extend(inspect_segment(f['camera'],p,moving_boxes,0,True) for p in
                      (target,(target[0],target[1],72),(target[0],target[1],24)))
        if any(errors):failures.append({'moving_frame':i,'errors':[e for e in errors if e]})
        last=f['camera']
    report={'kind':'synthetic bounded stress; no game performance or compatibility claim',
            'seed':681923,'independent_random_scenes':1200,'accepted_scenes':accepted,
            'reasons':reasons,'maximum_queries':max(queries),'invariant_failures':failures,
            'moving_frames':len(moving['frames']),
            'moving_minimum_radius':min(f['distance'] for f in moving['frames']),
            'moving_final_radius':moving['frames'][-1]['distance'],
            'elapsed_seconds':time.perf_counter()-began,
            'limits':['Analytic axis-aligned boxes only; selected hero is not part of fixture world.',
                      'Visibility/solidity are explicit fixture properties, not verified game masks.',
                      'Independent one-unit sampling is not a proof for arbitrarily thin geometry.',
                      'No asynchronous scene changes, native queries, live FPS or actual rendered near plane.']}
    (HERE/'stress-review.json').write_text(json.dumps(report,indent=2)+'\n')
    assert not failures,failures[:1]
    assert accepted>=300,accepted
    print(json.dumps(report,indent=2))

if __name__=='__main__':run()
