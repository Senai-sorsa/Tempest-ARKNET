"""Real Earth-GRAM 2016 against balloons and the tool, by climatology: mean, spread, tails, density, and bias against 2024-25 balloons. REPORT ONLY.
Complements b9_gram_compare.py (which scores the same members case by case: CRPS, coverage, coupling, shape).

Groups: station (EPZ, MAF) x calendar month x UTC hour (00, 12) that hold at least one b9 case. Per group:
  balloons   1991-2020 IGRA profiles of that station, month and hour (the reference climatology)
  gram_ncep  the 100 GRAM Monte Carlo members of the group's first case (NCEP 1997-2015 climatology)  [data/kit/earthgram_ncep.npz]
  gram_rra   same with the 2006 Range Reference Atmosphere (El Paso RRA at EPZ; MAF identical to ncep)    [data/kit/earthgram_rra.npz]
  tool       100 tool members (climate mode) for the group's first case
Scores per height band (mean over groups): mean bias vs the balloon climatology, spread ratio (SD / balloon SD; target 1),
  wind-speed q99 ratio (target 1), density mean bias in % (balloon density = p / (Rd T), dry air).
Against the 2024-25 balloons (all b9 cases): mean error of the member mean (source - balloon), the drift since each source's base period.
Sanity: GRAM's own reported SD vs the SD of its Monte Carlo members.

    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b9_earthgram_clim.py
Result: docs/results/logs/kit_b9_earthgram_clim.log
"""
import os
import time

import numpy as np
import pandas as pd

import kit_common as K

RD = 287.05
VARS = ("u", "v", "T")
XV = ("spd", "sos")          # wind speed [m/s] and speed of sound [m/s, dry: sqrt(1.4 Rd T)] - what drag, Mach and drift see


def load(name):
    d = np.load(os.path.join(K.OUT, f"earthgram_{name}.npz"))
    return {str(c): i for i, c in enumerate(d["case"])}, {k: d[k].astype(float) for k in ("u", "v", "T", "p")}


def band(x):
    """(..., 44) -> (..., 4) nan-mean per height band."""
    return np.stack([np.nanmean(x[..., K.band_idx(lo, hi)], -1) for _, lo, hi in K.BANDS], -1)


def stats(m):
    """members dict (n, 44) -> per-height mean, SD, speed q99, density mean."""
    m = dict(m, spd=np.hypot(m["u"], m["v"]), sos=np.sqrt(1.4 * RD * m["T"]))
    spd = m["spd"]
    rho = m["p"] / (RD * m["T"])
    with np.errstate(all="ignore"):
        out = {f"{q}_mean": np.nanmean(m[q], 0) for q in VARS + XV} | {f"{q}_sd": np.nanstd(m[q], 0) for q in VARS + XV}
        out |= {"spd_q99": np.nanpercentile(spd, 99, 0), "rho_mean": np.nanmean(rho, 0)}
    return out


def fmt(v):
    return " ".join(f"{x:+7.2f}" if np.isfinite(x) else "    nan" for x in v)


