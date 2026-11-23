"""Bilinear lookup of the change in Cx over Mach and log Reynolds ratio. Standard library only: runs in FS's venv too."""
from bisect import bisect_right


def _cell(axis: list[float], x: float) -> tuple[int, float]:
    """Cell holding x and the fraction across it, held at the axis ends."""
    i = min(max(bisect_right(axis, x) - 1, 0), len(axis) - 2)
    return i, min(max((x - axis[i]) / (axis[i + 1] - axis[i]), 0.0), 1.0)


class Surface:
    def __init__(self, keys: list[float], machs: list[float], dcx: list[list[float]]) -> None:
        """keys: strictly rising log Reynolds ratio; dcx[key][mach]."""
        if any(b <= a for a, b in zip(keys, keys[1:])) or any(b <= a for a, b in zip(machs, machs[1:])):
            raise ValueError("Surface axes must rise strictly")
        self.keys, self.machs, self.dcx = keys, machs, dcx

    def __call__(self, key: float, mach: float) -> float:
        i, u = _cell(self.keys, key)
        j, v = _cell(self.machs, mach)
        a, b = self.dcx[i], self.dcx[i + 1]
        low = a[j] + v * (a[j + 1] - a[j])
        return low + u * (b[j] + v * (b[j + 1] - b[j]) - low)
