"""RA step 0 (New_Plan.md section 11): read-only premise check for the real-air idea. Changes nothing.

How far is a forecast from the REAL balloon, compared with how far it is from ERA5 (today's truth)?
'gap' = sqrt(fc-balloon^2 - fc-ERA5^2): the part of the real error that the ERA5 truth cannot show.
Data on disk only: data/raw/wb2_hres_global (HRES at 7483 world points, 986 of them balloon stations),
data/raw/era5_global, data/igra_heights. Year 2019 (a fit year; never the 2022 test year, never 2026),
4 months, sampled stations. Model levels are interpolated linearly in height (13 levels): this adds a
little error to both balloon columns, so 'gap' is an upper estimate. About 1.5 GB RAM, 3 minutes.

    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b6_realair_step0.py [root] [stations]

No rule was set before this run (it is a measurement). Reading set afterwards, stated in the plan:
the idea is dead if 'gap' is under 0.5 m/s (balloon noise alone) or if it grows with lead.
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
TARGETS = np.array([1500.0, 3000.0, 5000.0, 9000.0, 12000.0])
LEADS = [(6, 24, "6-24 h"), (72, 120, "3-5 d"), (168, 240, "7-10 d")]


def dec(f, n, code=None):
    if code is None:
        code = {c.split()[0]: (float(c.split()[1]), float(c.split()[2])) for c in f["code"]}
    s, o = code[n]
    return f[n][..., pt].astype(np.float32) * s + o


def at_heights(z_asl, x, want_asl):
    o = np.argsort(z_asl)
    return np.interp(want_asl, z_asl[o], x[o], left=np.nan, right=np.nan)


bal = {}
for s in ids:
    z = np.load(files[s])
    t = z["time"]
    m = (t >= np.datetime64("2019-01-01T00")) & (t < np.datetime64("2020-01-01T00"))
    h = z["heights"]
    hi = [int(np.where(h == x)[0][0]) for x in TARGETS]
    u, v = z["u"][m].astype(np.float32), z["v"][m].astype(np.float32)
    u[u < -32000], v[v < -32000] = np.nan, np.nan
    bal[s] = dict(t=t[m], u=u[:, hi] / 10, v=v[:, hi] / 10, u10=u[:, 0] / 10, v10=v[:, 0] / 10, elev=float(np.nanmedian(z["elev"][m])) if m.any() else np.nan)

keys = []
rows = []  # lead, band, hres-era5 (u,v), hres-balloon (u,v), era5-balloon (u,v)
sfc = []  # lead, speeds: balloon, hres, era5 ; vector diffs
for mo in ("01", "04", "07", "10"):
    f = np.load(os.path.join(HRES, "2019%s.npz" % mo))
    e = np.load(os.path.join(ERA5, "2019-%s.npz" % mo))
    ev = e["valid_time"]
    hu, hv, hz = dec(f, "u"), dec(f, "v"), dec(f, "z") / G
    hu10, hv10 = dec(f, "u10"), dec(f, "v10")
    eu, evv, ez = dec(e, "u", ecode), dec(e, "v", ecode), dec(e, "z", ecode) / G
    eu10, ev10 = dec(e, "u10", ecode), dec(e, "v10", ecode)
    for r in range(f["valid"].size):
        vt, lead = f["valid"][r], int(f["lead_h"][r])
        ei = np.where(ev == vt)[0]
        if ei.size == 0:
            continue
        ei = int(ei[0])
        for k, s in enumerate(ids):
            b = bal[s]
            bi = np.where(b["t"] == vt)[0]
            if bi.size == 0 or not np.isfinite(b["elev"]):
                continue
            bi = int(bi[0])
            want = b["elev"] + TARGETS
            hU, hV = at_heights(hz[r, :, k], hu[r, :, k], want), at_heights(hz[r, :, k], hv[r, :, k], want)
            eU, eV = at_heights(ez[ei, :, k], eu[ei, :, k], want), at_heights(ez[ei, :, k], evv[ei, :, k], want)
            for j in range(TARGETS.size):
                rows.append((lead, j, hU[j] - eU[j], hV[j] - eV[j], hU[j] - b["u"][bi, j], hV[j] - b["v"][bi, j], eU[j] - b["u"][bi, j], eV[j] - b["v"][bi, j]))
            keys.append((k, vt))
            sfc.append((lead, np.hypot(b["u10"][bi], b["v10"][bi]), np.hypot(hu10[r, k], hv10[r, k]), np.hypot(eu10[ei, k], ev10[ei, k]),
                        hu10[r, k] - eu10[ei, k], hv10[r, k] - ev10[ei, k], hu10[r, k] - b["u10"][bi], hv10[r, k] - b["v10"][bi]))
    f.close(), e.close()

R, S = np.array(rows, dtype=np.float64), np.array(sfc, dtype=np.float64)
rm = lambda a, b: float(np.sqrt(np.nanmean((a ** 2 + b ** 2) / 2)))
nb = len({(k, t) for k, t in keys})
print("stations %d, year 2019 (4 months), matched forecast-balloon-ERA5 triples %d from %d distinct balloons on %d distinct valid times" % (len(ids), len(S), nb, len({t for _, t in keys})))
print("wind error per component, m/s (RMSE). model truth = forecast vs ERA5; real truth = forecast vs balloon")
print("%-8s %-8s %10s %10s %10s %8s %8s %8s" % ("lead", "height", "fc-ERA5", "fc-balloon", "ERA5-ball", "ratio", "gap", "n"))
for lo, hi, name in LEADS:
    for j, h in enumerate(TARGETS):
        m = (R[:, 0] >= lo) & (R[:, 0] <= hi) & (R[:, 1] == j) & np.isfinite(R[:, 2:]).all(axis=1)
        if m.sum() < 30:
            continue
        a, b, c = rm(R[m, 2], R[m, 3]), rm(R[m, 4], R[m, 5]), rm(R[m, 6], R[m, 7])
        print("%-8s %-8d %10.2f %10.2f %10.2f %8.2f %8.2f %8d" % (name, h, a, b, c, b / a, max(b * b - a * a, 0.0) ** 0.5, m.sum()))
print("10 m wind (balloon surface report vs model 10 m wind):")
for lo, hi, name in LEADS:
    m = (S[:, 0] >= lo) & (S[:, 0] <= hi) & np.isfinite(S[:, 1:]).all(axis=1)
    if m.sum() < 30:
        continue
    print("%-8s fc-ERA5 %.2f  fc-real %.2f  ratio %.2f  gap %.2f | mean speed real %.2f fc %.2f ERA5 %.2f | calm (<1 m/s) real %.3f fc %.3f ERA5 %.3f | p95 speed real %.1f fc %.1f ERA5 %.1f | n %d" % (
        name, rm(S[m, 4], S[m, 5]), rm(S[m, 6], S[m, 7]), rm(S[m, 6], S[m, 7]) / rm(S[m, 4], S[m, 5]), max(rm(S[m, 6], S[m, 7]) ** 2 - rm(S[m, 4], S[m, 5]) ** 2, 0.0) ** 0.5, S[m, 1].mean(), S[m, 2].mean(), S[m, 3].mean(),
        (S[m, 1] < 1).mean(), (S[m, 2] < 1).mean(), (S[m, 3] < 1).mean(), np.percentile(S[m, 1], 95), np.percentile(S[m, 2], 95), np.percentile(S[m, 3], 95), m.sum()))
