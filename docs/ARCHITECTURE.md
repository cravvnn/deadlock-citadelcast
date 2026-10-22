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
remain separate issues. The retained 6812 module gate needs a narrow update
review before another live test. Keep its current refusal intact meanwhile.

Offline-authored XYZ can supply a desired starting pose without `getpos`, but
actual relocation must be demonstrated. `getpos` was refused in the tested live
lobby. Console command registration alone is not evidence of movement or a
reachable transport; normal-client netconsole flags previously produced no
listener. No current supported absolute-pose interface is established.

Route B: authorized live broadcast -> separate rendering viewer -> local camera
adapter -> producer. Confirm private-match feed availability, access/delay,
entity coverage, viewer launch mode, clocks and camera interface first. An HTTP
relay or SSE entity query alone does not supply that viewer. Some live-URL
broker endpoints spectate a lobby when requested; do not treat them as inert
metadata lookups. No live match endpoint has been called by this project.

## Delivery gates

1. Prove one rendered camera handoff and bounded timed move on the chosen route.
2. Import a real Dolly free-camera shot, set its initial pose and compare repeated
   executions, including framing, endpoint error and visible frame holds.
3. Prove stop/takeover, focus loss, stream loss, reconnect and cleanup behavior.
4. Rehearse the complete observer-to-producer capture and delay workflow.

Synthetic tests prove software contracts. Disk analysis proves named-build
facts. Only observed rendering establishes live motion quality. Keep those
evidence categories distinct in status reports.
