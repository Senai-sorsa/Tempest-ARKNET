"""Step-0 premise checks for New_Plan.md section 12 (ideas VS, FF, SV). Read-only, changes nothing.

(a) VS  : how much of a real balloon profile lives BETWEEN the 13 pressure levels, and how many
          thin unstable layers (Richardson number under 1) a 13-level view of the same balloon loses.
(b) FF  : is the real-air gap (forecast minus balloon, leads 6-24 h) the same along the wind as across it?
(c) SV  : how much of the 10 m gap is a fixed property of the station (ERA5 minus balloon surface wind,
          2016-20), and does a station keep its offset from one half of the dates to the other?

Data on disk only; fit years only (never the 2022 test year, never 2026). About 1.5 GB RAM, a few minutes.

    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b6_ideas_step0.py [root] [stations]

Measurements, no rule set before the run. Readings set afterwards are stated in the plan.
"""
import glob
import os
import sys

import numpy as np

root = sys.argv[1] if len(sys.argv) > 1 else "."
NST = int(sys.argv[2]) if len(sys.argv) > 2 else 90
G = 9.80665
HRES, ERA5 = os.path.join(root, "data/raw/wb2_hres_global"), os.path.join(root, "data/raw/era5_global")
P = np.load(os.path.join(HRES, "points.npz"))
ig = P["igra"]
ecode = {c.split()[0]: (float(c.split()[1]), float(c.split()[2])) for c in np.load(os.path.join(ERA5, "points.npz"))["code"]}
files = {os.path.basename(f)[:-4]: f for f in glob.glob(os.path.join(root, "data/igra_heights/*.npz"))}
ids = sorted(s for s in np.unique(ig[ig != ""]) if s in files)
rng = np.random.default_rng(7)
ids = [ids[i] for i in rng.choice(len(ids), size=min(NST, len(ids)), replace=False)]
pt = np.array([np.where(ig == s)[0][0] for s in ids])
PL = np.array([1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50.0]) * 100.0
BANDS = [(1000, 5000, "1-5 km"), (5000, 12000, "5-12 km"), (12000, 18000, "12-18 km")]


def load(s, y0, y1):
    z = np.load(files[s])
    t = z["time"]
    m = (t >= np.datetime64("%d-01-01T00" % y0)) & (t < np.datetime64("%d-01-01T00" % y1))
    out = {}
    for n in ("u", "v", "T", "lnp"):
        a = z[n][m].astype(np.float32)
        a[a < -32000] = np.nan
        out[n] = a / (2000.0 if n == "lnp" else 10.0)
    out["t"], out["h"], out["lat"] = t[m], z["heights"], (float(z["lat"][-1]) if z["lat"].size else float("nan"))
    return out


# ---------- (a) VS: fine structure between the 13 levels ----------
fine = {b[2]: [] for b in BANDS}
ri_full = {b[2]: [0, 0] for b in BANDS}
ri_coarse = {b[2]: [0, 0] for b in BANDS}
n2s = []
nprof = 0
for s in ids:
    d = load(s, 2019, 2020)
    h = d["h"]
    k18 = h <= 18000
    h = h[k18]
    for i in range(d["t"].size):
        u, v, T, lp = d["u"][i, k18], d["v"][i, k18], d["T"][i, k18], d["lnp"][i, k18]
        ok = np.isfinite(u) & np.isfinite(v) & np.isfinite(T) & np.isfinite(lp)
        if ok.sum() < 40:
            continue
        nprof += 1
        hh, u, v, T, p = h[ok], u[ok], v[ok], T[ok], np.exp(lp[ok])
        th = T * (1e5 / p) ** 0.2857
        zl = np.interp(-np.log(PL), -np.log(p), hh, left=np.nan, right=np.nan)  # heights of the 13 levels
        zl = zl[np.isfinite(zl)]
        if zl.size < 8:
            continue
        zc = np.concatenate([[hh[0]], zl])  # surface value + the levels, as a forecast holds them
        zc = np.unique(zc)
        cu, cv, cth = (np.interp(hh, zc, np.interp(zc, hh, x)) for x in (u, v, th))
        dz = np.diff(hh)
        mid = 0.5 * (hh[1:] + hh[:-1])
        for full, store in (((u, v, th), ri_full), ((cu, cv, cth), ri_coarse)):
            a, b, c = full
            n2 = G / (0.5 * (c[1:] + c[:-1])) * np.diff(c) / dz
            s2 = (np.diff(a) ** 2 + np.diff(b) ** 2) / dz ** 2
            ri = n2 / np.maximum(s2, 1e-10)
            for lo, hi, name in BANDS:
                mm = (mid >= lo) & (mid < hi) & (hh[1:] <= zc[-1])  # only where the 13-level view has data
                store[name][0] += int((ri[mm] < 1).sum())
                store[name][1] += int(mm.sum())
        n2f = G / (0.5 * (th[1:] + th[:-1])) * np.diff(th) / dz
        for lo, hi, name in BANDS:
            mm = (hh >= lo) & (hh < hi) & (hh <= zc[-1])
            if mm.sum() > 3:
                fr = float(np.sqrt(np.mean(((u - cu)[mm] ** 2 + (v - cv)[mm] ** 2) / 2)))
                fine[name].append(fr)
                m2 = (mid >= lo) & (mid < hi)
                n2s.append((BANDS.index((lo, hi, name)), float(np.mean(n2f[m2])), fr))
