"""Breakdown of the Earth-GRAM comparison: per height band, season, UTC hour and station; PIT shape; spread-skill; GRAM wind-scale sensitivity. REPORT ONLY.
Complements b9_gram_compare.py (overall paired scores) and b9_earthgram_clim.py (climatology check). Same 800 b9 cases (2024-25 balloons: development set, reused).

Sources (all 100 members per case):
  tool                 installed tool, climate mode, the kit's seed rule (1000 * year + day of year) -> the same members as the kit; cached in data/kit/tool_members.npz
  gram_ncep, gram_rra  real Earth-GRAM 2016 (b9_earthgram_run.py)
  gram_ncep_ru<s>      GRAM NCEP with the wind perturbations scaled by s (b9_earthgram_scale.py; T untouched, so only u, v and wind speed change)
  gramlike, bank, gaussfull   the kit's stand-ins (data/kit/gram_*.npz)
Per case, variable (u, v, T, wind speed) and height: CRPS, PIT (randomised ranks), inside the central 90 % range. Then per band:
  CRPS by season / hour / station, with the paired difference to the tool and a day-block 95 % interval;
  PIT mean (target 0.5), 12 x PIT variance (target 1; above 1 = too narrow), share in the outer 10 % on each side (target 0.20);
  spread-skill: mean member SD / RMSE of the member mean, corrected by sqrt(m / (m + 1)) (target 1; below 1 = too narrow).
Writes docs/results/logs/kit_b9_earthgram_breakdown.log and data/kit/breakdown_scores.npz (per-case arrays for figures).

    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b9_earthgram_breakdown.py
"""
import os

import numpy as np
import pandas as pd

import kit_common as K

QS = ("u", "v", "T", "spd")
SEASON = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}
FILES = {"gram_ncep": "earthgram_ncep", "gram_rra": "earthgram_rra", "gram_ncep_ru1.2": "earthgram_ncep_ru1.2", "gram_ncep_ru1.35": "earthgram_ncep_ru1.35",
         "gram_ncep_ru1.5": "earthgram_ncep_ru1.5", "gramlike": "gram_gramlike", "bank": "gram_bank", "gaussfull": "gram_gaussfull"}


def crps_ens(e, y):
    """e (m, n), y (n,) -> CRPS per column (the kit's crps1, vectorised)."""
    e = np.sort(e, 0)
    m = e.shape[0]
    w = (2 * np.arange(1, m + 1) - m - 1)[:, None]
    return np.abs(e - y).mean(0) - (w * e).sum(0) / (m * m)


def pit(e, y, rng):
    """Randomised rank PIT in (0, 1) per column."""
    lo, eq = (e < y).sum(0), (e == y).sum(0)
    return (lo + rng.uniform(0, 1, y.shape) * (eq + 1)) / (e.shape[0] + 1)


def tool_members(cases):
    path = os.path.join(K.OUT, "tool_members.npz")
    if os.path.exists(path):
        d = np.load(path)
        if list(d["case"]) == list(cases.case):
            return {q: d[q] for q in ("u", "v", "T")}
    out = {q: [] for q in ("u", "v", "T")}
    for c in cases.itertuples():
        t = pd.Timestamp(c.time_utc)
        lat, lon, elev = K.station_pos(c.station)
        atm = K.tool(lat, lon, t, seed=1000 * t.year + int(t.dayofyear), n=100, elevation=elev)
        for q in out:
            out[q].append(np.asarray(atm[q], np.float32))
    out = {q: np.stack(v) for q, v in out.items()}
    np.savez_compressed(path, case=np.array(cases.case.tolist(), dtype=str), **out)
    return out


def band(x):
    return np.stack([np.nanmean(x[..., K.band_idx(lo, hi)], -1) for _, lo, hi in K.BANDS], -1)


