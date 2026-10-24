"""Author synthetic production concepts; never emits game-loadable files."""
from dataclasses import asdict
from pathlib import Path
import json
import math
from obstruction import Box, BoxWorld, Frame, Resolver

HERE=Path(__file__).resolve().parent

def concept(id,title,family,seconds,shape,cue,picture,needs,radius=600,height=180,start=-50,end=40,bank=0):
    return dict(id=id,title=title,family=family,duration=seconds,shape=shape,cue=cue,picture=picture,
                requires=needs,radius=radius,height=height,start=start,end=end,bank=bank,
                status="synthetic concept; not a game-ready path",coordinate_space="illustrative local anchor",
                fallback="Operator cuts to native chase or an already-qualified wide; no automatic target selection.")

CATALOG=[
 concept("walker-reveal","Walker reveal","Walkers",7,"arc","Before a lane story or during a lull",
         "Low three-quarter approach into a broad side reveal; bank peaks gently and resolves level.",
         ["Current-map Walker anchor and clear corridor","New authored Dolly keys"],700,160,-60,25,4),
 concept("walker-defense","Walker defense wide","Walkers",6,"crane","Defending team gathers before a push",
         "Rise enough to include both approach lanes, then hold the readable wide.",
         ["Per-Walker overview anchor","Roof and foliage clearance"],760,330,-30,-20),
 concept("walker-after","Walker aftermath","Walkers",5,"pullback","After objective destruction, once action settles",
         "Start on the objective area and pull back to reveal the team and lane context.",
         ["Operator timing; destruction event not bound","Anchor remains usable after objective changes"],450,160,20,35),
 concept("opening-lane","Opening lane rollout","Match opening",8,"rail","Viewer already receives the opening; operator cues on departure",
         "Travel above one lane toward its first contest, with a level horizon and stable direction.",
         ["Received opening footage; no live rewind assumed","Manually surveyed lane path"],750,260,-30,25),
 concept("opening-escort","Team departure escort","Match opening",6,"hero-side","Select a departing hero before movement begins",
         "Parallel elevated side view provides travel direction and team context.",
         ["Target lifetime and zipline/dash behavior","Clearance for a moving rig"],350,110,90,90),
 concept("opening-reveal","Base-to-city reveal","Match opening",6,"crane","Pre-match or an opening buffer segment",
         "Slow lift from team staging into the city skyline; end on a stable overview.",
         ["Base anchor and sky/roof clearance","Native map-relative path authoring"],850,360,-50,-10),
 concept("midboss-establish","Midboss arena reveal","Midboss",6,"arc","Before teams commit to the objective",
         "A short perimeter arc explains the pit and entrances; stop before the contested moment.",
         ["Current arena geometry and ceiling","Arena anchor; no entity tracking required"],650,300,-55,15),
 concept("midboss-fight","Midboss fight master","Midboss",8,"locked","Combat begins in the objective area",
         "Hold a high three-quarter view of the arena and entrances; prioritize readable action.",
         ["Surveyed wide bookmark","Visible arena and entrances; no participant list assumed"],780,450,25,25),
 concept("midboss-entrance","Entrance watch","Midboss",5,"rail","Producer expects a contest from one entrance",
         "Short lateral move ends in a stable angle linking the entrance and objective.",
         ["Operator-selected entrance","No hidden information or prediction of arrivals"],620,240,10,35),
 concept("midboss-after","Objective aftermath","Midboss",4,"pullback","After the decisive event is already visible",
         "Pull back for team context, then hand off to the selected player's native view.",
         ["Manual cue first","No automatic steal/reward detection yet"],500,230,35,40),
 concept("hero-turn","Hero three-quarter: turn","Players",6,"hero-follow","Select the hero after a standout play",
         "Follow hero facing with a restrained three-quarter front/side angle, keeping the hero centered.",
         ["Based on accepted motion and tested A profile","Shorter timing and clearance remain new"],260,84,45,45),
 concept("hero-hold","Hero three-quarter: hold","Players",6,"hero-hold","Use when a stable background matters",
         "Hold the starting world bearing while tracking position; hero may turn side-on or away.",
         ["Based on tested B profile","Clearance and chosen duration remain new"],260,84,45,45),
 concept("hero-parallel","Lateral action profile","Players",5,"hero-side","Open-lane run or dash; action remains readable",
         "A side view lets a moving hero travel through the scene without an orbit chasing every turn.",
         ["Moving-target corridor","Dash discontinuity and framing tests"],320,96,90,90),
 concept("hero-victory","Post-play portrait","Players",3.5,"hero-push","After a big play, once the hero is out of immediate danger",
         "Brief front/side push-in with enough room for the weapon and hands, then native chase.",
         ["Clearance and hero-specific framing","Manual producer decision; no kill automation"],300,84,45,45),
 concept("billy-reload","Billy reload insert","Players",2.5,"reload","Operator sees reload begin and elects to feature it",
         "Hold weapon-side three-quarter framing; let the hand animation cross the frame naturally.",
         ["Actual Billy recording with reload/entry/exit timestamps","No reload trigger or phase has been measured"],230,76,55,55),
 concept("hero-exit","Hero-to-context exit","Players",5,"hero-pullback","After a player insert, reveal where the next action is",
         "Ease wider and higher while keeping the hero anchored, then cut to a tactical overview.",
         ["Moving-target clearance","Separate overview bookmark; no automatic feed switch"],270,120,45,55),
]

