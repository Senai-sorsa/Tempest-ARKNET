"""23.T4 step 0: COSMIC-2 NRT atmPrf (dry Temp) vs IGRA balloons at 8-18 km, EPZ/MAF, occultation within 300 km and +-3 h of a balloon.
Usage: python scripts/t4_step0.py 2024 160 [161 ...]   Prints bias/sd per 2 km layer (K, COSMIC minus balloon). Report only."""
import io, sys, tarfile, urllib.request
import numpy as np, pandas as pd, xarray as xr
sys.path[:0] = [".", "new_plan_kit"]
import kit_common as K
yr, days = sys.argv[1], sys.argv[2:]
st = {n: (K.station_pos(s), *K.balloon(s)) for n, s in (("EPZ", K.EPZ), ("MAF", K.MAF))}
def km(a, b, c, d):
    p = np.pi / 180
    return 6371 * np.arccos(np.clip(np.sin(a*p)*np.sin(c*p) + np.cos(a*p)*np.cos(c*p)*np.cos((b-d)*p), -1, 1))
edges = np.arange(8, 19, 2.0)
diffs = {n: [] for n in st}
nocc = {n: 0 for n in st}
for d in days:
    u = f"https://data.cosmic.ucar.edu/gnss-ro/cosmic2/nrt/level2/{yr}/{d}/atmPrf_nrt_{yr}_{d}.tar.gz"
    tf = tarfile.open(fileobj=urllib.request.urlopen(u, timeout=300), mode="r|gz")
    for m in tf:
        if not m.isfile(): continue
        b = tf.extractfile(m).read()
        ds = xr.open_dataset(io.BytesIO(b), engine="scipy" if b[:3] == b"CDF" else "h5netcdf")
        la, lo = float(ds.attrs["lat"]), float(ds.attrs["lon"])
        for n, ((slat, slon, elev), tb, bb) in st.items():
            if km(la, lo, slat, slon) > 300: continue
            t = pd.Timestamp(int(ds.attrs["year"]), int(ds.attrs["month"]), int(ds.attrs["day"]), int(ds.attrs["hour"]), int(ds.attrs["minute"]))
            dt = np.abs((tb - t) / pd.Timedelta("1h"))
            i = int(np.argmin(dt))
            if dt[i] > 3: continue
            nocc[n] += 1
            z = ds["MSL_alt"].values; T = ds["Temp"].values + 273.15
            ok = np.isfinite(z) & np.isfinite(T)
            o = np.argsort(z); z, T, ok = z[o], T[o], ok[o]   # profile is stored top-down
            zb = K.H + elev
            tbal = bb["T"][i]
            for lo_, hi_ in zip(edges[:-1], edges[1:]):
                mk = (zb >= lo_ * 1000) & (zb < hi_ * 1000) & np.isfinite(tbal)
                if mk.sum() and ok.sum() > 50:
                    diffs[n].append((lo_, float(np.mean(np.interp(zb[mk] / 1000, z[ok], T[ok]) - tbal[mk]))))
    print("day", d, nocc, flush=True)
for n in st:
    row = [f"{lo}-{lo+2} km: {np.mean(v):+.2f} K sd {np.std(v):.2f} (n {len(v)})" for lo in edges[:-1] if (v := [x for l, x in diffs[n] if l == lo])]
    print(n, nocc[n], "matched occultations;", "; ".join(row))
