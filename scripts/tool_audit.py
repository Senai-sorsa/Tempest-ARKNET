"""IL-171 (2026-11-10): END-TO-END audit of the SHIPPED tool. Checks that what the bundled assets actually serve matches what the logs claim, without trusting any checkpoint score.
For each region (NM/TX, Denver) and each part of the day (DAY file, NIGHT file) it takes held-out 2024-25 rows that lie exactly on a grid point, asks the real tool
(tempest_weather.api.atmosphere_set, climate mode, naive time = local solar time) for 199 atmospheres at that place, solar hour and date, and scores them against the ERA5
truth row with the ensemble CRPS, next to a climatology ensemble (199 training-year rows <= 2020 of the same grid point x month x 2-hour bin, as score.py does).
Prints per region / part of day: rows served, rows REFUSED (and why), CRPS skill vs climatology for u, v, T (all heights) and t2m, and the 90 % coverage.
A skill near or below 0, or refusals, means the shipped tool does not deliver what was verified. CPU only, memory-mapped data (about 1-2 GB RAM).
Usage: PYTHONPATH=. python -W ignore scripts/tool_audit.py [--rows 120] [--seed 0] [--out docs/results/logs/tool_audit.log]"""
import argparse
import math
from datetime import datetime, timedelta

import numpy as np

from tempest.generator.features import FEATURES
from tempest.generator.sample import to_physical
from tempest.profiles.to_heights import HEIGHTS, PROFILE
from tempest.scoring.score import group_keys
from tempest_weather import api

N = len(HEIGHTS)
SETS = [("NM/TX", "day", "data/train/pilot80_dpd.npz"), ("NM/TX", "night", "data/train/pilot80_l21_night_dpd.npz"),
        ("Denver", "day", "data/train/denver_full_dpd.npz"), ("Denver", "night", "data/train/denver_full_fill_night_dpd.npz")]


def crps(x, y):
    """x (m, D) ensemble, y (D,) -> (D,) ensemble CRPS (sorted-sample formula)."""
    m = x.shape[0]
    xs = np.sort(x, 0)
    a = np.abs(xs - y).mean(0)
    w = (2 * np.arange(1, m + 1) - m - 1)[:, None]
    return a - (w * xs).sum(0) / (m * m)


def when_of(c):
    """Feature row -> naive local-solar datetime (year, day of year, solar hour)."""
    f = {k: float(c[FEATURES.index(k)]) for k in ("doy_sin", "doy_cos", "hour_sin", "hour_cos", "year")}
    doy = (math.atan2(f["doy_sin"], f["doy_cos"]) % (2 * math.pi)) / (2 * math.pi) * 365.25
    hour = (math.atan2(f["hour_sin"], f["hour_cos"]) % (2 * math.pi)) / (2 * math.pi) * 24
    return datetime(int(round(f["year"])), 1, 1) + timedelta(days=int(doy)) + timedelta(hours=round(hour * 4) / 4)


def tool_columns(atm):
    """Tool atmosphere -> (m, 3N + 1) array: u, v, T at the model heights and t2m."""
    return np.concatenate([np.asarray(atm["u"], float), np.asarray(atm["v"], float), np.asarray(atm["T"], float), np.asarray(atm["t2m"], float).reshape(-1, 1)], 1)


def truth_columns(p):
    iu, iv, it = (PROFILE.index(k) * N for k in ("u", "v", "T"))
    return np.concatenate([p[..., iu:iu + N], p[..., iv:iv + N], p[..., it:it + N], p[..., 4 * N:4 * N + 1]], -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=120)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="docs/results/logs/tool_audit.log")
    a = ap.parse_args()
    lines = [f"tool audit {datetime.now():%Y-%m-%d %H:%M}, {a.rows} held-out 2024-25 rows per set, 199 atmospheres per row, seed {a.seed}"]
    for region, part, path in SETS:
        d = np.load(path, mmap_mode="r")
        cond, year = np.asarray(d["cond"]), np.asarray(d["year"])
        keys = group_keys(cond)
        rng = np.random.default_rng(a.seed)
        held = np.flatnonzero((year >= 2024) & (year <= 2025))
        va = np.sort(rng.choice(held, min(a.rows, len(held)), replace=False))
        tr = np.flatnonzero(year <= 2020)
        tr = tr[np.argsort(keys[tr], kind="stable")]
        refused, served, sc_t, sc_c, cov = {}, 0, [], [], []
        for r in va:
            c = cond[r]
            lat, lon = float(c[FEATURES.index("lat")]), float(c[FEATURES.index("lon")])
            try:
                atm, info = api.atmosphere_set(lat, lon, when_of(c).isoformat(), n=199, seed=int(r) % 100000, mode="ai")
            except ValueError as e:
                msg = str(e).split(":")[0][:70] if "outside" not in str(e) else str(e)[:70]
                refused[msg] = refused.get(msg, 0) + 1
                continue
            lo, hi = np.searchsorted(keys[tr], keys[r], "left"), np.searchsorted(keys[tr], keys[r], "right")
            if hi <= lo:
                continue
            clim = to_physical(np.asarray(d["target"][np.sort(rng.choice(tr[lo:hi], 199, replace=hi - lo < 199))]))
            y = truth_columns(to_physical(np.asarray(d["target"][r:r + 1]))[0])
            x = tool_columns(atm)
            sc_t.append(crps(x, y)); sc_c.append(crps(truth_columns(clim), y))
            q = np.quantile(x, [0.05, 0.95], axis=0)
            cov.append((y >= q[0]) & (y <= q[1]))
            served += 1
        lines.append(f"{region:6s} {part:5s} ({path.split('/')[-1]}): served {served}, refused {sum(refused.values())} {refused if refused else ''}")
        if served:
            t, cl, cv = np.array(sc_t), np.array(sc_c), np.array(cov)
            parts = []
            for name, sl in (("u", slice(0, N)), ("v", slice(N, 2 * N)), ("T", slice(2 * N, 3 * N)), ("t2m", slice(3 * N, 3 * N + 1))):
                parts.append(f"{name} skill {1 - t[:, sl].mean() / cl[:, sl].mean():+.3f} cov90 {cv[:, sl].mean():.2f}")
            lines.append("         " + " | ".join(parts) + f" | ALL skill {1 - t.mean() / cl.mean():+.3f}")
        print(lines[-2] if served else lines[-1], flush=True)
        if served:
            print(lines[-1], flush=True)
    with open(a.out, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n")


if __name__ == "__main__":
    main()
