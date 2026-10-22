"""Loopback-only local operator UI. No game launch or automatic game connection."""
import argparse
import hashlib
import http.client
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import threading
import webbrowser
from urllib.parse import urlparse

from demo_session import Session

HERE = Path(__file__).resolve().parent


def revision():
    digest = hashlib.sha256()
    for name in ("demo_web.py", "demo_web.html", "demo_session.py", "demo_core.py", "normal_console_probe.py"):
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def make_server(session, port=0, *, page="demo_web.html", app="dolly-live-test-2", source=None, actions=None):
    token = secrets.token_urlsafe(32)
    instance = secrets.token_hex(16)
    source = source or revision()
    actions = dict(actions or {})  # Fixed server-owned handlers, never supplied by a browser.

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # No request bodies, credentials, console text or browser data logged.

        def reply(self, code, value, content_type="application/json"):
            blob = value.encode("utf-8") if isinstance(value, str) else json.dumps(value, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(blob)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(blob)

        def valid_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def do_GET(self):
            if not self.valid_host():
                return self.reply(403, {"error": "Local host mismatch"})
            if self.path == "/":
                html = (HERE / page).read_text(encoding="utf-8")
                return self.reply(200, html.replace("__CSRF_TOKEN__", token), "text/html")
            if self.path == "/state":
                return self.reply(200, session.snapshot())
            if self.path == "/health":
                return self.reply(200, {"app": app, "simulated": session.env.simulated,
                                        "instance": instance, "revision": source})
            return self.reply(404, {"error": "Not found"})

        def do_POST(self):
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if (not self.valid_host() or self.headers.get("Origin") != origin or
                    not secrets.compare_digest(self.headers.get("X-Dolly-Token", ""), token)):
                return self.reply(403, {"error": "Local origin or request token mismatch"})
            if self.headers.get_content_type() != "application/json":
                return self.reply(415, {"error": "JSON required"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 4096:
                    raise ValueError("Invalid request length")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object")
                if self.path in actions:
                    return self.reply(200, actions[self.path](data))
                if self.path == "/prepare":
                    if set(data) - {"port"}:
                        raise ValueError("Unexpected setup fields")
                    return self.reply(200, session.prepare(data.get("port", 29090)))
                if self.path in ("/inspect", "/echo", "/pan"):
                    session.start(self.path[1:], data)
                    return self.reply(202, {"accepted": True})
                if self.path in ("/stop", "/quit"):
                    if data:
                        raise ValueError("Unexpected fields")
                    session.stop()
                    self.reply(200, {"stopped": True})
                    if self.path == "/quit":
                        threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                return self.reply(404, {"error": "Unknown action"})
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                # Validation messages are authored locally; don't echo request data.
                message = str(error) if type(error) is ValueError else "Invalid action data"
                return self.reply(400, {"error": message})
            except Exception:
                return self.reply(500, {"error": "Local helper error. Stop and inspect the private logs."})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.instance = instance
    server.source = source
    return server


def run(session, *, info_path, open_browser=True, page="demo_web.html", app="dolly-live-test-2", source=None, actions=None):
    server = make_server(session, page=page, app=app, source=source, actions=actions)
    url = f"http://127.0.0.1:{server.server_port}/"
    info_path.write_text(json.dumps({"url": url, "simulated": session.env.simulated,
                                    "instance": server.instance, "revision": server.source}), encoding="utf-8")
    print(url, flush=True)  # URL contains no credentials or access tokens.
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        session.stop()
        server.server_close()
        if session.worker:
            session.worker.join(timeout=15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    info_path = HERE / "test2-server.json"
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
        target = urlparse(info["url"])
        if target.scheme == "http" and target.hostname == "127.0.0.1" and target.port and target.path == "/":
            connection = http.client.HTTPConnection("127.0.0.1", target.port, timeout=1)
            try:
                connection.request("GET", "/health")
                response = connection.getresponse()
                health = json.loads(response.read(4096))
                if (response.status == 200 and health.get("app") == "dolly-live-test-2" and
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
    run(Session(HERE / "test2-evidence"), info_path=info_path, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
