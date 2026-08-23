"""System.Random (.NET Framework classic) + XXHash32 stand-ins.

IL2CPP on many Unity builds still ships the Framework subtractive RNG
(MBIG/MSEED/55-cell SeedArray). Dump RVAs for Random in this Mach-O are
misaligned, so we mirror the published Framework algorithm rather than the
broken disasm windows.
"""
from __future__ import annotations

from typing import List, TypeVar

T = TypeVar("T")

MBIG = 0x7FFFFFFF  # Int32.MaxValue
MSEED = 161803398


class SystemRandom:
    """System.Random — Framework algorithm (ctor(int), Next, NextDouble, Sample)."""

    def __init__(self, seed: int = 0) -> None:
        self.inext = 0
        self.inextp = 0
        self.SeedArray = [0] * 56
        self._seed(int(seed))

    def _seed(self, Seed: int) -> None:
        subtraction = MBIG if Seed == -0x80000000 else abs(Seed)
        mj = MSEED - subtraction
        self.SeedArray[55] = mj
        mk = 1
        for i in range(1, 55):
            ii = (21 * i) % 55
            self.SeedArray[ii] = mk
            mk = mj - mk
            if mk < 0:
                mk += MBIG
            mj = self.SeedArray[ii]
        for _ in range(1, 5):
            for i in range(1, 56):
                self.SeedArray[i] -= self.SeedArray[1 + (i + 30) % 55]
                if self.SeedArray[i] < 0:
                    self.SeedArray[i] += MBIG
        self.inext = 0
        self.inextp = 21

    def InternalSample(self) -> int:
        locINext = self.inext
        locINextp = self.inextp
        locINext += 1
        if locINext >= 56:
            locINext = 1
        locINextp += 1
        if locINextp >= 56:
            locINextp = 1
        retVal = self.SeedArray[locINext] - self.SeedArray[locINextp]
        if retVal == MBIG:
            retVal -= 1
        if retVal < 0:
            retVal += MBIG
        self.SeedArray[locINext] = retVal
        self.inext = locINext
        self.inextp = locINextp
        return retVal

    def Sample(self) -> float:
        return self.InternalSample() * (1.0 / MBIG)

    def Next(self, minValue: int | None = None, maxValue: int | None = None) -> int:
        """Overloads: Next() | Next(maxValue) | Next(minValue, maxValue)."""
        if minValue is None and maxValue is None:
            return self.InternalSample()
        if maxValue is None:
            # Next(maxValue) — minValue holds the max
            max_exclusive = int(minValue)  # type: ignore[arg-type]
            if max_exclusive < 0:
                raise ValueError("maxValue must be non-negative")
            if max_exclusive == 0:
                return 0
            return int(self.Sample() * max_exclusive)
        # Next(min, max)
        lo, hi = int(minValue), int(maxValue)  # type: ignore[arg-type]
        if lo > hi:
            raise ValueError("minValue > maxValue")
        rng = hi - lo
        if rng == 0:
            return lo
        if rng <= MBIG:
            return lo + int(self.Sample() * rng)
        # large range path (simplified)
        return lo + int(self.GetSampleForLargeRange() * rng)

    def GetSampleForLargeRange(self) -> float:
        result = self.InternalSample()
        if self.InternalSample() % 2 == 0:
            result = -result
        d = result
        d += MBIG - 1
        return d / (2.0 * MBIG - 1.0)

    def NextDouble(self) -> float:
        return self.Sample()

    def NextFloat(self) -> float:
        return float(self.Sample())


class XXHash:
    """xxHash32-ish deterministic stream (Phase 2 stand-in for game XXHash)."""

    def __init__(self, seed: int = 0) -> None:
        self._state = int(seed) & 0xFFFFFFFF

    def _mix(self) -> int:
        self._state = (self._state * 0x9E3779B1 + 0x85EBCA77) & 0xFFFFFFFF
        x = self._state
        x ^= (x >> 16)
        x = (x * 0x85EBCA6B) & 0xFFFFFFFF
        x ^= (x >> 13)
        x = (x * 0xC2B2AE35) & 0xFFFFFFFF
        x ^= (x >> 16)
        return x

    def NextFloat(self) -> float:
        return (self._mix() & 0xFFFFFF) / float(0x1000000)

    def Next(self, max_value: int) -> int:
        if max_value <= 0:
            return 0
        return self._mix() % max_value


def fisher_yates_shuffle(rng: SystemRandom, items: List[T]) -> None:
    n = len(items)
    for i in range(n - 1, 0, -1):
        j = rng.Next(i + 1)
        items[i], items[j] = items[j], items[i]
