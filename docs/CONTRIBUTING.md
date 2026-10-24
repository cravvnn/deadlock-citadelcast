# Collaborator setup

Clone `https://github.com/cravvnn/deadlock-citadelcast.git` after accepting the
private-repository invitation. This project is independent of replay Dolly and
does not require Hyperline for offline development.

Python 3.12, Node.js with `node:test`, and Git are sufficient for the source/mock
checks. On Windows, MSVC, CMake and the Windows SDK enable the additional native
test executables. No game or downloaded game binaries are needed for these tests.

```powershell
py -3.12 -m venv .venv
& .venv/Scripts/python.exe -B tools/test_offline.py
& .venv/Scripts/python.exe -B tools/test_research.py
& .venv/Scripts/python.exe -B tools/test_research.py --native
```

See [the research source index](../research/README.md) for source owners, byte
preservation and synthetic previews. The default `dolly_live` desk is still a
simulation; it is separate from the accepted experimental native adapter.

Use feature branches and focused changes. Keep SDKs, game files, extracted art,
credentials, private captures and runtime evidence out of source control. Add
source files to `SOURCE_FILES.txt`. Preserve native cancellation, input-release,
ownership, build pins, archive and exact configuration-restoration guards.
Do not turn an offline pass into a live compatibility claim.

The historical source snapshots are immutable references. Put follow-up work in
a separately named candidate/module and record its provenance; do not silently
rewrite an accepted source/DLL baseline. A build made from copied source is not
the previously accepted binary until its own artifacts and behavior are qualified.

Live camera/UI tests are paused as of this checkpoint. A collaborator invitation
or Hyperline release does not authorize game launches, attachments, server joins,
input, configuration edits or cleanup on Andrew's computer. Resume those only on
Andrew's explicit instruction, within a reviewed bounded test. Any future owned
launch requires `-condebug` in actual arguments and the exact identity validator.

For Hyperline collaboration, see [the connector boundary and readiness](HYPERLINE.md).
Ordinary Hyperline Spectate access follows its own supported flow and does not
require Cast's native test package, dev/insecure flags or custom UI.
