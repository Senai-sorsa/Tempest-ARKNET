"""G2-2 Student-t widening (README Part 5, recipe 'Innovative idea review.md' lines 171-174): Launch.observe(..., t_update=True) (opt-in, off by default) scales the conditioned
members' departures by sqrt((8 + D^2) / (8 + k)), limited to 1-2, where D^2 sums the squared standardised surprises of the k observed numbers (launch._t_widen_factor).
Cases: the W6 / W3 cases (scripts/w6_observe_eval.py: TCS and MAF ASOS 2023-25, 08-20 local, the measured speed and direction an hour earlier, predict the 10 m speed at the hour),
shipped soft observe() (speed-space default) vs the same + t_update=True, same seed. Surprise = D^2 of the previous-hour reading against the unconditioned pool.
PASS (set 2026-11-12 08:50, before any result; recipe step 3): on the 10 % most surprising cases (both stations pooled) |cov90 - 0.90| falls, AND on the other 90 % the CRPS change
(t - shipped) has a day-block 95 % interval that contains 0 or lies below it. Otherwise FAIL (flag stays off). Radar (p3_vad_condition.py) not run: that script bypasses Launch.
Fault gate (recipe step 2) not built: it needs a previous reading of the same sensor or a second sensor, and observe() has no such input.

    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b3_g22_t_update.py [--n 300]      # about 20-40 min, < 3 GB
Result: docs/results/logs/kit_b3_g22_t_update.log
"""
import argparse
import csv
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

import kit_common as K
from tempest_weather_v2 import Launch
from w6_observe_eval import ST, KT, crps


def cases(st, n, rng):
    tz, *_ = ST[st]
    z_ = ZoneInfo(tz)
    obs = {}
    for y in range(2023, 2026):
        with open(os.path.join(K.REPO, "data", "raw", "asos", st, f"{y}.csv"), newline="") as f:
            for r in csv.DictReader(f):
                try:
                    t = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                    s, d = float(r["sknt"]) * KT, float(r["drct"])
                except (ValueError, KeyError):
                    continue
                h = (t + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
                if abs((t - h).total_seconds()) <= 20 * 60:
                    obs[h] = (s, d)
    test = [h for h in obs if (h - timedelta(hours=1)) in obs and 8 <= h.astimezone(z_).hour <= 20 and obs[h - timedelta(hours=1)][0] >= 0.5]
    return obs, [test[i] for i in rng.choice(len(test), min(n, len(test)), replace=False)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    a = ap.parse_args()
    K.ram_gate(3.0)
    rng = np.random.default_rng(0)       # same draw of cases as w6_observe_eval.py
    R = []   # station, day, surprise D^2, crps shipped, crps t, cov shipped, cov t, factor
    for st, (tz, lat, lon, elev) in ST.items():
        obs, test = cases(st, a.n, rng)
        for h in test:
            sp0, d0 = obs[h - timedelta(hours=1)]
            y = obs[h][0]
            try:
                L = Launch(lat, lon, h.strftime("%Y-%m-%d %H:%M"), tz="UTC", n=200, seed=int(h.timestamp()) % 100000, units="si", elevation=elev, mode="ai")
                kw = dict(wind_10m=f"{sp0:.2f} m/s", wind_from_deg=float(d0), age_hours=1.0, distance_km=0.0, elevation_diff_m=0.0, source=f"ASOS {st}")
                prior = L._ensure_pool()["samples"]
                u0, v0 = -sp0 * np.sin(np.radians(d0)), -sp0 * np.cos(np.radians(d0))
                pu, pv = np.asarray(prior["u"], float)[:, 0], np.asarray(prior["v"], float)[:, 0]
                D2 = (u0 - pu.mean()) ** 2 / pu.var() + (v0 - pv.mean()) ** 2 / pv.var()     # prior-only surprise for ranking (the obs error is the same for every case)
                row = [st, h.date(), D2]
                ws = []
                for LL in (L.observe(**kw), L.observe(**kw, t_update=True)):
                    s = LL._ensure_pool()["samples"]
                    w = np.hypot(np.asarray(s["u"], float)[:, 0], np.asarray(s["v"], float)[:, 0])
                    ws.append(w)
                row += [crps(ws[0], y), crps(ws[1], y), np.percentile(ws[0], 5) <= y <= np.percentile(ws[0], 95), np.percentile(ws[1], 5) <= y <= np.percentile(ws[1], 95),
                        np.std(ws[1]) / max(np.std(ws[0]), 1e-9)]
                R.append(row)
            except Exception as e:  # noqa: BLE001 - count and continue
                print(st, h, "skipped:", repr(e)[:80], flush=True)
        print(st, "done", len(R), flush=True)
    st_, day, D2, c0, c1, k0, k1, fr = (np.array(x) for x in zip(*R))
    c0, c1, D2, fr = (x.astype(float) for x in (c0, c1, D2, fr))
    k0, k1 = k0.astype(bool), k1.astype(bool)
    top = D2 >= np.quantile(D2, 0.90)
    lines = [f"G2-2 t-update, W6 cases (TCS + MAF ASOS 2023-25, 08-20 local, previous-hour soft observe), {len(R)} cases; shipped observe vs + t_update=True (same seed)"]
    lines.append("%-24s %5s %10s %10s %8s %8s %12s" % ("cases", "n", "crps ship", "crps t", "cov ship", "cov t", "spread ratio"))
    for lab, sel in (("all", np.ones_like(top)), ("top 10 % surprise", top), ("other 90 %", ~top)) + tuple((f"{s} all", st_ == s) for s in ST):
        lines.append("%-24s %5d %10.3f %10.3f %8.2f %8.2f %12.2f" % (lab, sel.sum(), c0[sel].mean(), c1[sel].mean(), k0[sel].mean(), k1[sel].mean(), np.median(fr[sel])))
    days = np.array([f"{s}{d}" for s, d in zip(st_, day)])
    dm, lo, hi = K.block_boot((c1 - c0)[~top], days[~top], draws=1000)
    lines.append("other 90 %%: CRPS change t - shipped %+.4f [%+.4f, %+.4f] (day blocks)" % (dm, lo, hi))
    dm2, lo2, hi2 = K.block_boot((c1 - c0)[top], days[top], draws=1000)
    lines.append("top 10 %%:  CRPS change t - shipped %+.4f [%+.4f, %+.4f] (day blocks); D^2 threshold %.1f" % (dm2, lo2, hi2, np.quantile(D2, 0.90)))
    cov_ok = abs(k1[top].mean() - 0.90) < abs(k0[top].mean() - 0.90)
    crps_ok = lo <= 0.0
    lines.append("VERDICT: %s (top-10 %% coverage error %.2f -> %.2f: %s; other-90 %% CRPS interval contains 0 or below: %s)" % (
        "PASS" if cov_ok and crps_ok else "FAIL, flag stays off", abs(k0[top].mean() - 0.90), abs(k1[top].mean() - 0.90), "falls" if cov_ok else "does not fall", "yes" if crps_ok else "no"))
    K.report("b3_g22_t_update", lines)


if __name__ == "__main__":
    main()
