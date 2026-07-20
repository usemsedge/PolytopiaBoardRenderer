"""Extract every Unit prefab's part layout from data.unity3d -> pyrender/unit_parts.json.

IL2CPP release typetrees are stripped, so we parse the serialized files by fixed layout:
find the single `Unit` MonoScript, resolve the prefab GameObjects that reference it
(via the externals table for cross-file PPtrs), walk each prefab's Transform hierarchy
accumulating world position/scale, and for every node carrying a SpriteRenderer read its
m_Sprite (the 4-aligned PPtr<Sprite>) and m_SortingOrder (int16 just before m_Sprite).

Each unit -> ordered list of parts {node, sprite, tint, pos[x,y], scale[x,y], order}.
"""
from __future__ import annotations
import json, os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unityfs import read_bundle
from unityserial import Reader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(ROOT, "Polytopia.app/Contents/Resources/Data/data.unity3d")


def parse_full(data):
    """SerializedFile parse incl. externals (v22 / Unity 6000)."""
    r = Reader(data, little=False)
    r.u32(); r.u32(); version = r.u32(); r.u32()
    endian = r.u8() if version >= 9 else 0
    if version >= 9: r.bytes(3)
    if version >= 22:
        r.u32(); r.i64(); data_offset = r.i64(); r.i64()
    little = (endian == 0); r.little = little; r.e = "<" if little else ">"
    r.cstr(); r.u32()
    enable_tt = bool(r.u8()) if version >= 13 else True
    types = []
    for _ in range(r.u32()):
        cid = r.i32(); r.u8() if version >= 16 else 0
        r.i16() if version >= 17 else -1
        if version >= 13:
            if (version < 16 and cid < 0) or (version >= 16 and cid == 114): r.bytes(16)
            r.bytes(16)
        if enable_tt and version >= 21:
            r.bytes(r.u32() * 4)
        types.append((cid, None))
    objects = []
    for _ in range(r.u32()):
        r.align(); pid = r.i64()
        bs = r.i64() if version >= 22 else r.u32()
        sz = r.u32(); tid = r.i32()
        objects.append((pid, data_offset + bs, sz, tid))
    if version >= 11:
        for _ in range(r.u32()):
            r.i32()
            if version >= 14: r.align(); r.i64()
            else: r.i32()
    externals = []
    for _ in range(r.u32()):
        if version >= 6: r.cstr()
        if version >= 5: r.bytes(16)
        r.i32(); externals.append(r.cstr())
    objs = {pid: (start, size, types[tid][0]) for (pid, start, size, tid) in objects}
    return {"little": little, "objs": objs, "externals": externals, "raw": data}


def rd_pptr(r): return (r.i32(), r.i64())
def rd_str(r): n = r.u32(); s = r.bytes(n).decode("utf-8", "replace"); r.align(); return s