def main():
    cases = pd.read_csv(os.path.join(K.OUT, "gram_cases.csv"))
    t = pd.to_datetime(cases.time_utc)
    cases["hour"], cases["season"], cases["day"] = t.dt.hour, cases.month.map(SEASON), t.dt.strftime("%Y-%m-%d")
    src = {"tool": tool_members(cases)}
    for name, f in FILES.items():
        p = os.path.join(K.OUT, f + ".npz")
        if not os.path.exists(p):
            print("missing", p)
            continue
        d = np.load(p)
        ids = {str(c): i for i, c in enumerate(d["case"])}
        sel = [ids[c] for c in cases.case]
        src[name] = {q: d[q][sel] for q in ("u", "v", "T")}
    bal = {s: K.balloon(s) for s in cases.station.unique()}
    obs = {q: np.full((len(cases), K.NH), np.nan) for q in ("u", "v", "T")}
    for i, c in enumerate(cases.itertuples()):
        tb, b = bal[c.station]
        k = tb.get_loc(pd.Timestamp(c.time_utc))
        for q in obs:
            obs[q][i] = b[q][k]
    obs["spd"] = np.hypot(obs["u"], obs["v"])
    rng = np.random.default_rng(0)
    S = {}                                                       # name -> dict q -> (crps, pit, in90, sd, mean) each (n, 44)
    for name, m in src.items():
        m = dict(m, spd=np.hypot(m["u"], m["v"]))
        S[name] = {}
        for q in QS:
            e = m[q].astype(float)                               # (n, mem, 44)
            y = obs[q]
            cr = np.stack([crps_ens(e[i], y[i]) for i in range(len(y))])
            pt = np.stack([pit(e[i], y[i], rng) for i in range(len(y))])
            lo, hi = np.percentile(e, 5, 1), np.percentile(e, 95, 1)
            bad = ~np.isfinite(y)
            for a in (cr, pt):
                a[bad] = np.nan
            inr = ((y >= lo) & (y <= hi)).astype(float)
            inr[bad] = np.nan
            S[name][q] = dict(crps=cr, pit=pt, in90=inr, sd=e.std(1), mean=e.mean(1))
    np.savez_compressed(os.path.join(K.OUT, "breakdown_scores.npz"), case=np.array(cases.case.tolist(), dtype=str),
                        **{f"{n}__{q}__{k}": v.astype(np.float32) for n, d in S.items() for q, dd in d.items() for k, v in dd.items()},
                        **{f"obs__{q}": v for q, v in obs.items()})
    names = list(S)
    f2 = lambda v: " ".join(f"{x:6.3f}" for x in v)
    L = [f"Earth-GRAM breakdown: {len(cases)} cases (2024-25 balloons, development set, reused), 100 members per source; sources: {', '.join(names)}.",
         "Columns are the height bands " + ", ".join(b[0] for b in K.BANDS) + ". gram_ncep_ru<s> scales GRAM's wind perturbations only (T is unchanged).", ""]
    L.append("1. CRPS by band (lower is better), all cases")
    for q in QS:
        L.append(f"  {q}")
        for n in names:
            L.append(f"    {n:18s} {f2(np.nanmean(band(S[n][q]['crps']), 0))}")
    L.append("")
    L.append("2. PAIRED CRPS source minus tool by band, % of the tool's CRPS, day-block 95 % interval in brackets (below 0 = source better)")
    for q in QS:
        L.append(f"  {q}")
        bt = band(S["tool"][q]["crps"])
        for n in names[1:]:
            d = band(S[n][q]["crps"]) - bt
            parts = []
            for j in range(len(K.BANDS)):
                ok = np.isfinite(d[:, j])
                m, lo, hi = K.block_boot(d[ok, j], cases.day.values[ok], draws=1000)
                base = np.nanmean(bt[:, j])
                parts.append(f"{100 * m / base:+6.1f} [{100 * lo / base:+5.1f},{100 * hi / base:+5.1f}]")
            L.append(f"    {n:18s} " + "  ".join(parts))
    L.append("")
    for key, label in (("season", "3. CRPS by SEASON"), ("hour", "4. CRPS by UTC HOUR (00 = late afternoon local, 12 = early morning)"), ("station", "5. CRPS by STATION")):
        L.append(f"{label}: source / tool CRPS ratio per band (below 1 = source better); the tool's CRPS itself on the first line of each group")
        for g, sub in cases.groupby(key):
            ix = sub.index.values
            L.append(f"  {g}  (n = {len(ix)})")
            for q in QS:
                bt = np.nanmean(band(S["tool"][q]["crps"][ix]), 0)
                L.append(f"    {q:4s} tool CRPS          {f2(bt)}")
                for n in ("gram_ncep", "gram_rra", "gram_ncep_ru1.35", "bank"):
                    if n in S:
                        L.append(f"    {q:4s} {n:18s} {f2(np.nanmean(band(S[n][q]['crps'][ix]), 0) / bt)}")
        L.append("")
    L.append("6. CALIBRATION by band: PIT mean (0.5) | 12 x PIT variance (1; >1 too narrow) | outer share, PIT<0.1 plus PIT>0.9 (0.20) | 90 % coverage (0.90) | spread-skill (1)")
    for q in QS:
        L.append(f"  {q}")
        for n in names:
            d = S[n][q]
            pm = np.nanmean(band(d["pit"]), 0)
            pv = [12 * np.nanvar(d["pit"][:, K.band_idx(lo, hi)]) for _, lo, hi in K.BANDS]
            po = [np.nanmean((d["pit"][:, K.band_idx(lo, hi)] < 0.1) | (d["pit"][:, K.band_idx(lo, hi)] > 0.9)) for _, lo, hi in K.BANDS]
            cov = np.nanmean(band(d["in90"]), 0)
            err = d["mean"] - obs[q]
            ss = [np.sqrt(np.nanmean(d["sd"][:, K.band_idx(lo, hi)] ** 2) / np.nanmean(err[:, K.band_idx(lo, hi)] ** 2)) * np.sqrt(100 / 101) ** -1
                  for _, lo, hi in K.BANDS]
            L.append(f"    {n:18s} {f2(pm)} | {f2(pv)} | {f2(po)} | {f2(cov)} | {f2(ss)}")
    L.append("")
    L.append("7. PIT HISTOGRAM, wind speed, 0-12 km pooled (10 bins, frequency / 0.1; flat = 1.00)")
    for n in names:
        p = S[n]["spd"]["pit"][:, K.band_idx(0, 12000)].ravel()
        h = np.histogram(p[np.isfinite(p)], bins=10, range=(0, 1))[0]
        L.append(f"    {n:18s} " + " ".join(f"{x:4.2f}" for x in h / h.sum() / 0.1))
    L.append("")
    L.append("Notes: the tool is balloon-corrected at these two stations (not a blind test); bank and gaussfull are built from these stations' 1991-2020 balloons; "
             "GRAM uses only its own global/RRA climatology. The ru scaling is exact for GRAM (checked against a real ruscale=1.4 run to 0.012 m/s). "
             "Spread-skill uses the m=100 finite-ensemble factor sqrt((m+1)/m). Day-block intervals resample whole days (1000 draws).")
    K.report("b9_earthgram_breakdown", L)


if __name__ == "__main__":
    rng = np.random.default_rng(1)
    e, y = rng.normal(size=(100, 3)), np.array([0.0, 1.0, -2.0])
    assert np.allclose(crps_ens(e, y), [K.crps1(e[:, j], y[j]) for j in range(3)])
    assert np.all((pit(e, y, rng) > 0) & (pit(e, y, rng) < 1))
    main()
