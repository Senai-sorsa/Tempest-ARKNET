"""GW-E part 3 and W10: from the NREL WIND Toolkit points (data/raw/wtk/{SAF,TCS,MAF}_{year}.npz; scripts/fetch_wtk_points.py).
 (a) 10 m speed ratio pad (SAF) / airport (TCS, MAF) by local hour block and by month (same years, same hours);
 (b) Weibull shape k and scale c of the speed at SAF by local hour block and height (W10), mean over the available years.
Local solar time is approximated by UTC-7 (mountain standard time; the pad is at -107 deg). Run:  PYTHONPATH=. python scripts/wtk_pad_factors.py"""
import glob
import os

import numpy as np

H = ["10m", "40m", "80m", "100m", "200m"]
D = "data/raw/wtk"


def load(site):
    out = {}
    for f in sorted(glob.glob(f"{D}/{site}_*.npz")):
        z = np.load(f, allow_pickle=True)
        t = z["time"].astype("datetime64[h]")
        out[int(os.path.basename(f)[4:8])] = (t, {h: z[f"windspeed_{h}"] for h in H})
    return out


def weibull(x):
    x = x[np.isfinite(x) & (x > 0.05)]
    if len(x) < 50:
        return np.nan, np.nan
    lx = np.log(x)
    k = 1.2 / lx.std()                                   # Justus moment estimate refined by Newton steps
    for _ in range(30):
        xk = x ** k
        f = (xk * lx).sum() / xk.sum() - 1.0 / k - lx.mean()
        df = ((xk * lx ** 2).sum() * xk.sum() - ((xk * lx).sum()) ** 2) / xk.sum() ** 2 + 1.0 / k ** 2
        k = max(k - f / df, 0.3)
    return k, (np.mean(x ** k)) ** (1.0 / k)


S, A = load("SAF"), {"TCS": load("TCS"), "MAF": load("MAF")}
blocks = [(0, 4), (4, 8), (8, 12), (12, 16), (16, 20), (20, 24)]
lh = lambda t: (t.astype("datetime64[h]").astype(int) - 7) % 24
mo = lambda t: t.astype("datetime64[M]").astype(int) % 12 + 1
print("(a) pad / airport 10 m speed ratio, same hours (years with both sites)")
for name, ad in A.items():
    yrs = sorted(set(S) & set(ad))
    ps, as_, hh, mm = [], [], [], []
    for y in yrs:
        n = min(len(S[y][0]), len(ad[y][0]))
        ps.append(S[y][1]["10m"][:n]); as_.append(ad[y][1]["10m"][:n]); hh.append(lh(S[y][0][:n])); mm.append(mo(S[y][0][:n]))
    p, a, h, m = map(np.concatenate, (ps, as_, hh, mm))
    print(f" {name} years {yrs}: all-hours ratio {p.mean() / a.mean():.2f}")
    print("   by local hour block " + "  ".join(f"{lo:02d}-{hi:02d}h {p[(h >= lo) & (h < hi)].mean() / a[(h >= lo) & (h < hi)].mean():.2f}" for lo, hi in blocks))
    print("   by month " + " ".join(f"{k}:{p[m == k].mean() / a[m == k].mean():.2f}" for k in range(1, 13)))
print("\n(b) SAF Weibull k / c (m/s) by local hour block, mean over years", sorted(S))
t = np.concatenate([S[y][0] for y in sorted(S)])
h = lh(t)
print("height  " + "  ".join(f"{lo:02d}-{hi:02d}h" .rjust(11) for lo, hi in blocks) + "      all")
for ht in H:
    x = np.concatenate([S[y][1][ht] for y in sorted(S)])
    row = [weibull(x[(h >= lo) & (h < hi)]) for lo, hi in blocks] + [weibull(x)]
    print(f"{ht:6s}  " + "  ".join(f"{k:4.2f}/{c:5.2f}" for k, c in row))
print("\ncalm share (< 0.5 m/s) at SAF 10 m by block:", " ".join(f"{lo:02d}-{hi:02d}h {100 * np.mean(np.concatenate([S[y][1]['10m'] for y in sorted(S)])[(h >= lo) & (h < hi)] < 0.5):.1f}%" for lo, hi in blocks))