def smooth(u): return u*u*(3-2*u)
def path(c,t):
    u=t/c['duration'];v=smooth(u);shape=c['shape']
    moving=shape.startswith('hero') or shape=='reload'
    target=[240*math.sin(u*math.pi),100*math.sin(u*math.pi*2),48] if moving else [0,0,100 if c['family']=='Walkers' else 40]
    hero_yaw=65*math.sin(u*math.pi*2) if moving else 0
    bearing=c['start']+(c['end']-c['start'])*v
    if shape=='hero-follow': bearing+=hero_yaw
    radius=c['radius'];height=c['height']
    if shape in ('pullback','hero-pullback'): radius*=.75+.6*v;height+=80*v
    if shape in ('hero-push','reload'): radius*=1-.15*v
    if shape=='crane':height=60+(height-60)*v
    a=math.radians(bearing)
    camera=[target[0]+radius*math.cos(a),target[1]+radius*math.sin(a),height+target[2]]
    if shape=='rail': camera[1]+=(v-.5)*600
    return dict(t=round(t,4),camera=camera,target=target,yaw=hero_yaw,
                bank=c['bank']*math.sin(math.pi*u)**2,vfov=55-5*math.sin(math.pi*u)**2)

def obstruction_scenario():
    # Corridor wall, in illustrative units. All poses are synthetic and not from
    # a measured Deadlock map. Use exact production proposal code above.
    box=Box((600,-200,-40),(630,200,180),'corridor wall')
    world=BoxWorld([box],1);r=Resolver();frames=[]
    for i in range(601):
        t=i/60;focus=(490*math.sin(math.pi*t/10)**2,0,48)
        desired=(focus[0]+260,0,48)
        f=Frame(t,1,7,focus,desired,(focus,(focus[0],0,72),(focus[0],0,24)))
        result=r.step(f,world,(260,0,48) if i==0 else None)
        frames.append(dict(t=t,target=focus,desired=desired,**asdict(result)))
    failures=[f for f in frames if f['action']!='publish-proposal']
    assert not failures,failures[:1]
    return dict(name='Approach wall, then recover',boxes=[asdict(box)],frames=frames,
                caption='A synthetic corridor: contract before the wall and recover outward after clearance. No game geometry or game calls.')

def build():
    assert len({c['id'] for c in CATALOG})==len(CATALOG)
    shots=[]
    for c in CATALOG:
        n=round(c['duration']*30)
        frames=[path(c,c['duration']*i/n) for i in range(n+1)]
        for f in frames:
            assert all(math.isfinite(x) for k in ('camera','target') for x in f[k])
            assert 0<f['vfov']<179
        shots.append(dict(c,frames=frames))
    data=dict(kind='offline synthetic concept study',game_loadable=False,
              warning='Schematic local anchors, not Deadlock map coordinates or game footage.',
              shots=shots,obstruction=obstruction_scenario())
    (HERE/'shot-catalog.json').write_text(json.dumps(CATALOG,indent=2)+'\n')
    (HERE/'preview-data.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    print(json.dumps({'concepts':len(shots),'synthetic_path_frames':sum(len(c['frames']) for c in shots),
                      'obstruction_frames':len(data['obstruction']['frames']),'game_files_written':False}))
    return data

if __name__=='__main__':build()
