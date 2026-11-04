"""Surface value + neighbour differences, the representation the generator and calibration work in."""
import numpy as np


def to_diff(profiles: np.ndarray) -> np.ndarray:
    """(..., levels) heights-ordered values -> (..., levels): [surface value, 43 neighbour differences]."""
    return np.concatenate([profiles[..., :1], np.diff(profiles, axis=-1)], axis=-1)


def from_diff(d: np.ndarray) -> np.ndarray:
    """Inverse of to_diff: sum the differences up from the surface."""
    return np.cumsum(d, axis=-1)
