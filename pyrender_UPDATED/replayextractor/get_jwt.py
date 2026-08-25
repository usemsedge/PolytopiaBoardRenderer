#!/usr/bin/env python3
"""Print the most recently modified Polytopia JWT from local app data."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

APP_SUPPORT = Path.home() / "Library" / "Application Support"

# Unity persistentDataPath folders used by Polytopia builds on macOS.
DIR_GLOBS = (
    "com.midjiwan.polytopia*",
    "*polytopia*",
    "*Polytopia*",
)


def find_jwt_files() -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    if not APP_SUPPORT.is_dir():
        return found

    for pattern in DIR_GLOBS:
        for root in APP_SUPPORT.glob(pattern):
            if not root.is_dir():
                continue
            for path in root.rglob("jwtToken"):
                if not path.is_file():
                    continue
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                found.append(path)
    return found


def newest_jwt() -> Path | None:
    files = find_jwt_files()
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def load_jwt() -> str:
    """Return the newest jwtToken file contents (stripped). Raises FileNotFoundError."""
    path = newest_jwt()
    if path is None:
        raise FileNotFoundError(
            "No jwtToken file found under ~/Library/Application Support/"
        )
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise FileNotFoundError(f"Empty jwtToken file: {path}")
    return token


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        action="store_true",
        help="Print the file path instead of the token contents",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all jwtToken files with mtimes, newest first",
    )
    args = parser.parse_args()

    files = find_jwt_files()
    if not files:
        print("No jwtToken file found under ~/Library/Application Support/", file=sys.stderr)
        return 1

    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    if args.list:
        for path in files:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            print(f"{mtime.isoformat(sep=' ', timespec='seconds')}\t{path}")
        return 0

    path = files[0]
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    dated = mtime.isoformat(sep=" ", timespec="seconds")

    if args.path:
        print(f"{dated}\t{path}")
        return 0

    token = path.read_text(encoding="utf-8").strip()
    if not token:
        print(f"Empty jwtToken file: {path}", file=sys.stderr)
        return 1

    print(f"modified: {dated}", file=sys.stderr)
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
