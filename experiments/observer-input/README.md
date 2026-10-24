# Retained Windows observer prototype

This is the former private live-input experiment, extracted into its own source
folder for continued development. It is separate from the default mock desk.
Nothing starts automatically. The previous helper instances were stopped.

`travel_trial.py` and `travel_web.py` implement bounded ordinary Windows input:
forward/vertical movement and relative mouse pan, with process identity,
foreground, countdown, module fingerprint, stall and key-release checks.
The browser's **Connect probe** button runs a read-only client inspection.
Its status shows the checked PID, reviewed build and remaining three-minute
arming window. It does not discover the match ID, observer role or camera pose.
The push/pan controls remain available after inspection and off-air confirmation;
they are not a full Dolly JSON player.
`anchor_web.py` is an offline Dolly free-camera anchor importer and command
preview. It never sends the generated XYZ command to a game.

An operator previously accepted forward travel and sweeps as smooth. Some
mouse-angle movement remained jarring. On 2026-10-22 the operator reported a
successful manually pasted starting-pose command imported from a Dolly project.
The operator later observed a successful manual pose dump through Watch.
Automatic teleport/capture, measured repeatability and a complete Dolly path
have not been demonstrated.

`input_build.py` pins the exact reviewed 6819 client/engine pair. On 2026-10-22,
a narrow disk/Windows-ABI review followed the 6817 gate's correct refusal.
Named camera registrations and angle-callback instruction structure match the
retained 6817 records after address normalization. The bank callback and selected
orientation getters are unchanged; moved external call targets are recorded
separately. A fresh bounded data-flow trace still establishes zero output roll.
Engine, tier0, network and Steam Input manifest bytes are unchanged. This permits
bounded operator-started input trials; no 6819 input-helper motion trial has been observed.
Changed modules remain refused. This review does not qualify native startup;
the separate camera-file experiment below has its own evidence. The test suite
uses fake environments and does not inspect or control the game.

An operator observed `citadel_camera_hero_fov` changing the roaming view, but its
mapping to Dolly's saved framing remains unverified. The lobby bank-command
test was refused. A later Watch connection reported viewer `sv_cheats=false`:
pose readback and pitch commands worked, but the authored sideways-roll command
produced no visible bank without a console rejection. The traced 6817
third-person camera path zeroes its angle getter's roll output. A later, separate
owned dev/insecure trial loaded a reviewed unlocker and connected to Watch with
viewer `sv_cheats=false`. The operator loaded a native camera file through
`camera_cut_to_datadriven_camera` and confirmed left bank followed by a return
to level. Its `CDataDrivenCamera` output differs from the earlier camera path.
Manual clicks/observer cycling recovered freecam; automatic handoff is unverified.
This does not add native access to the normal-input helper, which still rejects
dev/insecure clients. A separate startup candidate implements the original
Walker curves, framing, bank and timing for offline checks against 6819. It is
not connected to this helper. Full rendered JSON playback remains unverified.

Historical console panels and helpers are retained because the input prototype
shares their lifecycle utilities. Their normal-client netconsole route did not
obtain a listener and is not a working fallback. No old launch-option setup is
required by the default offline desk.

Source imports resolve against this repository. The operator's existing game
location is retained in `normal_console_probe.EXE`; it is not discovered or
changed during offline tests. Runtime server identities, evidence logs, anchor
banks and credentials are ignored and were not copied into source.

Run all retained simulation checks from the repository root:

```powershell
& .\.venv\Scripts\python.exe -B tools/test_offline.py
```

Before live testing, verify the reviewed installed pair and normal process,
preserve all gates, and use the operator's explicit off-air confirmation and
countdown. A changed build needs a new narrow review. Do not attach the replay
native backend to a live multiplayer client.
