"""RGBA image core backed by NumPy + Pillow.

Public API matches the old stdlib implementation: ``w``/``h``, flat mutable
``px`` (length ``w*h*4``), and ``new`` / ``load_png`` / ``paste`` / ``tinted`` /
``colorized`` / ``resized`` / ``flipped_x`` / ``save_png``.
"""
from __future__ import annotations

from typing import Optional, Union

import numpy as np
from PIL import Image as PILImage

Buffer = Union[bytes, bytearray, memoryview, np.ndarray]


class Image:
    __slots__ = ("_arr",)

    def __init__(self, w: int, h: int, px: Optional[Buffer] = None):
        w, h = int(w), int(h)
        if px is None:
            self._arr = np.zeros((h, w, 4), dtype=np.uint8)
        else:
            arr = np.asarray(px, dtype=np.uint8)
            if arr.ndim == 3 and arr.shape == (h, w, 4):
                self._arr = np.ascontiguousarray(arr)
            else:
                flat = np.ascontiguousarray(arr).reshape(-1)
                assert flat.size == w * h * 4, (flat.size, w * h * 4)
                self._arr = flat.reshape(h, w, 4).copy()

    # ---- shape / buffer -------------------------------------------------
    @property
    def w(self) -> int:
        return int(self._arr.shape[1])

    @property
    def h(self) -> int:
        return int(self._arr.shape[0])

    @property
    def px(self) -> np.ndarray:
        """Flat mutable RGBA view (length ``w*h*4``), for legacy callers."""
        return self._arr.reshape(-1)

    @property
    def arr(self) -> np.ndarray:
        """HxWx4 uint8 array (shared storage)."""
        return self._arr

    # ---- construction -------------------------------------------------
    @classmethod
    def new(cls, w: int, h: int, rgba=(0, 0, 0, 0)) -> "Image":
        img = cls(w, h)
        if rgba != (0, 0, 0, 0):
            img._arr[:] = np.asarray(rgba, dtype=np.uint8)
        return img

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "Image":
        arr = np.array(arr, dtype=np.uint8, copy=True, order="C")
        assert arr.ndim == 3 and arr.shape[2] == 4, arr.shape
        img = cls.__new__(cls)
        img._arr = arr
        return img

    @classmethod
    def from_pil(cls, pil: PILImage.Image) -> "Image":
        return cls.from_array(np.asarray(pil.convert("RGBA")))

    def to_pil(self) -> PILImage.Image:
        return PILImage.fromarray(self._arr, mode="RGBA")

    @classmethod
    def load_png(cls, path: str) -> "Image":
        with PILImage.open(path) as im:
            return cls.from_pil(im)

    @classmethod
    def from_png_bytes(cls, data: bytes) -> "Image":
        from io import BytesIO
        with PILImage.open(BytesIO(data)) as im:
            return cls.from_pil(im)

    # ---- output -------------------------------------------------------
    def save_png(self, path: str, compress: int = 6) -> None:
        # Pillow: compress_level 0..9 (zlib); map our old zlib level directly.
        level = max(0, min(9, int(compress)))
        self.to_pil().save(path, format="PNG", compress_level=level)

    def to_png_bytes(self, compress: int = 6) -> bytes:
        from io import BytesIO
        buf = BytesIO()
        level = max(0, min(9, int(compress)))
        self.to_pil().save(buf, format="PNG", compress_level=level)
        return buf.getvalue()

    # ---- ops ----------------------------------------------------------
    def copy(self) -> "Image":
        return Image.from_array(self._arr.copy())

    def flipped_x(self) -> "Image":
        return Image.from_array(np.ascontiguousarray(self._arr[:, ::-1, :]))

    def resized(self, new_w: int, new_h: int) -> "Image":
        """Bilinear resize (RGBA)."""
        new_w = max(1, int(new_w))
        new_h = max(1, int(new_h))
        if new_w == self.w and new_h == self.h:
            return self.copy()
        return Image.from_pil(
            self.to_pil().resize((new_w, new_h), resample=PILImage.Resampling.BILINEAR)
        )

    def tinted(self, rgb, strength: float = 1.0) -> "Image":
        """Multiply each RGB channel by rgb/255, optionally blended with the original."""
        tr, tg, tb = rgb
        out = self._arr.astype(np.float32)
        a = out[..., 3] > 0
        mul = out.copy()
        mul[..., 0] = out[..., 0] * (tr / 255.0)
        mul[..., 1] = out[..., 1] * (tg / 255.0)
        mul[..., 2] = out[..., 2] * (tb / 255.0)
        if strength >= 1.0:
            result = mul
        else:
            s = float(strength)
            result = out * (1.0 - s) + mul * s
            result[..., 3] = out[..., 3]
        result[~a, :3] = out[~a, :3]
        return Image.from_array(np.clip(result, 0, 255).astype(np.uint8))

    def colorized(self, rgb, strength: float) -> "Image":
        """Additive lerp toward rgb: result = original*(1-s) + rgb*s."""
        tr, tg, tb = rgb
        s = max(0.0, min(1.0, float(strength)))
        inv = 1.0 - s
        out = self._arr.astype(np.float32)
        a = out[..., 3] > 0
        out[a, 0] = out[a, 0] * inv + tr * s
        out[a, 1] = out[a, 1] * inv + tg * s
        out[a, 2] = out[a, 2] * inv + tb * s
        return Image.from_array(np.clip(np.rint(out), 0, 255).astype(np.uint8))

    def multiply_alpha(self, factor: float) -> "Image":
        """Return a copy with all alphas multiplied by ``factor`` (0..1)."""
        out = self._arr.copy()
        a = max(0.0, min(1.0, float(factor)))
        out[..., 3] = np.clip(np.rint(out[..., 3].astype(np.float32) * a), 0, 255).astype(np.uint8)
        return Image.from_array(out)

    def paste(self, src: "Image", x: int, y: int, opacity: float = 1.0) -> None:
        """Source-over alpha composite ``src`` onto self at integer (x, y).

        Composites only the overlapping ROI through Pillow's C ``alpha_composite``
        so large canvases stay fast (full-buffer round-trips would dominate).
        """
        op = max(0.0, min(1.0, float(opacity)))
        if op <= 0.0:
            return
        if op < 1.0:
            src = src.multiply_alpha(op)

        x, y = int(x), int(y)
        dw, dh = self.w, self.h
        sw, sh = src.w, src.h
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(dw, x + sw)
        y1 = min(dh, y + sh)
        if x0 >= x1 or y0 >= y1:
            return
        sx0 = x0 - x
        sy0 = y0 - y
        cw, ch = x1 - x0, y1 - y0

        dst_roi = PILImage.fromarray(self._arr[y0:y1, x0:x1], mode="RGBA")
        src_roi = PILImage.fromarray(
            src._arr[sy0:sy0 + ch, sx0:sx0 + cw], mode="RGBA"
        )
        dst_roi.alpha_composite(src_roi, dest=(0, 0))
        self._arr[y0:y1, x0:x1] = np.asarray(dst_roi, dtype=np.uint8)
