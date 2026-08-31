"""Board editor HTTP server (stdlib only).

Run from repo root:
  python3 frontend/server.py
  python3 frontend/server.py --state pyrender_UPDATED/replayextractor/state.json --port 8765
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from editor import EditorSession  # noqa: E402

STATIC = os.path.join(_HERE, "static")
session: EditorSession | None = None


def get_session() -> EditorSession:
    global session
    if session is None:
        session = EditorSession()
    return session


class Handler(BaseHTTPRequestHandler):
    server_version = "PolytopiaEditor/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        raw = json.dumps(obj).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def _read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _static(self, rel: str) -> None:
        path = os.path.normpath(os.path.join(STATIC, rel))
        if not path.startswith(STATIC) or not os.path.isfile(path):
            self._json(404, {"error": "not found"})
            return
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            self._send(200, f.read(), ctype)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/" or path == "/index.html":
                self._static("index.html")
            elif path.startswith("/static/"):
                self._static(path[len("/static/") :])
            elif path == "/api/session":
                self._json(200, get_session().snapshot())
            elif path in ("/api/board.jpg", "/api/board.jpeg", "/api/board.png"):
                data, _ = get_session().board_image_and_meta()
                self._send(200, data, "image/jpeg")
            elif path == "/api/board/meta":
                _, meta = get_session().board_image_and_meta()
                self._json(200, meta)
            else:
                self._json(404, {"error": "not found"})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def do_PUT(self):
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            if path == "/api/player":
                get_session().set_player(int(body["player_id"]))
                self._json(200, get_session().snapshot())
            elif path == "/api/modification":
                get_session().set_modification(
                    category=body.get("category"),
                    value=body.get("value"),
                    remove=bool(body.get("remove", False)),
                )
                self._json(200, get_session().snapshot())
            else:
                self._json(404, {"error": "not found"})
        except Exception as e:
            self._json(400, {"error": str(e)})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            if path == "/api/paint":
                result = get_session().apply(int(body["x"]), int(body["y"]))
                self._json(200, result)
            elif path == "/api/reload":
                get_session().reload(body.get("path"))
                self._json(200, get_session().snapshot())
            else:
                self._json(404, {"error": "not found"})
        except Exception as e:
            self._json(400, {"error": str(e)})


def main(argv=None):
    global session
    parser = argparse.ArgumentParser(description="Polytopia board editor server")
    parser.add_argument(
        "--state",
        default=os.path.join(
            _ROOT, "pyrender_UPDATED", "replayextractor", "state.json"
        ),
        help="GameState JSON to edit",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    session = EditorSession(args.state)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Editing {args.state}")
    print(f"Open http://{args.host}:{args.port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