print("(a) VS  real balloons 2019, %d stations, %d profiles" % (len(ids), nprof))
print("    band      wind between the 13 levels (rms m/s)   thin unstable layers (Ri<1): full balloon / same balloon seen at 13 levels")
for lo, hi, name in BANDS:
    f = np.array(fine[name])
    print("    %-9s %6.2f (p90 %.2f)                       %.3f / %.3f" % (name, np.sqrt(np.mean(f ** 2)), np.percentile(f, 90),
                                                                           ri_full[name][0] / max(ri_full[name][1], 1), ri_coarse[name][0] / max(ri_coarse[name][1], 1)))
A = np.array(n2s)
for j, (lo, hi, name) in enumerate(BANDS):
    a = A[A[:, 0] == j]
    q = np.quantile(a[:, 1], [1 / 3, 2 / 3])
    r = [np.sqrt(np.mean(a[(a[:, 1] < q[0]), 2] ** 2)), np.sqrt(np.mean(a[(a[:, 1] >= q[0]) & (a[:, 1] < q[1]), 2] ** 2)), np.sqrt(np.mean(a[a[:, 1] >= q[1], 2] ** 2))]
    print("    %-9s fine wind by stability third (low / mid / high N^2): %.2f / %.2f / %.2f m/s" % (name, r[0], r[1], r[2]))

# ---------- (b) FF: gap along and across the forecast wind ----------
TARGETS = np.array([1500.0, 5000.0, 9000.0, 12000.0])


def dec(f, n, code=None):
    if code is None:
        code = {c.split()[0]: (float(c.split()[1]), float(c.split()[2])) for c in f["code"]}
    sc, o = code[n]
    return f[n][..., pt].astype(np.float32) * sc + o


bal = {}
for s in ids:
    d = load(s, 2019, 2020)
    z = np.load(files[s])
    hi_ = [int(np.where(d["h"] == x)[0][0]) for x in TARGETS]
    bal[s] = dict(t=d["t"], u=d["u"][:, hi_], v=d["v"][:, hi_], elev=(float(np.nanmedian(z["elev"])) if z["elev"].size else float("nan")), lat=d["lat"])
rows = []
for mo in ("01", "04", "07", "10"):
    f = np.load(os.path.join(HRES, "2019%s.npz" % mo))
    hu, hv, hz = dec(f, "u"), dec(f, "v"), dec(f, "z") / G
    for r in range(f["valid"].size):
        if int(f["lead_h"][r]) > 24:
            continue
        vt = f["valid"][r]
        for k, s in enumerate(ids):
            b = bal[s]
            bi = np.where(b["t"] == vt)[0]
            if bi.size == 0:
                continue
            o = np.argsort(hz[r, :, k])
            for j, tg in enumerate(TARGETS):
                fu = np.interp(b["elev"] + tg, hz[r, o, k], hu[r, o, k], left=np.nan, right=np.nan)
                fv = np.interp(b["elev"] + tg, hz[r, o, k], hv[r, o, k], left=np.nan, right=np.nan)
                du, dv = b["u"][bi[0], j] - fu, b["v"][bi[0], j] - fv  # real minus forecast
                sp = np.hypot(fu, fv)
                if not np.isfinite(du + dv + sp) or sp < 3:
                    continue
                al = (du * fu + dv * fv) / sp
                cr = (-du * fv + dv * fu) / sp * (1.0 if b["lat"] >= 0 else -1.0)  # mirrored in the south
                rows.append((j, sp, du, dv, al, cr))
    f.close()
