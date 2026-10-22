"""Simulated mouse-test UI environment. Never constructs or calls SendInput."""
from pathlib import Path
from demo_web import run
from mouse_trial import MouseEnvironment, MouseSession
from mouse_web import revision


class FakeMouseEnvironment(MouseEnvironment):
    simulated = True

    def __init__(self):
        self.moves = []
        self.version = 1
        self.focus = True
        self.fail_send = False
        self.stop_countdown = False
        self.module_error = False

    def inspect(self):
        if self.module_error:
            raise ValueError("Unreviewed fixture module")
        return {"modules": {"client.dll": "synthetic", "engine2.dll": "synthetic"},
                "process": self.identity(), "abi": {"fixture": True}}

    def identity(self):
        return {"pid": 4242, "created": str(self.version), "executable": "synthetic"}

    def active(self, pid):
        return self.focus

    def countdown(self, cancel, note):
        note("SIMULATED countdown. No OS input will be sent.")
        if self.stop_countdown:
            cancel.set()

    def ticks(self, rate, duration):
        return ({"index": i, "elapsed": i / rate, "lateness_ms": 0.}
                for i in range(round(rate * duration) + 1))

    def send(self, dx):
        if self.fail_send:
            raise ValueError("Fixture rejected input")
        self.moves.append(dx)


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    run(MouseSession(here / "mouse-fixture-evidence", FakeMouseEnvironment()),
        info_path=here / "mouse-fixture-server.json", open_browser=False,
        page="mouse_web.html", app="dolly-live-mouse-fixture", source=revision())
