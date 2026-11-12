"""RA stage 1a (New_Plan.md section 11.6): gap rows from disk + arm A1 (6 numbers). Changes nothing in the tool.

Rows: every HRES forecast (lead 6-240 h) at a balloon station point whose valid time has a balloon AND an
ERA5 field, years 2016-22 (never 2026). Compared at the 13 HRES level heights (+10 m): balloon (fine
81-height profile, interpolated), HRES (exact), ERA5 (interpolated in its own heights).
Arm A1: real = forecast + model error (sd per lead bin and band, from fc-ERA5) + gap (sd per band,
gap^2 = mean (fc-balloon)^2 - mean (fc-ERA5)^2, per wind component). Six bands -> six gap numbers.
Fit: valid years 2016-20, stations not left out. Check: left-out stations (1 in 5 by a fixed crc32
hash, the 7 world-held stations, El Paso / Midland / Denver), 2022 (and 2016-20 as a larger look).

Rule set before the run (section 11.6, stage 1a): PASS if the A1 90 % band covers the balloon
0.87-0.93 in every band at left-out stations; KILL if any band is below 0.85 (the gap is not a
simple added part). The 2022 sample is small (about 30 balloon times): quick look, no final verdict.

    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b6_realair_rows.py [root] [max_months]
"""
import glob
import os
import sys
import zlib

import numpy as np

root = sys.argv[1] if len(sys.argv) > 1 else "."
MAXM = int(sys.argv[2]) if len(sys.argv) > 2 else 999
G, Z90 = 9.80665, 1.6448536
HRES, ERA5 = os.path.join(root, "data/raw/wb2_hres_global"), os.path.join(root, "data/raw/era5_global")
P = np.load(os.path.join(HRES, "points.npz"))
ig = P["igra"]
ecode = {c.split()[0]: (float(c.split()[1]), float(c.split()[2])) for c in np.load(os.path.join(ERA5, "points.npz"))["code"]}
files = {os.path.basename(f)[:-4]: f for f in glob.glob(os.path.join(root, "data/igra_heights/*.npz"))}
ids = sorted(s for s in np.unique(ig[ig != ""]) if s in files)
pt = np.array([np.where(ig == s)[0][0] for s in ids])
held = set(P["held_igra"]) | {"USM00072364", "USM00072265", "USM00072469"}  # world-held + El Paso, Midland, Denver
out = np.array([s in held or zlib.crc32(s.encode()) % 5 == 0 for s in ids])
BANDS = [(0, 11, "10 m"), (11, 1500, "0-1.5 km"), (1500, 3000, "1.5-3 km"), (3000, 6000, "3-6 km"), (6000, 10000, "6-10 km"), (10000, 17000, "10-17 km")]
LEADS = [(6, 24, "6-24 h"), (30, 72, "1-3 d"), (78, 144, "3-6 d"), (150, 240, "6-10 d")]
mfiles = sorted(glob.glob(os.path.join(HRES, "20[12][0-9][01][0-9].npz")))[:MAXM]
months = [os.path.basename(f)[:6] for f in mfiles]
assert months and not any(m.startswith("2026") for m in months)


def dec(f, n, code=None):
    if code is None:
        code = {c.split()[0]: (float(c.split()[1]), float(c.split()[2])) for c in f["code"]}
    s, o = code[n]
    return f[n][..., pt].astype(np.float32) * s + o


# valid times that can match: HRES valid times with an ERA5 row at the same time
want_t = set()
for fp, mo in zip(mfiles, months):
    hv = np.load(fp)["valid"].astype("datetime64[h]")
    ev = np.load(os.path.join(ERA5, "%s-%s.npz" % (mo[:4], mo[4:6])))["valid_time"].astype("datetime64[h]")
    want_t |= set(np.intersect1d(hv, ev).tolist())
want_t = np.array(sorted(want_t), dtype="datetime64[h]")

bal = {}  # station index -> times, heights AGL, u, v (m/s), elev; matchable times only (full files are about 9 GB)
for k, s in enumerate(ids):
    z = np.load(files[s])
    t = z["time"].astype("datetime64[h]")
    m = np.isin(t, want_t)
    if not m.any():
        continue
    u, v = z["u"][m].astype(np.float32), z["v"][m].astype(np.float32)
    u[u <= -32000], v[v <= -32000] = np.nan, np.nan
    bal[k] = (t[m], z["heights"].astype(np.float64), u / 10, v / 10, float(np.nanmedian(z["elev"][m])))


def interp(zx, x, want):
    ok = np.isfinite(zx) & np.isfinite(x)
    if ok.sum() < 2:
        return np.full(np.shape(want), np.nan)
    o = np.argsort(zx[ok])
    return np.interp(want, zx[ok][o], x[ok][o], left=np.nan, right=np.nan)


