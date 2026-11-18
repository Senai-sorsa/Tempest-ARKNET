"""E3 step 1 part B2 (variation of b77, pre-set rule unchanged): the pair spread is multiplied by one factor f per radar-month-lag, fit on the FIT (odd) days only by 2-fold cross-validation (f = 90th percentile of |z| / 1.645); everything else as b77.
(b77 doc follows) E3 step 1 part B (New_Plan 16.4 E3): radar pair ensemble vs the tool + observe_radar, same targets.
Cases: radar (MAF Jan/Apr/Jun/Sep 2024, HDX Jun 2024) even days, start 15 UTC (volume at 15 UTC = the observation), target = the radar volume k h later (k = 1, 2, 3), scored at the model
heights 0.5-5 km above the radar (u and v). Tool arm: Launch(radar position, target time, climate-AI mode, n 200).observe_radar(profile = the 15 UTC radar u, v, default levels and sigma).
Pair arm: Gaussian from the odd-day fit of part A (start hour 15, same month and radar), CRPS closed form. Tool arm CRPS from its 200 members. Coverage = share inside the central 90 %.
PRE-SET RULE (before the run): PASS if pair CRPS <= 0.90 x tool + observe_radar CRPS at EACH of k = 1, 2, 3 (the plan's -10 %) and pair 90 % coverage in 0.85-0.95. Else MISS.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b78_e3_pairs_step1c.py     Result: docs/results/logs/kit_b78_e3_pairs_step1c.log
"""
import glob
import os
from math import erf, pi, sqrt

import numpy as np
import pandas as pd

import kit_common as K
from p3_vad_vs_balloon import parse

SETS = [("MAF", "2024-01"), ("MAF", "2024-04"), ("MAF", "2024-06"), ("MAF", "2024-09"), ("HDX", "2024-06")]
POS = {"MAF": (31.943, -102.189, 872.0), "HDX": (32.8506, -106.1228, 1287.0)}
LAGS = (1, 2, 3)
band = (K.H >= 500) & (K.H <= 5000)
_N = np.vectorize(lambda z: 0.5 * (1 + erf(z / sqrt(2))))


def crps_g(mu, sd, y):
    z = (y - mu) / sd
    return sd * (z * (2 * _N(z) - 1) + 2 * np.exp(-z * z / 2) / sqrt(2 * pi) - 1 / sqrt(pi))


def load(rad, month, elev):
    first = {}
    for f in sorted(glob.glob(f"data/raw/nexrad_nvw_t3/{rad}_NVW_{month.replace('-', '_')}_*")):
        t = pd.to_datetime(os.path.basename(f)[8:], format="%Y_%m_%d_%H_%M_%S").floor("h")
        first.setdefault(t, f)
    W = {}
    for t, f in first.items():
        try:
            W[t] = np.stack(parse(f, elev))          # (2, 44)
        except Exception:
            pass
    return W


