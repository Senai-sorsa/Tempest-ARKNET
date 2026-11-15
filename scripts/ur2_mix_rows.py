"""UR2 stage 4 rows and UR12 signals (New_Plan 17). For every row of data/modeF_v2{,_denver} (00Z and 12Z starts, leads 0.25-10 d) read from the
HRES archive on disk (data/raw/wb2_hres_v2{,_denver}, the same profile builder as the rows: modeF.forecast_profiles):
  old   the run started 36 h earlier, at lead + 36 h (00Z start -> the 12Z run of two days before, 12Z start -> the 00Z run of the day before;
        the newest older run in this archive, as CHORUS stage 1); missing when lead + 36 h > 240 h (most rows beyond 8.5 d)
  next  the same run 6 h later in lead (lead + 6 h <= 240 h)
Closed-rule mix (CHORUS 14.4 improvement 1, as scripts/chorus_stage1_rows.py, refitted here for these rows): per lead bin (1 / 3 / 5 / 7 / 9) x
variable x height, w_new = (S_oo - S_no) / (S_nn + S_oo - 2 S_no) from the error moments of fit years 2018-2020, clipped to [0, 1];
mixed = w_new new + (1 - w_new) old; rows without the older run keep the newest run.
Writes (new folders only; nothing existing is touched):
  data/ur2_<box>_mixv2/<year>.npz      2016-2022, the source rows with `hres` = the mixed profile (UR2 stage 4: il6_modeF.py --rows-dir)
  data/ur2_<box>_signals/<year>.npz    d36 (n, 8) = RMS(newest - older), c6 (n, 8) = RMS(next - newest) per cell (wind 0-1 / 1-5 / 5-12 / 12-18 km,
                                       T 0-1 / 1-5 / 5-12 / 12-18 km; NaN where missing), have_old, have_next, and the row keys (valid, lead_days, lat, lon)
                                       for UR12 (new_plan_kit/b35_ur12_beta_signal.py)
  models/ur2_<box>_weights.npz
Self-check first: the newest run rebuilt by the same code must equal the stored `hres` (20 rows per month, two years, both start hours).
    PYTHONPATH=. .venv/Scripts/python -W ignore -u scripts/ur2_mix_rows.py [nmtx|denver] [--check-only]
About 1-2 h CPU per box, a few GB RAM.
"""
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

from tempest.forecast import modeF

BOX = next((x for x in sys.argv[1:] if x in ("nmtx", "denver")), "nmtx")
SRC = {"nmtx": "data/modeF_v2", "denver": "data/modeF_v2_denver"}[BOX]
HDIR = {"nmtx": "data/raw/wb2_hres_v2", "denver": "data/raw/wb2_hres_v2_denver"}[BOX]
OUT, SIG = f"data/ur2_{BOX}_mixv2", f"data/ur2_{BOX}_signals"
OLDER_H, NEXT_H, MAX_LEAD_H = 36, 6, 240
FIT_YEARS, YEARS = (2018, 2019, 2020), range(2016, 2023)
LEAD_BINS = (1, 3, 5, 7, 9)
BL = dict(np.load("models/modeF_bl.npz"))
G = 9.80665
H = np.asarray(modeF.HEIGHTS, float)
CELL_BANDS = [(0, 1000), (1000, 5000), (5000, 12000), (12000, 18001)]


def lead_bin9(lead_days):
    b = modeF.lead_bin(lead_days)
    return np.where(b == 0, 9, b)


