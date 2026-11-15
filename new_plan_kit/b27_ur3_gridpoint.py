"""New_Plan 17 UR3: one measured "grid to point" table in place of widening factors. Changes nothing in the tool.
  (a) 10 m: the RA stage 1a gap (sd 1.54 m/s per wind component at 10 m, fit 2016-20, kit_b6_realair_rows; no site fit) added to each member's
      u10 and v10 of the raw WB2 IFS ENS at the points nearest TCS / MAF (the AV6 / G1-5 data: 50 members, 00Z, leads 1-7 d pooled, vs ASOS
      00 UTC), scored 2023-24 beside AV6's fitted per-site speed factor (refitted here on 2016-22 exactly as b11).
  (b) RA coverage by lead bin: new_plan_kit/b6_realair_rows.py is run in this process (it builds the 30.9 M gap rows in memory, ~30-60 min,
      several GB) and its A1 90 % band coverage at the left-out stations, 2022, is split by lead bin 6-24 h / 1-3 d / 3-6 d / 6-10 d.
  (c) Instrument noise (information): triple collocation of balloon, radar and ERA5 wind at El Paso (EPZ radar + Santa Teresa balloons) and
      Midland (MAF), 2021-23 00Z: noise variance of the balloon component = mean((b - r)(b - e)) per band; the gap with that noise removed in
      squares is printed and (b) is repeated with it ("A1 clean"). Radar volumes are 23 UTC (~1 h before the balloon): an upper bound.
Rule (set 2026-11-13 in New_Plan 17.1 before any run):
  (a) PASS: 90 % coverage error at or under 0.15 at both sites AND CRPS within 0.010 of AV6's fitted-factor CRPS at both.
      KILL: coverage error above 0.20 at either site (the gap is not what the fitted factors measure; keep per-site fits).
  (b) PASS: 90 % coverage 0.87-0.93 in every band x lead bin. KILL: any band x lead bin under 0.85.  Otherwise MISS.
Scored against stations and balloons only (against ERA5 the table must look worse; not part of the rule).
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b27_ur3_gridpoint.py [--parts a,b,c]
Result: docs/results/logs/kit_b27_ur3_gridpoint.log
"""
import argparse
import glob
import os
import runpy
import sys

import numpy as np
import pandas as pd

import kit_common as K

GAP10 = 1.54                          # m/s per component, RA stage 1a (New_Plan 9, row "RA stage 1a"), fit 2016-20 at kept stations
NAME = "b27_ur3_gridpoint"
TC_BANDS = [(500, 1500, "0.5-1.5 km"), (1500, 3000, "1.5-3 km"), (3000, 6000, "3-6 km")]


def add_gap(u, v, g, rng):
    """members u, v (n, m) -> speed after adding an independent N(0, g) to each component of each member."""
    return np.hypot(u + rng.normal(0, g, u.shape), v + rng.normal(0, g, v.shape))


def judge_a(cells):
    """cells[site] = (coverage error with the gap, CRPS with the gap, CRPS with AV6's factor) -> verdict."""
    if any(c[0] > 0.20 for c in cells.values()):
        return "KILL"
    return "PASS" if all(c[0] <= 0.15 and c[1] - c[2] <= 0.010 for c in cells.values()) else "MISS"


def judge_b(covs):
    covs = np.asarray([c for c in covs if np.isfinite(c)])
    if (covs < 0.85).any():
        return "KILL"
    return "PASS" if ((covs >= 0.87) & (covs <= 0.93)).all() else "MISS"


