"""Offline camera-clearance experiment. No game bindings or process access.

The AABB world is an analytic fixture, not a Deadlock map. A camera uses an
axis-aligned box as a conservative proxy; live near-plane coverage is unproved.
The controller returns a proposal or a native-return decision, never executes it.
"""
from dataclasses import dataclass
import math
from typing import Protocol

Vec = tuple[float, float, float]

def finite(v): return len(v) == 3 and all(math.isfinite(x) and abs(x) < 1e7 for x in v)
def add(a, b): return tuple(x+y for x, y in zip(a,b))
def sub(a, b): return tuple(x-y for x, y in zip(a,b))
def scale(a, k): return tuple(x*k for x in a)
def length(a): return math.sqrt(sum(x*x for x in a))
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])

def near_plane_radius(near, vertical_fov_degrees, aspect):
    """Conservative rotation-independent eye-centered envelope, in scene units.

    Requires a measured vertical FOV, aspect and near clip. None is read from the
    game here. A live mapping must account for the camera's lens convention.
    """
    if not all(math.isfinite(v) for v in (near,vertical_fov_degrees,aspect)) or not (
        near > 0 and 0 < vertical_fov_degrees < 179 and aspect > 0):
        raise ValueError("invalid projection")
    half_height=near*math.tan(math.radians(vertical_fov_degrees)/2)
    return math.sqrt(near*near+half_height*half_height*(1+aspect*aspect))

@dataclass(frozen=True)
class Box:
    low: Vec
    high: Vec
    name: str = "wall"
    solid: bool = True
    occludes: bool = True
    def __post_init__(self):
        if not finite(self.low) or not finite(self.high) or any(a >= b for a,b in zip(self.low,self.high)):
            raise ValueError("invalid obstacle")

@dataclass(frozen=True)
class Hit:
    valid: bool
    fraction: float = 1.0
    start_solid: bool = False
    obstacle: str = ""

class Query(Protocol):
    epoch: int
    def sweep(self, start: Vec, end: Vec, extent: float, purpose: str = "clearance") -> Hit: ...

class BoxWorld:
    def __init__(self, boxes=(), epoch=0): self.boxes, self.epoch = tuple(boxes), epoch
    def sweep(self, start, end, extent, purpose="clearance"):
        if not finite(start) or not finite(end) or not math.isfinite(extent) or extent < 0 or purpose not in ("clearance","visibility"):
            return Hit(False)
        best = Hit(True)
        for box in self.boxes:
            if (purpose == "clearance" and not box.solid) or (purpose == "visibility" and not box.occludes):
                continue
            lo = tuple(v-extent for v in box.low)
            hi = tuple(v+extent for v in box.high)
            if all(a <= x <= b for x,a,b in zip(start,lo,hi)):
                return Hit(True,0.0,True,box.name)
            enter, leave = 0.0, 1.0
            for x,d,a,b in zip(start,sub(end,start),lo,hi):
                if abs(d) < 1e-12:
                    if x < a or x > b: enter, leave = 1.0,0.0; break
                else:
                    near, far = sorted(((a-x)/d,(b-x)/d))
                    enter, leave = max(enter,near), min(leave,far)
                    if enter > leave: break
            if enter <= leave and 0 <= enter <= best.fraction:
                best = Hit(True,enter,False,box.name)
        return best

@dataclass(frozen=True)
class Projection:
    vertical_fov_degrees: float
    aspect: float
    near: float
    edge_margin: float = 0.05

    def valid(self):
        return all(math.isfinite(v) for v in (self.vertical_fov_degrees,self.aspect,self.near,self.edge_margin)) and (
            0 < self.vertical_fov_degrees < 179 and self.aspect > 0 and self.near > 0 and 0 <= self.edge_margin < 1)

def subjects_in_frame(camera,focus,landmarks,projection,bank):
    """Synthetic pinhole/framing check, separate from geometric visibility."""
    if not projection.valid() or not math.isfinite(bank): return False
    forward=sub(focus,camera);distance=length(forward)
    if distance <= projection.near: return False
    forward=scale(forward,1/distance)
    right=cross(forward,(0,0,1));right_length=length(right)
    if right_length < 1e-8: return False
    right=scale(right,1/right_length);up=cross(right,forward)
    angle=math.radians(bank)
    rolled_right=add(scale(right,math.cos(angle)),scale(up,math.sin(angle)))
    rolled_up=add(scale(up,math.cos(angle)),scale(right,-math.sin(angle)))
    slope=math.tan(math.radians(projection.vertical_fov_degrees)/2)*(1-projection.edge_margin)
    for point in landmarks:
        delta=sub(point,camera);depth=dot(delta,forward)
        if depth <= projection.near or abs(dot(delta,rolled_right)) > depth*slope*projection.aspect or abs(dot(delta,rolled_up)) > depth*slope:
            return False
    return True

@dataclass(frozen=True)
class Frame:
    time: float
    epoch: int
    target: int
    focus: Vec
    desired: Vec
    landmarks: tuple[Vec, ...]
    allowed: bool = True
    projection: Projection | None = None
    bank: float = 0.0

@dataclass(frozen=True)
class Config:
    half_extent: float = 8.0
    skin: float = 2.0
    minimum_distance: float = 64.0
    recover_speed: float = 120.0
    clear_hold: float = 0.15
    maximum_gap: float = 0.25
    maximum_target_step: float = 512.0
    query_budget: int = 24