rows = []  # year, lead, station k, height AGL, du_fe, dv_fe, du_fb, dv_fb
for fp, mo in zip(mfiles, months):
    f = np.load(fp)
    e = np.load(os.path.join(ERA5, "%s-%s.npz" % (mo[:4], mo[4:6])))
    ev = e["valid_time"].astype("datetime64[h]")
    hvs = f["valid"].astype("datetime64[h]")
    rsel = [r for r in range(hvs.size) if np.isin(hvs[r], want_t) and 6 <= int(f["lead_h"][r]) <= 240]
    if not rsel:
        continue
    hu, hv, hz = dec(f, "u"), dec(f, "v"), dec(f, "z") / G
    hu10, hv10 = dec(f, "u10"), dec(f, "v10")
    eu, evv, ez = dec(e, "u", ecode), dec(e, "v", ecode), dec(e, "z", ecode) / G
    eu10, ev10 = dec(e, "u10", ecode), dec(e, "v10", ecode)
    yr = int(mo[:4])
    for r in rsel:
        vt, lead = hvs[r], int(f["lead_h"][r])
        ei = int(np.where(ev == vt)[0][0])
        for k, b in bal.items():
            bi = np.where(b[0] == vt)[0]
            if bi.size == 0 or not np.isfinite(b[4]):
                continue
            bi = int(bi[0])
            hagl = hz[r, :, k] - b[4]
            lv = hagl > 50  # levels below or at the ground are skipped
            want = hagl[lv]
            bU, bV = interp(b[1], b[2][bi], want), interp(b[1], b[3][bi], want)
            eU, eV = interp(ez[ei, :, k] - b[4], eu[ei, :, k], want), interp(ez[ei, :, k] - b[4], evv[ei, :, k], want)
            fU, fV = hu[r, lv, k], hv[r, lv, k]
            n = want.size
            blk = np.empty((n + 1, 8), dtype=np.float32)  # float32 blocks: tuples would need about 8 GB for all years
            blk[:, 0], blk[:, 1], blk[:, 2] = yr, lead, k
            blk[:n, 3], blk[:n, 4], blk[:n, 5], blk[:n, 6], blk[:n, 7] = want, fU - eU, fV - eV, fU - bU, fV - bV
            blk[n] = (yr, lead, k, 10.0, hu10[r, k] - eu10[ei, k], hv10[r, k] - ev10[ei, k], hu10[r, k] - b[2][bi, 0], hv10[r, k] - b[3][bi, 0])
            rows.append(blk)
    f.close(), e.close()

R = np.concatenate(rows).astype(np.float64)
R = R[np.isfinite(R[:, 4:]).all(axis=1)]
R = R[np.abs(R[:, 4:]).max(axis=1) < 60]  # shortcut: drops rows with impossible errors (bad reports); no other balloon QC
yr, lead, kk, h = R[:, 0], R[:, 1], R[:, 2].astype(int), R[:, 3]
lo = out[kk]
band = np.full(len(R), -1)
for j, (a, b_, _) in enumerate(BANDS):
    band[(h >= a) & (h < b_)] = j
lbin = np.full(len(R), -1)
for j, (a, b_, _) in enumerate(LEADS):
    lbin[(lead >= a) & (lead <= b_)] = j
fit = (yr <= 2020) & ~lo & (band >= 0) & (lbin >= 0)


def ms(x):
    return float(np.mean(np.concatenate([x[:, 0], x[:, 1]]) ** 2))


sd_m = np.zeros((len(LEADS), len(BANDS)))
gap = np.zeros(len(BANDS))
for j in range(len(BANDS)):
    mj = fit & (band == j)
    assert mj.sum() > 0, "no fit rows in band %d" % j
    gap[j] = max(ms(R[mj][:, 6:8]) - ms(R[mj][:, 4:6]), 0.0) ** 0.5
    for i in range(len(LEADS)):
        sd_m[i, j] = ms(R[mj & (lbin == i)][:, 4:6]) ** 0.5
print("months %d (%s..%s), stations %d (left out %d), matchable valid times %d, rows %d" % (len(months), months[0], months[-1], len(ids), int(out.sum()), want_t.size, len(R)))
print("A1 gap sd per band (m/s, per component), fit 2016-20 kept stations:", "  ".join("%s %.2f" % (n, g) for (_, _, n), g in zip(BANDS, gap)))
print("model error sd (fc-ERA5) per lead x band:")
for i, (_, _, ln) in enumerate(LEADS):
    print("  %-7s" % ln, "  ".join("%.2f" % x for x in sd_m[i]))


def cover(sel, with_gap):
    s = np.sqrt(sd_m[lbin[sel], band[sel]] ** 2 + (gap[band[sel]] ** 2 if with_gap else 0.0))
    return float(np.mean(np.concatenate([np.abs(R[sel, 6]) <= Z90 * s, np.abs(R[sel, 7]) <= Z90 * s])))


verdict = []
for name, ysel in (("2022 (test)", yr == 2022), ("2016-20 (larger look)", yr <= 2020)):
    print("90 %% band coverage at LEFT-OUT stations, %s: A0 = model error only, A1 = + gap" % name)
    for j, (_, _, bn) in enumerate(BANDS):
        sel = ysel & lo & (band == j) & (lbin >= 0)
        if sel.sum() < 30:
            print("  %-9s too few rows (%d)" % (bn, sel.sum()))
            continue
        c0, c1 = cover(sel, False), cover(sel, True)
        print("  %-9s A0 %.3f  A1 %.3f  n %d" % (bn, c0, c1, sel.sum()))
        if name.startswith("2022"):
            verdict.append(c1)
if verdict:
    lo_c, hi_c = min(verdict), max(verdict)
    print("RULE (2022 left-out): min %.3f max %.3f over %d bands ->" % (lo_c, hi_c, len(verdict)),
          "KILL" if lo_c < 0.85 else "PASS" if (lo_c >= 0.87 and hi_c <= 0.93 and len(verdict) == len(BANDS)) else "NEITHER (between the rules)")
