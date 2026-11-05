"""Mode P (past dates, PHASE4_FORECAST.md 4.4): the best estimate of the atmosphere on a date ERA5 covers, with an honest range.

The first guess is ERA5 at that hour. A small residual network (Engression, noise in front of the network, trained on CRPS) learns
how balloons differ from ERA5: target = balloon - ERA5 on the 44 heights of u, v, T, RH; inputs = the ERA5 profile itself, the
station, the season and the launch hour. Samples are ERA5 + residual draws; a range map fitted on 2021-23 (pooled per
variable x height band, as the balloon calibration in sonde.py) makes the 99 % range hold 99 % of balloons.
Training pairs: IGRA 00Z and 12Z soundings at Santa Teresa and Midland paired with ERA5 at the nearest grid point and the same hour.
Everything here is for the pilot box; the model is only as good as ~40,000 soundings allow, so it is small.
"""
import numpy as np
import pandas as pd
import xarray as xr

from tempest.calibrate import spread, station
from tempest.profiles.to_heights import HEIGHTS, PROFILE

NV, NH = len(PROFILE), len(HEIGHTS)
D = NV * NH  # 176 profile columns
BANDS = [(0, 1000), (1000, 5000), (5000, 12000), (12000, 18001)]
COND_NAMES = ["station", "doy_sin", "doy_cos", "hour12"] + [f"era_{i}" for i in range(D)]
COND_NAMES_TEND = COND_NAMES + [f"tend_{i}" for i in range(D)]


def load_pairs(profiles, igra, first=1991, last=2025, tendency=False):
    """-> dict(time, station, hour12, era (S, 4, 44), obs (S, 4, 44)) for soundings with a complete ERA5 and balloon profile."""
    ds = xr.open_zarr(profiles)
    keep = []
    for s, (sid, (lat, lon)) in enumerate(station.STATIONS.items()):
        t, prof, _ = station.read_igra(f"{igra}/{sid}-drvd.txt.zip", first, last)
        pt = station.nearest_point(ds, lat, lon)
        era = station.era5_at(ds, pt, t)
        ok = np.isfinite(era).all((1, 2)) & np.isfinite(prof).all((1, 2))
        row = dict(time=t[ok], station=np.full(int(ok.sum()), s), era=era[ok], obs=prof[ok])
        if tendency:  # ERA5 one hour after the nominal launch minus at it: a balloon climbs for ~90 min, so the air it sampled is not the launch-hour air
            nxt = station.era5_at(ds, pt, t + pd.Timedelta(hours=1))
            ok2 = ok & np.isfinite(nxt).all((1, 2))
            row = dict(time=t[ok2], station=np.full(int(ok2.sum()), s), era=era[ok2], obs=prof[ok2], tend=(nxt - era)[ok2])
        keep.append(row)
    out = {k: np.concatenate([x[k] for x in keep]) for k in ("station", "era", "obs") + (("tend",) if tendency else ())}
    out["time"] = pd.DatetimeIndex(np.concatenate([x["time"].values for x in keep]))
    out["hour12"] = (out["time"].hour == 12).astype(np.float32)
    return out


def cond_matrix(d):
    """Network inputs: station, season harmonics, launch hour, and the ERA5 profile."""
    a = 2 * np.pi * d["time"].dayofyear.to_numpy() / 365.25
    head = np.stack([d["station"], np.sin(a), np.cos(a), d["hour12"]], 1).astype(np.float32)
    parts = [head, d["era"].reshape(len(head), D).astype(np.float32)]
    if "tend" in d:
        parts.append(d["tend"].reshape(len(head), D).astype(np.float32))
    return np.concatenate(parts, 1)


def residual(d):
    return (d["obs"] - d["era"]).reshape(len(d["era"]), D).astype(np.float32)


def groups():
    """(176,) group id per column: variable x height band."""
    g = np.zeros(D, int)
    for v in range(NV):
        for b, (lo, hi) in enumerate(BANDS):
            g[v * NH:(v + 1) * NH][(HEIGHTS >= lo) & (HEIGHTS < hi)] = v * len(BANDS) + b
    return g


def names():
    return [(PROFILE[v], f"{lo / 1000:g}-{min(hi, 18000) / 1000:g} km", np.isin(np.arange(D), np.flatnonzero(groups() == v * len(BANDS) + b)))
            for v in range(NV) for b, (lo, hi) in enumerate(BANDS)]


def to_physical(era_flat, res):
    """ERA5 (S, 176) + residual samples (S, m, 176) -> profile samples with RH held to 0-100 %."""
    x = era_flat[:, None, :] + res
    i = PROFILE.index("RH") * NH
    x[..., i:i + NH] = np.clip(x[..., i:i + NH], 0, 100)
    return x


def fit_calibration(samples, truth, rng):
    """Pooled range map (one per variable x band) from 2021-23 samples (S, m, 176) and balloons (S, 176)."""
    z, u = spread.parts(samples, truth, keep=samples.shape[1], rng=rng)
    t = spread.table(z, u, groups())
    t["m"] = np.array(samples.shape[1])
    return t
