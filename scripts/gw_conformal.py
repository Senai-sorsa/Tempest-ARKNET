"""M10 on real data: past-mode 10 m wind ensembles (u and v, m = 100) for 2024-25 ASOS cases at TCS and MAF in time order; central 90 % interval of the ensemble, raw and with adaptive conformal stretching
(online, one sequence per station and component, state starts at stretch 1). Reports the coverage of the raw interval, of a fixed 1.3 x spread inflation, and of the adaptive one (second half of the sequence, after warm-up), and the mean interval widths.
    PYTHONPATH=. TEMPEST_ERA5_STORE=data/pilot/profiles.zarr .venv/Scripts/python -W ignore scripts/gw_conformal.py [--n 300]
"""
import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import ground_wind_bench as gw   # noqa: E402
from tempest_weather_v2.montecarlo import AdaptiveConformal   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    a = ap.parse_args()
    os.environ.setdefault("TEMPEST_ERA5_STORE", os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    asos = {st: gw.load_asos(st, range(2000, 2026)) for st in gw.STATIONS}
    cases = gw.sample_cases(np.random.default_rng(3), {2024, 2025}, a.n, asos, list(gw.STATIONS))
    for st in gw.STATIONS:
        cs = sorted([c for c in cases if c[0] == st], key=lambda c: c[1])
        ens = [np.stack(gw.ensemble(st, h, 100, "past", 9000 + k)) for k, (_, h) in enumerate(cs)]
        for comp, name in ((0, "u"), (1, "v")):
            ac = AdaptiveConformal(0.10, gamma=0.05)
            hit_raw, hit_inf, hit_ac, w_raw, w_ac = [], [], [], [], []
            for (_, h), e in zip(cs, ens):
                y = asos[st][h][comp]
                x = e[comp]
                lo, hi = np.quantile(x, [0.05, 0.95])
                med = np.median(x)
                hit_raw.append(lo <= y <= hi)
                hit_inf.append(med + 1.3 * (lo - med) <= y <= med + 1.3 * (hi - med))
                i = ac.interval(x)
                hit_ac.append(i[0] <= y <= i[1])
                ac.update(y, i)
                w_raw.append(hi - lo)
                w_ac.append(i[1] - i[0])
            half = len(cs) // 2
            f = lambda v: float(np.mean(v[half:]))
            print(f"{st} {name}: {len(cs)} cases; coverage (2nd half) raw {f(hit_raw):.2f}, fixed x1.3 {f(hit_inf):.2f}, adaptive {f(hit_ac):.2f}; mean width raw {np.mean(w_raw):.2f} m/s, adaptive {np.mean(w_ac):.2f}; final stretch {ac.stretch:.2f}", flush=True)


if __name__ == "__main__":
    main()
