"""Local Test3 UI for the user-started finite mouse trial. Never starts a game."""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
from urllib.parse import urlparse
import webbrowser

from demo_web import run
from mouse_trial import MouseSession

HERE = Path(__file__).resolve().parent


def revision():
    digest = hashlib.sha256()
    for name in ("mouse_trial.py", "mouse_web.py", "mouse_web.html", "demo_web.py",
                 "demo_core.py", "normal_console_probe.py"):
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    info_path = HERE / "mouse-test3-server.json"
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
        target = urlparse(info["url"])
        if target.scheme == "http" and target.hostname == "127.0.0.1" and target.port and target.path == "/":
            connection = http.client.HTTPConnection("127.0.0.1", target.port, timeout=1)
            try:
                connection.request("GET", "/health")
                response = connection.getresponse()
                health = json.loads(response.read(4096))
                if (response.status == 200 and health.get("app") == "dolly-live-mouse-test3" and
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
    run(MouseSession(HERE / "mouse-test3-evidence"), info_path=info_path,
        open_browser=not args.no_browser, page="mouse_web.html", app="dolly-live-mouse-test3", source=revision())


if __name__ == "__main__":
    main()
