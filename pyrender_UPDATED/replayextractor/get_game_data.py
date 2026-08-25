#!/usr/bin/env python3
"""Fetch a finished Polytopia game's GameState blob from a share link.

Uses the local jwtToken (see get_jwt.py) and POSTs to
``api/game/get_game_view_model``. Writes JSON containing metadata plus the
server's ``currentGameStateData`` (finished board) as base64.

The binary GameState is the same payload ``ClientBase.OpenSession`` loads.
Convert it with ``deserialize_gamestate.py``.

Usage
-----
    python3 get_game_data.py https://share.polytopia.io/g/<uuid>
    python3 get_game_data.py <uuid> -o out.json
    python3 get_game_data.py <uuid> --bin out.gamestate.bin
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

try:
    from .get_jwt import load_jwt
except ImportError:  # running as a script from this folder
    from get_jwt import load_jwt

BACKEND = "https://polytopia-prod.net"
GET_GAME_VIEW_MODEL = f"{BACKEND}/api/game/get_game_view_model"
SPECTATE_GAME = f"{BACKEND}/api/game/spectate_game"

# GameSessionState.Ended (dump / summary responses).
STATE_ENDED = 4

_SHARE_RE = re.compile(
    r"(?:share\.polytopia\.io/g/|opengame\?id=)?([0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def parse_game_id(link_or_id: str) -> UUID:
    text = link_or_id.strip()
    try:
        return UUID(text)
    except ValueError:
        pass
    m = _SHARE_RE.search(text)
    if not m:
        raise ValueError(f"Could not parse game id from: {link_or_id!r}")
    return UUID(m.group(1))


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def api_post(path: str, jwt: str, body: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        path,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {jwt}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=_ssl_context(), timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        # macOS Python often lacks certs; fall back to curl which uses system trust.
        if "CERTIFICATE_VERIFY_FAILED" not in str(e):
            raise
        return _api_post_curl(path, jwt, body)


def _api_post_curl(path: str, jwt: str, body: dict[str, Any]) -> dict[str, Any]:
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        json.dump(body, tmp)
        tmp_path = tmp.name
    try:
        proc = subprocess.run(
            [
                "curl",
                "-sS",
                "-X",
                "POST",
                path,
                "-H",
                "Content-Type: application/json",
                "-H",
                f"Authorization: Bearer {jwt}",
                "--data-binary",
                f"@{tmp_path}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return json.loads(proc.stdout)


def fetch_game_view_model(game_id: UUID, jwt: str) -> dict[str, Any]:
    payload = {"GameId": str(game_id)}
    resp = api_post(GET_GAME_VIEW_MODEL, jwt, payload)
    if resp.get("success") and resp.get("data"):
        return resp
    # Not a participator / restricted — try spectate.
    spec = api_post(SPECTATE_GAME, jwt, payload)
    if spec.get("success") and spec.get("data"):
        return spec
    err = resp.get("errorMessage") or spec.get("errorMessage") or "unknown error"
    code = resp.get("errorCode", spec.get("errorCode"))
    raise RuntimeError(f"Failed to fetch game {game_id}: errorCode={code} {err}")


def build_output(resp: dict[str, Any]) -> dict[str, Any]:
    data = resp["data"]
    current_b64 = data.get("currentGameStateData")
    if not current_b64:
        raise RuntimeError("Response missing currentGameStateData")
    return {
        "id": data.get("id"),
        "state": data.get("state"),
        "date_created": data.get("dateCreated"),
        "date_last_command": data.get("dateLastCommand"),
        "owner_id": data.get("ownerId"),
        "game_settings_json": data.get("gameSettingsJson"),
        "timer_settings": data.get("timerSettings"),
        "game_context": data.get("gameContext"),
        # Finished board — same bytes OpenSession uses for the live/final state.
        "current_game_state_data": current_b64,
        "initial_game_state_data": data.get("initialGameStateData"),
        "_comment": (
            "current_game_state_data is the finished IBinarySerializable GameState "
            "(base64). Decode with deserialize_gamestate.py."
        ),
    }


DEFAULT_SHARE_LINK = (
    "https://share.polytopia.io/g/600d9435-991c-4cad-bd0f-08def66897ab"
)


def fetch_game_data(
    share_link: str,
    *,
    jwt: Optional[str] = None,
    allow_unfinished: bool = False,
) -> dict[str, Any]:
    """Share URL/UUID → metadata dict with base64 ``current_game_state_data``.

    Raises ``RuntimeError`` if the game is not Ended unless ``allow_unfinished``.
    Uses ``load_jwt()`` when ``jwt`` is omitted.
    """
    game_id = parse_game_id(share_link)
    token = jwt if jwt is not None else load_jwt()
    out = build_output(fetch_game_view_model(game_id, token))
    state = out.get("state")
    if state != STATE_ENDED and not allow_unfinished:
        raise RuntimeError(
            f"Game state is {state}, expected Ended ({STATE_ENDED}). "
            f"Pass allow_unfinished=True to fetch anyway."
        )
    return out


def game_state_bytes(out: dict[str, Any]) -> bytes:
    """Decode ``current_game_state_data`` from a ``fetch_game_data`` / ``build_output`` dict."""
    b64 = out.get("current_game_state_data") or out.get("currentGameStateData")
    if not b64:
        raise KeyError("no current_game_state_data in response")
    return base64.b64decode(b64)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "share_link",
        nargs="?",
        default=DEFAULT_SHARE_LINK,
        help="Share URL or bare game UUID "
        f"(default: {DEFAULT_SHARE_LINK})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write JSON to this path (default: stdout)",
    )
    parser.add_argument(
        "--bin",
        type=Path,
        dest="bin_path",
        help="Also write decoded currentGameStateData bytes to this path",
    )
    parser.add_argument(
        "--allow-unfinished",
        action="store_true",
        help="Do not error when server state is not Ended (4)",
    )
    args = parser.parse_args()

    try:
        out = fetch_game_data(
            args.share_link, allow_unfinished=args.allow_unfinished
        )
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1
    except Exception as e:
        print(e, file=sys.stderr)
        return 1

    state = out.get("state")
    text = json.dumps(out, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(text)

    if args.bin_path:
        raw = game_state_bytes(out)
        args.bin_path.write_bytes(raw)
        print(f"wrote {args.bin_path} ({len(raw)} bytes)", file=sys.stderr)

    print(
        f"game {out['id']} state={state} "
        f"currentGameStateData={len(out['current_game_state_data'])} b64 chars",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
