"""E3 step 1, part A (New_Plan 16.4 E3): does the radar pair structure (wind now -> wind k h later) beat the radar's own hourly climatology? REPORT with a pre-set rule.
Pairs: first KNVW VAD volume of each UTC hour, radars MAF / HDX, 0.5-5 km above the radar (heights with u, v finite), lags 1, 2, 3, 6 h.
Fit on odd days of month, test on even days (days not used for the fit). Per radar x height x component x start hour: climatology = mean/sd of the target hour over fit days;
pair ensemble = Gaussian, mean = clim + rho * (x_now - clim_now) * (sd_t/sd_now), sd = sd_t * sqrt(1 - rho^2), rho fit on fit days (shrunk to 0 when < 15 fit pairs).
Both are scored with the Gaussian CRPS on test pairs; coverage = share of test targets inside the central 90 % interval of the pair ensemble.
PRE-SET RULE (before the run): PASS if CRPS reduction vs climatology >= 10 % at EACH of lags 1, 2, 3 and 90 % coverage in 0.85-0.95. Else MISS.
NOTE: part A is a necessary condition only. The plan's real comparison (vs tool + observe_radar) needs the tool run per pair (part B), not done here.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b76_e3_pairs_step1.py     Result: docs/results/logs/kit_b76_e3_pairs_step1.log
"""
import glob
import os

import numpy as np
import pandas as pd
from math import erf, sqrt, pi

import kit_common as K
from p3_vad_vs_balloon import parse

ELEV = {"MAF": 872.0, "HDX": 1287.0}
LAGS = (1, 2, 3, 6)
band = (K.H >= 500) & (K.H <= 5000)
_N = np.vectorize(lambda z: 0.5 * (1 + erf(z / sqrt(2))))


def crps_g(mu, sd, y):
    z = (y - mu) / sd
    return sd * (z * (2 * _N(z) - 1) + 2 * np.exp(-z * z / 2) / sqrt(2 * pi) - 1 / sqrt(pi))


def load(rad):
    first = {}
    for f in sorted(glob.glob(f"data/raw/nexrad_nvw_t3/{rad}_NVW_*")):
        t = pd.to_datetime(os.path.basename(f)[8:], format="%Y_%m_%d_%H_%M_%S").floor("h")
        first.setdefault(t, f)
    W = {}
    for t, f in first.items():
        try:
            W[t] = np.stack(parse(f, ELEV[rad]))[:, band]
        except Exception:
            pass
    return W


def main():
    S = {k: {"cp": [], "cc": [], "cov": []} for k in LAGS}
    for rad in ELEV:
        W = load(rad)
        for k in LAGS:
            pairs = [(t, t + pd.Timedelta(hours=k)) for t in W if (t + pd.Timedelta(hours=k)) in W]
            for h0 in sorted({p[0].hour for p in pairs}):
                P = [p for p in pairs if p[0].hour == h0]
                fit = [p for p in P if (p[0].month, p[0].day % 2) and p[0].day % 2 == 1]
                te = [p for p in P if p[0].day % 2 == 0]
                if len(fit) < 15 or not te:
                    continue
                a = np.stack([W[p[0]] for p in fit]); b = np.stack([W[p[1]] for p in fit])          # (n, 2, nh)
                ta = np.stack([W[p[0]] for p in te]); tb = np.stack([W[p[1]] for p in te])
                for c in range(2):
                    for j in range(a.shape[2]):
                        x, y = a[:, c, j], b[:, c, j]
                        m = np.isfinite(x) & np.isfinite(y)
                        if m.sum() < 15 or x[m].std() < 1e-6 or y[m].std() < 1e-6:
                            continue
                        mx, my, sx, sy = x[m].mean(), y[m].mean(), x[m].std(), y[m].std()
                        rho = float(np.corrcoef(x[m], y[m])[0, 1])
                        xs, ys = ta[:, c, j], tb[:, c, j]
                        mm = np.isfinite(xs) & np.isfinite(ys)
                        if not mm.any():
                            continue
                        mu = my + rho * (xs[mm] - mx) * sy / sx
                        sd = sy * sqrt(max(1 - rho * rho, 1e-4))
                        S[k]["cp"].append(crps_g(mu, sd, ys[mm]).mean())
                        S[k]["cc"].append(crps_g(my, sy, ys[mm]).mean())
                        S[k]["cov"].append((np.abs(ys[mm] - mu) <= 1.645 * sd).mean())
    L = ["E3 step 1 part A: radar pair ensemble vs radar hourly climatology (odd days fit, even days test), MAF + HDX, 0.5-5 km, u and v",
         "lag h  cells   CRPS clim   CRPS pair   change    90% coverage"]
    ok = True
    for k in LAGS:
        s = S[k]
        if not s["cp"]:
            L.append(f"  {k}     no test cells")
            ok = False
            continue
        cp, cc, cv = np.mean(s["cp"]), np.mean(s["cc"]), np.mean(s["cov"])
        ch = 100 * (cp / cc - 1)
        L.append(f"  {k}    {len(s['cp']):>5}   {cc:8.3f}   {cp:8.3f}   {ch:+6.1f} %   {cv:.3f}")
        if k <= 3 and (ch > -10 or not 0.85 <= cv <= 0.95):
            ok = False
    L.append("VERDICT (pre-set rule: >= 10 % CRPS gain at lags 1, 2, 3 and coverage 0.85-0.95): " + ("PASS part A" if ok else "MISS part A"))
    L.append("Part A only: baseline is radar climatology, not tool + observe_radar. Pairs share days (not independent).")
    K.report("b76_e3_pairs_step1", L)


if __name__ == "__main__":
    main()
