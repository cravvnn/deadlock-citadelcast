# Camera and broadcast architecture

The product goal is one operator desk with a repeatable shot library, smooth
motion, immediate takeover and predictable recovery. The means of obtaining
camera authority depends on the session. Keep that difference in adapters.

## Shared core (`main`)

`dolly_live` owns offline shot data, validation, cue orchestration, motion plans,
timing models and synthetic broadcast recovery. Its default desk remains a mock.
The isolated `_vendor/dolly` snapshot reads Dolly projects without importing
the replay application. Importing a format never grants a runtime capability.

Future real adapters must explicitly report their supported operations:
absolute pose, pose feedback, timed path, target tracking, lens control,
camera handoff and cancellation. Unsupported operations must be refused.
A telemetry feed is distinct from a rendered picture and camera control.

## Organizer-hosted route (`research/hosted-server`)

Candidate architecture: operator desk -> authenticated server adapter ->
server-controlled ghost/observer target -> ordinary observer rendering client ->
producer capture. Modlock's Watch/Unwatch and movement hooks are the research
starting point, not an installed component of this repository.

The ghost guide describes server authority. An ordinary client cannot add those
server operations to a Valve-hosted lobby. Before implementation, obtain the
actual host integration contract or Freestyle source and establish:

- XYZ/velocity and facing updates, interpolation and final rendered camera pose;
- spectator handoff, disconnect/rejoin, cleanup and operator takeover;
- tick-to-render timing, path fidelity, startup stalls and repeatability;
- supported host/client modes on the chosen installation;
- restart, regional hosting and recovery behavior acceptable to organizers.

Do not infer security/anti-cheat compatibility from the ability to join a server.
No production completion estimate follows from the guide alone.

## Valve-hosted route (`research/valve-hosted`)

Route A: normal observer client plus ordinary input. Earlier manual trials
accepted forward travel and sweeps; angle judder, rebase and endpoint accuracy
remain separate issues. The exact 6819 module pair passed a narrow disk/host
review on 2026-10-22 after the 6817 gate refused the updated client. No 6819
input-helper motion trial has been observed; changed modules still refuse before input.

On 2026-10-22 the operator reported that one manually pasted `spec_goto`
command, imported from a Dolly project's initial XYZ/pitch/yaw, worked in the
normal live observer. This supplies an initial manual relocation observation;
numerical accuracy, repeated takes and automatic command delivery remain
unmeasured. `getpos` was refused in the tested live lobby. Command registration
alone remains insufficient evidence; normal-client netconsole flags previously
produced no listener, and a working automated console transport is not established.

Route B: authorized live broadcast -> separate rendering viewer -> local camera
adapter -> producer. Confirm private-match feed availability, access/delay,
entity coverage, viewer launch mode, clocks and camera interface first. An HTTP
relay or SSE entity query alone does not supply that viewer. Some live-URL
broker endpoints spectate a lobby when requested; do not treat them as inert
metadata lookups. No live match endpoint has been called by this project.

The operator subsequently supplied a Watch-mode console capture showing a
broadcast connection, viewer `sv_cheats=false` and successful pose readback.
Pitch commands worked; the earlier `cl_citadel_forceangles` bank trial produced
no visible roll. The reviewed 6817 third-person camera path zeroes its angle
getter's roll output. This remains a scoped finding about that camera.

A separate owned dev/insecure startup with a reviewed unlocker subsequently
connected to Watch and reported viewer `sv_cheats=false`. The operator loaded
a stationary file using `camera_cut_to_datadriven_camera` and observed a left
bank followed by a return to level. This uses the distinct `CDataDrivenCamera`
orientation path. Freecam was recovered through manual clicks/observer cycling;
automatic handoff was not established. The experiment is separate from the
normal-input helper and is not a delivered camera adapter.

The subsequent reviewed build 6819 viewer completed two distinct original
14.125-second Walker takes. The operator accepted movement, sideways bank,
deliberate zoom/framing and immediate WASD/mouse freecam return. Its evaluator
matches the original model at 4,135 timestamps. This qualifies that shot/build
and operator observation, not pixelwise lens equivalence, a generic importer or
production reliability. The earlier short interrupted take and ambient-sound
assertion remain preserved; their causal relationship is unresolved.

A separate four-entry shot library adds the original, a reverse pass and two
exact excerpts with independent durations. It passed offline curve, lifecycle,
cancellation and startup checks and registered in a fresh owned viewer. The
reverse, bank-sweep and arrival variants subsequently completed their respective
14.125, 7.9375 and 3.078125-second takes. The operator accepted their pictures
and immediate freecam return. This demonstrates sequential shot selection and
independent durations in that reviewed viewer, not simultaneous outputs or a
general runtime importer.
The operator also confirmed native attached hero chase and smooth wider/closer
steps using `spec_dolly_out` / `spec_dolly_in`; the distance cvar400 test had no
visible effect. Custom tracking and failure recovery remain separate work. See
[the production roadmap](PRODUCTION.md).

Build changes still require reviewed camera method/table relocations and exact
module pins. An offline pass does not establish live compatibility, source-server
settings or production readiness.
Server-wide cheats and OBS rotation are outside the selected tournament route.

## Delivery gates

1. Prove one rendered camera handoff and bounded timed move on the chosen route.
2. Import a real Dolly free-camera shot, set its initial pose and compare repeated
   executions, including framing, endpoint error and visible frame holds.
3. Prove stop/takeover, focus loss, stream loss, reconnect and cleanup behavior.
4. Rehearse the complete observer-to-producer capture and delay workflow.

Synthetic tests prove software contracts. Disk analysis proves named-build
facts. Only observed rendering establishes live motion quality. Keep those
evidence categories distinct in status reports.