def profiles_at(d, init, lead_h, family):
    """Profiles (n, 4, 44) of the runs started at `init` (DatetimeIndex), read at `lead_h` (n,), from file family (n,) '00z' / '12z'. NaN where missing."""
    out = np.full(d["hres"].shape, np.nan, np.float32)
    ok_lead = lead_h <= MAX_LEAD_H
    for fam in ("00z", "12z"):
        for ym in sorted({(t.year, t.month) for t, f, k in zip(init, family, ok_lead) if f == fam and k}):
            sel = np.flatnonzero((init.year == ym[0]) & (init.month == ym[1]) & (family == fam) & ok_lead)
            f = f"{HDIR}/{ym[0]}{ym[1]:02d}_{fam}.nc"
            if not os.path.exists(f):
                continue
            with xr.open_dataset(f) as h:
                h = h.load()
                case = pd.DatetimeIndex(h.time.values).get_indexer(init[sel])
                td = h.prediction_timedelta.values.astype("timedelta64[h]").astype(int)
                lead = np.array([np.flatnonzero(td == x)[0] if (td == x).any() else -1 for x in lead_h[sel]])
                ok = (case >= 0) & (lead >= 0)
                s = sel[ok]
                if not len(s):
                    continue
                la = np.array([np.flatnonzero(np.round(h.latitude.values - x, 3) == 0)[0] for x in d["lat"][s]])
                lo = np.array([np.flatnonzero(np.round(h.longitude.values - 360.0 - x, 3) == 0)[0] for x in d["lon"][s]])
                hp = modeF.forecast_profiles(h, case[ok], lead[ok], la, lo, d["z_sfc"][s] * G, BL)
                out[s] = np.stack([hp[v] for v in modeF.PROFILE], 1)
    return out


def own_init(d):
    return pd.DatetimeIndex(d["valid"]) - pd.to_timedelta(d["lead_hours"], unit="h")


def family_of(start_hour):
    return np.where(np.asarray(start_hour) == 0, "00z", "12z")


def older(d):
    init = own_init(d) - pd.Timedelta(hours=OLDER_H)
    return profiles_at(d, init, np.asarray(d["lead_hours"]) + OLDER_H, family_of((np.asarray(d["start_hour"]) + 12) % 24))


def next6(d):
    return profiles_at(d, own_init(d), np.asarray(d["lead_hours"]) + NEXT_H, family_of(d["start_hour"]))


def cell_rms(a, b):
    """(n, 4, 44) x 2 -> (n, 8) RMS difference: wind (u and v together) per band, then T per band."""
    vi = {v: i for i, v in enumerate(modeF.PROFILE)}
    out = np.full((len(a), 8), np.nan, np.float32)
    for j, (lo, hi) in enumerate(CELL_BANDS):
        k = (H >= lo) & (H < hi)
        du = a[:, [vi["u"], vi["v"]]][:, :, k] - b[:, [vi["u"], vi["v"]]][:, :, k]
        out[:, j] = np.sqrt(np.mean(du.reshape(len(a), -1) ** 2, 1))
        out[:, 4 + j] = np.sqrt(np.mean((a[:, vi["T"], k] - b[:, vi["T"], k]) ** 2, 1))
    return out


def weights(moments):
    W = {}
    for L, (nn, oo, no) in moments.items():
        W[L] = np.clip((oo - no) / np.maximum(nn + oo - 2 * no, 1e-12), 0, 1).astype(np.float32)
    return W


def mix(hres, old, lb, W):
    have = np.isfinite(old).all((1, 2))
    w = np.stack([W[L] for L in lb])
    return np.where(have[:, None, None], w * hres + (1 - w) * np.nan_to_num(old), hres).astype(np.float32), have


def load(y):
    return dict(np.load(f"{SRC}/{y}.npz"))


def selfcheck_rebuild():
    for y in (2019, 2022):
        d = load(y)
        m = pd.DatetimeIndex(d["valid"]).month
        pick = np.concatenate([np.flatnonzero((m == k) & (d["start_hour"] == s))[:10] for k in range(1, 13) for s in (0, 12)])
        sub = {k: v[pick] for k, v in d.items()}
        re = profiles_at(sub, own_init(sub), np.asarray(sub["lead_hours"]), family_of(sub["start_hour"]))
        err = np.nanmax(np.abs(re - sub["hres"]))
        assert np.isfinite(re).all() and err < 1e-3, f"rebuilt newest run differs from stored hres ({y}: {err})"
        print(f"self-check {y}: newest run rebuilt for {len(pick)} rows (00Z and 12Z starts), max diff {err:.2e}", flush=True)


