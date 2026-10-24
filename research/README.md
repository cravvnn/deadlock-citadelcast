# Source checkpoint and offline research

This directory brings the current camera, collision, Panorama and synthetic
research out of ignored local labs so collaborators can inspect and test it.
It contains source and numeric/synthetic fixtures, not game executables, SDK
libraries, extracted Valve art/fonts/layouts, raw session logs or credentials.

Start with [current status](../docs/RESEARCH_STATUS.md),
[Hyperline interoperability](../docs/HYPERLINE.md), and
[collaborator setup](../docs/CONTRIBUTING.md).

| Snapshot | What is included |
| --- | --- |
| `hero-framing-ab-6819-20261023` | Exact accepted native camera source, 19 owning test programs, original/reverse/excerpt carriers and numeric references. Preferred hero A turns with the hero. |
| `native-floor-control-6819-20261023` | Exact separate static line/sphere diagnostic source, checked result decoder, phase/floor fixtures. Not integrated collision avoidance. |
| `camera-condebug-6819-20261023` | Owned-startup source and mock tests with required exact `-condebug` arguments. |
| `panorama-static-mount-6819-20261023` | Corrected mount/rollback/log/archive source and mock tests; historical pinned configuration, not a current launch recipe. |
| `panorama-broadcast-6819-20261023` | Custom recap XML/CSS/JS, pure recent-event model, Node tests and offline authoring tools. |
| `panorama-static-watch-6819-20261023` | Authored additive-host generator, bounded static UI controller and tests; native host input is deliberately not included. |
| `overnight-camera-lab-20261023` | 16 shot concepts, independent obstruction model/tests, adversarial fixture generator and standalone synthetic HTML previews. |
| `collision-query-6819-20261023` | Earlier independent query-contract/layout source and probes. |

Snapshots are byte-preserved with `.gitattributes` and
`SNAPSHOT_MANIFEST.json`. `SOURCE_PROVENANCE.json` identifies accepted source
hashes and historical DLL hashes without shipping those binaries. Originals in
ignored local labs remain unchanged. The snapshot tools retain historical local
paths and lab assumptions; they are source evidence, not a generic installed SDK.
Use the maintained runner below, not the historical snapshot CMake entry points.

```powershell
python -B tools/test_offline.py
python -B tools/test_research.py
# Windows + MSVC/CMake/Windows SDK; builds test executables only:
python -B tools/test_research.py --native
```

The tests use mocks, owned allocations or synthetic scenes. No game installation,
Valve SDK, Hyperline account or live server is required. MSVC/Windows SDK are
required for the additional native Windows fixtures. Native DLL builds would
require a separately obtained compatible SDK and a separately reviewed build and
startup package; this checkpoint does not provide a one-click deployment.

The archived `startup_trial.py`, capture and cleanup tools are intentionally
incomplete as deployable packages: binaries, candidate deployment manifests,
session identities and installed configuration snapshots are excluded. Do not
run their live entry points or supply missing pieces from stale sessions.
Actual owned launches require explicit authorization, fresh build/artifact/config
qualification, exact ownership and `-condebug`, successful prior-exit audit, and
current configuration preservation. Runtime tests are currently paused.

Standalone prototypes (synthetic diagrams, not game footage):

- [Shot concepts and obstruction study](snapshots/overnight-camera-lab-20261023/camera-study.html)
- [Matched hero A/B inputs](snapshots/overnight-camera-lab-20261023/matched-ab.html)
- [Obstruction adversarial cases](snapshots/overnight-camera-lab-20261023/obstruction-cases.html)

Open the HTML files locally after cloning; GitHub's source view does not execute
them. Panorama resource compilation and historical roundtrips are documented
evidence, not a current engine render or spectator-wide UI installation.