def part_a(lines):
    import xarray as xr
    from b3_g15_spread_replay import SITES, ens_crps
    from b11_av6_fixed_widen import FIT, SCORE, best_factor, coverr, widen
    from bias_backtest import obs_series
    files = sorted(glob.glob(K.REPO + "/data/raw/wb2_ifs_ens/*_00z.nc"))
    rng = np.random.default_rng(0)
    cells = {}
    for st, (lat, lon) in SITES.items():
        obs = obs_series(st)
        ds = xr.open_mfdataset(files, combine="by_coords")[["u10", "v10"]].sel(latitude=lat, longitude=lon % 360, method="nearest").load()
        U, V, Y, T = [], [], [], []
        for li, td in enumerate(ds.prediction_timedelta.values):
            u = ds.u10.isel(prediction_timedelta=li).transpose("time", "number").values.astype(float)
            v = ds.v10.isel(prediction_timedelta=li).transpose("time", "number").values.astype(float)
            valid = pd.DatetimeIndex(ds.time.values) + pd.Timedelta(td)
            y = obs["ws"].reindex(valid).to_numpy()
            ok = np.isfinite(y) & np.isfinite(u).all(1) & np.isfinite(v).all(1)
            U.append(u[ok]), V.append(v[ok]), Y.append(y[ok]), T.append(valid[ok])
        u, v, y, t = np.concatenate(U), np.concatenate(V), np.concatenate(Y), pd.DatetimeIndex(np.concatenate([x.values for x in T]))
        assert t.max() < pd.Timestamp("2026-01-01"), "no 2026 data here"
        fit, sc = (t >= FIT[0]) & (t <= FIT[1] + " 23:59"), (t >= SCORE[0]) & (t <= SCORE[1] + " 23:59")
        e = np.hypot(u, v)
        f = best_factor(e[fit], y[fit])
        eg = add_gap(u[sc], v[sc], GAP10, rng)
        c_raw, c_fac, c_gap = (ens_crps(x, y[sc]).mean() for x in (e[sc], widen(e[sc], f), eg))
        cells[st] = (coverr(eg, y[sc]), c_gap, c_fac)
        lines.append(f"  (a) {st}: {sc.sum()} cases 2023-24; CRPS raw {c_raw:.4f}, AV6 factor {f:.2f} {c_fac:.4f}, gap {GAP10} m/s {c_gap:.4f}; "
                     f"coverage error raw {coverr(e[sc], y[sc]):.3f}, factor {coverr(widen(e[sc], f), y[sc]):.3f}, gap {cells[st][0]:.3f}")
    lines.append("  (a) verdict: " + judge_a(cells))


def triple(lines):
    """-> {band name: balloon noise sd per component} from balloon x radar x ERA5 at EPZ and MAF, 2021-23 00Z."""
    acc = {b[2]: [] for b in TC_BANDS}
    for site, sid in (("EPZ", K.EPZ), ("MAF", K.MAF)):
        t, b = K.balloon(sid)
        keep = (t.year >= 2021) & (t.year <= 2023) & (t.hour == 0)
        t, bu, bv = t[keep], b["u"][keep], b["v"][keep]
        lat, lon, elev = K.station_pos(sid)
        et, e = K.era5_at(lat, lon, t, names=("u", "v"))
        pos = {x: i for i, x in enumerate(t)}
        idx = K.radar_files(site)
        n = 0
        for j, tt in enumerate(et):
            r = K.radar_uv(site, tt, elev, index=idx)
            if r is None:
                continue
            i = pos[tt]
            for lo, hi, name in TC_BANDS:
                k = (K.H >= lo) & (K.H < hi)
                for bb, rr, ee in ((bu[i, k], r[0][k], e["u"][j, k]), (bv[i, k], r[1][k], e["v"][j, k])):
                    ok = np.isfinite(bb) & np.isfinite(rr) & np.isfinite(ee)
                    acc[name] += list(((bb - rr) * (bb - ee))[ok])
            n += 1
        lines.append(f"  (c) {site}: {n} balloon times with radar and ERA5")
    out = {}
    for name, v in acc.items():
        if len(v) >= 100:
            out[name] = float(np.sqrt(max(np.mean(v), 0.0)))
            lines.append(f"  (c) balloon wind noise sd {name}: {out[name]:.2f} m/s per component ({len(v)} values; upper bound, radar 1 h earlier)")
    return out


