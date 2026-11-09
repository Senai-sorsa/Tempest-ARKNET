"""W6: hourly persistence of the wind SPEED in Weibull-copula space. For TCS and MAF: per (month, local hour) Weibull marginals fitted on ASOS 2015-2022 reports; z = Phi^-1(F_weibull(speed)); AR(1) in z with rho fitted per hour class;
forecast of the next hour's speed from the previous hour's speed = Weibull quantiles of N(rho z_prev, 1 - rho^2). Test 2023-2025 against (i) the climatological Weibull of the cell (no observation), (ii) a persistence ensemble
'previous speed x lognormal factor' (no marginal knowledge), (iii) linear persistence of the speed anomaly (speed = cell mean + r (previous - mean) + noise). Scores: CRPS of the speed (m/s), coverage of the central 90 % interval.
    .venv/Scripts/python -W ignore scripts/weibull_persistence.py
"""
import csv
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from weibull_check import weibull_mle   # noqa: E402

KT = 0.514444
ST = {"TCS": "America/Denver", "MAF": "America/Chicago"}
phi = lambda z: 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(z) / math.sqrt(2.0)))


def ppf_norm(p):
    from statistics import NormalDist
    nd = NormalDist()
    return np.array([nd.inv_cdf(float(min(max(x, 1e-6), 1 - 1e-6))) for x in np.atleast_1d(p)])


def crps(ens, y):
    ens = np.sort(ens)
    m = len(ens)
    i = np.arange(1, m + 1)
    return 2.0 / m ** 2 * np.sum((ens - y) * (m * (y < ens) - i + 0.5))


def main():
    rng = np.random.default_rng(0)
    for st, tz in ST.items():
        z_ = ZoneInfo(tz)
        rows = []
        for y in range(2015, 2026):
            with open(os.path.join(REPO, "data", "raw", "asos", st, f"{y}.csv"), newline="") as f:
                for r in csv.DictReader(f):
                    try:
                        t = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                        s = float(r["sknt"]) * KT
                    except (ValueError, KeyError):
                        continue
                    h = (t + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
                    if abs((t - h).total_seconds()) <= 20 * 60 or (h - t).total_seconds() <= 20 * 60:
                        rows.append((h, s))
        sp = {h: s for h, s in rows}
        cell = lambda h: (h.astimezone(z_).month, h.astimezone(z_).hour)
        fit_cells = {}
        for h, s in sp.items():
            if h.year <= 2022:
                fit_cells.setdefault(cell(h), []).append(s)
        par = {c: weibull_mle(v) for c, v in fit_cells.items() if len(v) >= 150}
        zq = lambda s, c: ppf_norm(1 - math.exp(-((max(s, 0.05) / par[c][1]) ** par[c][0])))[0]
        pairs = [(h, sp[h - timedelta(hours=1)], sp[h]) for h in sp if h.year <= 2022 and (h - timedelta(hours=1)) in sp and cell(h) in par and cell(h - timedelta(hours=1)) in par and sp[h] > 0.3 and sp[h - timedelta(hours=1)] > 0.3 and 8 <= cell(h)[1] <= 20]
        zz = np.array([[zq(a, cell(h - timedelta(hours=1))), zq(b, cell(h))] for h, a, b in pairs])
        rho = float(np.corrcoef(zz[:, 0], zz[:, 1])[0, 1])
        mean_c = {c: np.mean(v) for c, v in fit_cells.items()}
        rl = float(np.corrcoef([a for _, a, _ in pairs], [b for _, _, b in pairs])[0, 1])
        test = [(h, sp[h - timedelta(hours=1)], sp[h]) for h in sp if h.year >= 2023 and (h - timedelta(hours=1)) in sp and cell(h) in par and cell(h - timedelta(hours=1)) in par and 8 <= cell(h)[1] <= 20]
        test = [test[i] for i in rng.choice(len(test), min(1500, len(test)), replace=False)]
        res = {"climatological Weibull of the cell": [], "previous speed x lognormal factor": [], "linear persistence of the speed anomaly": [], f"AR(1) in Weibull-copula space (rho {rho:.2f})": []}
        cov = {k: [] for k in res}
        resid = np.std([np.log(max(b, 0.3) / max(a, 0.3)) for _, a, b in pairs])
        for h, a, b in test:
            c = cell(h)
            k, sc = par[c]
            e0 = sc * (-np.log(1 - rng.random(200))) ** (1.0 / k)
            e1 = max(a, 0.2) * np.exp(rng.normal(0, resid, 200))
            mu = mean_c[c]
            e2 = np.maximum(mu + rl * (a - mu) + rng.normal(0, np.std([b - (mean_c[cell(hh)] + rl * (aa - mean_c[cell(hh)])) for hh, aa, b in pairs[:400]]), 200), 0.0)
            zprev = zq(a, cell(h - timedelta(hours=1)))
            zn = rho * zprev + math.sqrt(1 - rho ** 2) * rng.normal(size=200)
            e3 = sc * (-np.log(1 - phi(zn))) ** (1.0 / k)
            for key, e in zip(res, (e0, e1, e2, e3)):
                res[key].append(crps(e, b))
                cov[key].append(np.percentile(e, 5) <= b <= np.percentile(e, 95))
        print(f"\n{st}: {len(pairs)} fit pairs, {len(test)} test hours 2023-25; speed autocorrelation {rl:.2f}, Weibull-space {rho:.2f}")
        for key in res:
            print(f"  {key:46} CRPS {np.mean(res[key]):.3f}  90 % coverage {np.mean(cov[key]):.2f}")


if __name__ == "__main__":
    main()
