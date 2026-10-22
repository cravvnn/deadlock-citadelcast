"""Offline named camera-position desk. No game launch, pose capture or input."""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse
import webbrowser

from anchors import Anchor, AnchorBank, dolly_keyframe
from demo_web import run

HERE = Path(__file__).resolve().parent
APP = "dolly-live-anchor-authoring"


class AnchorDesk:
    def __init__(self, bank):
        self.bank = bank
        self.env = SimpleNamespace(simulated=False)
        self.worker = None

    def snapshot(self):
        return {"mode": "offline-authoring", "anchors": self.bank.snapshot(),
                "simulated": self.env.simulated, "live_capture": False, "live_teleport": False}

    def stop(self):
        pass  # No worker, connection or input to stop.

    def prepare(self, port):
        raise ValueError("This desk only authors positions; game control is unavailable")

    def start(self, mode, data):
        raise ValueError("This desk only authors positions; game control is unavailable")

    def preview(self, data):
        return Anchor.from_dict(data).display()

    def save(self, data):
        return self.bank.add(Anchor.from_dict(data))

    def import_key(self, data):
        if set(data) != {"format", "version", "key", "name", "map_label"}:
            raise ValueError("Import needs project format/version, one key and position labels")
        return dolly_keyframe({"format": data["format"], "version": data["version"],
                               "keyframes": [data["key"]]}, 0,
                              data["name"], data["map_label"]).display()

    def actions(self):
        return {"/anchors/preview": self.preview, "/anchors/save": self.save,
                "/anchors/import": self.import_key}


def revision():
    digest = hashlib.sha256()
    for name in ("anchors.py", "anchor_web.py", "anchor_web.html", "demo_web.py"):
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    info_path = HERE / "anchor-server.json"
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
        target = urlparse(info["url"])
        if target.scheme == "http" and target.hostname == "127.0.0.1" and target.port and target.path == "/":
            connection = http.client.HTTPConnection("127.0.0.1", target.port, timeout=1)
            try:
                connection.request("GET", "/health")
                response = connection.getresponse()
                health = json.loads(response.read(4096))
                if (response.status == 200 and health.get("app") == APP and
                        health.get("simulated") is False and health.get("instance") == info.get("instance") and
                        health.get("revision") == revision()):
                    if not args.no_browser:
                        webbrowser.open(info["url"])
                    print(info["url"], flush=True)
                    return
            finally:
                connection.close()
    except (OSError, ValueError, KeyError, http.client.HTTPException):
        pass
    desk = AnchorDesk(AnchorBank(HERE / "anchor-data" / "anchors.json"))
    run(desk, info_path=info_path, open_browser=not args.no_browser,
        page="anchor_web.html", app=APP, source=revision(), actions=desk.actions())


if __name__ == "__main__":
    main()
