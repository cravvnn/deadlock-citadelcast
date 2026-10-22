"""Explicit simulation fixture. No Windows input, process reads or game access."""
from pathlib import Path
from demo_web import run
from mouse_fixture import FakeMouseEnvironment
from preset_sweep import SweepSession
from preset_web import revision


class FakeSweepEnvironment(FakeMouseEnvironment):
    def send_xy(self, dx, dy):
        if self.fail_send:
            raise ValueError("Fixture rejected input")
        self.moves.append((dx, dy))


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    run(SweepSession(here / "preset-fixture-evidence", FakeSweepEnvironment()),
        info_path=here / "preset-fixture-server.json", open_browser=False,
        page="preset_web.html", app="dolly-live-preset-fixture", source=revision())
