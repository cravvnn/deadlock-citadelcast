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

No Modlock or Freestyle source, game binaries/assets, unlocker, ReShade, native
bridge or other replay vendor libraries are included in tracked source.
Local research copies of externally supplied material are excluded from Git.
