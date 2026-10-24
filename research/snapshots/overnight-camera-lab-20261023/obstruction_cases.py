"""Generate distinct proposal decisions and a conservative-proxy counterexample."""
from dataclasses import asdict,replace
from pathlib import Path
import hashlib,json,math
from obstruction import Box,BoxWorld,Frame,Projection,Resolver,near_plane_radius

H=Path(__file__).resolve().parent
def frame(t,desired,fov):
    return Frame(t,1,7,(0,0,48),desired,((0,0,24),(0,0,48),(0,0,72)),
                 projection=Projection(fov,16/9,10))

def run():
    cases=[]
    specifications=[
      ('corner','Blocked entry','Both endpoints are clear, but the direct camera move crosses the corner.',
       [Box((45,45,-20),(160,160,130),'corner')],(200,0,48),(0,200,48),'camera travel blocked'),
      ('curtain','Clear travel, blocked view','This opaque curtain is non-solid in the fixture. Clearance alone misses it.',
       [Box((100,-25,0),(110,25,100),'curtain',solid=False)],(260,0,48),(260,0,48),'hero sightline blocked'),
      ('wall','Wall contraction','The camera stays on the hero side. A wider lens needs more room.',
       [Box((160,-100,-50),(180,100,180),'wall')],(100,0,48),(260,0,48),'contracted'),
      ('proxy','Conservative proxy limitation','The wall is behind the eye. The enclosing cube can reject a clear body and near plane.',
       [Box((272,-300,-200),(274,300,300),'rear wall')],(260,0,48),(260,0,48),None)]
    for key,title,description,boxes,initial,desired,expected in specifications:
        series=[]
        for fov in range(30,111,5):
            world=BoxWorld(boxes,1);rig=Resolver()
            for i in range(61 if key=='wall' else 1):
                d=rig.step(frame(i*.1,desired,fov),world,initial if i==0 else None)
                if d.action=='return-native':break
            if expected:assert d.reason==expected,(key,fov,d)
            if key=='proxy':
                proxy_hits=near_plane_radius(10,fov,16/9)>=12
                assert d.reason==('camera travel blocked' if proxy_hits else 'clear'),(fov,d)
            series.append({'fov':fov,'extent':near_plane_radius(10,fov,16/9),'decision':asdict(d)})
        cases.append({'id':key,'title':title,'description':description,'focus':[0,0,48],
                      'initial':initial,'desired':desired,'boxes':[asdict(b) for b in boxes],'results':series})
    # Independent simple oracle for this intentionally axis-aligned fixture:
    # body box ends at eyeX+8; every point of the near rectangle has x=eyeX-10.
    # A wall starting eyeX+gap, gap>8, cannot intersect either actual primitive.
    false_refusals=[]
    for fov in [30,55,90,110]:
        for gap in [9,12,16,24,32]:
            eye=260;near_x=eye-10;wall_x=eye+gap
            reference_clear=(eye+8<wall_x and near_x<wall_x)
            assert reference_clear
            wall=Box((wall_x,-300,-200),(wall_x+2,300,300),'behind eye')
            d=Resolver().step(frame(0,(eye,0,48),fov),BoxWorld([wall],1),(eye,0,48))
            false_refusals.append({'vertical_fov':fov,'gap':gap,'reference_body_and_near_plane_clear':True,
                                  'proxy_extent':near_plane_radius(10,fov,16/9),'decision':asdict(d)})
    refused=sum(r['decision']['action']=='return-native' for r in false_refusals)
    assert refused>0
    record={'kind':'synthetic counterexample to proxy optimality, not a clearance safety failure',
      'tested':len(false_refusals),'conservative_refusals':refused,'cases':false_refusals,
      'reference':'Exact axis-aligned near rectangle at eyeX-10 plus body cube halfextent8; rear wall starts at eyeX+gap>eyeX+8.',
      'limit':'No native camera geometry convention assumed. A tighter oriented native shape could reduce refusals only after ABI and lens qualification.',
      'resolver_sha256':hashlib.sha256((H/'obstruction.py').read_bytes()).hexdigest()}
    (H/'proxy-false-refusals.json').write_text(json.dumps(record,indent=2)+'\n')
    (H/'obstruction-cases.json').write_text(json.dumps({'synthetic':True,'game_access':False,'cases':cases},indent=2)+'\n')
    print(json.dumps({'visual_cases':len(cases),'lens_variants_each':len(cases[0]['results']),
                     'proxy_comparisons':len(false_refusals),'conservative_refusals':refused}))

if __name__=='__main__':run()
