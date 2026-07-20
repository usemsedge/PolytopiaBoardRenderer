"""Extract per-sprite pivot + pixelsToUnits + rect from the Unity bundle (no deps).

Sprite (classID 213) leading fields (Unity 5.4.1+ .. 6000), before the complex
m_RD render data: m_Name(string), m_Rect(Rectf), m_Offset(Vec2), m_Border(Vec4),
m_PixelsToUnits(float), m_Pivot(Vec2). Writes pyrender/sprite_pivots.json.
"""
from __future__ import annotations
import glob, json, os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unityfs import read_bundle
from unityserial import parse, Reader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(ROOT, "Polytopia.app/Contents/Resources/Data/data.unity3d")
# Themed sprites (per-tribe/skin heads, bodies, animals, weapons) live in addressable
# bundles, NOT data.unity3d. Their pixelsToUnits must be read too, or render_scale falls
# back to a family guess and they draw at the wrong size (e.g. body_rider_arty too small).
AA = os.path.join(ROOT, "Polytopia.app/Contents/Resources/Data/StreamingAssets/aa/StandaloneOSX")
# The UI bundle holds icons authored at tiny pixelsToUnits (e.g. MarketIcon ppu≈9.6) so they
# display large in menus; using that ppu for board render_scale blows them up ~28x. UI art is
# not board art, so exclude it — board improvements that reuse an icon name (MarketIcon,
# icebank_icon) then fall back to native scale, which is how they rendered before.
BUNDLES = [BUNDLE] + [p for p in sorted(glob.glob(os.path.join(AA, "sprites_assets_*.bundle")))
                      if "_ui." not in os.path.basename(p)]


def read_sprite(raw, start, little):
    r = Reader(raw, little); r.o = start
    n = r.u32()
    name = r.bytes(n).decode("utf-8", "replace"); r.align()
    rx, ry, rw, rh = r.f32(), r.f32(), r.f32(), r.f32()   # m_Rect
    ox, oy = r.f32(), r.f32()                              # m_Offset
    bx, by, bz, bw = r.f32(), r.f32(), r.f32(), r.f32()    # m_Border
    ppu = r.f32()                                          # m_PixelsToUnits
    pvx, pvy = r.f32(), r.f32()                            # m_Pivot
    return name, (rw, rh), ppu, (pvx, pvy)


def _read_bundle_sprites(path, out):
    """Read every Sprite (213) in a bundle into ``out`` (first writer wins, so data.unity3d
    is authoritative when a name appears in multiple bundles)."""
    n_added = 0
    for nd, sf in read_bundle(path):
        if nd.path.endswith(".resS"):           # raw texture payload, not a SerializedFile
            continue
        try:
            m = parse(sf)
        except Exception:
            continue
        if not m.get("objects"):
            continue
        little = m["little"]
        for (path_id, start, size, type_id) in m["objects"]:
            if m["types"][type_id][0] != 213:
                continue
            try:
                name, (rw, rh), ppu, piv = read_sprite(m["raw"], start, little)
            except Exception:
                continue
            # sanity filter
            if not name or name in out or rw <= 0 or rh <= 0 or rw > 8192 or rh > 8192:
                continue
            if not (0.0 <= ppu <= 100000):
                continue
            out[name] = {"w": round(rw), "h": round(rh), "ppu": round(ppu, 4),
                         "pivot": [round(piv[0], 5), round(piv[1], 5)]}
            n_added += 1
    return n_added


def main():
    out = {}
    for path in BUNDLES:
        added = _read_bundle_sprites(path, out)
        print(f"  {os.path.basename(path):40} +{added} sprites")
    dest = os.path.join(ROOT, "pyrender", "sprite_pivots.json")
    json.dump(out, open(dest, "w"))
    print(f"extracted {len(out)} sprite pivots -> {dest}")
    # quick validation against the texture catalog
    cat = json.load(open(os.path.join(ROOT, "pyrender", "sprite_catalog.json")))
    ok = miss = dimok = 0
    for n, info in out.items():
        if n in cat:
            ok += 1
            if abs(cat[n]["w"] - info["w"]) <= 1 and abs(cat[n]["h"] - info["h"]) <= 1:
                dimok += 1
        else:
            miss += 1
    print(f"  names matching texture catalog: {ok} (dims match {dimok}), not-in-catalog: {miss}")
    # sample
    for s in ["ground_imperius", "mountain_imperius", "body_default", "bodytint_default",
              "head_imperius", "head", "weapon_sword", "animal_imperius", "House_1_imperius",
              "Temple_1", "water", "ice"]:
        if s in out:
            print(f"  {s:20} rect={out[s]['w']}x{out[s]['h']} ppu={out[s]['ppu']} pivot={out[s]['pivot']}")


if __name__ == "__main__":
    main()
