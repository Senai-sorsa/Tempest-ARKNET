"""CHORUS stage 1 rows (New_Plan 14.4, stage 1; no training). For each ENSF2 mode F row (data/modeF_ens{,_denver}: 00Z starts, leads 1-7 d)
add the OLDER run for the same valid time and grid point: the 12Z start 36 h before (the newest older run in the wb2_hres_v2 archive; 12Z starts sit
36 h before each 00Z start, so a 12 h older run does not exist here), read at lead + 36 h with the same profile builder (modeF.forecast_profiles).
Closed-rule mix (14.4 improvement 1 = the best fixed mix of 14.2 b, no free numbers): per lead bin x variable x height,
w_new = (S_oo - S_no) / (S_nn + S_oo - 2 S_no) from the error moments of fit years 2018-2020 (before the 2021 range-map year and the 2022 test), clipped
to [0, 1]; mixed = w_new * new + (1 - w_new) * old. Writes data/chorus_<box>_mix/<year>.npz: years 2016-2021 hard links of the source rows, 2022 with
`hres` replaced by the mixed profile (everything else unchanged), plus models/chorus_<box>_weights.npz. Self-check: the newest run rebuilt by the
same code must equal the stored `hres` (first rows of every month).
    PYTHONPATH=. python scripts/chorus_stage1_rows.py [nmtx|denver]"""
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

from tempest.forecast import modeF

BOX = sys.argv[1] if len(sys.argv) > 1 else "nmtx"
SRC = {"nmtx": "data/modeF_ens", "denver": "data/modeF_ens_denver"}[BOX]
HDIR = {"nmtx": "data/raw/wb2_hres_v2", "denver": "data/raw/wb2_hres_v2_denver"}[BOX]
OUT = f"data/chorus_{BOX}_mix"
OLDER_H = 36
FIT_YEARS = (2018, 2019, 2020)
BL = dict(np.load("models/modeF_bl.npz"))
G = 9.80665


def profiles(d, start, lag_h):
    """Profiles (n, 4, 44) of the run started lag_h before each row's own start, read at lead + lag_h. start: '00z' or '12z' (file family)."""
    init = pd.DatetimeIndex(d["valid"]) - pd.to_timedelta(d["lead_hours"] + lag_h, unit="h")
    lead_h = d["lead_hours"] + lag_h
    out = np.full(d["hres"].shape, np.nan, np.float32)
    for ym in sorted({(t.year, t.month) for t in init}):
        sel = np.flatnonzero((init.year == ym[0]) & (init.month == ym[1]))
        f = f"{HDIR}/{ym[0]}{ym[1]:02d}_{start}.nc"
        if not os.path.exists(f):
            continue
        with xr.open_dataset(f) as h:
            h = h.load()
            case = pd.DatetimeIndex(h.time.values).get_indexer(init[sel])
            td = (h.prediction_timedelta.values.astype("timedelta64[h]")).astype(int)
            lead = np.array([np.flatnonzero(td == x)[0] if (td == x).any() else -1 for x in lead_h[sel]])
            ok = (case >= 0) & (lead >= 0)
            s = sel[ok]
            la = np.array([np.flatnonzero(np.round(h.latitude.values - x, 3) == 0)[0] for x in d["lat"][s]])
            lo = np.array([np.flatnonzero(np.round(h.longitude.values - 360.0 - x, 3) == 0)[0] for x in d["lon"][s]])
            hp = modeF.forecast_profiles(h, case[ok], lead[ok], la, lo, d["z_sfc"][s] * G, BL)
            out[s] = np.stack([hp[v] for v in modeF.PROFILE], 1)
    return out


def load(y):
    return dict(np.load(f"{SRC}/{y}.npz"))


# self-check: the newest run rebuilt here must be the stored hres
for y in (2019, 2022):
    d = load(y)
    m = pd.DatetimeIndex(d["valid"]).month
    pick = np.concatenate([np.flatnonzero(m == k)[:20] for k in range(1, 13)])
    sub = {k: v[pick] for k, v in d.items()}
    re = profiles(sub, "00z", 0)
    err = np.nanmax(np.abs(re - sub["hres"]))
    assert np.isfinite(re).all() and err < 1e-3, f"rebuilt newest run differs from stored hres ({y}: {err})"
    print(f"self-check {y}: newest run rebuilt for {len(pick)} rows, max diff {err:.2e}", flush=True)

# weights from the fit years
E = {}
for y in FIT_YEARS:
    d = load(y)
    old = profiles(d, "12z", OLDER_H)
    ok = np.isfinite(old).all((1, 2))
    lb = modeF.lead_bin(d["lead_days"])[ok]
    en, eo = (d["hres"] - d["obs"])[ok], (old - d["obs"])[ok]
    for L in (1, 3, 5, 7):
        k = lb == L
        s = E.setdefault(L, np.zeros((3,) + en.shape[1:]))
        s[0] += (en[k] ** 2).sum(0)
        s[1] += (eo[k] ** 2).sum(0)
        s[2] += (en[k] * eo[k]).sum(0)
    print(f"fit {y}: {ok.sum():,} of {len(ok):,} rows have the older run", flush=True)
W = {}
for L, s in E.items():
    nn, oo, no = s[0], s[1], s[2]
    W[L] = np.clip((oo - no) / np.maximum(nn + oo - 2 * no, 1e-12), 0, 1).astype(np.float32)
    rho = no / np.sqrt(nn * oo)
    gain = 1 - (W[L] ** 2 * nn + (1 - W[L]) ** 2 * oo + 2 * W[L] * (1 - W[L]) * no) / nn
    print(f"lead {L} d: w_new median {np.median(W[L]):.2f} (10-90 % {np.quantile(W[L], 0.1):.2f}-{np.quantile(W[L], 0.9):.2f}), error corr median "
          f"{np.median(rho):.2f}, fit-years MSE cut median {100 * np.median(gain):.1f} %", flush=True)
np.savez(f"models/chorus_{BOX}_weights.npz", **{f"w{L}": W[L] for L in W}, older_h=OLDER_H, fit_years=np.array(FIT_YEARS))

# rows dir: 2016-2021 as is, 2022 with the mixed profile
os.makedirs(OUT, exist_ok=True)
for y in range(2016, 2022):
    dst = f"{OUT}/{y}.npz"
    if not os.path.exists(dst):
        os.link(f"{SRC}/{y}.npz", dst)
d = load(2022)
old = profiles(d, "12z", OLDER_H)
ok = np.isfinite(old).all((1, 2))
assert ok.mean() > 0.95, f"older run missing for {1 - ok.mean():.1%} of 2022 rows"
lb = modeF.lead_bin(d["lead_days"])
w = np.stack([W[L] for L in lb])                       # (n, 4, 44)
mix = np.where(ok[:, None, None], w * d["hres"] + (1 - w) * np.nan_to_num(old), d["hres"]).astype(np.float32)
for L in (1, 3, 5, 7):
    k = (lb == L) & ok
    print(f"2022 lead {L} d: {k.sum()} rows, MSE newest {((d['hres'] - d['obs'])[k] ** 2).mean():.3f} mixed {((mix - d['obs'])[k] ** 2).mean():.3f}", flush=True)
np.savez(f"{OUT}/2022.part.npz", **{**d, "hres": mix})
os.replace(f"{OUT}/2022.part.npz", f"{OUT}/2022.npz")
np.savez(f"models/chorus_{BOX}_old2022.npz", old=old, ok=ok)
print(f"wrote {OUT} (2022: {ok.sum():,} of {len(ok):,} rows mixed, the rest keep the newest run)", flush=True)
