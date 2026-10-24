# Source attribution

This project was extracted from [Deadlock Dolly](https://github.com/cravvnn/deadlock-dolly),
worktree branch `dolly-live`, base commit
`0be18905f2918329c2f8878ae977f6e52cbf1c25`, including the local Live additions
present at extraction. Copyright (c) 2026 Deadlock Dolly contributors.
The MIT permission and warranty text is retained in [LICENSE.txt](LICENSE.txt).

`dolly_live/_vendor/dolly/` contains a snapshot of these MIT Dolly modules:

- `path.py`, with its `particles.py`, `object_model.py` and `object_library.py`
  dependencies, for project validation, persistence and pure interpolation;
- `console.py`, a diagnostic transport used by the retained historical console
  experiment. It is not imported by the default offline camera desk.

The original module contents are retained. The snapshot adds package markers;
consumer imports point to the local snapshot. `UPSTREAM.json` records source
hashes so later format updates can be reviewed deliberately.

The console module documents independently implemented framing informed by
theokyr/CS2RemoteConsole and uilton-oliveira/VConsoleLib.python. No files from
those projects were copied in this extraction.

The native source snapshots under `research/snapshots/` include an independent
test variant derived from [Artemon121/cvar-unhide-s2-citadel v0.5.3](https://github.com/Artemon121/cvar-unhide-s2-citadel/tree/v0.5.3),
including its MIT license (copyright2023 Saul Rennison), plus CitadelCast's
camera/diagnostic additions. The license is retained as `source/LICENSE.md` in
each native snapshot. Original upstream SHA256 values: main.cpp
`01975a77d6d429483481c0cd0f429984e9debbc9af6b9dc829a055592ad3d34f`,
cvars.cpp `d90135bb19e1c5120a0f6c30a5f1bf777cca0d9ccae771e1f21b1e74752e21c9`,
LICENSE.md `68eb8d30b095c4f225d55df7a358de31221013d8dd4d23cc0adb800184c58c5f`.
These identify the original files; modified snapshot hashes are recorded separately.

No Modlock/Freestyle source, game binaries, extracted Valve art/fonts/layouts,
SDK libraries, ReShade or replay vendor binaries are included. Panorama source
references standard installed resources by name; it does not redistribute them.
ValveResourceFormat/Source2Viewer and Valve's resource compiler were used as
external authoring tools and are not bundled. Native adapter builds need a
separately obtained compatible SDK; offline test builds do not use it.
