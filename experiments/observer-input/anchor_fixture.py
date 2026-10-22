"""Synthetic offline authoring UI fixture; temporary bank, no game interface."""
from pathlib import Path
import tempfile

from anchors import AnchorBank
from anchor_web import AnchorDesk, revision
from demo_web import run


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as folder:
        desk = AnchorDesk(AnchorBank(Path(folder) / "anchors.json"))
        desk.env.simulated = True
        run(desk, info_path=here / "anchor-fixture-server.json", open_browser=False,
            page="anchor_web.html", app="dolly-live-anchor-fixture", source=revision(),
            actions=desk.actions())
