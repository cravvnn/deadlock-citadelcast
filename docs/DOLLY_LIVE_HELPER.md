# CitadelCast helper: Phase 0

Phase 0 is a source-only offline motion compiler, mock player, rate model and
host-clock probe. **These entry points do not verify live compatibility or
smoothness.** See the root README for the separately tested input prototype and
its stale build gate. Nothing in these entry points sends OS input, opens a console
connection, inspects a process, launches a game or edits game files. The mock desk
retains its separate entry point in this independent repository.

## What the Hz question changes

A helper's timer rate, Windows input delivery, the game's input/movement update,
console command application, renderer and recording all have separate clocks.
Increasing the helper timer does not force the other clocks to run faster or
align their phase. A 240 Hz sender can still produce a 16 Hz camera.

The reviewed pose-command path applies position/angles directly; no supported
duration/easing parameter has been found. Sampling a smooth Dolly curve creates
smooth *numbers*, but the camera can hold each number until the next application.
At a constant 600 units/s, 16 applied poses/s creates 37.5-unit jumps; 120 creates
5-unit jumps. The actual live application rate has not been measured. The old
observer adapter's 4/20 Hz limits are typed-input policy, not measured limits of
the engine or a hypothetical direct console transport.

Held WASD is different: one key-down can feed engine velocity integration until
key-up, without resending the key every frame. That does not establish render-rate
movement or arbitrary rail fidelity. Mouse look is still quantized and consumed
on another clock. Digital movement has limited directions/speeds; emulating a
fractional speed with rapid key pulses can produce judder or alias. Steering
forward by pointing at a path tangent would also discard authored framing, so
the compiler keeps look direction independent and uses strafe/vertical actions.

Windows SendInput inserts events into the input stream. Successful insertion
does not establish that Deadlock consumes them. Relative mouse input can be
affected by pointer settings, and MOVE_NOCOALESCE concerns WM_MOUSEMOVE; it is
not a promise of raw-input delivery or game frame synchronization. See Microsoft's
[SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)
and [MOUSEINPUT](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-mouseinput)
documentation (reviewed 2026-10-17). No system input settings are changed here.

## Generate plans and the rate comparison

From this worktree, with Python 3.10+:

```powershell
python -B -m dolly_live.helper --out analysis/helper-phase0
python -B -m dolly_live.helper --consume-hz 16 --out analysis/helper-phase0-consume16
python -B -m dolly_live.helper --rate 240 --mock-play console --out analysis/helper-phase0-paced
```

`--out` must be a new directory. Output files are JSON data, not runnable game
configs. The default shot is the **SYNTHETIC** bridge exercise with invented
coordinates. No claim is made that those coordinates describe Deadlock geometry.

- `report.json`: 16/30/60/120/240 Hz emission comparisons at explicitly assumed
  consumption/render rates. Contains frame holds, position/angular jumps and
  tracking error. A visually static shot also produces unchanged frames; that
  number alone is not a stutter verdict.
- `console-timeline.json`: monotonic deadlines and one public five-number
  `spec_goto` per sampled pose; exact final deadline and shortest-angle unwrap.
- `input-timeline.json`: hypothetical held actions, cumulative integer mouse
  counts and believed pose. Infeasible input speed is refused and reported;
  console compilation can still be inspected. No real key bindings are inferred.
- `calibration-plan.json`: timestamped input-probe data and an unexecuted off-air
  measurement protocol. Separate trials require separate manual rebases.
- `mock-playback.json`, with `--mock-play`: real host pacing into an in-memory
  trace; still no game access. `--mock-play input` selects the input model.

Use `--library bank.json --shot ID` for a synthetic offline library, or
`--project shot.json` for a Dolly project containing free camera poses. User
project coordinates are marked user-authored, not verified. Helper shots have
2-256 keys starting at zero, 0.1-30 seconds and requested emission rates of
1-500 Hz. Unsupported roll, zoom, attachments, effects and cvar tracks are
refused rather than silently discarded. `--duration` retimes the complete shot.

