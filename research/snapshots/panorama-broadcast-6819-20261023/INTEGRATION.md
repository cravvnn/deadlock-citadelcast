# Native observer UI integration and test slate

## Presentation

First insert: player identity, kills, assists and earned souls over an honest
observed window up to120s. Show after the camera settles, stagger/fade future event
details, clear before returning to chase. Suggested 12s cue: camera entry0–1s,
reveal1.2s, card ends8.2s, native camera return12s. These timings are a proposal;
current controller shows only after an explicit settled cue and clears within7s.
Browser replay uses invented times and a shared pure model, not game capture.

Start with a side card because it needs no unproved 3D projection. Above-head is
the next placement candidate: stock in-world text resources exist on disk, but
their callable entity/anchor contract is not qualified. A native head anchor must
use the displayed/interpolated pose and actual current camera, not tick-rate root
position or a guessed model height. Use real panel/UI scale and tested HUD bounds.
Suppress if hidden, occluded, offscreen or overlapping reserved UI. Do not clamp a
label so it appears attached to the wrong player. Prototype anchor checks use a
conservative fixed rectangle only; per-resolution actual HUD measurement remains.

Other short stories, all conditional on verified source data:

| Insert | Useful content | Data needed |
|---|---|---|
| Recent fight |2kills,3assists, confirmed event order | Stable kill/assist IDs and presentation timestamps |
| Economy surge |+3.2k earned souls; later show purchased item icon | Earned-income feed; separate purchases and native item IDs |
| Pressure | Damage to heroes or objective during recent fight | Complete attributed damage events; do not derive from health loss |
| Survival | Low-health escape, damage absorbed, healing | Correct damage/heal/shield semantics and coverage |
| Objective | Walker down / Midboss taken, then team advantage | Team objective events; player participation separately verified |
| Billy reload insert | Shot timed around reload gesture, concise recent recap | Reload animation phase/exit cue; prior operator idea retained, no automatic detector yet |

Avoid a wall of floating numbers. One recap per camera take, three metrics max,
optional one event story later. Use native fonts/icons/team coloring; keep health,
abilities, minimap, kill feed and objective information in their original places.
Localization, long/unicode names, font fallback, UI scaling and accessible motion
settings need engine checks before production. Do not animate fake counters from
zero as though kills happened during the insert.

## Shared spectator goal

Each viewer must have compatible custom content and a verified loading route.
The local Panorama debugger can inspect UI; it does not install layouts or relay
JavaScript to everyone. Do not assume CS tournament HUD mechanisms or CS-specific
entities exist in Deadlock, or that a server connection transfers arbitrary UI.

Separate three responsibilities:

1. Producer forms a versioned semantic recap cue from observed game state.
2. A qualified delivery route carries the cue to eligible spectators.
3. Each local Panorama renderer uses its own viewport, HUD, current target and
   presentation clock. It renders only if camera/target/context match. A spectator
   who chooses another player should not get a head label on the wrong model.

Proposed envelope: schemaVersion, matchEpoch, streamEpoch, cueId, sequence,
playerId, takeId, presentationStart, presentationEnd, observedWindowStart,
observedWindowEnd, per-metric coverage and authoritative values. Absolute wall
time is not the match clock. Account for broadcast delay/rebuffer/reconnect;
late cues expire, duplicates do not replay animation. Identity uses a stable
match+participant key, never display name or reusable entity index alone.
Joining viewers need either an authoritative qualified history snapshot or an
honest partial-history label. A camera cue is not permission to move another
viewer automatically. Director-follow policy is separate and unimplemented.

Organizer-hosted: investigate content distribution plus a supported spectator
message path on a server we control. Valve-hosted: first qualify local installed
observer content; shared distribution requires its own supported route and may
need cooperating clients. No new server adapter, match API, network listener,
shared relay or auto-join has been implemented by this work.

## Next work, in order

1. Qualify current stock-layout decoding and locate an additive, full-screen Watch
   HUD parent with stable lifetime through connection, hero swap and map change.
   Preserve stock source/payload pins and all existing controls. Hideout's earlier
   loading-notice host is not automatically the right parent. No stock host edited
   yet. The VPK intentionally has no auto-loading stock override.
2. Build a separate UI diagnostic startup candidate using reviewed -condebug actual
   argv AND strict identity validator. Preserve accepted camera candidates52/49
   sources and two DLLs. Finish the old closed viewer's exact exit/mount audit
   before one newly requested launch. Do not mount this prototype casually.
3. ONE bounded static-card test: operator Watch/offair; test label/icon/fonts with
   fixture numbers marked SAMPLE. Confirm native HUD and inputs stay intact,
   card can be removed, map/menu transitions leave no orphan. Read logs directly;
   screenshot only for actual visual review. No camera take needed for this step.
4. Read-only stats qualification: find public Panorama/native observer sources for
   kills, assists and earned souls; test identifiers, timing, observer visibility,
   duplicate/reset behavior and coverage against native UI. Do not scrape displayed
   localized labels into authoritative numeric data. No fields/offsets guessed here.
5. Connect the panel to preferred A's existing start/settled/end/cancel lifecycle
   in a separate candidate; reuse existing camera acceptance. This is a new UI
   coexistence/cleanup check, not another bank/zoom/smooth-follow baseline.
6. Qualify the head/world anchor and collision/occlusion handling separately, then
   independently qualify two cooperating spectators with delay/reconnect and
   differing local camera selections. No all-spectator claim from a one-client test.

## What remains unproved

Actual Panorama render, runtime loading API, host lifetime, native stats source,
head/world projection, world occlusion, measured performance and delivery to other
spectators. Native floor-contact proof is unchanged and is not a UI occlusion or
camera collision solution. No production replacement, remote distribution, full
HUD redesign, event detector or new gameplay/camera implementation is claimed.
