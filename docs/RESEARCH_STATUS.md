# Camera and UI research checkpoint

Source checkpoint dated 2026-10-24. Runtime camera/UI tests are PAUSED. Evidence
below separates operator observations, native/static disk findings and synthetic
results; none is a blanket production claim. See [source index](../research/README.md).

Export verification passed: 177 exact source/fixture hashes, 257 core tests,
66 research Python mock/model tests, 14 JavaScript tests and 24 MSVC native fixture
executables. The native fixtures use owned allocations/synthetic inputs, not a
running game. This new source-only test entry point requires no installed game SDK
or Hyperline account; it is not a native adapter deployment qualification.

## Observed camera acceptance

In reviewed build6819 owned dev/insecure Watch viewers, operator observations and
saved adapter readbacks accepted the original 14.125s Walker shot, bank, framing
and immediate freecam return. Original, reverse, bank-sweep and arrival entries
completed at their own durations. The native hero-position correction produced
smooth selected-hero following; native chase and controls resumed. Andrew later
selected **A: turn-with-hero** over **B: hold-bearing**. Use the explicit profile;
the compiled no-suffix legacy default was not changed.

The published accepted source is byte-identical to the A/B candidate. Its historical
DLL SHA256 is `3cc2cbcd2b1e43e4666ae7991e8b58dbb22b8b219d7dd02f2d7379130755b846`;
the binary is not shipped here. These are bounded build/shot observations, not
arbitrary-server compatibility, a general importer, new pixelwise projection
proof or production reliability. Earlier FPS loss, jitter, interruptions and sound
assertions remain real historical failures. No root-cause fix is claimed for all.

## Collision and shot concepts

A separate static diagnostic observed its first positive downward floor-contact
pair: line and sphere8 hits, no start-solid, valid result/context guards, zero
camera writes. Clear-control misses also completed. Wall-labeled samples did not
independently establish a crossing; do not call those proof of a working wall
avoidance solution. Native phase/context checks and a result-decoder correction
are independent of camera motion.

The synthetic obstruction model distinguishes camera volume, travel and hero
visibility, contracts before contact and limits outward recovery while following
ordinary target translation. Completed studies covered 16 concepts, 1,200 geometry
scenes, 601 moving frames, 961 matched A/B samples and adversarial/lens cases.
These are invented geometry and diagrams, not Deadlock maps, footage or a live
collision fix. World/phase lifetime, full filters, camera lens footprint, travel,
rendered visibility and production avoidance remain unqualified/unintegrated.
Native/static layout evidence does not itself supply a safe world lease.

## Panorama UI

Custom recap XML/CSS/JS and a pure rolling120s event model compile/roundtrip/package
in historical local checks. Ten model/controller tests and four static lifecycle
tests are included. Native font/icon resource references are retained; extracted
Valve assets, SDK tools and compiled packages are not distributed here.

The first asset-only live attempt did NOT mount its UI VPK despite the requested
argv. No UI script marker or card render was observed. Exact argv/file existence
is insufficient payload proof. A separate corrected loader requires both actual
current-session filesystem mount evidence and native adapter registration, plus
exact configuration compare/restore. It was built/tested offline but NOT launched;
the pause remains. Its historical configuration hash must never be restored over
a different current configuration. Later peer-reported unrelated mount changes
were not inspected here.

Real stat sources, complete prior120s coverage, head/world projection, occlusion,
engine card rendering and all-spectator content/cue delivery remain unproved.
The proposed recap shows kills, assists and earned souls only with qualified
event/identity/clock coverage. Wallet delta is not earned income. The Billy reload
insert is a useful operator composition idea; no measured reload detector exists.

## Collaboration and next boundaries

Hyperline interoperability is intended while Cast remains independent of an
exclusive provider. See [current readiness](HYPERLINE.md). No generic source
connector or working Hyperline camera integration is claimed. Standard spectator
access does not need the Cast diagnostic package.

Next tests must be bounded to the new connection/UI/collision uncertainty, with
explicit Andrew resume and reviewed ownership/configuration gates. Do not require
repetition of accepted bank/zoom/smooth-follow baselines as though they were unknown.
No automated join, input, attachment, hot replacement or live retry is part of this
checkpoint. Console logging requires actual `-condebug` and strict argv validation
for any future Cast-owned launch. Prefer logs/native records; ask for images when
visual evidence is needed.
