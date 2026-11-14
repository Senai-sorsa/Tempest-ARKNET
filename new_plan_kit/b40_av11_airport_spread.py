"""New_Plan 13 AV11: A2 past-mode spread x1.2 again, switched by station type only: x1.2 when the target is an airport ASOS site, 1.0 elsewhere
(no descriptor model; P7 was neutral). USCRN / pad sites keep 1.0 by construction, so their CRPS change is exactly 0 (<= 0.0009 holds).
Test: every airport with ASOS on disk (TCS ONM LRU ELP ALM MAF FST PEQ ABQ), 2019-22 (the years the A2 USCRN bench used), local 10-18 h,
past mode + ERA5 anchor (data/pilot/profiles.zarr) at x1.0 vs x1.2, same seed per hour; 10 m speed CRPS against the ASOS speed,
paired day-block interval. The switch has no fitted part, so leave-one-airport-out = each airport judged on its own as the held-out one.
An hour where past mode falls back or cannot serve is skipped and counted; an airport with < 30 hours is reported as not servable.
Rule written 2026-11-13 before any AV11 result (New_Plan 13):
PASS: every servable airport better at x1.2 (x1.2 minus x1.0 interval < 0), and no site worse by more than 0.0009 (USCRN sites: 0 by construction).
KILL: any servable airport worse (x1.2 minus x1.0 > +0.0009). Otherwise MISS: record, keep 1.0.
A pad is not an airport, so the pad default stays 1.0 either way.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b40_av11_airport_spread.py [--n 120]
Result: docs/results/logs/kit_b40_av11_airport_spread.log
"""
import argparse
import os
from zoneinfo import ZoneInfo

import numpy as np

import kit_common as K
from tempest.scoring.score import coverage90, crps_ensemble

NAME = "b40_av11_airport_spread"
STORE = os.path.join(K.REPO, "data", "pilot", "profiles.zarr")
TZ = {"MAF": "America/Chicago", "FST": "America/Chicago", "PEQ": "America/Chicago"}       # the rest: America/Denver


def judge(rows):
    """rows = {airport: (mean diff, hi) or None (not servable)} -> verdict."""
    ok = {k: v for k, v in rows.items() if v is not None}
    if not ok:
        return "INCOMPLETE (no servable airport)"
    if any(d > 0.0009 for d, _ in ok.values()):
        return "KILL"
    if all(hi < 0 for _, hi in ok.values()):
        return "PASS"
    return "MISS (record, keep 1.0)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120, help="hours per airport")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    from tempest_weather_v2 import Launch
    from tempest_weather_v2 import obs as O
    K.ram_gate(4.0)
    lines = [f"AV11 past-mode 10 m spread x1.2 vs x1.0 at the airports (past + ERA5 anchor), 2019-22, local 10-18 h, {a.n} hours each, seed {a.seed}"]
    rows = {}
    for st, (lat, lon, elev) in O.STATIONS.items():
        z = ZoneInfo(TZ.get(st, "America/Denver"))
        obs = K.asos_speed(st, range(2019, 2023))
        hs = sorted(h for h in obs if 10 <= h.astimezone(z).hour <= 18 and 2019 <= h.astimezone(z).year <= 2022)
        rng = np.random.default_rng(a.seed)
        res, days, skipped = [], [], []
        for k in rng.permutation(len(hs)):
            if len(res) >= a.n or len(skipped) > 3 * a.n:
                break
            h = hs[k]
            y, local = obs[h][0], h.astimezone(z).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M")
            try:
                e = []
                for s in (1.0, 1.2):
                    P = Launch(lat, lon, local, tz=z.key, mode="past", era5_store=STORE, n=200, units="si", seed=int(k) % 100000, elevation=elev,
                               past_era5_anchor=True, past_wind_spread=s)
                    pool = P._ensure_pool()
                    if set(pool["modes"]) != {"past"}:
                        raise RuntimeError(f"past mode fell back: {pool['modes']}")
                    e.append(np.hypot(pool["samples"]["u"][:, 0], pool["samples"]["v"][:, 0]))
            except Exception as ex:   # noqa: BLE001  (an hour past mode cannot serve is skipped, and counted)
                skipped.append(repr(ex)[:80])
                continue
            res.append([crps_ensemble(x[None, :, None], np.array([[y]]))[0, 0] for x in e]
                       + [coverage90(x[None, :, None], np.array([[y]]), 0.9)[0, 0] for x in e])
            days.append(h.astimezone(z).date().isoformat())
        if len(res) < 30:
            rows[st] = None
            lines.append(f"{st}: {len(res)} hours, {len(skipped)} skipped -> not servable" + (f" (first: {skipped[0]})" if skipped else ""))
            continue
        r = np.array(res)
        dm, dlo, dhi = K.block_boot(r[:, 1] - r[:, 0], days, draws=1000)
        rows[st] = (dm, dhi)
        lines.append(f"{st}: {len(r)} hours, {len(skipped)} skipped; x1.0 CRPS {r[:, 0].mean():.3f} cov {r[:, 2].mean():.2f} | x1.2 CRPS {r[:, 1].mean():.3f} "
                     f"cov {r[:, 3].mean():.2f} | x1.2 minus x1.0 {dm:+.4f} [{dlo:+.4f}, {dhi:+.4f}]  {'better' if dhi < 0 else 'worse' if dm > 0.0009 else 'neutral'}")
    lines.append("Rule (pre-set): PASS = every servable airport x1.2 minus x1.0 interval < 0 (USCRN sites 1.0, change 0); KILL = any airport > +0.0009.")
    lines.append("AV11 verdict: " + judge(rows))
    K.report(NAME, lines)


def _selfcheck():
    assert judge({"A": (-0.02, -0.01), "B": None}) == "PASS" and judge({"A": (-0.02, -0.01), "B": (0.002, 0.01)}) == "KILL"
    assert judge({"A": (-0.02, -0.01), "B": (0.0005, 0.01)}).startswith("MISS") and judge({"A": None}).startswith("INCOMPLETE")


_selfcheck()
if __name__ == "__main__":
    main()
