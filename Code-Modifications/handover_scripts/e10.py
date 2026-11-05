"""E10: score the held-out balloons sonde.py drops (incomplete), per cell where the balloon has data, vs the complete ones.
Mirrors tempest/scoring/sonde.py (unknown drivers, clim15 from the same station/month, calibrated) on 2024-25."""
import sys
import numpy as np, torch, xarray as xr
from tempest.calibrate import spread
from tempest.calibrate.station import ELEV, STATIONS, nearest_point, read_igra
from tempest.generator.build_dataset import solar_hour
from tempest.generator.features import FEATURES, features
from tempest.generator.sample import Sampler, to_site
from tempest.ingest import indices
from tempest.scoring.score import band_masks, coverage90, crps_ensemble
model, calib = sys.argv[1], sys.argv[2]
M, HELD, LAST, DR = 199, 2024, 2025, ["oni", "wwv", "qbo30", "qbo50"]
rng = np.random.default_rng(0)
sampler = Sampler(torch.load(model, map_location="cpu", weights_only=True)); cal = spread.load(calib)
ds = xr.open_zarr("data/pilot/profiles80.zarr"); tbl = indices.load("data/raw/indices")
acc = {k: [] for k in ("y", "unk", "c15", "inc")}
for sid, (slat, slon) in STATIONS.items():
    t, prof, sfc = read_igra(f"data/raw/igra/{sid}-drvd.txt.zip", 1991, LAST)
    phys = np.concatenate([prof.reshape(len(t), -1), sfc], 1)
    fin = np.isfinite(phys); z00 = np.asarray(t.hour == 0)
    full = z00 & fin.all(1)
    tr = np.flatnonzero(full & np.asarray(t.year < HELD) & np.asarray(t.year >= HELD - 15))
    va = np.flatnonzero(z00 & np.asarray(t.year >= HELD) & (fin.mean(1) > 0))
    p = nearest_point(ds, slat, slon); lat, lon, z = (float(ds[k].values[p]) for k in ("lat", "lon", "z_sfc"))
    for mo in range(1, 13):
        v, r = va[t.month[va] == mo], tr[t.month[tr] == mo]
        if len(v) == 0: continue
        draws = r[rng.integers(0, len(r), (len(v), M))]
        tv = t[v]
        cond = features(lat, lon, z, z, tv.dayofyear.to_numpy(), solar_hour(tv, np.array([lon]))[0],
                        tv.year.to_numpy(), *indices.at(tbl, tv)[:, [0, 3, 1, 2]].T)
        rep = np.repeat(cond, M, axis=0); dc = [FEATURES.index(k) for k in DR]
        rep[:, dc] = features(0, 0, 0, 0, 0, 0, 0, *indices.at(tbl, t[draws.ravel()])[:, [0, 3, 1, 2]].T)[:, dc]
        acc["unk"].append(to_site(spread.apply(cal, sampler.profiles(rep).reshape(len(v), M, -1)), z, ELEV[sid]))
        acc["c15"].append(phys[draws]); acc["y"].append(phys[v]); acc["inc"].append(~full[v])
y, unk, c15, inc = (np.concatenate(acc[k]) for k in ("y", "unk", "c15", "inc"))
ok = np.isfinite(y); y0 = np.where(ok, y, 0)
cm, cc, cv = crps_ensemble(unk, y0), crps_ensemble(c15, y0), coverage90(unk, y0, 0.99)
print(f"held-out {HELD}-{LAST} 00Z: {(~inc).sum()} complete, {inc.sum()} incomplete soundings")
print(f"{'var':5}{'band':9}{'skill15 complete':>18}{'skill15 incomplete':>20}{'cov99 compl':>13}{'cov99 incompl':>15}{'cells kept':>12}")
for v, b, sel in band_masks():
    row = []
    for s in (~inc, inc):
        mk = ok[s][:, sel]
        row += [1 - cm[s][:, sel][mk].sum() / cc[s][:, sel][mk].sum(), cv[s][:, sel][mk].mean(), mk.mean()]
    print(f"{v:5}{b:9}{row[0]:18.3f}{row[3]:20.3f}{row[1]:13.4f}{row[4]:15.4f}{row[5]:12.2f}")
