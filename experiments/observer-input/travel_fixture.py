"""Translation browser fixture. No Windows calls or real input."""
from pathlib import Path
from demo_web import run
from preset_fixture import FakeSweepEnvironment
from travel_trial import TravelSession
from travel_web import revision


class FakeTravelEnvironment(FakeSweepEnvironment):
    def __init__(self):
        super().__init__()
        self.key_events = []
        self.keys_down = set()
        self.reject_down = set()
        self.reject_up = set()
        self.manual = set()

    def travel_active(self, pid, held):
        return self.focus and not (self.manual - set(held))

    def key(self, key, down):
        if key in (self.reject_down if down else self.reject_up):
            raise ValueError("Fixture rejected key event")
        self.key_events.append((key, down))
        if down:
            self.keys_down.add(key)
        else:
            self.keys_down.discard(key)


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    run(TravelSession(here / "travel-fixture-evidence", FakeTravelEnvironment()),
        info_path=here / "travel-fixture-server.json", open_browser=False,
        page="travel_web.html", app="dolly-live-travel-fixture", source=revision())