`--model model.json` accepts `speed`, `yaw_degrees_per_count` and
`pitch_degrees_per_count`. The signs matter. Defaults (600, +0.02, +0.02) are
**illustrative assumptions**, not calibration results. The hypothetical model
assumes forward follows look, horizontal strafe, world-Z vertical movement,
normalized combined directions and instantaneous velocity without inertia or
collision. Even with measured constants, these semantics need validation.

The renderer simulation optimistically consumes the latest state on a fixed
clock: console poses hold; input velocity integrates continuously between
consumption times, with sampled key chords and accumulated mouse counts. No
network/queue delay, jitter, acceleration, prediction or real game rendering is
modeled. Key pulses can vanish when sampled at a lower consumption rate. Neither
input nor console model output is evidence of observed live camera movement.

## Host timer measurement

```powershell
python -B -m dolly_live.helper --clock-probe --rate 120 --duration 3 --out analysis/helper-clock120
python -B -m dolly_live.helper --clock-probe --rate 240 --duration 3 --out analysis/helper-clock240
```

The clock probe uses the same absolute-deadline scheduler as mock playback,
records actual elapsed times/lateness and skips expired ticks. It does not spin,
change global timer settings, measure game application Hz or measure FPS. Run
rates separately; contention changes results. There is no universal 120 Hz
smoothness guarantee.

Mock playback requires arm and explicit simulated manual-rebase confirmation.
Hold, abort, completion, foreground loss, operator override, backwards clock,
output failure and excessive scheduling stalls release all modeled movement
actions. Interrupted shots cannot resume. Small delays select only the latest
due sample, avoiding stale-command bursts. Mouse counts are cumulative so skipped
samples preserve total motion; stalls still abort to avoid large catch-up moves.
These are simulated lifecycle checks, not implemented global hotkeys, OS focus
monitoring, or protection against a real helper process being killed.

## Console command contract for the next experiment

Replace placeholders with measured operator-authored poses; do not paste them
literally:

```text
spec_goto <x> <y> <z> <pitch> <yaw>
spec_setpos <x> <y> <z>
spec_setang <pitch> <yaw>
citadel_observer_roaming_speed <measured-speed>
```

Use the full five-number `spec_goto` to set position and facing together. An
alternative rebase is `spec_setpos` paired with `spec_setang`; these are separate
commands and can apply separately. Never append invented `duration`, `ease` or
`Hz` arguments. Speed is a candidate calibration cvar, not a position rail API;
record its original value before any separately authorized edit and restore it.
The compiler does not emit internal `obs_spec_goto` messages or cheat-gated pose
readback. Static non-cheat flags are not a guarantee that an observer session
will accept a command or that it will be local-only.

## Gate to a real helper build

Phase 0 leaves real SendInput, hotkeys and console transport disconnected until
a supported observer interface is verified. An off-air observation needs a
physical-input baseline, synthetic-input acceptance, movement/rotation calibration,
measured command application cadence, repeatability, takeover and local video
frame inspection. Record observer FPS and capture FPS. A 60 FPS recording cannot
resolve every 120 Hz camera update. Do not infer camera cadence from input logs.

Compare a constant-speed straight move, pan and curved move at identical authored
duration, using manual rebases off-air. Measure holds/jumps, within-shot drift and
endpoint repeatability. No live camera route is selected solely because the
offline model or host timer passes. If console application is uneven/too slow
and calibrated input cannot meet the motion requirement, external interpolation
alone cannot deliver native-equivalent rails; the project needs another supported
camera interface before promising that capability.

## Verification

```powershell
python -B -m unittest discover -s tests -p 'test_live*.py' -q
python -B tools/test_offline.py
```

The first checks the owning offline modules. The second also checks the local
path/transport snapshot and simulated input prototype. Neither tests live compatibility.
