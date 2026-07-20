#!/usr/bin/env python3
"""Extract the per-tribe and per-skin base colours from the game data.

The engine stores all balance/data in a ``GameLogicData`` TextAsset embedded in
``data.unity3d`` (a plain JSON blob once the UnityFS bundle is LZ4-decompressed).
``GameLogicData.GetTribeColor(tribe, skin)`` (binary 0x84A314) resolves a player's
colour as:

    skinData[skin].color   if that skin defines a positive colour   (field +0x10)
    else tribeData[tribe].color                                      (field +0x14)
    else 0xFFFFFF

Both are packed 0x00RRGGBB ints. This dumps the highest data version's tribe and
skin colours, keyed by the engine's TribeType / SkinType enum values, into
``pyrender/tribe_colors.json`` so the renderer can reproduce GetTribeColor exactly.

Run:  python3 tools/extract_tribe_colors.py
"""
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from unityfs import read_bundle  # noqa: E402

BUNDLE = os.path.join(ROOT, "Polytopia.app", "Contents", "Resources", "Data", "data.unity3d")
OUT = os.path.join(ROOT, "pyrender", "tribe_colors.json")

# TribeType enum (game) -> data JSON key (lowercase tribe name).
TRIBE_NAME_TO_ID = {
    "none": 0, "nature": 1, "aimo": 2, "aquarion": 3, "bardur": 4, "elyrion": 5,
    "hoodrick": 6, "imperius": 7, "kickoo": 8, "luxidoor": 9, "oumaji": 10,
    "quetzali": 11, "vengir": 12, "xinxi": 13, "yadakk": 14, "zebasi": 15,
    "polaris": 16, "cymanti": 17,
}
# SkinType enum (game) -> data JSON key (skin name; matched case-insensitively, as
# the data mixes cases: "Scholar", "swamp", "DarkElf"...).
SKIN_NAME_TO_ID = {
    "ranger": 1, "ninja": 2, "baerion": 3, "scholar": 5, "mercenary": 7,
    "sfinx": 8, "skeleton": 9, "arty": 10, "pirate": 11, "aibo": 12, "urkaz": 13,
    "ikarus": 14, "darkelf": 15, "swamp": 17, "magma": 18, "cute": 19,
}


def _read_textasset(sf: bytes, start: int):
    """Read a Unity TextAsset's (name, body) given the offset of its name bytes."""
    name_len = struct.unpack_from("<I", sf, start - 4)[0]
    name = sf[start:start + name_len]
    p = start + name_len
    p = (p + 3) & ~3                       # align(4) after the name string
    body_len = struct.unpack_from("<I", sf, p)[0]
    p += 4
    return name.decode("utf-8", "replace"), sf[p:p + body_len]


def load_game_logic_data():
    """Return the parsed JSON of the highest-versioned GameLogicData TextAsset."""
    sf = None
    for nd, data in read_bundle(BUNDLE):
        if nd.path == "sharedassets0.assets":
            sf = data
            break
    if sf is None:
        raise SystemExit("sharedassets0.assets not found in bundle")

    best_ver, best_json = -1, None
    for m in re.finditer(rb"GameLogicData([0-9]+)", sf):
        ver = int(m.group(1))
        name, body = _read_textasset(sf, m.start())
        if name != m.group().decode() or b"tribeData" not in body[:256]:
            continue
        if ver > best_ver:
            best_ver, best_json = ver, body
    if best_json is None:
        raise SystemExit("no GameLogicData TextAsset with tribeData found")
    return best_ver, json.loads(best_json.decode("utf-8"))


def main():
    ver, gld = load_game_logic_data()

    tribe_colors = {}
    tribe_skin = {}                        # tribe id -> its special skin id (from "skins")
    for name, t in gld.get("tribeData", {}).items():
        tid = TRIBE_NAME_TO_ID.get(name)
        if tid is None:
            continue
        tribe_colors[str(tid)] = int(t.get("color", 0))
        # Each tribe lists its special (premium) skin in "skins"; the first is the one
        # offered for that tribe. The unlisted "normal" skin is SkinType.Default.
        for sname in (t.get("skins") or []):
            sid = SKIN_NAME_TO_ID.get(sname.lower())
            if sid is not None:
                tribe_skin[str(tid)] = sid
                break

    skin_colors = {}
    for name, s in gld.get("skinData", {}).items():
        sid = SKIN_NAME_TO_ID.get(name.lower())
        if sid is None:
            continue
        # Only skins with a positive colour override the tribe colour (engine: color > 0).
        col = int(s.get("color", 0))
        if col > 0:
            skin_colors[str(sid)] = col

    out = {"version": ver, "tribe": tribe_colors, "skin": skin_colors,
           "tribe_skin": tribe_skin}
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")

    print(f"GameLogicData v{ver}: {len(tribe_colors)} tribe colours, "
          f"{len(skin_colors)} skin colour override(s) -> {OUT}")
    for tid, c in sorted(tribe_colors.items(), key=lambda kv: int(kv[0])):
        sk = tribe_skin.get(tid)
        print(f"  tribe {tid:>2}  #{c & 0xFFFFFF:06X}  special skin={sk}")
    for sid, c in sorted(skin_colors.items(), key=lambda kv: int(kv[0])):
        print(f"  skin  {sid:>2}  #{c & 0xFFFFFF:06X}")


if __name__ == "__main__":
    main()