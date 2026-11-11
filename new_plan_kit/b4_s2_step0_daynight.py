"""New_Plan 10.1 S2 step 0: is the TCS error a too-flat daily cycle (premise of S2), seen at most stations?
For each of the 9 ASOS stations in tempest_weather_v2.obs.STATIONS: the tool's prior 10 m speed (no report) against ASOS at
DAY hours (11-17 local) and NIGHT hours (22-05 local), fit years 2021-22 only (test years 2023-25 stay clean). bias = mean(obs - prior median).
Pre-set rule (New_Plan 10.1, written before the run): the night bias must be OPPOSITE in sign to the day bias at >= 6 of 9 stations,
otherwise STOP S2 (premise wrong). A station the tool cannot serve (outside the trained area) counts as not opposite.
    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b4_s2_step0_daynight.py            # 9 x 2 x 40 hours, about 30-45 min
    KIT_SMOKE=1 PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b4_s2_step0_daynight.py --n 3
Result: docs/results/logs/kit_b4_s2_step0_daynight.log
"""
import argparse
from datetime import timedelta
from zoneinfo import ZoneInfo

import numpy as np

import kit_common as K
from b1_observe_loso import speed10

TZ = {"MAF": "America/Chicago", "FST": "America/Chicago", "PEQ": "America/Chicago"}   # the others are America/Denver
DAY, NIGHT = range(11, 18), (22, 23, 0, 1, 2, 3, 4, 5)


def pick(obs, tz, hours, n, rng):
    z = ZoneInfo(tz)
    ok = [h for h in sorted(obs) if 2021 <= h.year <= 2022 and h.astimezone(z).hour in hours]
    return [ok[i] for i in np.sort(rng.choice(len(ok), min(n, len(ok)), replace=False))] if ok else []


def opposite(day, night):
    return day is not None and night is not None and day * night < 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="hours per station and per day/night")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    from tempest_weather_v2 import obs as O
    from tempest_weather_v2.launch import Launch
    K.ram_gate(4.0)
    rng = np.random.default_rng(a.seed)
    lines = [f"S2 step 0: day (11-17 local) vs night (22-05 local) bias of the tool's 10 m prior median, no report, 2021-22, {a.n} hours each, seed {a.seed}"]
    n_opp = 0
    for st, (lat, lon, elev) in O.STATIONS.items():
        tz = TZ.get(st, "America/Denver")
        own = K.asos_speed(st, (2021, 2022))
        res = {}
        for name, hours in (("day", DAY), ("night", NIGHT)):
            errs, days, skipped = [], [], 0
            for h in pick(own, tz, hours, a.n, rng):
                assert K.day_ok(h)
                try:
                    w = speed10(Launch(lat, lon, h.strftime("%Y-%m-%d %H:%M"), tz="UTC", n=200, seed=int(h.timestamp()) % 100000, units="si", elevation=elev, mode="ai"))
                except Exception:   # noqa: BLE001  (an hour the tool cannot serve is skipped, and counted)
                    skipped += 1
                    continue
                errs.append(own[h][0] - float(np.median(w)))
                days.append((h - timedelta(hours=6)).date().isoformat())   # night hours across midnight share one block
            if errs:
                m, lo, hi = K.block_boot(np.array(errs), days, draws=1000)
                res[name] = m
                lines.append(f"  {st:<4} {name:<5} n {len(errs):3d} skipped {skipped:3d}  bias {m:+.2f} [{lo:+.2f}, {hi:+.2f}] m/s")
            else:
                res[name] = None
                lines.append(f"  {st:<4} {name:<5} no hours served (skipped {skipped})")
        opp = opposite(res["day"], res["night"])
        n_opp += opp
        lines.append(f"  {st:<4} opposite sign: {'yes' if opp else 'no'}")
    lines.append(f"Rule (pre-set): night bias opposite in sign to day bias at >= 6 of 9 stations. Found {n_opp} of {len(O.STATIONS)}. "
                 "Caveat: ONM, FST, ABQ lie outside the trained area (IL-209), so 6 is also the most that can pass.")
    lines.append("VERDICT: " + ("PREMISE HOLDS -> run S2 full (b4_regional_shape_loso.py)" if n_opp >= 6 else "PREMISE WRONG -> STOP S2; the TCS factor stays a per-site item (ASK_LATER 24)"))
    K.report("b4_s2_step0_daynight", lines)


def _selfcheck():
    assert opposite(1.0, -0.5) and not opposite(1.0, 0.2) and not opposite(None, -1.0)


_selfcheck()
if __name__ == "__main__":
    main()