def main():
    files = {}
    for nd, sf in read_bundle(BUNDLE):
        if nd.path.endswith(".assets"):
            try: files[nd.path] = parse_full(sf)
            except Exception: pass
    bn = {p.split("/")[-1]: p for p in files}

    def resolve(fp, fid, pid):
        if fid == 0: return (fp, pid)
        ext = files[fp]["externals"]
        if 1 <= fid <= len(ext) and ext[fid - 1].split("/")[-1] in bn:
            return (bn[ext[fid - 1].split("/")[-1]], pid)
        return None

    def cid(fp, pid): return files[fp]["objs"][pid][2] if pid in files[fp]["objs"] else None

    def rms(fp, s):  # MonoScript class name
        r = Reader(files[fp]["raw"], files[fp]["little"]); r.o = s
        rd_str(r); r.i32(); r.bytes(16); return rd_str(r)

    def rmb(fp, s):  # MonoBehaviour (gameobject, script)
        r = Reader(files[fp]["raw"], files[fp]["little"]); r.o = s
        go = rd_pptr(r); r.u8(); r.align(); return go, rd_pptr(r)

    def rgo(fp, s):  # GameObject (components, name)
        r = Reader(files[fp]["raw"], files[fp]["little"]); r.o = s
        c = [rd_pptr(r) for _ in range(r.u32())]; r.i32(); return c, rd_str(r)

    def rtf(fp, s):  # Transform (gameobject, pos, scale, children)
        r = Reader(files[fp]["raw"], files[fp]["little"]); r.o = s
        go = rd_pptr(r); r.bytes(16)
        pos = (r.f32(), r.f32(), r.f32()); scl = (r.f32(), r.f32(), r.f32())
        ch = [rd_pptr(r) for _ in range(r.u32())]
        return go, pos, scl, ch

    def spname(fp, pid):
        r = Reader(files[fp]["raw"], files[fp]["little"]); r.o = files[fp]["objs"][pid][0]
        return r.bytes(r.u32()).decode("utf-8", "replace")

    def sr_sprite_order(fp, pid):
        st, size, _ = files[fp]["objs"][pid]; raw = files[fp]["raw"]
        e = "<" if files[fp]["little"] else ">"; best = None
        for off in range(st, st + size - 12):
            if (off - st) % 4: continue                 # m_Sprite PPtr is 4-aligned
            fid = struct.unpack_from(e + "i", raw, off)[0]
            pp = struct.unpack_from(e + "q", raw, off + 4)[0]
            if 0 <= fid <= 50 and pp > 0:
                t = resolve(fp, fid, pp)
                if t and cid(*t) == 213: best = (off, t)
        if not best: return None, None
        off, t = best
        return spname(*t), struct.unpack_from(e + "h", raw, off - 2)[0]

    # locate Unit + SkinVisualsReference MonoScripts
    us = svr_script = None
    for fp, m in files.items():
        for pid, (s, sz, c) in m["objs"].items():
            if c == 115:
                try:
                    nm = rms(fp, s)
                except Exception:
                    continue
                if nm == "Unit": us = (fp, pid)
                elif nm == "SkinVisualsReference": svr_script = (fp, pid)

    def _fileid(host_fp, target_fp):
        """fileID of target_fp's objects as referenced from host_fp (0 = same file)."""
        if target_fp == host_fp:
            return 0
        ext = files[host_fp]["externals"]
        tail = target_fp.split("/")[-1]
        for i, exn in enumerate(ext):
            if exn.split("/")[-1] == tail:
                return i + 1
        return None

    def svr_on(fp, gp):
        """The SkinVisualsReference MonoBehaviour (fp,pid) on a prefab root, or None."""
        for cf, cp in rgo(fp, files[fp]["objs"][gp][0])[0]:
            t = resolve(fp, cf, cp)
            if not t or cid(*t) != 114:
                continue
            _go, sc = rmb(t[0], files[t[0]]["objs"][t[1]][0])
            if resolve(t[0], sc[0], sc[1]) == svr_script:
                return t
        return None

    def skin_logic(svr, node_fp, node_pid):
        """VisualPart.skinLogic for a node's GameObject (0 UseTribe, 1 UseClimate,
        2 UseBirthClimate, 3 DontChangeSkin), or None if not a skinned part. Each
        VisualPart begins with visualPart(PPtr 12B)+outline(PPtr 12B); skinLogic is the
        int at +24. We find the entry by its visualPart PPtr and validate the value."""
        if svr is None:
            return None
        sfp, spid = svr
        st, sz, _ = files[sfp]["objs"][spid]
        raw = files[sfp]["raw"]; e = "<" if files[sfp]["little"] else ">"
        fid = _fileid(sfp, node_fp)
        if fid is None:
            return None
        needle = struct.pack(e + "iq", fid, node_pid)
        pos = st
        while True:
            off = raw.find(needle, pos, st + sz)
            if off == -1:
                return None
            val = struct.unpack_from(e + "i", raw, off + 24)[0]
            if 0 <= val <= 3:                # plausible SkinningLogic enum value
                return val
            pos = off + 4

    # prefab GameObjects referencing Unit
    unit_go = {}
    for fp, m in files.items():
        for pid, (s, sz, c) in m["objs"].items():
            if c != 114: continue
            try: go, sc = rmb(fp, s)
            except Exception: continue
            if resolve(fp, sc[0], sc[1]) == us:
                g = resolve(fp, go[0], go[1])
                if g and cid(*g) == 1:
                    unit_go[rgo(g[0], files[g[0]]["objs"][g[1]][0])[1]] = g

    def go_tf(fp, gp):
        for cf, cp in rgo(fp, files[fp]["objs"][gp][0])[0]:
            t = resolve(fp, cf, cp)
            if t and cid(*t) == 4: return t
    def go_sr(fp, gp):
        for cf, cp in rgo(fp, files[fp]["objs"][gp][0])[0]:
            t = resolve(fp, cf, cp)
            if t and cid(*t) == 212: return t

    SKIP = {"Outline", "Outline_Tint", "Bubble"}
    def extract(name):
        fp, gp = unit_go[name]; root = go_tf(fp, gp); parts = []
        svr = svr_on(fp, gp)
        def walk(tfp, tpid, wx, wy, sx, sy):
            go, pos, scl, ch = rtf(tfp, files[tfp]["objs"][tpid][0])
            gfp, gpid = resolve(tfp, *go); nm = rgo(gfp, files[gfp]["objs"][gpid][0])[1]
            nx = wx + sx * pos[0]; ny = wy + sy * pos[1]; nsx = sx * scl[0]; nsy = sy * scl[1]
            if nm not in SKIP:
                sr = go_sr(gfp, gpid)
                if sr:
                    spr, order = sr_sprite_order(*sr)
                    if spr and not spr.endswith("_Outline"):
                        # skinLogic governs how this part is re-skinned (UseTribe vs the
                        # tile climate vs not at all); default UseTribe (0) when no entry.
                        sl = skin_logic(svr, gfp, gpid)
                        parts.append({"node": nm, "sprite": spr, "tint": "tint" in spr.lower(),
                                      "pos": [round(nx, 5), round(ny, 5)],
                                      "scale": [round(nsx, 5), round(nsy, 5)], "order": order,
                                      "skinLogic": 0 if sl is None else sl})
            for cf, cp in ch:
                c = resolve(tfp, cf, cp)
                if c: walk(c[0], c[1], nx, ny, nsx, nsy)
        if root: walk(root[0], root[1], 0.0, 0.0, 1.0, 1.0)
        parts.sort(key=lambda p: p["order"])
        return parts

    data = {n: extract(n) for n in unit_go}
    dest = os.path.join(ROOT, "pyrender", "unit_parts.json")
    json.dump(data, open(dest, "w"), indent=1)
    print(f"extracted {len(data)} unit prefabs -> {dest}")


if __name__ == "__main__":
    main()