def main():
    cases = pd.read_csv(os.path.join(K.OUT, "gram_cases.csv"))
    cases["hour"] = pd.to_datetime(cases.time_utc).dt.hour
    src = {"gram_ncep": load("ncep"), "gram_rra": load("rra")}
    bal = {s: K.balloon(s) for s in cases.station.unique()}
    rows, sanity, t_tool = [], [], []
    for (sid, mon, hr), g in cases.groupby(["station", "month", "hour"]):
        t, b = bal[sid]
        sel = (t.year >= 1991) & (t.year <= 2020) & (t.month == mon) & (t.hour == hr)
        ref = stats({q: b[q][sel] for q in ("u", "v", "T", "p")})
        c0 = g.iloc[0]
        mem = {name: {q: arr[q][ids[c0.case]] for q in arr} for name, (ids, arr) in src.items()}
        t0 = time.perf_counter()
        atm = K.tool(c0.lat, c0.lon, c0.time_utc, seed=7, n=100, elevation=c0.elevation_m)
        t_tool.append(time.perf_counter() - t0)
        mem["tool"] = {q: np.asarray(atm[q], float) for q in ("u", "v", "T", "p")}
        for name, m in mem.items():
            s = stats(m)
            r = dict(src=name, station=sid, month=mon, hour=hr, nbal=int(sel.sum()))
            for q in VARS + XV:
                r[f"{q}_bias"] = band(s[f"{q}_mean"] - ref[f"{q}_mean"])
                r[f"{q}_sdr"] = band(s[f"{q}_sd"] / ref[f"{q}_sd"])
            r["spd_q99r"] = band(s["spd_q99"] / ref["spd_q99"])
            r["rho_bias_pct"] = band(100 * (s["rho_mean"] / ref["rho_mean"] - 1))
            rows.append(r)
    for name in ("gram_ncep", "gram_rra"):
        d = np.load(os.path.join(K.OUT, f"earthgram_{name.split('_')[1]}_clim.npz"))
        ids, arr = src[name]
        for q in VARS:
            mc_sd = np.std(arr[q], 1)                                    # (n, 44)
            own = d[f"{q}_sd"][[ids[str(c)] for c in d["case"]]]
            sanity.append(f"  {name:10s} {q}: median MC-member SD / GRAM-reported SD per band  " + " ".join(f"{x:5.2f}" for x in np.nanmedian(band(mc_sd / own), 0)))
    df = pd.DataFrame(rows)
    L = [f"Real Earth-GRAM 2016 climatology check: {df.groupby(['station','month','hour']).ngroups} station x month x hour groups, "
         f"100 members per source; balloon climatology 1991-2020 (median {int(df.nbal.median())} balloons per group).",
         "Columns are height bands " + ", ".join(b[0] for b in K.BANDS) + ". Means over groups (EPZ and MAF together, then each station).", ""]
    for title, key, unit in [("MEAN BIAS vs balloon climatology", "_bias", "(m/s, m/s, K)"), ("SPREAD RATIO SD / balloon SD (target 1.00)", "_sdr", "")]:
        L.append(f"{title} {unit}")
        for stn in (None, K.EPZ, K.MAF):
            sub = df if stn is None else df[df.station == stn]
            L.append(f"  {'both stations' if stn is None else stn}")
            for name in ("gram_ncep", "gram_rra", "tool"):
                s = sub[sub.src == name]
                L.append(f"    {name:10s} " + "   ".join(f"{q}: {fmt(np.mean(np.stack(s[q + key]), 0))}" for q in VARS))
                L.append(f"    {'':10s} " + "   ".join(f"{q}: {fmt(np.mean(np.stack(s[q + key]), 0))}" for q in XV))
        L.append("")
    L.append("TAILS AND DENSITY (both stations): wind speed q99 ratio to balloons (target 1.00); density mean bias in % (dry balloon density)")
    for name in ("gram_ncep", "gram_rra", "tool"):
        s = df[df.src == name]
        L.append(f"    {name:10s} q99 speed: {fmt(np.mean(np.stack(s.spd_q99r), 0))}    density %: {fmt(np.mean(np.stack(s.rho_bias_pct), 0))}")
    L.append("    spread of the group means (SD over groups of the band mean bias) shows how much of a mean bias is seasonal rather than fixed:")
    for name in ("gram_ncep", "tool"):
        s = df[df.src == name]
        L.append(f"    {name:10s} " + "   ".join(f"{q}: {fmt(np.std(np.stack(s[q + '_bias']), 0))}" for q in VARS))
    L.append("")
    L.append("MEAN ERROR vs the 2024-25 balloons (member mean minus observed, all b9 cases; the drift since each base period)")
    obs = {q: [] for q in VARS}
    me = {n: {q: [] for q in VARS} for n in ("gram_ncep", "gram_rra", "balloon clim 1991-2020")}
    for c in cases.itertuples():
        t, b = bal[c.station]
        k = t.get_loc(pd.Timestamp(c.time_utc))
        sel = (t.year >= 1991) & (t.year <= 2020) & (t.month == c.month) & (t.hour == c.hour)
        for q in VARS:
            y = b[q][k]
            for name, (ids, arr) in src.items():
                me[name][q].append(arr[q][ids[c.case]].mean(0) - y)
            with np.errstate(all="ignore"):
                me["balloon clim 1991-2020"][q].append(np.nanmean(b[q][sel], 0) - y)
    for name, d in me.items():
        L.append(f"    {name:22s} " + "   ".join(f"{q}: {fmt(np.nanmean(band(np.stack(d[q])), 0))}" for q in VARS))
    L.append("    (the tool's paired accuracy against these balloons is in kit_b9_gram_compare.log)")
    L.append("")
    L.append("SANITY (target 1.00 within MC noise ~0.07 at 100 members):")
    L += sanity
    L.append("Notes: GRAM's NCEP base period is 1997-2015, the RRA El Paso base is 1990-95; the balloons are 1991-2020 and the tool is trained 1991-2020 with trend terms, "
             "so a warm 2024-25 shows up as a negative T mean error for every climatology. Balloon density ignores humidity (under 1 % near the ground). "
             "GRAM heights are taken as above sea level (the geoid offset there is about 25 m, under one model level near the ground).")
    L.append("")
    L.append(f"RUNTIME per case, 100 members x 44 heights (this machine): tool median {np.median(t_tool):.2f} s over {len(t_tool)} calls (first call {t_tool[0]:.1f} s, loads assets); "
             f"Earth-GRAM {gram_seconds():.2f} s median over 5 single-process runs (NCEP)")
    K.report("b9_earthgram_clim", L)


def gram_seconds(n=5):
    """Wall time of one GRAM run (100 MC members) on its own, the cost a user pays per case."""
    import tempfile
    import b9_earthgram_run as R
    cases = pd.read_csv(os.path.join(K.OUT, "gram_cases.csv"))
    hts = pd.read_csv(os.path.join(K.OUT, "gram_cases_heights.csv"))
    out = []
    with tempfile.TemporaryDirectory() as wd:
        for i, row in cases.head(n).iterrows():
            z = hts[hts.station == row.station].sort_values("height_above_ground_m").height_above_sea_m.values
            t0 = time.perf_counter()
            R.run_case(i, row, z, "ncep", 100, wd)
            out.append(time.perf_counter() - t0)
    return float(np.median(out))


if __name__ == "__main__":
    assert np.allclose(band(np.arange(44.0)[None])[0], [np.arange(44.0)[K.band_idx(lo, hi)].mean() for _, lo, hi in K.BANDS])
    main()