@dataclass(frozen=True)
class Decision:
    action: str
    reason: str
    camera: Vec | None
    distance: float | None
    queries: int

class Refused(Exception): pass

class Resolver:
    """Contract inward immediately; recover outward slowly after a clear hold.

    Always check final camera volume, travel segment and all supplied landmarks.
    No side switching, tunnelling through obstacles or holding stale target poses.
    A failed frame latches stopped; the caller must explicitly create a new rig.
    Input desired position is AFTER entry/rig smoothing. Never smooth the output
    again without repeating the clearance checks.
    """
    def __init__(self, config=Config()):
        values=(config.half_extent,config.skin,config.minimum_distance,
                config.recover_speed,config.clear_hold,config.maximum_gap,config.maximum_target_step)
        if any(not math.isfinite(v) or v <= 0 for v in values) or config.query_budget < 1:
            raise ValueError("invalid camera limits")
        self.config=config
        self.previous=None
        self.last=None
        self.distance=None
        self.clear_since=None
        self.stopped=False
        self.count=0

    def stop(self, reason):
        self.stopped=True
        return Decision("return-native",reason,None,None,self.count)

    def step(self, f: Frame, world: Query, initial_camera: Vec | None = None):
        self.count=0
        if self.stopped: return self.stop("already stopped")
        c=self.config
        if (not f.allowed or f.target <= 0 or not math.isfinite(f.time) or
            not finite(f.focus) or not finite(f.desired) or not f.landmarks or
            not all(finite(p) for p in f.landmarks) or not math.isfinite(f.bank)):
            return self.stop("invalid target, input or ownership")
        if f.projection is not None and not f.projection.valid():
            return self.stop("invalid projection")
        extent=c.half_extent if f.projection is None else max(c.half_extent,
            near_plane_radius(f.projection.near,f.projection.vertical_fov_degrees,f.projection.aspect))
        if self.last:
            dt=f.time-self.last.time
            if f.target != self.last.target: return self.stop("selected target changed")
            if not 0 < dt <= c.maximum_gap: return self.stop("clock discontinuity")
            if length(sub(f.focus,self.last.focus)) > c.maximum_target_step:
                return self.stop("target discontinuity")
        else:
            dt=0.0
            if initial_camera is None or not finite(initial_camera):
                return self.stop("missing native entry pose")
            self.previous=initial_camera

        def query(a,b,extent,purpose="clearance"):
            if world.epoch != f.epoch: raise Refused("stale world query")
            if self.count >= c.query_budget: raise Refused("query budget exhausted")
            self.count+=1
            h=world.sweep(a,b,extent,purpose)
            if world.epoch != f.epoch: raise Refused("world changed during query")
            if not h.valid or not math.isfinite(h.fraction) or not 0 <= h.fraction <= 1:
                raise Refused("invalid world query")
            return h

        def clear(a,b,extent,purpose="clearance"):
            h=query(a,b,extent,purpose)
            return not h.start_solid and h.fraction >= 1.0 and not h.obstacle

        try:
            delta=sub(f.desired,f.focus); desired_distance=length(delta)
            if desired_distance < c.minimum_distance: raise Refused("framing radius too small")
            direction=scale(delta,1/desired_distance)
            radial=query(f.focus,f.desired,extent)
            if radial.start_solid: raise Refused("target pivot inside obstacle proxy")
            allowed_distance=desired_distance
            blocked=bool(radial.obstacle) or radial.fraction < 1
            if blocked:
                allowed_distance=max(0,desired_distance*radial.fraction-c.skin)
            if allowed_distance < c.minimum_distance: raise Refused("no usable camera distance")

            # Rate-limit ONLY the obstruction-induced radius, not target
            # translation. Recomputing radius from yesterday's camera and today's
            # hero would incorrectly cap ordinary tracking at recover_speed.
            previous_distance=self.distance if self.last else length(sub(self.previous,f.focus))
            if allowed_distance <= previous_distance+1e-6:
                self.clear_since=None
            elif self.clear_since is None:
                self.clear_since=f.time
            if allowed_distance > previous_distance:
                ready=self.clear_since is not None and f.time-self.clear_since >= c.clear_hold
                allowed_distance=min(allowed_distance,previous_distance+(c.recover_speed*dt if ready else 0))
            if allowed_distance < c.minimum_distance: raise Refused("entry radius too small")
            camera=add(f.focus,scale(direction,allowed_distance))
            if not clear(camera,camera,extent): raise Refused("camera volume occupied")
            if not clear(self.previous,camera,extent): raise Refused("camera travel blocked")
            for point in f.landmarks:
                if not clear(camera,point,0,"visibility"): raise Refused("hero sightline blocked")
            if f.projection is not None and not subjects_in_frame(camera,f.focus,f.landmarks,f.projection,f.bank):
                raise Refused("hero leaves frame")
            self.previous=camera; self.last=f; self.distance=allowed_distance
            return Decision("publish-proposal","contracted" if blocked else
                            "recovering" if allowed_distance < desired_distance-1e-6 else "clear",
                            camera,allowed_distance,self.count)
        except Refused as exc:
            return self.stop(str(exc))