R = np.array(rows)
print("(b) FF  gap = real minus forecast, leads 6-24 h, forecast wind >= 3 m/s, %d rows" % len(R))
print("    height   sd east / north     sd along / across wind    mean along (real faster +)   mean across (left of wind +, south mirrored)")
for j, tg in enumerate(TARGETS):
    a = R[R[:, 0] == j]
    print("    %5.1f km   %.2f / %.2f          %.2f / %.2f               %+.2f                        %+.2f      n %d" % (
        tg / 1000, a[:, 2].std(), a[:, 3].std(), a[:, 4].std(), a[:, 5].std(), a[:, 4].mean(), a[:, 5].mean(), len(a)))
a = R[R[:, 0] >= 2]
q = np.quantile(a[:, 1], [0.5, 0.9])
for nm, mm in (("slow half", a[:, 1] < q[0]), ("fast half", (a[:, 1] >= q[0]) & (a[:, 1] < q[1])), ("fastest tenth", a[:, 1] >= q[1])):
    print("    9-12 km, %-13s forecast speed %5.1f : mean along %+.2f, sd along %.2f, sd across %.2f" % (nm, a[mm, 1].mean(), a[mm, 4].mean(), a[mm, 4].std(), a[mm, 5].std()))

# ---------- (c) SV: is the 10 m gap a fixed property of the station? ----------
surf = {s: load(s, 2016, 2021) for s in ids}
acc = {s: [] for s in ids}
for y in range(2016, 2021):
    for mo in range(1, 13):
        fn = os.path.join(ERA5, "%d-%02d.npz" % (y, mo))
        if not os.path.exists(fn):
            continue
        e = np.load(fn)
        ev = e["valid_time"]
        eu, evv = dec(e, "u10", ecode), dec(e, "v10", ecode)
        for k, s in enumerate(ids):
            d = surf[s]
            ix = np.searchsorted(d["t"], ev)
            for r in np.where((ix < d["t"].size))[0]:
                if d["t"][ix[r]] != ev[r]:
                    continue
                bu, bv = d["u"][ix[r], 0], d["v"][ix[r], 0]
                if np.isfinite(bu + bv):
                    acc[s].append((np.hypot(bu, bv) - np.hypot(eu[r, k], evv[r, k]), np.hypot(bu, bv), np.hypot(eu[r, k], evv[r, k])))
        e.close()
st = [(s, np.array(v)) for s, v in acc.items() if len(v) >= 40]
allv = np.concatenate([v for _, v in st])
mb = np.array([v[:, 0].mean() for _, v in st])
within = np.sqrt(np.mean([v[:, 0].var() for _, v in st]))
se = np.sqrt(np.mean([v[:, 0].var() / len(v) for _, v in st]))
between = np.sqrt(max(mb.var() - se ** 2, 0))
h1 = np.array([v[0::2, 0].mean() for _, v in st])
h2 = np.array([v[1::2, 0].mean() for _, v in st])
ratio = np.array([v[:, 1].mean() / max(v[:, 2].mean(), 0.1) for _, v in st])
print("(c) SV  10 m speed, real (balloon surface report) minus ERA5, 2016-20: %d stations with >= 40 pairs, %d pairs" % (len(st), len(allv)))
print("    all pairs: mean %+.2f, sd %.2f m/s | station offsets: sd between stations %.2f m/s (after removing sampling noise), sd inside a station %.2f" % (allv[:, 0].mean(), allv[:, 0].std(), between, within))
print("    share of the squared speed gap that is a fixed station offset: %.2f" % (between ** 2 / (between ** 2 + within ** 2)))
print("    same station, odd dates vs even dates: correlation of the offset %.2f | real / ERA5 mean speed per station: p10 %.2f, median %.2f, p90 %.2f" % (
    np.corrcoef(h1, h2)[0, 1], np.percentile(ratio, 10), np.median(ratio), np.percentile(ratio, 90)))
for kk in (5, 10, 30):
    est = np.array([v[:kk, 0].mean() for _, v in st])
    rest = np.array([v[kk:, 0].mean() for _, v in st])
    print("    offset from the first %2d reports explains %.2f of the variance of the station's later offset" % (kk, 1 - np.mean((rest - est) ** 2) / np.mean((rest - rest.mean()) ** 2)))
