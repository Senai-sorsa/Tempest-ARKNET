"""New_Plan WD2 (step 0): how much real calm does ERA5 and the tool miss? Measurement only, CPU, no training, nothing in the tool changes.
Stations ALM ELP LRU MAF PEQ TCS (all inside the tool box), ASOS one-minute 2-minute-mean wind (data/raw/asos1min, minute :00 of the UTC hours 0 / 6 / 12 / 18,
whole knots x 0.5144), ERA5 10 m speed at the nearest grid point (data/raw/era5_em u10 / v10), same hours, 2016-2022; tool = api.atmosphere_sequence climate mode, n 1024,
query date 2013-<month>-15, offset 0, per month x hour cell, cells weighted by the station's sample count (as b50).
Printed: P(speed < 1 / 2 / 3 / 5 m/s) for ASOS, ERA5 and tool, and the ASOS minus ERA5 gap.
Rule (set 2026-11-16 before running, New_Plan WD2): STOP (WD2 closed, no real-calm arm) if |ASOS - ERA5| at 3 m/s is under 0.03 at every station. Otherwise continue
to the leave-one-station-out quantile-map test (fit 2016-20, test 2021-23) with the WD2 pass / kill rule.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b57_wd2_calm_step0.py
Result: docs/results/logs/kit_b57_wd2_calm_step0.log
"""
import glob
import os

import numpy as np
import pandas as pd
import xarray as xr

import kit_common as K

NAME = "b57_wd2_calm_step0"
SITES = {"ALM": (32.8399, -105.9906), "ELP": (31.8067, -106.3778), "LRU": (32.2894, -106.9222),
         "MAF": (31.9425, -102.2019), "PEQ": (31.3817, -103.5106), "TCS": (33.2369, -107.2672)}
HOURS, YEARS, LIMITS, KT = (0, 6, 12, 18), range(2016, 2023), (1.0, 2.0, 3.0, 5.0), 0.514444


def asos_hours(st):
    """-> DataFrame index = UTC hour, column s (m/s): the :00 minute of hours in HOURS, years YEARS."""
    parts = []
    for y in YEARS:
        f = os.path.join(K.REPO, "data", "raw", "asos1min", f"{st}_{y}.csv")
        if os.path.exists(f):
            d = pd.read_csv(f, usecols=["valid(UTC)", "sknt"], na_values=["M", ""]).dropna()
            d["t"] = pd.to_datetime(d["valid(UTC)"])
            parts.append(d[(d.t.dt.minute == 0) & d.t.dt.hour.isin(HOURS)].set_index("t")[["sknt"]])
    d = pd.concat(parts)
    d = d[~d.index.duplicated()]
    return pd.DataFrame({"s": d["sknt"].values * KT}, index=d.index)


def probs(speed):
    return np.array([(np.asarray(speed) < l).mean() for l in LIMITS])


def judge(gaps):
    """gaps = {station: |ASOS - ERA5| at 3 m/s} -> verdict string."""
    n = sum(g >= 0.03 for g in gaps.values())
    return "STOP, WD2 closed (gap under 0.03 at every station)" if n == 0 else f"continue to the leave-one-station-out test ({n} of {len(gaps)} stations with gap >= 0.03)"


def main():
    K.ram_gate(4.0)
    from tempest_weather import api
    u = xr.open_zarr(os.path.join(K.REPO, "data", "raw", "era5_em", "u10.zarr"))["u10"]
    v = xr.open_zarr(os.path.join(K.REPO, "data", "raw", "era5_em", "v10.zarr"))["v10"]
    lines = ["WD2 step 0: P(10 m speed < 1 / 2 / 3 / 5 m/s), UTC hours 0 / 6 / 12 / 18, 2016-2022; order ASOS | ERA5 | tool | ASOS - ERA5"]
    gaps = {}
    for st, (la, lo) in SITES.items():
        a = asos_hours(st)
        lon = lo % 360
        e = np.hypot(u.sel(latitude=la, longitude=lon, method="nearest").sel(valid_time=a.index, method=None).values,
                     v.sel(latitude=la, longitude=lon, method="nearest").sel(valid_time=a.index, method=None).values)
        ok = np.isfinite(e)
        a, e = a[ok], e[ok]
        tp, w = np.zeros(len(LIMITS)), 0
        for (m, h), g in a.groupby([a.index.month, a.index.hour]):
            try:
                atms, _ = api.atmosphere_sequence(la, lo, f"2013-{m:02d}-15T{h:02d}:00:00+00:00", offsets=(0,), n=1024, seed=0, mode="ai")
            except ValueError:
                continue
            tp += probs(np.hypot(atms[0]["u"][:, 0].astype(float), atms[0]["v"][:, 0].astype(float))) * len(g)
            w += len(g)
        pa, pe, pt = probs(a["s"].values), probs(e), tp / max(w, 1)
        gaps[st] = abs(pa[2] - pe[2])
        lines.append(f"  {st}: n {len(a)}; " + "; ".join(f"<{l:g}: {pa[i]:.3f} | {pe[i]:.3f} | {pt[i]:.3f} | {pa[i] - pe[i]:+.3f}" for i, l in enumerate(LIMITS)))
    lines.append("Rule (set 2026-11-16, WD2): stop if |ASOS - ERA5| at 3 m/s is under 0.03 at every station.")
    lines.append("Result: " + judge(gaps))
    K.report(NAME, lines)


def _selfcheck():
    assert np.allclose(probs([0.5, 1.5, 2.5, 4, 6]), [0.2, 0.4, 0.6, 0.8])
    assert judge({"a": 0.01, "b": 0.02}).startswith("STOP") and judge({"a": 0.01, "b": 0.05}).startswith("continue")


_selfcheck()
if __name__ == "__main__":
    main()
