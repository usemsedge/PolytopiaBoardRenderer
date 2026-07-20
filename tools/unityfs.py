"""Minimal pure-Python UnityFS bundle reader (zero deps).

Parses a UnityFS bundle (LZ4/LZMA/none block compression) into its serialized
files. Enough to then read Sprite pivots/PPU and Transform/GameObject data.
"""
from __future__ import annotations
import struct, lzma


def lz4_decompress(src: bytes, dst_size: int) -> bytes:
    """LZ4 block-format decompression (pure python)."""
    dst = bytearray()
    i, n = 0, len(src)
    while i < n:
        token = src[i]; i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255:
                    break
        dst += src[i:i + lit]; i += lit
        if len(dst) >= dst_size or i >= n:
            break
        off = src[i] | (src[i + 1] << 8); i += 2
        ml = token & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255:
                    break
        ml += 4
        start = len(dst) - off
        for j in range(ml):
            dst.append(dst[start + j])
    return bytes(dst)


def _decomp(block: bytes, flags: int, usize: int) -> bytes:
    ctype = flags & 0x3f
    if ctype == 0:
        return block
    if ctype == 1:  # LZMA (raw alone stream, 5-byte props + 8-byte size omitted in Unity)
        props = block[0]
        dictsize = struct.unpack_from("<I", block, 1)[0]
        filt = [{"id": lzma.FILTER_LZMA1, "dict_size": dictsize,
                 "lc": props % 9, "lp": (props // 9) % 5, "pb": props // 45}]
        d = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filt)
        return d.decompress(block[5:], usize)
    if ctype in (2, 3):  # LZ4 / LZ4HC
        return lz4_decompress(block, usize)
    raise ValueError(f"unknown block compression {ctype}")


class Node:
    __slots__ = ("offset", "size", "flags", "path")
    def __init__(self, offset, size, flags, path):
        self.offset, self.size, self.flags, self.path = offset, size, flags, path


def read_bundle(path):
    """Return list of (Node, serialized-file-bytes)."""
    data = open(path, "rb").read()
    o = 0
    def cstr():
        nonlocal o
        e = data.index(0, o); s = data[o:e].decode("utf-8", "replace"); o = e + 1; return s
    sig = cstr(); ver = struct.unpack_from(">I", data, o)[0]; o += 4
    cstr(); cstr()  # unity version, revision
    size = struct.unpack_from(">q", data, o)[0]; o += 8
    cbis = struct.unpack_from(">I", data, o)[0]; o += 4
    ubis = struct.unpack_from(">I", data, o)[0]; o += 4
    flags = struct.unpack_from(">I", data, o)[0]; o += 4
    if ver >= 7:
        o = (o + 15) & ~15  # align 16

    # blocksInfo location
    if flags & 0x80:  # at end
        bi_off = len(data) - cbis
    else:
        bi_off = o
    bi = _decomp(data[bi_off:bi_off + cbis], flags, ubis)
    if not (flags & 0x80):
        o = bi_off + cbis
        if flags & 0x200:  # padding at start of blocks
            o = (o + 15) & ~15

    # parse blocksInfo
    p = 16  # skip uncompressedDataHash
    block_count = struct.unpack_from(">i", bi, p)[0]; p += 4
    blocks = []
    for _ in range(block_count):
        us, cs = struct.unpack_from(">II", bi, p); p += 8
        bf = struct.unpack_from(">H", bi, p)[0]; p += 2
        blocks.append((us, cs, bf))
    node_count = struct.unpack_from(">i", bi, p)[0]; p += 4
    nodes = []
    for _ in range(node_count):
        noff, nsize = struct.unpack_from(">qq", bi, p); p += 16
        nflags = struct.unpack_from(">I", bi, p)[0]; p += 4
        e = bi.index(0, p); npath = bi[p:e].decode("utf-8", "replace"); p = e + 1
        nodes.append(Node(noff, nsize, nflags, npath))

    # decompress all data blocks -> one blob
    blob = bytearray()
    bo = o
    for (us, cs, bf) in blocks:
        blob += _decomp(data[bo:bo + cs], bf, us); bo += cs

    return [(nd, bytes(blob[nd.offset:nd.offset + nd.size])) for nd in nodes]


if __name__ == "__main__":
    import sys
    for nd, sf in read_bundle(sys.argv[1]):
        print(f"{nd.path:40} size={len(sf)} flags={nd.flags}")