def main():
    from tempest_weather_v2 import Launch
    K.ram_gate(3.0)
    S = {k: {"tool": [], "pair": [], "cov_t": [], "cov_p": []} for k in LAGS}
    for rad, month in SETS:
        lat, lon, elev = POS[rad]
        W = load(rad, month, elev)
        for k in LAGS:
            fit = [t for t in W if t.hour == 15 and t.day % 2 == 1 and t + pd.Timedelta(hours=k) in W]
            test = [t for t in W if t.hour == 15 and t.day % 2 == 0 and t + pd.Timedelta(hours=k) in W]
            if len(fit) < 8 or not test:
                continue
            a = np.stack([W[t][:, band] for t in fit]); b = np.stack([W[t + pd.Timedelta(hours=k)][:, band] for t in fit])
            zs = []
            for h in (0, 1):
                tr, ho = np.flatnonzero(np.arange(len(fit)) % 2 != h), np.flatnonzero(np.arange(len(fit)) % 2 == h)
                for c in range(2):
                    for j in range(a.shape[2]):
                        x, z_ = a[tr, c, j], b[tr, c, j]; m = np.isfinite(x) & np.isfinite(z_)
                        if m.sum() < 6 or x[m].std() < 1e-6 or z_[m].std() < 1e-6:
                            continue
                        mx, my, sx, sy = x[m].mean(), z_[m].mean(), x[m].std(), z_[m].std()
                        rho = float(np.corrcoef(x[m], z_[m])[0, 1]); sd = sy * sqrt(max(1 - rho * rho, 1e-4))
                        xo, yo = a[ho, c, j], b[ho, c, j]; mo = np.isfinite(xo) & np.isfinite(yo)
                        zs += list(np.abs(yo[mo] - (my + rho * (xo[mo] - mx) * sy / sx)) / sd)
            fct = float(np.quantile(zs, 0.9) / 1.645) if len(zs) > 50 else 1.0
            print(rad, month, "lag", k, "spread factor", round(fct, 2), flush=True)
            for t in test:
                x0, y0 = W[t], W[t + pd.Timedelta(hours=k)]
                ok = np.isfinite(x0[0]) & np.isfinite(x0[1])
                if ok.sum() < 8:
                    continue
                prof = dict(heights_asl_m=list(K.H[ok] + elev), u=list(x0[0][ok]), v=list(x0[1][ok]), site=rad, time=str(t))
                tt = t + pd.Timedelta(hours=k)
                try:
                    L = Launch(lat, lon, tt.strftime("%Y-%m-%d %H:%M"), tz="UTC", n=200, seed=int(tt.timestamp()) % 100000, units="si", elevation=elev, mode="ai")
                    s = L.observe_radar(site=rad, profile=prof)._ensure_pool()["samples"]
                except Exception as e:   # noqa: BLE001
                    print(tt, "skipped:", repr(e)[:80], flush=True)
                    continue
                ct, cp, vt, vp = [], [], [], []
                for c, q in enumerate(("u", "v")):
                    X = np.asarray(s[q], float)[:, band]
                    for j in range(X.shape[1]):
                        y = y0[c, band][j]
                        x = a[:, c, j]; z = b[:, c, j]; m = np.isfinite(x) & np.isfinite(z)
                        if not np.isfinite(y) or not np.isfinite(x0[c, band][j]) or m.sum() < 8 or x[m].std() < 1e-6 or z[m].std() < 1e-6:
                            continue
                        mx, my, sx, sy = x[m].mean(), z[m].mean(), x[m].std(), z[m].std()
                        rho = float(np.corrcoef(x[m], z[m])[0, 1])
                        mu = my + rho * (x0[c, band][j] - mx) * sy / sx
                        sd = fct * sy * sqrt(max(1 - rho * rho, 1e-4))
                        ct.append(K.crps1(X[:, j], y)); cp.append(float(crps_g(mu, sd, y)))
                        vt.append(np.percentile(X[:, j], 5) <= y <= np.percentile(X[:, j], 95)); vp.append(abs(y - mu) <= 1.645 * sd)
                if ct:
                    for key, v in (("tool", ct), ("pair", cp), ("cov_t", vt), ("cov_p", vp)):
                        S[k][key].append(float(np.mean(v)))
            print(rad, month, "lag", k, "cases so far", len(S[k]["tool"]), flush=True)
    L_ = ["E3 step 1 part B: radar pair ensemble vs tool + observe_radar (MAF Jan/Apr/Jun/Sep 2024, HDX Jun 2024; even days at 15 UTC; 0.5-5 km; u and v)",
          "lag h  cases   CRPS tool+radar   CRPS pair   change    cov90 tool   cov90 pair"]
    ok = True
    for k in LAGS:
        s = S[k]
        if not s["tool"]:
            L_.append(f"  {k}     no cases"); ok = False; continue
        ct, cp = np.mean(s["tool"]), np.mean(s["pair"]); cvp = np.mean(s["cov_p"])
        L_.append(f"  {k}    {len(s['tool']):>4}   {ct:10.3f}      {cp:8.3f}   {100 * (cp / ct - 1):+6.1f} %   {np.mean(s['cov_t']):.3f}        {cvp:.3f}")
        ok &= cp <= 0.90 * ct and 0.85 <= cvp <= 0.95
    L_.append("VERDICT (pre-set rule: pair CRPS <= 0.90 x tool + observe_radar at lags 1, 2, 3 and pair coverage 0.85-0.95): " + ("PASS" if ok else "MISS"))
    L_.append("Cases share days/months; one-off 15 UTC start only. Not independent.")
    K.report("b78_e3_pairs_step1c", L_)


if __name__ == "__main__":
    main()
