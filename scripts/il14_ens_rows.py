"""L14 (2026-11-10): IFS ensemble features for mode F (user decision 2026-11-08: use the files as they are, no imputation; accept only if better than HRES-only on the same rows).
From the mode F rows of the 00Z + 12Z refetch (data/modeF_v2/<year>.npz), keep the 00Z starts at whole-day leads 1-7 d that have an IFS ensemble start at the same time (data/raw/wb2_ifs_ens,
00Z every 8 days, 50 members, 500 / 700 / 850 hPa), and add 24 features at the row's grid point: ensemble mean and spread of u10, v10, t2m and of u, v, t at the three levels. Rows where any
feature is missing (source gaps 2016-17) are dropped, never filled. Writes data/modeF_ens/<year>.npz (the same fields as the source rows + `ens` (n, 24)); HRES-only and ensemble runs of
scripts/il6_modeF.py then use exactly these rows. Test year 2022 (the HRES rows end in 2022, so the decision's 2024 test is not possible).
    PYTHONPATH=. python -W ignore scripts/il14_ens_rows.py"""
import os

import numpy as np
import pandas as pd
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC, OUT, ENS = (os.path.join(REPO, *p) for p in (("data", "modeF_v2"), ("data", "modeF_ens"), ("data", "raw", "wb2_ifs_ens")))


def main():
    os.makedirs(OUT, exist_ok=True)
    for y in range(2016, 2023):
        d = dict(np.load(os.path.join(SRC, f"{y}.npz")))
        lh = d["lead_hours"].astype(int)
        keep = (d["start_hour"] == 0) & (lh % 24 == 0) & (lh >= 24) & (lh <= 168)
        d = {k: v[keep] for k, v in d.items()}
        init = pd.DatetimeIndex(d["valid"]) - pd.to_timedelta(d["lead_hours"].astype(int), unit="h")
        feats = np.full((len(init), 24), np.nan, np.float32)
        for ym in sorted({(t.year, t.month) for t in init}):
            f = os.path.join(ENS, f"{ym[0]}{ym[1]:02d}_00z.nc")
            if not os.path.exists(f):
                continue
            e = xr.open_dataset(f)
            et = pd.DatetimeIndex(e.time.values)
            el = (e.prediction_timedelta.values // np.timedelta64(1, "h")).astype(int)
            lat, lon = e.latitude.values, e.longitude.values - 360.0
            rows = np.flatnonzero((init.year == ym[0]) & (init.month == ym[1]))
            arrs = {v: e[v].values for v in ("u10", "v10", "t2m", "u", "v", "t")}
            for r in rows:
                ti = et.get_indexer([init[r]])[0]
                li = np.flatnonzero(el == int(d["lead_hours"][r]))
                if ti < 0 or not len(li):
                    continue
                i, j = int(np.abs(lat - d["lat"][r]).argmin()), int(np.abs(lon - d["lon"][r]).argmin())
                vals = []
                for v in ("u10", "v10", "t2m"):
                    x = arrs[v][ti, :, li[0], i, j] if arrs[v].ndim == 5 else arrs[v][ti, :, li[0], i, j]
                    vals += [np.nanmean(x), np.nanstd(x)]
                for v in ("u", "v", "t"):
                    x = arrs[v][ti, :, li[0], :, i, j]                                    # (members, levels)
                    vals += list(np.ravel(np.stack([np.nanmean(x, 0), np.nanstd(x, 0)], 1)))
                if np.isfinite(vals).all() and np.isfinite(arrs["u"][ti, :, li[0], :, i, j]).all():
                    feats[r] = vals
            e.close()
        ok = np.isfinite(feats).all(1)
        out = {k: v[ok] for k, v in d.items()}
        out["ens"] = feats[ok]
        np.savez(os.path.join(OUT, f"{y}.npz"), **out)
        print(y, f"{int(ok.sum()):,} rows with a complete ensemble of {len(ok):,} 00Z whole-day rows", flush=True)


if __name__ == "__main__":
    main()