def part_b(lines, noise):
    sys.argv = ["b6_realair_rows.py", "."]
    g = runpy.run_path(os.path.join(K.KIT, "b6_realair_rows.py"), run_name="ur3_b")
    R, lbin, band, lo, yr, sd_m, gap = (g[k] for k in ("R", "lbin", "band", "lo", "yr", "sd_m", "gap"))
    BANDS, LEADS, Z90 = g["BANDS"], g["LEADS"], g["Z90"]
    gap_clean = gap.copy()
    for j, (a, b_, _) in enumerate(BANDS):                              # noise from (c) where a TC band lies inside the RA band
        hits = [s for (lo_, hi_, nm), s in zip(TC_BANDS, [noise.get(x[2]) for x in TC_BANDS]) if s is not None and lo_ >= a and hi_ <= b_]
        if hits:
            gap_clean[j] = np.sqrt(max(gap[j] ** 2 - np.mean(hits) ** 2, 0.0))

    def cover(sel, gp):
        s = np.sqrt(sd_m[lbin[sel], band[sel]] ** 2 + gp[band[sel]] ** 2)
        return float(np.mean(np.concatenate([np.abs(R[sel, 6]) <= Z90 * s, np.abs(R[sel, 7]) <= Z90 * s])))

    covs = []
    for i, (_, _, ln) in enumerate(LEADS):
        row, rowc = [], []
        for j, (_, _, bn) in enumerate(BANDS):
            sel = (yr == 2022) & lo & (band == j) & (lbin == i)
            c = cover(sel, gap) if sel.sum() >= 30 else np.nan
            row.append(f"{bn} {c:.3f} (n {sel.sum()})")
            rowc.append(f"{cover(sel, gap_clean):.3f}" if sel.sum() >= 30 else "nan")
            covs.append(c)
        lines.append(f"  (b) {ln:<7} A1: " + ", ".join(row))
        if noise:
            lines.append(f"      {ln:<7} A1 clean: " + ", ".join(rowc))
    lines.append("  (b) gap per band " + ", ".join(f"{n} {x:.2f}" for (_, _, n), x in zip(BANDS, gap)) + ("; clean " + ", ".join(f"{x:.2f}" for x in gap_clean) if noise else ""))
    lines.append("  (b) verdict (A1, as in the rule): " + judge_b(covs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="a,b,c")
    a = ap.parse_args()
    parts = set(a.parts.split(","))
    K.ram_gate(8.0)
    lines = ["UR3 grid-to-point table: (a) 10 m gap on the raw ensemble at TCS / MAF, (b) RA coverage by lead bin, (c) balloon noise by triple collocation"]
    if "a" in parts:
        part_a(lines)
    noise = triple(lines) if "c" in parts else {}
    if "b" in parts:
        part_b(lines, noise)
    lines.append("Rule (pre-set, New_Plan 17.1): (a) PASS coverage error <= 0.15 and CRPS within 0.010 of AV6 at both sites, KILL > 0.20; "
                 "(b) PASS 0.87-0.93 in every band x lead bin, KILL any < 0.85.")
    K.report(NAME, lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    u, v = np.zeros((2000, 50)), np.zeros((2000, 50))
    s = add_gap(u, v, 1.5, rng)
    assert abs(np.median(s) - 1.5 * np.sqrt(2 * np.log(2))) < 0.05          # Rayleigh median
    assert judge_a({"A": (0.12, 1.00, 0.995), "B": (0.10, 1.2, 1.2)}) == "PASS"
    assert judge_a({"A": (0.21, 1.0, 1.0), "B": (0.1, 1.0, 1.0)}) == "KILL"
    assert judge_a({"A": (0.12, 1.02, 1.0), "B": (0.1, 1.0, 1.0)}) == "MISS"
    assert judge_b([0.9, 0.88, 0.92, np.nan]) == "PASS" and judge_b([0.9, 0.84]) == "KILL" and judge_b([0.9, 0.86]) == "MISS"


_selfcheck()
if __name__ == "__main__":
    main()
