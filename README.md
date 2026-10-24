# Deadlock CitadelCast

Camera controls and broadcast tools for live Deadlock matches.

CitadelCast grew out of Dolly Live. It has its own repository, with shared camera
code and separate research branches for organizer-hosted and Valve-hosted matches.

It is still experimental. The offline desk works, and earlier observer-input
tests produced smooth pushes and sweeps. A working GOTV service and automatic
camera paths are still in development.

The newer native camera, Panorama and obstruction research is now available in
[the source checkpoint](research/README.md), with [current evidence and limits](docs/RESEARCH_STATUS.md),
[collaborator setup](docs/CONTRIBUTING.md) and [Hyperline interoperability](docs/HYPERLINE.md).
Hyperline is one intended provider path; CitadelCast's core remains independent.
Camera/UI live testing is paused as of this checkpoint.

## Current capabilities

| Component | Evidence and current limit |
| --- | --- |
| Offline cue desk and path compiler | Working synthetic simulation; no game connection. Built-in coordinates are invented. |
| Windows observer-input prototype | Earlier operator trials reported smooth forward travel and sweeps; mouse-angle judder remains. The exact 6819 module pair passed a narrow disk/host review for bounded input trials. No 6819 input-helper motion trial has been observed. Changed modules are refused. |
| Dolly JSON position import | Free-camera anchor import and numeric command preview work. The operator reported an initial live XYZ/pitch/yaw relocation and later a successful pose dump in Watch mode. General runtime path import and automatic anchor-command delivery remain unfinished; the separately compiled Walker/library experiment is described below. |
| Organizer-hosted server cameras | Server-side ghost movement and observer handoff have a documented Modlock route. No server adapter or deployment is implemented here. |
| Valve-hosted match cameras | In reviewed build 6819 dev/insecure Watch viewers with `sv_cheats=false`, the operator accepted the original 14.125-second Walker take and three reverse/excerpt library variants, including their pictures and immediate freecam return. Native hero chase and dolly framing steps were also observed. Generic runtime import, custom tracking and production stability remain work in progress. |
| Broadcast fragments | A synthetic relay exercises sequencing, delay and recovery. It is not a Deadlock stream decoder or renderer. |

## Run offline

Python 3.10+ runs the core with the standard library. The retained Windows input
experiment uses Python 3.11+ (`hashlib.file_digest`); 3.12 x64 is recommended for it.
From this repository:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -B -m dolly_live --demo
& .\.venv\Scripts\python.exe -B tools/test_offline.py
```

The demo prints a deterministic terminal walkthrough and exits. Without
`--demo`, the desk is interactive. Neither entry point starts or controls a game.
The test runner includes offline core/path/transport checks and simulated
prototype lifecycle checks; its HTTP and console tests use local fixtures.

See [offline desk usage](docs/DOLLY_LIVE_OFFLINE.md),
[motion compiler](docs/DOLLY_LIVE_HELPER.md), and
[prototype status](experiments/observer-input/README.md).

## Development routes

Shared path, cue, timing and operator code lives on `main`.
`research/hosted-server` explores a provider-controlled server adapter;
`research/valve-hosted` explores normal observers and a separate broadcast viewer.
Both begin at the same extraction baseline. They are research branches, not
working hosting modes. Common fixes belong on `main` so the routes can converge.

The [architecture and milestones](docs/ARCHITECTURE.md) define what each route
still needs to prove. Hosting decisions include regional coverage, latency,
recovery and organizer support as well as camera control.

See [the observer production roadmap](docs/PRODUCTION.md) for follow cameras,
shot libraries, observer tools and the proposed showcase sequence, with observed
behavior kept separate from prepared experiments.

## Independence and attribution

No replay Dolly installation, compiled native DLL, SDK libraries, Steam credentials
or game files are included or required for offline use. Native experiment source
and its upstream license are included in the research checkpoint. A local MIT-licensed snapshot of
Dolly's project model preserves JSON and interpolation behavior. A separate
console utility is retained for historical diagnostics; its presence does not
establish a usable live transport. See [attribution](THIRD_PARTY_NOTICES.md).

This repository was extracted without deleting or modifying the replay checkout
or the earlier Live worktree. Personal diagnostics and research continuity are
kept outside tracked source. No Valve affiliation is implied.
