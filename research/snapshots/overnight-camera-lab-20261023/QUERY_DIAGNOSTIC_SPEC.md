# Proposed camera-preserving collision diagnostic

Offline specification, 2026-10-23. This is not a compiled adapter, a console
command, an approved startup, or a live qualification result. The accepted
native-position and A/B candidates stay unchanged.

## Question the first diagnostic must answer

Does one fully qualified native shape query describe the same obstruction the
operator sees, at the same world generation and camera phase, without changing
camera ownership or exceeding a small measured cost? A finite fraction alone
does not answer that question.

The diagnostic must retain the current native chase. It may sample the selected
hero, native camera and bounded physics queries; it must publish no pose, switch
no camera, change no lens/HUD/cvar/flags, send no input and perform no match action.
Calling the physics query has engine-internal initialization/profiling effects,
so describe this as camera-preserving, not a pure memory read.

## Prerequisites before any executable candidate

| Requirement | Current evidence | Remaining work |
| --- | --- | --- |
| Exact build, type and call route | Pinned6819 client, native-query-review.json proves8edges into named TraceShape | A new build requires a new review; no automatic pin refresh |
| Query world lifetime | native-lifetime-review.json proves group0set and matching-world shutdown clear | Other teardown/replacement routes, synchronization and eligibility during camera update |
| Shape construction | Native camera builds lens/aspect-scaled footprint | Complete tagged shape layout, extents/transform convention and allocation lifetime |
| Result contract | Start/end copy, fraction and blocking-byte consumer proved | Full initialization/destruction, contact/inside semantics, optional entity pointers and finite checks |
| Filter contract | Named CTraceFilter,0x48deleting-destructor size, base callback returns true | Every used field, contents/layers, target/owner/attachment exclusion and callback rules |
| Lens/projection | Existing accepted framing mapping; native collision footprint is lens-dependent | Measured current nearclip and exact collision footprint relation to rendered frame |
| Thread/order | Native third-person caller route established | Safe callback phase, no reentrant physics update and geometry/hero sampling coherence |
| Visibility | Synthetic physical/visual distinction only | Which walls, glass, cloth, props and effects physical queries actually represent |

Do not substitute a readable pointer for lifetime ownership. A static holder
address does not make its world permanent. The shutdown clear is useful evidence
but does not establish a lock, reference count or epoch for external callers.
The lab's epoch integer is a model contract, not a discovered native field.

## Proposed first bounded observation

1. Start only after a separately reviewed fresh owned viewer is explicitly
   requested. Existing build/artifact/process identity, Watch/viewer-cheatsfalse,
   selected-hero, native-chase, input/focus and cleanup gates remain in force.
2. Operator chooses a stationary simple-wall location off air. The first query
   set is manually requested once, with native camera unchanged throughout.
   No automatic retries, polling loop, target cycling or launch loop.
3. Capture one coherent native sample: take/sample identifier, relative clock,
   selected handle, measured hero root/focus, native camera pose and lens,
   confirmed query world identity and reviewed phase. Avoid persisting raw live
   addresses when a per-session identity token suffices.
4. Execute at most8qualified queries in that sample: radial volume, endpoint
   occupancy, proposed travel, and3subject sightlines, leaving2slots only for
   a defined same-sample control comparison. Queries have distinct physical
   clearance and visibility filter purposes; do not assume one mask fits both.
5. Record raw bounded result fields before interpretation, validity, fraction,
   reviewed inside-state semantics, hit category, query time and total sample
   time. Recheck the lifetime/ownership guard before accepting a result.
6. End immediately. Preserve the native camera and report one compact result
   outside the hot path. Any assertion, inconsistent world, invalid output or
   loss of focus/selection ends the diagnostic; preserve evidence before retry.

The8query count is a proposed ceiling, not a measured safe engine budget. If
field/lifetime qualification cannot support this sample, do not build a
best-guess callback. Avoid repeated slow Windows memory-region queries or log
formatting in the frame loop; the prior performance problem is already known.

## Observations required before camera movement

| Scene | Required observation | What a mismatch means |
| --- | --- | --- |
| Empty space | Clear path, no initial penetration, finite endpoint | ABI/filter/world mismatch; no motion test |
| Simple opaque wall | Volume contacts earlier than point ray by the expected shape allowance | Shape size/transform or collision classification unresolved |
| Wall edge/corner | Endpoints may be clear while travel is blocked | Entry must be rejected; endpoint-only policy is insufficient |
| Camera already touching geometry | Reviewed inside/occupancy signal agrees with picture | Do not guess escape direction or teleport through the obstruction |
| Selected hero and attachments | Hero does not spuriously block its own camera trace; nearby other geometry still does | Exclusion rules wrong or too broad |
| Glass and opaque non-solid prop | Physical clearance and visual occlusion are recorded separately | One filter cannot establish both; unsupported props remain a limitation |
| Moving door/prop | Same-sample query and rendered blockage agree | Physics/render phase mismatch or absent shape |
| Rejoin/level replacement | Queries stop before old world becomes unusable | Lifetime guard is incomplete; no automatic reactivation |

Screenshots/video and telemetry need a common take/sample identifier and a
visible match-clock cue. The earlier A/B videos are not synchronized input
comparisons. Three landmark rays do not establish full silhouette visibility,
and physical shape queries do not automatically model smoke, particles or every
animated surface. Report these limits rather than claiming a general vision API.

## Later performance and movement stages

After the single-sample geometry observations pass, a separately selected short
camera-preserving capture can measure query cost across a bounded frame window.
Report median,95th percentile and maximum query/total callback time plus game
frame pacing, allocations and failures. Compare equivalent native-only context;
synthetic Python runtime and unrelated matches are not FPS evidence.

Only then consider a separate obstruction candidate. It consumes the final
post-entry/post-smoothing desired pose, validates camera volume, prior-to-next
travel and subject framing, and publishes only after all checks. No later
smoothing may move the pose without revalidation. A blocked entry should retain
native chase; loss of a valid view during a take should request native return
once and stop writing. Reacquisition or shoulder changes require a new explicit
policy, not a hidden automatic retry.

Native return should be observed for a bounded window after relinquishing
ownership. Record its convergence and operator controls without continuing to
drive the camera. The older slow-return complaint is not fixed by collision
research and is not explained by the accepted smooth-position result.

## Stop conditions for this offline slate

The useful offline result is a reproducible proof record, a tested independent
proposal model and this diagnostic contract. Missing ABI/thread/visibility
prerequisites remain named work; no live collision support is claimed. Do not
extend this one-night schedule beyond8am or modify accepted candidates to fill
an unproved field.
