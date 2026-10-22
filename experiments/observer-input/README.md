# Retained Windows observer prototype

This is the former private live-input experiment, extracted into its own source
folder for continued development. It is separate from the default mock desk.
Nothing starts automatically. The previous helper instances were stopped.

`travel_trial.py` and `travel_web.py` implement bounded ordinary Windows input:
forward/vertical movement and relative mouse pan, with process identity,
foreground, countdown, module fingerprint, stall and key-release checks.
`anchor_web.py` is an offline Dolly free-camera anchor importer and command
preview. It never sends the generated XYZ command to a game.

An operator previously accepted forward travel and sweeps as smooth. Some
mouse-angle movement remained jarring. Automatic teleport, live pose capture
and a complete Dolly path have not been demonstrated.

**Do not run the motion panel yet.** `input_build.py` still pins reviewed build
6812. The last observed installed client was 6813 and was correctly refused.
Extraction is not an update review and changes no compatibility gate. The test
suite uses fake environments and does not inspect or control the game.

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

To continue live testing, first review the installed build, preserve all gates,
and explicitly resume the paused off-air test with the operator. Do not attach
the replay native backend to a live multiplayer client.
