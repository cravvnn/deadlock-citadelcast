# Hyperline interoperability and source independence

Andrew wants CitadelCast and Hyperline to work together fully. Hyperline should
be one supported provider path, not the only source Cast can use or a mandatory
backend for all Cast operation. A proper connector and camera/UI collaboration
are intended; no working Hyperline connector or generic multi-source transport
has been implemented in this repository yet.

Keep shot/cue/presentation logic independent. Scope Hyperline sign-in, grants,
content staging, tunnelling and session lifecycle to its connector. Qualify
camera, data and UI capabilities separately for each session/provider; permission
to receive a stream does not grant server camera control, complete stat history
or automatic UI delivery to every spectator. Existing Watch evidence remains
bounded to its reviewed build and viewer. Other source paths must not inherit
Hyperline-only admission requirements.

## Peer-reported readiness as of 2026-10-24

Christian's owning team reports implementation in Hyperline master `5eb6ac9d1`:
a `spectate` grant and Spectate button on previews of RUNNING lobbies. Hosted
SourceTV is privately tunnelled through the host peer connection for P2P and
dedicated hosts; no public IP/port or broadcast URL is exposed. The previously
considered public/playcast relay route was cancelled. Do not build against an
invented raw target, API, protocol ticket or public broadcast URL.

The latest peer update was posted at 06:46:17 UTC, with body stating as of06:50UTC;
both timestamps are preserved, without resolving the discrepancy. It reports:

| Gate | Reported state |
| --- | --- |
| Intended Cravvnn Steam identity | `spectate`, `ddk` and `quantum` granted with Christian's approval. Spectate applies to every running lobby, until admin revocation; no separate invite required. No Cast capability is inferred from the other grant names. |
| Grant backend | Live on hyperline.gg, confirmed by an owning-team successful grant call. Full deployment commit not supplied. |
| Signed desktop AND host release | Still pending. Current release158/desktop0.2.108 lacks Spectate; desktop0.2.109/release159 is approved to ship and being prepared, not confirmed live. Exact host version not supplied. |
| Rendered first frame | Nobody has seen a frame through this path yet, per peer. |

These are peer reports, not a local source audit, account inspection or live test.
Do not request admin credentials or change grants. Ordinary access does not need
Cast changes. Once the signed desktop/host release is confirmed live and the
desktop is updated, the reported flow is:

1. Be signed in at hyperline.gg with the updated desktop running.
2. Open any RUNNING lobby preview, except a game hosted on that same PC.
3. Press Spectate; the desktop stages content and launches the native spectator view.

The reported internal SourceTV port is gameport+1000, `tv_delay0`,
`tv_transmitall1`. These are implementation details, not values to configure here
or a public destination. Zero configured delay does not prove end-to-end latency
or complete event/stat coverage. A reported bare console-connect probe crashed
a client, possibly from missing mod content; cause is unproven. Use the shipped
content-staging flow for future proof, not a raw console connection.

## Qualification order

Ordinary Spectate access needs the owner's readiness; it must not wait on Cast's
adapter, dev/insecure flags, camera harness, UI or eventual semantic cue contract.
Andrew's separate live-test resume is still required before an agent runs a test.
A signed-release announcement alone does not resume Cast native/UI tests.

First future authorized proof is one standard Spectate press and a native picture,
with session/build/host and content staging recorded. No automatic retry or camera
take. P2P and dedicated need separate evidence. A later optional Cast camera/UI
candidate needs its own supported launch/ownership/logging and compatibility
contract; never attach to or commandeer an unrelated Hyperline-launched client,
bypass the shipped join flow or weaken Cast's native gates.

Remaining collaboration details: live release/host version and first-frame proof;
then supported opt-in observer assets/launch, native HUD coexistence, stable
identity/clocks/event coverage, spectator-only package delivery and cue/reconnect
semantics. Those later questions are not prerequisites for vanilla access.
