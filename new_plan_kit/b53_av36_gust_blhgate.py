"""New_Plan 13 AV36: AV12 (MISS 2026-11-14: clock gate solar 10-18 h = 00Z launches only; MAF +1.99 % [+0.44, +3.48], ELP / EPZ +4.21 %) with the gate set by BOUNDARY-LAYER
DEPTH instead of the clock: the gust predictor is used only when the ERA5 boundary-layer height (blh) at the launch hour is >= 1000 m (above the 750 m top of the truth layer).
blh = data/raw/era5_em/blh.zarr, nearest 0.25 deg grid point to the balloon station. Everything else as AV12 (new_plan_kit/b51_av12_gust_daygate.py: truth = balloon mean speed
300 / 500 / 750 m; predictors ws10 and physical gust excess; least squares fitted on 2016-2020 gated cases, tested on 2021-2023 gated cases; outside the gate the plain 10 m model
is used; paired bootstrap 2000 draws, 95 %). Stations MAF + 72265 (main), ELP ASOS + EPZ 72364 (check).
Rule written 2026-11-14 before any AV36 run (New_Plan 13 AV36 row, unchanged):
PASS: MAF gated MAE gain >= 2 % with the 95 % interval excluding 0, AND the ELP / EPZ gated gain > 0.
KILL: MAF gated gain under 1 %.
Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b53_av36_gust_blhgate.py
Result: docs/results/logs/kit_b53_av36_gust_blhgate.log
"""
import os

import numpy as np
import pandas as pd

import kit_common as K
from b51_av12_gust_daygate import SITES, errors, gain_ci, judge, station_cases

NAME = "b53_av36_gust_blhgate"
BLH = os.path.join(K.REPO, "data", "raw", "era5_em", "blh.zarr")
MIN_BLH = 1000.0


def blh_at(lat, lon, times):
    import xarray as xr
    b = xr.open_zarr(BLH)["blh"]
    glon = np.where(b.longitude.values > 180, b.longitude.values - 360, b.longitude.values)
    i, j = int(np.abs(b.latitude.values - lat).argmin()), int(np.abs(glon - lon).argmin())
    assert abs(b.latitude.values[i] - lat) <= 0.125 and abs(glon[j] - lon) <= 0.125, "station outside the blh grid"
    s = pd.Series(b.isel(latitude=i, longitude=j).values, index=pd.DatetimeIndex(b.valid_time.values))
    return s.reindex(times.floor("h")).values


def main():
    from tempest.calibrate import station
    rng = np.random.default_rng(0)
    lines, res = [], {}
    for asos, sid in SITES:
        j = station_cases(asos, sid)
        lat, lon = station.STATIONS[sid]
        j["blh"] = blh_at(lat, lon, j.index)
        j = j[np.isfinite(j.blh)].copy()
        j["gate"] = j.blh >= MIN_BLH
        test, out = errors(j)
        g = test.gate.values
        ae_a, ae_b = out["a"][1][g], out["b"][1][g]
        gain, lo, hi = gain_ci(ae_a, ae_b, rng)
        res[asos] = (gain, lo, hi)
        hrs = pd.Series(j.index.hour[j.gate]).value_counts().sort_index()
        lines.append(f"{asos} ASOS + {sid} balloons: {len(j)} matched launches 2016-23 with blh, gated (blh >= {MIN_BLH:.0f} m) {int(j.gate.sum())} "
                     f"(UTC hours: {', '.join(f'{h:02d}Z {n}' for h, n in hrs.items())}); test 2021-23 gated {int(g.sum())}, outside {int((~g).sum())}")
        lines.append(f"  median blh gated {j.blh[j.gate].median():.0f} m, not gated {j.blh[~j.gate].median():.0f} m; mean speed aloft (test, gated) {test.aloft.values[g].mean():.2f} m/s")
        lines.append(f"  MAE ws10 {ae_a.mean():.3f} -> ws10 + gust excess {ae_b.mean():.3f} m/s; gain {gain:+.2f} % (95 % interval {lo:+.2f} to {hi:+.2f}); "
                     f"coefficients b {np.round(out['b'][0], 3)}")
    lines.append("AV36 rule (pre-set): PASS = MAF gated gain >= 2 % with interval > 0 AND ELP / EPZ gated gain > 0; KILL = MAF gated gain < 1 %; else MISS.")
    lines.append("AV36 verdict: " + judge(*res["MAF"], res["ELP"][0]))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(2.5, 0.5, 4.0, 0.3).startswith("PASS") and judge(0.5, 0.1, 1.0, 0.3).startswith("KILL")
    assert MIN_BLH > 750.0


_selfcheck()
if __name__ == "__main__":
    main()
