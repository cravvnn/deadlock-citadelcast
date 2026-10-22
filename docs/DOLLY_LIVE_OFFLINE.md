# Deadlock Dolly Live — offline camera desk

This prototype is a **terminal operator interface** with an in-memory camera and
two synthetic characters. It never connects to Deadlock, Steam, netcon, a native
bridge or a running game process. It opens no windows and requires no GPU.
This desk is now maintained in the independent `deadlock-live` repository.
See the root README for the separate input prototype and current project status.

The separate [Phase 0 helper](DOLLY_LIVE_HELPER.md) now compiles offline console
trajectories and hypothetical input traces, compares consumption/render clocks,
and measures host scheduling. It does not enable live control. The observer
contract below retains its older pinned layout and typed-command rate policy;
those rates are not measured engine throughput limits.

All built-in shots are **SYNTHETIC**: their coordinates are made up, not real
Walker, bridge or mid-boss locations. The text preview has no map geometry,
collision detection, visibility checks or game rendering. This proves camera
orchestration only. Live spectator compatibility remains unverified.

## Run in an existing terminal

Python 3.10+; no additional packages needed for the offline desk.

```powershell
python -m dolly_live --demo
```

`--demo` prints a deterministic walkthrough and exits. To operate the desk:

```powershell
python -m dolly_live
```

Use this separate module. `python -m dolly`, `Dolly.exe` and the existing replay
launch scripts still belong to replay Dolly.

## First shot

Enter these at the `offline>` prompt, one per line:

```text
presets
cue walker 6
run
step 2
view
hold
step 1
status
release
cue hero-follow 10 hero-b
run
step 2
view
cancel
quit
```

Time advances **only** with `step`; waiting at the prompt changes nothing.
Each step accepts 0–30 seconds and samples at 60 simulation updates/second,
without sleeping or rendering. This is not a measured 60 FPS game adapter.
`cue` validates and snapshots a shot without moving the camera. `run` positions
the mock camera at the starting key immediately; treat it as an off-air setup,
not a smooth transition from the previous camera. There is no switcher/tally
connection or automatic on-air protection.

`hold` freezes the last camera pose and shot progress. Actors continue to move
when you step. At a shot's end, the final camera pose is held automatically.
`release` and `cancel` release mock ownership immediately. To start another shot,
release, cue and run again. There is deliberately no automatic resume.

## Shot bank and character tracking

| ID | Synthetic exercise | Default duration |
| --- | --- | --- |
| `walker` | Blue-lane top-Walker sweep | 6 s |
| `mid-boss` | Mid-boss reveal | 4 s |
| `bridge` | Bridge-buff sweep | 4 s |
| `rollout` | Opening rollout rail | 6 s |
| `hero-pan` | Fixed world-space rail, looking at moving actor | 4 s |
| `hero-follow` | Moving actor with a constant world-axis camera offset | 2 s |

`cue ID [SECONDS] [TARGET]` overrides duration and, for tracking shots, chooses
`hero-a` or `hero-b`. It does not edit the saved preset. Follow offsets do not
rotate with character aim or animation. Tracking uses exact synthetic samples;
there is no prediction, smoothing, bone attachment or live roster lookup.
Angles use Z-up, pitch positive downward and yaw from +X toward +Y.

`view` prints an auto-scaled top-down plot: C is the last camera pose, A/B are
actors, dots are the last 512 applied poses, and + marks authored keys. Follow
keys are offsets, so that mode's + marks are not absolute camera locations.
The status shows whether the displayed last pose is currently owned or released.

## Save and author presets

```text
save "my-synthetic-shots.json"
load "my-synthetic-shots.json"
```

Save refuses to overwrite an existing file. Choose a new filename for each
revision. Edit exported JSON in your editor to author paths, then load it while
released. Loading validates the complete bank before replacing the current one.
Malformed libraries leave the previous bank intact.

