#!/usr/bin/env python3
"""Fetch a Polytopia game's GameState blob from a share link.

Uses the local jwtToken (see get_jwt.py) and POSTs to
``api/game/get_game_view_model``. Writes JSON containing metadata plus the
server's ``currentGameStateData`` (finished / latest board) and
``initialGameStateData`` (game start) as base64.

The binary GameState is the same payload ``ClientBase.OpenSession`` loads.
Convert it with ``deserialize_gamestate.py``.

Usage
-----
    python3 get_game_data.py https://share.polytopia.io/g/<uuid>
    python3 get_game_data.py <uuid> -o out.json
    python3 get_game_data.py <uuid> --bin out.gamestate.bin
    python3 get_game_data.py <uuid> --which start --bin start.bin
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import ssl
import sys
import traceback
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

# First-seen share snapshots. Duplicate links reuse this instead of hitting the API.
CACHE_DIR = Path(__file__).resolve().parent / ".share_cache"


def cache_path(game_id: UUID) -> Path:
    return CACHE_DIR / f"{game_id}.json"


def read_cached_game_data(game_id: UUID) -> Optional[dict[str, Any]]:
    path = cache_path(game_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("current_game_state_data"):
        return None
    return data


def write_cached_game_data(game_id: UUID, out: dict[str, Any]) -> None:
    """Save the first snapshot only — later duplicate links keep the older file.

    If an existing cache is missing ``initial_game_state_data`` and ``out`` has
    it, merge that field so start-of-game loads can reuse the file.
    """
    path = cache_path(game_id)
    payload = {k: v for k, v in out.items() if not str(k).startswith("_")}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if isinstance(existing, dict) and existing.get("initial_game_state_data"):
            return
        initial = payload.get("initial_game_state_data")
        if isinstance(existing, dict) and initial:
            existing["initial_game_state_data"] = initial
            payload = existing
        elif path.exists() and not initial:
            return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


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


def _print_fetch_error(where: str, err: BaseException, extra: str = "") -> None:
    print(f"[get_game_data] {where}: {err}", file=sys.stderr)
    if extra:
        print(extra, file=sys.stderr)
    traceback.print_exception(type(err), err, err.__traceback__)


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
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace") if e.fp is not None else ""
        _print_fetch_error(
            f"HTTP {e.code} {path}",
            e,
            extra=raw or e.reason,
        )
        raise
    except urllib.error.URLError as e:
        # macOS Python often lacks certs; fall back to curl which uses system trust.
        if "CERTIFICATE_VERIFY_FAILED" not in str(e):
            _print_fetch_error(f"URLError {path}", e)
            raise
        print(
            f"[get_game_data] cert verify failed for {path}; retrying with curl",
            file=sys.stderr,
        )
        return _api_post_curl(path, jwt, body)
    except Exception as e:
        _print_fetch_error(f"api_post {path}", e)
        raise


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
    except subprocess.CalledProcessError as e:
        _print_fetch_error(
            f"curl {path} exit {e.returncode}",
            e,
            extra=f"stdout:\n{e.stdout}\nstderr:\n{e.stderr}",
        )
        raise
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        _print_fetch_error(
            f"curl {path} invalid JSON",
            e,
            extra=proc.stdout,
        )
        raise


def fetch_game_view_model(game_id: UUID, jwt: str) -> dict[str, Any]:
    payload = {"GameId": str(game_id)}
    resp = api_post(GET_GAME_VIEW_MODEL, jwt, payload)
    if resp.get("success") and resp.get("data"):
        return resp
    print(
        f"[get_game_data] get_game_view_model failed for {game_id}: "
        f"{json.dumps(resp, default=str)}",
        file=sys.stderr,
    )
    # Not a participator / restricted — try spectate.
    spec = api_post(SPECTATE_GAME, jwt, payload)
    if spec.get("success") and spec.get("data"):
        return spec
    print(
        f"[get_game_data] spectate_game failed for {game_id}: "
        f"{json.dumps(spec, default=str)}",
        file=sys.stderr,
    )
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
            "current_game_state_data is the finished/latest IBinarySerializable "
            "GameState (base64); initial_game_state_data is the opening board. "
            "Decode with deserialize_gamestate.py --which start|end."
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
    use_cache: bool = True,
    which: str = "end",
) -> dict[str, Any]:
    """Share URL/UUID → metadata dict with start and end GameState blobs.

    Raises ``RuntimeError`` if the game is not Ended unless ``allow_unfinished``.
    Uses ``load_jwt()`` when ``jwt`` is omitted.

    When ``use_cache`` is true (default), a previously saved snapshot for this
    game id is returned and the Polytopia API is not called. ``which`` is
    ``"start"`` or ``"end"`` (aliases accepted); a cached file missing the
    requested blob is ignored so the API can fill it in.
    """
    game_id = parse_game_id(share_link)
    snapshot = normalize_snapshot(which)
    if use_cache:
        cached = read_cached_game_data(game_id)
        if cached is not None:
            if snapshot == "start":
                has_blob = (
                    cached.get("initial_game_state_data")
                    or cached.get("initialGameStateData")
                )
            else:
                has_blob = (
                    cached.get("current_game_state_data")
                    or cached.get("currentGameStateData")
                )
            if has_blob:
                state = cached.get("state")
                if state != STATE_ENDED and not allow_unfinished:
                    raise RuntimeError(
                        f"Game state is {state}, expected Ended ({STATE_ENDED}). "
                        f"Pass allow_unfinished=True to fetch anyway."
                    )
                cached = dict(cached)
                cached["_from_cache"] = True
                return cached

    token = jwt if jwt is not None else load_jwt()
    out = build_output(fetch_game_view_model(game_id, token))
    state = out.get("state")
    if state != STATE_ENDED and not allow_unfinished:
        raise RuntimeError(
            f"Game state is {state}, expected Ended ({STATE_ENDED}). "
            f"Pass allow_unfinished=True to fetch anyway."
        )
    if use_cache:
        write_cached_game_data(game_id, out)
    out = dict(out)
    out["_from_cache"] = False
    return out


def normalize_snapshot(which: Optional[str] = None) -> str:
    """Map UI/CLI aliases onto ``"start"`` or ``"end"`` (default end)."""
    if which is None or which is False:
        return "end"
    if which is True:
        return "start"
    text = str(which).strip().lower()
    if text in ("", "end", "current", "final", "finished"):
        return "end"
    if text in ("start", "initial", "begin", "beginning"):
        return "start"
    raise ValueError(f"unknown snapshot {which!r}; use 'start' or 'end'")


def game_state_bytes(out: dict[str, Any], *, which: str = "end") -> bytes:
    """Decode start (``initial_game_state_data``) or end (``current_game_state_data``)."""
    snapshot = normalize_snapshot(which)
    if snapshot == "start":
        b64 = out.get("initial_game_state_data") or out.get("initialGameStateData")
        if not b64:
            raise KeyError("no initial_game_state_data in response")
        return base64.b64decode(b64)
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
        help="Also write decoded GameState bytes (start or end, see --which) to this path",
    )
    parser.add_argument(
        "--allow-unfinished",
        action="store_true",
        help="Do not error when server state is not Ended (4)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore the local share-link cache and call the API",
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Decode the opening board (initialGameStateData) instead of the end",
    )
    parser.add_argument(
        "--which",
        choices=("start", "end"),
        default=None,
        help="Which board snapshot to decode for --bin: start or end (default end)",
    )
    args = parser.parse_args()

    which = args.which or ("start" if args.start else "end")
    try:
        out = fetch_game_data(
            args.share_link,
            allow_unfinished=args.allow_unfinished,
            use_cache=not args.no_cache,
            which=which,
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
        raw = game_state_bytes(out, which=which)
        args.bin_path.write_bytes(raw)
        print(f"wrote {args.bin_path} ({len(raw)} bytes) [{which}]", file=sys.stderr)

    current_n = len(out.get("current_game_state_data") or "")
    initial_n = len(out.get("initial_game_state_data") or "")
    print(
        f"game {out['id']} state={state} which={which} "
        f"{'cache-hit' if out.get('_from_cache') else 'fetched'} "
        f"current={current_n} initial={initial_n} b64 chars",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
