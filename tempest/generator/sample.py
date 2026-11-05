"""Draw profiles from a trained generator checkpoint."""
import numpy as np
import torch

from tempest.generator.model import Generator
from tempest.profiles.diff import from_diff
from tempest.profiles.to_heights import HEIGHTS, PROFILE

SURFACE = ["t2m", "sp", "rh2m"]  # same order as build_dataset.SURFACE


def to_physical(raw: np.ndarray) -> np.ndarray:
    """(..., 179) raw targets (differences) -> (..., 179) physical: 4 x 44 profile values, then t2m, sp, rh2m.
    Range rule: RH and rh2m clipped to 0-100 %. No lapse-rate cap: the 13-level ERA5 training profiles
    themselves cool faster than dry-adiabatic up to ~2 km on hot afternoons (interpolation from 2 m), so a
    cap would fight the training data; revisit after the CDS boundary-layer merge."""
    n, p = len(HEIGHTS), len(PROFILE)
    prof = from_diff(raw[..., :n * p].reshape(*raw.shape[:-1], p, n))
    return clip_ranges(np.concatenate([prof.reshape(*raw.shape[:-1], n * p), raw[..., n * p:]], axis=-1))


def clip_ranges(phys: np.ndarray) -> np.ndarray:
    """(..., 179) physical values -> same with RH and rh2m clipped to 0-100 % (in place)."""
    n = len(HEIGHTS)
    i = PROFILE.index("RH") * n
    phys[..., i:i + n] = np.clip(phys[..., i:i + n], 0, 100)
    j = n * len(PROFILE) + SURFACE.index("rh2m")
    phys[..., j] = np.clip(phys[..., j], 0, 100)
    return phys


def standard_pressure(z):
    """Standard-atmosphere pressure (Pa) at elevation z (m). Subtracted from the sp target in training, so the
    model learns weather (~500 Pa) instead of re-learning elevation (~10,000 Pa across the box)."""
    return 101325.0 * (1 - 2.25577e-5 * np.asarray(z, np.float64)) ** 5.25588


def to_site(phys: np.ndarray, z_grid, z_site) -> np.ndarray:
    """(..., 179) physical values at the ERA5 grid elevation -> surface T and pressure at the site elevation (in
    place): standard lapse rate for t2m, hypsometric equation for sp. Profiles are above ground, so they stay."""
    dz = np.asarray(z_site, np.float64) - np.asarray(z_grid, np.float64)
    j = len(HEIGHTS) * len(PROFILE)
    t = phys[..., j + SURFACE.index("t2m")]
    phys[..., j + SURFACE.index("sp")] *= np.exp(-9.80665 * dz / (287.05 * (t - 0.0065 * dz / 2)))
    phys[..., j + SURFACE.index("t2m")] = t - 0.0065 * dz
    return phys


class Sampler:
    """Loads one trained model, or an ensemble file {"members": [...]}; samples are split evenly over members."""

    def __init__(self, ckpt, device=None):
        if not isinstance(ckpt, dict):
            ckpt = torch.load(ckpt, map_location="cpu", weights_only=True)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.members = []
        for k in ckpt.get("members", [ckpt]):
            c = k["cfg"]
            model = Generator(k["n_cond"], k["n_out"], c["noise_dim"], c["width"], c["depth"], linear_cols=k.get("linear_cols"))
            model.load_state_dict(k["state"])
            self.members.append((model.to(self.device).eval(), {n: v.to(self.device) for n, v in k["norm"].items()}))
        self.sp_offset = ckpt.get("members", [ckpt])[0].get("sp_offset")  # [target col, cond col], or None (old files)

    @torch.inference_mode()
    def __call__(self, cond: np.ndarray) -> np.ndarray:
        """cond (N, F) raw features, one row per sample (drivers already drawn) -> (N, D) raw targets.
        Row i goes to member i % K, so repeated rows (one query, many samples) are shared evenly."""
        c = torch.as_tensor(cond, dtype=torch.float32, device=self.device)
        out = torch.empty(len(c), self.members[0][0].head[-1].out_features, device=self.device)
        for i, (model, n) in enumerate(self.members):
            out[i::len(self.members)] = model((c[i::len(self.members)] - n["cm"]) / n["cs"], 1)[:, 0] * n["ts"] + n["tm"]
        out = out.cpu().numpy()
        if self.sp_offset is not None:
            j, e = self.sp_offset
            out[:, j] += standard_pressure(cond[:, e]).astype(np.float32)
        return out

    def profiles(self, cond: np.ndarray) -> np.ndarray:
        """Like __call__, but physical profiles with the range rules applied (see to_physical)."""
        return to_physical(self(cond))