The version-1 format contains `format: "deadlock-dolly-live-offline"`, `version: 1`
and a `presets` array. Each preset has `id`, `name`, `landmark`, `side`,
`map_revision`, `synthetic`, `mode`, `target`, `interpolation` and `keys`.
Keep `synthetic: true` and `map_revision: "synthetic-stage-v1"`. Those are enforced,
not optional labels. Every key needs `time`, `x`, `y`, `z`, `pitch`, `yaw`, `roll`.
Use 2–256 increasing keys, beginning at zero, total duration 0.1–120 seconds.
`interpolation` is `smooth` (Dolly's existing path math) or `linear`.
Modes are `rail` (target null), `look-at` and `follow` (named synthetic target).
Banks allow 1–128 unique IDs and at most 1 MiB. Console commands, CVAR tracks,
native attachments and replay timing are not part of this format.

## Fault exercises

During a running tracking shot:

```text
target hero-a freeze
step 1
```

Data older than 0.25 simulation seconds causes a fault and releases the camera.
`target hero-a lose` simulates disappearance; `target hero-a restore` creates a
new identity. A changed identity requires a fresh cue. `disconnect`, `reconnect`
and `map wrong-map` simulate transport/map changes. Restore with
`map synthetic-stage-v1`. Reconnection never resumes an old shot. Held and
prepared shots also validate connection, map and target state.

## Scripted use and verification

Put commands in a UTF-8 text file, one per line. Blank lines and lines beginning
with `#` are ignored. This is a command interpreter, not a shell:

```powershell
python -m dolly_live --script commands.txt
python -B tools/test_offline.py
```

Script errors or camera faults stop the script with a nonzero exit code. EOF,
quit and Ctrl+C release the mock camera. The standalone test command checks
the core, vendored path/transport contracts and simulated observer prototype.
There are no replay launch, native DLL or real game tests in that command.

No binaries were packaged, no game tests performed and no live interface enabled
for this milestone. Future live work requires verified spectator controls for
position/orientation, permission-compatible access and target telemetry.
Twitch's downstream stream delay is not part of this simulation clock.

## Synthetic broadcast fixture

`dolly_live/broadcast.py` models the read side of a community Source 2 HLTV
relay without any network. An in-memory synthetic relay publishes numbered
fragments (start frame, full snapshot, delta update) behind a fixed fragment
delay; a consumer applies them with strict continuity, duplication, reconnect
and map/protocol checks. Missing, reordered or tampered fragments fault the
consumer, nothing is extrapolated, and a fresh session is required after any
interruption. The consumer accepts only the synthetic relay type, so it cannot
be pointed at a real relay or feed. This proves sequencing logic only: it is not
the real protocol and carries no match data, coordinates or telemetry.

```powershell
python -B -m unittest discover -s tests -p "test_live_broadcast.py" -q
python -B tools/broadcast_soak.py --iterations 20000 --seed 1
python -B tools/broadcast_soak.py --iterations 100000000 --seed 1
```

The soak is deterministic for a seed, in-memory, writes nothing and exits
nonzero if an invariant breaks. Run the large iteration count unattended when a
long offline check is useful; it is not a substitute for real-feed validation.

## Historical observer camera contract (offline)

`dolly_live/observer.py` encodes one older reviewed camera setter,
read out of a specific `client.dll` by offline static analysis. It launches no
game, attaches to no process and opens no socket. It produces gate decisions and
console command **text**.

Historical reviewed module, not the currently installed client:

    citadel/bin/win64/client.dll
    sha256 948260612c9b7243964e4a0d5f0f6252ae846ceaa6e8c0e95b83bd5eba4caf60
    58293912 bytes

Any other build invalidates every address in `LAYOUT` and must be re-verified.
The method and raw decompilations remain in the original worktree's private
analysis archive and are not part of this source release.

What the RE established, in short:

- The observer camera is a `CCitadel_ThirdPersonCamera` behind an `ICamera`
  interface. Per frame it hard-copies desired angles onto applied angles,
  clamps pitch to +/-89 degrees, adds camera *wobble* noise, then publishes and
  quantizes. **This setter snaps its absolute pose; it does not provide timed easing.**
- Replay Dolly supplies interpolation separately. This project's local pure
  model is `dolly_live/_vendor/dolly/path.py`; no replay/native engine is present.
- The commands `spec_goto`, `spec_setpos` and `spec_setang` are **not**
  cheat-gated: they register with flags `0x80000`, while the cheat bit is
  `0x4000` (which is what `cam_command`, `camortho` and `cam_showangles` use).
- Two argument rules matter and are enforced by the command builders:
  `spec_setang` needs exactly two numbers, and `spec_goto` only forwards
  pitch/yaw when given five. With three numbers it deliberately re-sends the
  angles it read, which is why a bind can appear to "ignore the angle".
- The roaming observer state exists only for **player slot 0**, and observer
  writes are refused outright while a replay or demo is playing.

`ConsoleObserverAdapter` turns an authored shot into per-frame command text with
the same arm/run/held/fault discipline as the offline runner. Any gate failure
releases ownership and requires a fresh arm; there is no auto-resume.

    >>> from dolly_live.observer import ConsoleObserverAdapter, Gates
    >>> from dolly_live.presets import defaults
    >>> gates = Gates(observer_attached=True, slot=0, replay_playing=False,
    ...               pawn_gate_0x290=True, pawn_gate_0x298=True)
    >>> adapter = ConsoleObserverAdapter(rate_hz=4)
    >>> adapter.arm(defaults().get("mid-boss").project, 3.0)
    'ready'
    >>> adapter.step(gates).commands
    ('spec_setpos -60.00 -100.00 90.00', 'spec_setang 30.00 60.00')

Two limits are stated rather than papered over:

1. **The console path is for framing, not smooth rails.** Typed commands are
   input-rate bound, so `rate_hz` is capped at 20 and warned above 4.
   `console_rate_warning()` says so in as many words.
2. **There is no in-process backend.** `native_backend()` exists only to raise
   `NativeBackendRefused`, so that anyone reaching for render-rate motion gets a
   named error instead of silently degrading to the console path and believing
   they got smooth rails.

## Draft release description (not published)

**0.1.0-offline**
- **Practice camera cues offline.** *Before:* Camera operation depended on a replay session. *After:* A separate terminal desk rehearses camera shots with synthetic actors.
- **Reusable shot library.** *Before:* There was no dedicated live-desk preset bank. *After:* Save and load clearly labeled synthetic sweeps and character-tracking shots.
- **Predictable operator control.** *Before:* Live-desk interruption behavior was untested. *After:* Hold, cancel and simulated failures have tested camera-release behavior.
