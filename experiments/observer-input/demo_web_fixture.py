"""Explicitly simulated browser fixture. No game/process/OS-input inspection."""
from pathlib import Path
from demo_session import Environment, Session
from demo_web import run


class FixtureConsole:
    def __init__(self, accepted=True):
        self.accepted = accepted
        self.commands = []
        self.closed = False

    def send(self, command):
        if self.closed:
            raise ValueError("Fixture console closed")
        self.commands.append(command)

    def request(self, command, timeout):
        self.commands.append(command)
        return command[5:] if self.accepted else command

    def close(self):
        self.closed = True


class FixtureEnvironment(Environment):
    simulated = True

    def __init__(self):
        self.clients = []
        self.identity_version = 1
        self.allow_auth = True
        self.allow_focus = True
        self.module_error = False
        self.cancel_countdown = False

    def generate_password(self):
        return "DEMO_FIXTURE_NOT_A_PASSWORD"

    def modules(self):
        if self.module_error:
            raise ValueError("Unreviewed fixture module")
        return {"client.dll": "synthetic-fixture", "engine2.dll": "synthetic-fixture"}

    def pids(self):
        return [4242]

    def identity(self, pid, port, password):
        return {"pid": pid, "created": str(self.identity_version),
                "listeners": {"LocalAddress": "127.0.0.1", "LocalPort": port}}

    def connect(self, port):
        client = FixtureConsole(self.allow_auth)
        self.clients.append(client)
        return client

    def active(self, pid):
        return self.allow_focus

    def countdown(self, cancel, note):
        note("SIMULATED countdown; no real game camera.")
        if self.cancel_countdown:
            cancel.set()

    def ticks(self, rate, duration):
        return ({"index": i, "elapsed": i / rate, "lateness_ms": 0.}
                for i in range(round(rate * duration) + 1))


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    run(Session(here / "test2-fixture-evidence", FixtureEnvironment()),
        info_path=here / "test2-fixture-server.json", open_browser=False)
