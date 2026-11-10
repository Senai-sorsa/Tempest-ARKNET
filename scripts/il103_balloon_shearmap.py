"""IL-103 (2026-11-10, L18): fit the shear tail on BALLOONS, not ERA5. The shipped shear map makes the model's neighbour-height shear match ERA5's, but ERA5 is about 1.7x smoother than real
balloons and the model's free-troposphere p99 shear is about 20 % below the balloons (il103_balloon_shear.py, 2026-11-08). Here: a SECOND shear map (tempest.calibrate.shear_map.fit, the
same method) fitted so the INSTALLED tool's shear quantiles match EPZ (72364) + MAF (72265) balloons of 2005-2020 at 00Z and 12Z, applied on top of the tool's output; judged on the held-out
2024-25 balloons: shear quantiles p50 / p99 / p99.9 by band (model, model + balloon map, balloons) and the CRPS of u and v at all 44 heights (a map that only fattens the tail but costs CRPS
is no win). Climate mode, the tool's own samples at the station. CPU only.
    PYTHONPATH=. python -W ignore scripts/il103_balloon_shearmap.py [--fit-per-group 800] [--out docs/results/logs/il103_balloon_shearmap.log]"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest.calibrate import shear_map, station   # noqa: E402
from tempest.scoring.score import crps_ensemble   # noqa: E402
from tempest_weather import _core, api   # noqa: E402

H = np.asarray(_core.HEIGHTS, float)
NH = len(H)


def balloons(sid):
    d = np.load(os.path.join(REPO, "data", "igra_heights", sid + ".npz"))
    sel = np.array([int(np.argmin(np.abs(d["heights"] - h))) for h in H])
    u, v = d["u"][:, sel].astype(float), d["v"][:, sel].astype(float)
    ok = ~((u == -32768) | (v == -32768)).any(1)
    return pd.DatetimeIndex(d["time"].astype("datetime64[ns]"))[ok], np.concatenate([u[ok], v[ok]], 1) * 0.1


def tool_uv(sid, t, seed):
    lat, lon = station.STATIONS[sid]
    atm, _ = api.atmosphere_set(lat, lon, t.isoformat() + "+00:00", n=199, seed=seed, mode="ai", elevation=station.ELEV[sid])
    return np.concatenate([np.asarray(atm["u"]), np.asarray(atm["v"])], 1)


def collect(years, per_group, rng):
    xs, ys = [], []
    for sid in ("USM00072364", "USM00072265"):
        t, uv = balloons(sid)
        for hh in (0, 12):
            idx = np.flatnonzero((t.year >= years[0]) & (t.year <= years[1]) & (t.hour == hh))
            idx = np.sort(rng.choice(idx, min(per_group, len(idx)), replace=False))
            for k in idx:
                try:
                    xs.append(tool_uv(sid, t[k], int(k)))
                    ys.append(uv[k])
                except ValueError:
                    continue
    return np.stack(xs).astype(np.float32), np.stack(ys).astype(np.float32)


def shear_q(uv, q):
    s = shear_map.shears(uv.reshape(*uv.shape[:-1], 2, NH).astype(np.float64))[1]
    flat = s.reshape(-1, s.shape[-1])
    return [np.quantile(flat[:, shear_map.BAND_OF_LAYER == b], q) for b in range(4)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit-per-group", type=int, default=800)
    ap.add_argument("--test-per-group", type=int, default=800)
    ap.add_argument("--test-years", type=int, nargs=2, default=[2024, 2025], help="IL-194: held-out balloon years (default 2024 2025 = as before; 2021 2022 = before the 2023 sonde change)")
    ap.add_argument("--out", default="docs/results/logs/il103_balloon_shearmap.log")
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    xf, yf = collect((2005, 2020), a.fit_per_group, rng)
    table = shear_map.fit(xf, yf)
    np.savez(os.path.join(REPO, "models", "il103_balloon_shearmap.npz"), **table)
    xt, yt = collect(tuple(a.test_years), a.test_per_group, rng)
    xb = shear_map.apply(table, xt)
    lines = [f"IL-103 balloon-fitted shear map: fit {len(yf)} balloons 2005-20, test {len(yt)} balloons {a.test_years[0]}-{a.test_years[1]} (EPZ + MAF, 00Z + 12Z), installed tool, climate mode",
             "shear (m/s per km) p50 / p99 / p99.9 by band: model | model + balloon map | balloons"]
    qs = [0.5, 0.99, 0.999]
    qm, qb, qo = shear_q(xt, qs), shear_q(xb, qs), shear_q(yt[:, None, :], qs)
    for b, name in enumerate(("0-1 km", "1-5 km", "5-12 km", "12-18 km")):
        lines.append(f"  {name:8s} " + " | ".join("/".join(f"{x:.1f}" for x in q[b]) for q in (qm, qb, qo)))
    c0, c1 = crps_ensemble(xt, yt), crps_ensemble(xb, yt)
    for name, sl in (("u", slice(0, NH)), ("v", slice(NH, 2 * NH))):
        for bn, (lo, hi) in (("0-1 km", (0, 1000)), ("1-5 km", (1000, 5000)), ("5-12 km", (5000, 12000)), ("12-18 km", (12000, 18001))):
            j = np.flatnonzero((H >= lo) & (H < hi))
            a0, a1 = c0[:, sl][:, j].mean(), c1[:, sl][:, j].mean()
            lines.append(f"  CRPS {name} {bn:8s} model {a0:.3f} -> + balloon map {a1:.3f} ({100 * (a1 / a0 - 1):+.1f} %)")
    print("\n".join(lines), flush=True)
    with open(a.out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n\n")


if __name__ == "__main__":
    main()
