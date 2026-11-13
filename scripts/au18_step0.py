"""AU-18 step 0 (New_Plan 15.3): does a pressure level just above the 100 m anchor make a false shear step in 100-150 m?
For sample years of the raw store (era5_em80 + the CDS fill, the profiles80 recipe, kept hours, every 4th time), per column:
flag = some pressure level sits at 100-150 m above ground. Wind shear |dV|/dz of the 100-150 m layer (store heights 100 and 150)
as built now (levels used from 100 m up) and with levels used only from 150 m up (the proposed fix). Prints the flagged share and
the p50 / p99 shear of flagged and other rows, both ways. Rule: act (from 150 m up, at the next planned store rebuild) only if the
flagged rows' p99 is clearly above the others' and the fix removes it. Writes models/au18_step0.csv.
Usage: PYTHONPATH=. python scripts/au18_step0.py [--years 1995 2010 2024] [--every 4]"""
import argparse
import os

import numpy as np
import pandas as pd

from tempest.profiles.to_heights import CDS_LEVELS, HEIGHTS, cds_levels, geometric_height, interp_columns, open_raw, parse_hours

ap = argparse.ArgumentParser()
ap.add_argument("--raw", default="data/raw/era5_em80")
ap.add_argument("--cds", default="data/raw/era5_cds")
ap.add_argument("--years", type=int, nargs="+", default=[1995, 2010, 2024])
ap.add_argument("--every", type=int, default=4)
ap.add_argument("--out", default="models/au18_step0.csv")
a = ap.parse_args()
i100, i150 = int(np.flatnonzero(HEIGHTS == 100)[0]), int(np.flatnonzero(HEIGHTS == 150)[0])
ds = open_raw(a.raw)
ds = ds.sel(valid_time=ds.valid_time.dt.hour.isin(parse_hours("12-23,0-4")))
z_sfc = ds.z_sfc.values.ravel()
rows = []
for y in a.years:
    b = ds.sel(valid_time=str(y)).isel(valid_time=slice(None, None, a.every)).load()
    n_pt = b.sizes["latitude"] * b.sizes["longitude"]
    em = lambda n: b[n].transpose("latitude", "longitude", "valid_time", "pressure_level").values.reshape(n_pt, -1, b.sizes["pressure_level"])
    if os.path.isdir(a.cds) and y >= 1991:
        fill = cds_levels(a.cds, b.valid_time.values, b.latitude.values, b.longitude.values)
        lv = lambda n: np.concatenate([em(n), fill[n].reshape(n_pt, -1, len(CDS_LEVELS))], -1)
    else:
        lv = em
    sf = lambda n: b[n].transpose("latitude", "longitude", "valid_time").values.reshape(n_pt, -1)
    zs = np.broadcast_to(z_sfc[:, None], sf("u10").shape)
    agl = geometric_height(lv("z")) - geometric_height(zs)[..., None]
    agl = np.where(agl > 0, agl, np.nan)
    flag = ((agl > 100) & (agl <= 150)).any(-1)
    shape = agl.shape[:-1] + (1,)
    u, v = lv("u"), lv("v")
    for how, start in (("now", 100.0), ("from150", 150.0)):   # "now" is profiles_from_levels' wind line
        hw = np.concatenate([np.full(shape, 10.0), np.full(shape, 100.0), np.where(agl > start, agl, np.nan)], -1)
        U = interp_columns(hw, np.concatenate([sf("u10")[..., None], sf("u100")[..., None], u], -1), HEIGHTS, 100)
        V = interp_columns(hw, np.concatenate([sf("v10")[..., None], sf("v100")[..., None], v], -1), HEIGHTS, 100)
        sh = np.hypot(U[..., i150] - U[..., i100], V[..., i150] - V[..., i100]) / 50.0
        for grp, m in (("flagged", flag), ("other", ~flag)):
            s = sh[m & np.isfinite(sh)]
            rows.append(dict(year=y, how=how, rows=grp, n=s.size, share=float(flag.mean()), p50=np.quantile(s, 0.5) if s.size else np.nan,
                             p99=np.quantile(s, 0.99) if s.size else np.nan))
    print(f"{y}: {flag.mean():.4f} of columns have a level at 100-150 m AGL", flush=True)
df = pd.DataFrame(rows)
df.to_csv(a.out, index=False)
print(df.to_string(index=False))
f = df.groupby(["how", "rows"]).apply(lambda g: np.average(g.p99, weights=g.n), include_groups=False)
print(f"[AU18] flagged share {df.share.mean():.4f}; p99 shear (1/s) now: flagged {f['now', 'flagged']:.4f} other {f['now', 'other']:.4f}; "
      f"from 150 m: flagged {f['from150', 'flagged']:.4f} other {f['from150', 'other']:.4f}", flush=True)
