#!/usr/bin/env python3
"""RE helpers for the flat biblical_greed layout (capstone via .pydeps).

  python3 tools/re_tools.py sym   0x2CC11AC                 # addr -> symbol
  python3 tools/re_tools.py rng   MapExtensions ToPosition  # find RVA range by name
  python3 tools/re_tools.py callees 0x2D4F6C0 [end]
  python3 tools/re_tools.py disasm  0x2CC11AC [end]          # capstone ARM64 dump
"""
from __future__ import annotations
import json, struct, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "GameAssembly_arm64.dylib"
SCRIPT = ROOT / "il2cpp_dump/script.json"
sys.path.insert(0, str(ROOT / ".pydeps"))

_methods = None
def methods():
    global _methods
    if _methods is None:
        _methods = sorted(json.load(open(SCRIPT))["ScriptMethod"], key=lambda m: m["Address"])
    return _methods

def sym(addr):
    prev = [m for m in methods() if m["Address"] <= addr]
    return prev[-1]["Name"] if prev else f"?@{addr:#x}"

def addr_of(*needles):
    needles = [n.lower() for n in needles]
    hits = [m for m in methods() if all(n in m["Name"].lower() for n in needles)]
    return hits

def next_addr(start):
    for m in methods():
        if m["Address"] > start:
            return m["Address"]
    return start + 0x4000

def callees(start, end=None):
    data = BIN.read_bytes()
    end = end or next_addr(start)
    from collections import Counter
    c = Counter()
    for off in range(start, min(end, len(data) - 4), 4):
        insn = struct.unpack_from("<I", data, off)[0]
        if (insn >> 26) != 0b100101:  # BL
            continue
        imm = insn & 0x3FFFFFF
        if imm & 0x2000000:
            imm -= 0x4000000
        c[sym(off + (imm << 2))] += 1
    return c

def disasm(start, end=None):
    import capstone
    data = BIN.read_bytes()
    end = end or next_addr(start)
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    md.detail = False
    code = data[start:end]
    out = []
    for ins in md.disasm(code, start):
        out.append(f"0x{ins.address:08x}: {ins.mnemonic:8} {ins.op_str}")
    return out

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "sym":
        for a in sys.argv[2:]:
            print(f"{int(a,0):#x} -> {sym(int(a,0))}")
    elif cmd == "rng":
        for m in addr_of(*sys.argv[2:]):
            print(f"0x{m['Address']:X}  {m['Name']}")
    elif cmd == "callees":
        s = int(sys.argv[2], 0); e = int(sys.argv[3], 0) if len(sys.argv) > 3 else None
        print(f"Callees of {sym(s)} ({s:#x}..{(e or next_addr(s)):#x}):")
        for name, n in callees(s, e).most_common():
            print(f"  {n:3d}  {name}")
    elif cmd == "disasm":
        s = int(sys.argv[2], 0); e = int(sys.argv[3], 0) if len(sys.argv) > 3 else None
        print("\n".join(disasm(s, e)))
