"""Zero-dependency RGBA image core (stdlib zlib only).

The extracted Polytopia sprites are all 8-bit RGBA, non-interlaced PNGs, so the
decoder only needs to support color-type 6 / bit-depth 8.  Output PNGs are
written with filter 0 + zlib deflate.  An ``Image`` is a flat ``bytearray`` of
RGBA pixels, row-major, top-left origin.

If Pillow ever becomes available it can be dropped in behind ``Image`` without
touching the renderer, but this module keeps the project dependency-free.
"""
from __future__ import annotations

import struct
import zlib
from typing import Optional


class Image:
    __slots__ = ("w", "h", "px")

    def __init__(self, w: int, h: int, px: Optional[bytearray] = None):
        self.w = w
        self.h = h
        if px is None:
            self.px = bytearray(w * h * 4)  # transparent black
        else:
            assert len(px) == w * h * 4, (len(px), w * h * 4)
            self.px = px

    # ---- construction -------------------------------------------------
    @classmethod
    def new(cls, w: int, h: int, rgba=(0, 0, 0, 0)) -> "Image":
        img = cls(w, h)
        if rgba != (0, 0, 0, 0):
            r, g, b, a = rgba
            row = bytes((r, g, b, a)) * w
            for y in range(h):
                img.px[y * w * 4:(y + 1) * w * 4] = row
        return img

    @classmethod
    def load_png(cls, path: str) -> "Image":
        with open(path, "rb") as f:
            data = f.read()
        return cls.from_png_bytes(data)

    @classmethod
    def from_png_bytes(cls, data: bytes) -> "Image":
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("not a PNG")
        pos = 8
        width = height = bit_depth = color_type = interlace = 0
        idat = bytearray()
        palette = None
        trns = None
        while pos < len(data):
            (length,) = struct.unpack_from(">I", data, pos)
            ctype = data[pos + 4:pos + 8]
            chunk = data[pos + 8:pos + 8 + length]
            pos += 12 + length  # length + type + data + crc
            if ctype == b"IHDR":
                width, height, bit_depth, color_type, _comp, _filt, interlace = \
                    struct.unpack(">IIBBBBB", chunk)
            elif ctype == b"PLTE":
                palette = chunk
            elif ctype == b"tRNS":
                trns = chunk
            elif ctype == b"IDAT":
                idat += chunk
            elif ctype == b"IEND":
                break
        if interlace != 0:
            raise ValueError("interlaced PNG not supported")
        raw = zlib.decompress(bytes(idat))
        return cls._unfilter(raw, width, height, bit_depth, color_type, palette, trns)

    @staticmethod
    def _unfilter(raw, w, h, bit_depth, color_type, palette, trns) -> "Image":
        if bit_depth != 8:
            raise ValueError(f"unsupported bit depth {bit_depth}")
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
        stride = w * channels
        out = bytearray(h * stride)
        prev = bytearray(stride)
        ipos = 0
        for y in range(h):
            ftype = raw[ipos]; ipos += 1
            line = bytearray(raw[ipos:ipos + stride]); ipos += stride
            if ftype == 0:
                pass
            elif ftype == 1:  # Sub
                for i in range(channels, stride):
                    line[i] = (line[i] + line[i - channels]) & 0xFF
            elif ftype == 2:  # Up
                for i in range(stride):
                    line[i] = (line[i] + prev[i]) & 0xFF
            elif ftype == 3:  # Average
                for i in range(stride):
                    a = line[i - channels] if i >= channels else 0
                    line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
            elif ftype == 4:  # Paeth
                for i in range(stride):
                    a = line[i - channels] if i >= channels else 0
                    b = prev[i]
                    c = prev[i - channels] if i >= channels else 0
                    p = a + b - c
                    pa = abs(p - a); pb = abs(p - b); pc = abs(p - c)
                    pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                    line[i] = (line[i] + pr) & 0xFF
            else:
                raise ValueError(f"bad filter {ftype}")
            out[y * stride:(y + 1) * stride] = line
            prev = line
        # expand to RGBA
        rgba = bytearray(w * h * 4)
        if color_type == 6:
            rgba[:] = out
        elif color_type == 2:  # RGB
            for i in range(w * h):
                rgba[i * 4:i * 4 + 3] = out[i * 3:i * 3 + 3]
                rgba[i * 4 + 3] = 255
        elif color_type == 0:  # grayscale
            for i in range(w * h):
                g = out[i]
                rgba[i * 4] = rgba[i * 4 + 1] = rgba[i * 4 + 2] = g
                rgba[i * 4 + 3] = 255
        elif color_type == 4:  # gray + alpha
            for i in range(w * h):
                g = out[i * 2]; a = out[i * 2 + 1]
                rgba[i * 4] = rgba[i * 4 + 1] = rgba[i * 4 + 2] = g
                rgba[i * 4 + 3] = a
        elif color_type == 3:  # palette
            for i in range(w * h):
                idx = out[i]
                rgba[i * 4] = palette[idx * 3]
                rgba[i * 4 + 1] = palette[idx * 3 + 1]
                rgba[i * 4 + 2] = palette[idx * 3 + 2]
                rgba[i * 4 + 3] = trns[idx] if (trns and idx < len(trns)) else 255
        return Image(w, h, rgba)

    # ---- output -------------------------------------------------------
    def save_png(self, path: str, compress: int = 6) -> None:
        with open(path, "wb") as f:
            f.write(self.to_png_bytes(compress))

    def to_png_bytes(self, compress: int = 6) -> bytes:
        w, h = self.w, self.h
        stride = w * 4
        raw = bytearray()
        for y in range(h):
            raw.append(0)  # filter type 0 (None)
            raw += self.px[y * stride:(y + 1) * stride]
        comp = zlib.compress(bytes(raw), compress)

        def chunk(typ, payload):
            return (struct.pack(">I", len(payload)) + typ + payload +
                    struct.pack(">I", zlib.crc32(typ + payload) & 0xFFFFFFFF))

        ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
                chunk(b"IDAT", comp) + chunk(b"IEND", b""))

    # ---- ops ----------------------------------------------------------
    def copy(self) -> "Image":
        return Image(self.w, self.h, bytearray(self.px))

    def flipped_x(self) -> "Image":
        w, h = self.w, self.h
        out = bytearray(w * h * 4)
        for y in range(h):
            row = self.px[y * w * 4:(y + 1) * w * 4]
            for x in range(w):
                sx = (w - 1 - x) * 4
                out[(y * w + x) * 4:(y * w + x) * 4 + 4] = row[sx:sx + 4]
        return Image(w, h, out)

    def resized(self, new_w: int, new_h: int) -> "Image":
        """Bilinear resize (RGBA). Used to fit oversized sprites (fog, heads) to scale."""
        new_w = max(1, int(new_w)); new_h = max(1, int(new_h))
        if new_w == self.w and new_h == self.h:
            return self.copy()
        sw, sh, sp = self.w, self.h, self.px
        out = bytearray(new_w * new_h * 4)
        x_ratio = sw / new_w
        y_ratio = sh / new_h
        for oy in range(new_h):
            fy = (oy + 0.5) * y_ratio - 0.5
            y0 = int(fy) if fy >= 0 else 0
            if y0 > sh - 1:
                y0 = sh - 1
            y1 = min(y0 + 1, sh - 1)
            wy = fy - y0
            if wy < 0:
                wy = 0.0
            for ox in range(new_w):
                fx = (ox + 0.5) * x_ratio - 0.5
                x0 = int(fx) if fx >= 0 else 0
                if x0 > sw - 1:
                    x0 = sw - 1
                x1 = min(x0 + 1, sw - 1)
                wx = fx - x0
                if wx < 0:
                    wx = 0.0
                p00 = (y0 * sw + x0) * 4
                p01 = (y0 * sw + x1) * 4
                p10 = (y1 * sw + x0) * 4
                p11 = (y1 * sw + x1) * 4
                o = (oy * new_w + ox) * 4
                for c in range(4):
                    top = sp[p00 + c] * (1 - wx) + sp[p01 + c] * wx
                    bot = sp[p10 + c] * (1 - wx) + sp[p11 + c] * wx
                    out[o + c] = int(top * (1 - wy) + bot * wy + 0.5)
        return Image(new_w, new_h, out)

    def tinted(self, rgb, strength: float = 1.0) -> "Image":
        """Multiply each RGB channel by rgb/255, optionally blended with the original.
        Used for team-colour tinting of bodytint/* parts (engine: ColorizeUnit tintable path).
        strength=1.0 → pure multiply; strength<1.0 → lerp(original, multiply_result, strength)."""
        tr, tg, tb = rgb
        out = bytearray(self.px)
        for i in range(0, len(out), 4):
            if out[i + 3] == 0:
                continue
            if strength >= 1.0:
                out[i] = (out[i] * tr) // 255
                out[i + 1] = (out[i + 1] * tg) // 255
                out[i + 2] = (out[i + 2] * tb) // 255
            else:
                mr = (out[i] * tr) // 255
                mg = (out[i + 1] * tg) // 255
                mb = (out[i + 2] * tb) // 255
                out[i] = int(out[i] * (1 - strength) + mr * strength)
                out[i + 1] = int(out[i + 1] * (1 - strength) + mg * strength)
                out[i + 2] = int(out[i + 2] * (1 - strength) + mb * strength)
        return Image(self.w, self.h, out)

    def colorized(self, rgb, strength: float) -> "Image":
        """Additive lerp toward rgb: result = original*(1-s) + rgb*s.
        This is ColorizeUnit's non-tintable overlay path (status effects, exhausted grey).
        Unlike tinted(), the overlay colour is mixed IN rather than multiplied — dark pixels
        become lighter when overlaid with a bright colour."""
        tr, tg, tb = rgb
        s = max(0.0, min(1.0, strength))
        inv = 1.0 - s
        out = bytearray(self.px)
        for i in range(0, len(out), 4):
            if out[i + 3] == 0:
                continue
            out[i]     = int(out[i]     * inv + tr * s + 0.5)
            out[i + 1] = int(out[i + 1] * inv + tg * s + 0.5)
            out[i + 2] = int(out[i + 2] * inv + tb * s + 0.5)
        return Image(self.w, self.h, out)

    def paste(self, src: "Image", x: int, y: int, opacity: float = 1.0) -> None:
        """Source-over alpha composite ``src`` onto self at integer (x, y)."""
        dw, dh = self.w, self.h
        sw, sh = src.w, src.h
        dp, sp = self.px, src.px
        x0 = max(0, x); y0 = max(0, y)
        x1 = min(dw, x + sw); y1 = min(dh, y + sh)
        if x0 >= x1 or y0 >= y1:
            return
        op = max(0.0, min(1.0, opacity))
        for yy in range(y0, y1):
            syy = yy - y
            d_off = (yy * dw + x0) * 4
            s_off = (syy * sw + (x0 - x)) * 4
            for _ in range(x1 - x0):
                sa = sp[s_off + 3]
                if op < 1.0:
                    sa = int(sa * op)
                if sa == 0:
                    d_off += 4; s_off += 4
                    continue
                if sa == 255:
                    dp[d_off] = sp[s_off]
                    dp[d_off + 1] = sp[s_off + 1]
                    dp[d_off + 2] = sp[s_off + 2]
                    dp[d_off + 3] = 255
                else:
                    da = dp[d_off + 3]
                    ia = 255 - sa
                    # premultiplied source-over; oa scaled to 0..255
                    oa = sa + (da * ia + 127) // 255
                    if oa == 0:
                        dp[d_off + 3] = 0
                    else:
                        dca = (da * ia + 127) // 255  # dest alpha weight (0..255)
                        r = (sp[s_off] * sa + dp[d_off] * dca + oa // 2) // oa
                        g = (sp[s_off + 1] * sa + dp[d_off + 1] * dca + oa // 2) // oa
                        b = (sp[s_off + 2] * sa + dp[d_off + 2] * dca + oa // 2) // oa
                        dp[d_off] = r if r < 255 else 255
                        dp[d_off + 1] = g if g < 255 else 255
                        dp[d_off + 2] = b if b < 255 else 255
                        dp[d_off + 3] = oa if oa < 255 else 255
                d_off += 4; s_off += 4