def _unit():
    a = np.zeros((2, 4, len(H)), np.float32)
    b = a.copy()
    b[:, 0] += 3.0                                      # u differs by 3 everywhere, v not: wind RMS = sqrt(9 / 2)
    r = cell_rms(a, b)
    assert np.allclose(r[:, :4], np.sqrt(4.5)) and np.allclose(r[:, 4:], 0)
    nn, oo, no = np.full((1, 1), 4.0), np.full((1, 1), 4.0), np.full((1, 1), 0.0)
    assert np.allclose(weights({1: (nn, oo, no)})[1], 0.5)            # two equal, independent errors: half and half
    hres, old = np.ones((2, 1, 1), np.float32), np.array([[[3.0]], [[np.nan]]], np.float32)
    mx, have = mix(hres, old, np.array([1, 1]), {1: np.full((1, 1), 0.5, np.float32)})
    assert np.allclose(mx[:, 0, 0], [2.0, 1.0]) and have.tolist() == [True, False]


_unit()
if __name__ == "__main__":
    selfcheck_rebuild()
    if "--check-only" in sys.argv:
        sys.exit(0)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SIG, exist_ok=True)
    olds, E = {}, {}
    for y in YEARS:
        d = load(y)
        old, nxt = older(d), next6(d)
        olds[y] = old
        sig = dict(d36=cell_rms(d["hres"], old), c6=cell_rms(nxt, d["hres"]), have_old=np.isfinite(old).all((1, 2)), have_next=np.isfinite(nxt).all((1, 2)),
                   valid=d["valid"], lead_days=d["lead_days"], lat=d["lat"], lon=d["lon"])
        np.savez(f"{SIG}/{y}.part.npz", **sig)
        os.replace(f"{SIG}/{y}.part.npz", f"{SIG}/{y}.npz")
        print(f"{y}: older run for {sig['have_old'].mean():.1%} of {len(old):,} rows, next 6 h for {sig['have_next'].mean():.1%}", flush=True)
        if y in FIT_YEARS:
            ok = sig["have_old"]
            lb = lead_bin9(d["lead_days"])[ok]
            en, eo = (d["hres"] - d["obs"])[ok], (old - d["obs"])[ok]
            for L in LEAD_BINS:
                k = lb == L
                s = E.setdefault(L, [np.zeros(en.shape[1:]) for _ in range(3)])
                s[0] += (en[k] ** 2).sum(0)
                s[1] += (eo[k] ** 2).sum(0)
                s[2] += (en[k] * eo[k]).sum(0)
    W = weights({L: tuple(s) for L, s in E.items()})
    for L in LEAD_BINS:                                  # a bin with no fit pair (not expected) keeps the newest run
        W.setdefault(L, np.ones(d["hres"].shape[1:], np.float32))
        print(f"lead bin {L}: w_new median {np.median(W[L]):.2f} (10-90 % {np.quantile(W[L], 0.1):.2f}-{np.quantile(W[L], 0.9):.2f})", flush=True)
    np.savez(f"models/ur2_{BOX}_weights.npz", **{f"w{L}": W[L] for L in LEAD_BINS}, older_h=OLDER_H, fit_years=np.array(FIT_YEARS))
    for y in YEARS:
        d = load(y)
        mx, have = mix(d["hres"], olds[y], lead_bin9(d["lead_days"]), W)
        np.savez(f"{OUT}/{y}.part.npz", **{**d, "hres": mx})
        os.replace(f"{OUT}/{y}.part.npz", f"{OUT}/{y}.npz")
        print(f"{y}: {have.sum():,} of {len(have):,} rows mixed; MSE newest {((d['hres'] - d['obs']) ** 2).mean():.3f} mixed {((mx - d['obs']) ** 2).mean():.3f}", flush=True)
    print(f"wrote {OUT} and {SIG}", flush=True)
