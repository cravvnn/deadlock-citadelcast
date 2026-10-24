# Observer production roadmap

CitadelCast's first accepted cinematic test is the original 14.125-second
Walker shot in a reviewed build 6819 Watch viewer. The operator confirmed
movement, sideways bank, zoom and immediate freecam control after playback;
two separate full-duration completion readbacks were retained. This is evidence
for that experiment, not a released general importer or production certification.

## What each control provides

Console variables configure a camera: distance, field of view, framing, target
alignment and HUD visibility. Commands choose a target or view. A timed camera
adapter supplies the path, its clock, roll, framing restoration and operator
handoff. An exposed variable is a candidate until its effect is observed in the
intended view. Removing visibility flags does not remove cheat restrictions.

The earlier Watch readback was spectator distance 250, automatic target view
enabled, hero FOV 90, autodirector disabled and HUD visible. Distance help reports
a client variable with a 10–600 range. After selecting a hero, the operator
confirmed that `spec_dolly_out` enters attached chase. Another out step widened
the view, an in step brought it closer, and following looked smooth. Changing
the distance cvar to 400 had no visible effect in that view. Use the observed
dolly controls for the first chase profile; do not label the cvar a working zoom.

The selected-hero rig now has a positive smooth-motion result and an explicit
operator confirmation that native chase and controls resumed. Earlier trials
had serious FPS loss and stale-position jitter; those failed results remain
part of the research record. The accepted correction samples the current hero
position before composing the view. It does not need mouse-driven aiming.

Two later framing profiles completed: one turns with hero facing, while the
other holds the starting world bearing. Both track position and aim at the
current hero. The operator found them visually similar; the saved traces show
different camera orbits. Andrew subsequently selected A, turn-with-hero, in a later
comparison. Use that explicit profile; the compiled legacy default is unchanged. Walls and
props can still obscure these views. A slow-return complaint from an earlier
take remains unmeasured; a request to return to native chase alone does not
prove how that transition looked. Collision handling, target lifetime and a
production cue button remain to qualify or build.

| Tool | Production use | Current evidence / next step |
| --- | --- | --- |
| Hero selection, player view, chase and fly cam | Follow the action and switch between hero and world context | Attached chase and smooth following positively observed after hero selection and `spec_dolly_out`. Freecam observed. Switching targets/death recovery remain to qualify. |
| Follow profiles | Close action, wider context, operator orbit and automatic target alignment | Native `spec_dolly_out` / `spec_dolly_in` widening/closing observed. Distance cvar 400 had no visible effect. Hero FOV has a positive roaming observation; chase FOV and auto-target comparisons remain unverified. |
| Saved cinematic paths | Establishing shots, objective reveals and transitions | Original Walker accepted. In the fresh four-entry viewer, the reverse pass, bank sweep and short arrival each completed at their own duration; the operator accepted their pictures and immediate freecam return. General runtime import remains to build. |
| Shot preview and cues | Select a known location, check map/build, rehearse, then start off air | Preview and compiled ID selection prepared. A production cue desk, on-air tally and hardware controls remain to build. |
| Stop and operator takeover | Recover control when action moves away | Immediate return positively observed after the original shot. Cancellation has offline checks; live interruption, reconnect and target-loss coverage remain. |
| Clean picture / information picture | Alternate cinematic imagery and readable game context | `citadel_hud_visible` is currently true; hiding and restoring all desired panels needs a visual check. Minimap team-view commands are listed but not qualified. |
| Bookmarks and tactical views | Lane, objective and fight overview positions | Position import and manual relocation observed. A map-specific, versioned bookmark bank remains to author and review. |
| Tracking offsets and composition | Side, high, lead and look-at cameras | Smooth selected-hero motion and native return accepted in a bounded test. Both profiles completed; Andrew later preferred A, turn-with-hero. Walls/props remain visibly problematic; target loss, teleports and production controls remain to qualify. |
| Session health and recovery | Detect stale broadcasts, build mismatch and failed handoff | Build/readiness gates and take diagnostics exist in the experiment. A production stream-health display and recovery rehearsal remain. Camera settings do not repair missing broadcast fragments. |
| Recording and replay | Producer recordings, feature reels, later instant replay | A local capture/edit package is prepared. Instant replay needs its own recording or demo workflow; changing a live camera does not rewind the match. |
| Multiple outputs | Cut between independent observer feeds | A path library selects sequential views in one renderer. Simultaneous pictures require a separate rendering/capture architecture, normally separate observer feeds or machines. No multi-instance deployment is implemented. |
| Suggested or automatic direction | Recommend an active fight or interesting target | Research only. Keep a clear manual override and qualify available received data before event-driven automation. |

## Build order

1. Use the now-observed native hero chase and dolly steps for the first demo.
   Qualify target changes, automatic alignment and chase FOV separately; change
   one setting at a time and restore the measured baseline.
2. Extend the now-tested library: the original remains intact, and all three
   reverse/excerpt variants completed and were accepted in the fresh viewer.
   Next add distinct map-specific authored paths and a general import workflow.
3. Add a shot/hero cue desk with readiness, preview, explicit start, stop and
   current-shot status. Keep the disconnected mock desk separate from runtime.
4. Resolve camera clearance and hero sightlines, then qualify hero switching,
   death/respawn, lost target, teleports, focus loss, stream failure and reconnect.
   Preserve the accepted motion baseline while testing each new behavior.
5. Capture a 60–90 second reel from successful real takes with short labels.
   Show observed features as working; label concepts separately or omit them.

## Next camera studies

The next authored-shot candidates are a short Walker reveal, a higher defense
wide, a lane-opening rollout, a stable Midboss fight overview and a short hero
portrait. Opening shots require the viewer to receive the opening footage;
camera control does not provide live rewind. A Billy reload insert is an
operator-suggested composition idea, with no measured animation trigger yet.
All new map anchors and paths need surveying and off-air visual qualification.

An isolated offline obstruction model now separates camera volume, travel
clearance and hero visibility. It contracts the camera before contact and limits
outward distance recovery without slowing ordinary target translation. Synthetic
fixtures are not a live collision fix: the game's query interface, filters,
scene lifetime, near-plane footprint and rendered obstructions still need review.

## Production architecture

The viewer receives the broadcast, renders one camera and sends that picture to
the producer's capture/switching system. Local camera control is separate from
changing every remote spectator's directed camera. A broadcast connection with
viewer `sv_cheats=false` does not establish the source server's security settings
or approval for deployment.

Valve's Source SDK shows separate fixed/chase shots, a human camera operator,
event-based shot selection, client chase collision and angle interpolation.
These are useful design precedents, not Deadlock interfaces or access to Valve's
servers. [Director source](https://github.com/ValveSoftware/source-sdk-2013/blob/master/src/game/server/hltvdirector.cpp),
[client camera source](https://github.com/ValveSoftware/source-sdk-2013/blob/master/src/game/client/hltvcamera.cpp).

Advancedfx documents saving/loading paths, path preview and editing position,
angles and FOV. Those workflows inform the shot library; HLAE compatibility with
Deadlock is not assumed. [Camera-path documentation](https://doc.hlae.site/commands/AfxHookSource/mirv_campath).

Public cvar dumps help find candidates. The local current-view readback and an
observed effect take precedence over an older default or a name in a list.
[Public Deadlock cvar list](https://github.com/Mikooboy/deadlock-cvar-list/blob/main/cvarlist.md).
