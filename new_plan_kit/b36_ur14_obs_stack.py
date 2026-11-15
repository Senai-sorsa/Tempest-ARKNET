"""New_Plan 17 UR14: the observation stack. Site map first (S1 / AV8's method: per-cell speed factor = mean observed / mean tool prior, 6 cells
hour block x warm / cool, 120 tool prior hours per cell from 2015-22), then the merged two-neighbour report (O1 / AV7's method, b4_two_neighbours:
gains from Launch._report_gain, second gain cut by the error correlation of the two neighbours fitted on 2019-22, one observe call).
Targets as AV7: TCS from LRU + ONM, ELP from LRU + ALM. Test hours 2023-25, 08-20 local, report 1 h old, 600 hours per target, two NEW hour
seeds (4 and 5). Arms on the same hours (paired): merged report without a map, and the same with the map first. Nothing on disk changes.
Run after AV7 and AV8 have their verdicts (New_Plan 17.3 step 6).
Rule (set 2026-11-13 in New_Plan 17.2 before any run):
  PASS: stack CRPS better than merged alone with a 21-day block interval below 0 at both targets, coverage >= 0.80 (TCS merged alone was 0.81
        in AV7), in both seeds.  KILL: coverage under 0.80 at either target.  Otherwise MISS.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b36_ur14_obs_stack.py        # about 3 h CPU
    KIT_SMOKE=1 PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b36_ur14_obs_stack.py --n 3 --fit 3
Result: docs/results/logs/kit_b36_ur14_obs_stack.log
"""
import argparse
from datetime import timedelta
from zoneinfo import ZoneInfo

import numpy as np

import kit_common as K
from b1_observe_loso import score, speed10, test_hours
from b3_il207b_site_shift import cell_of
from b4_debias_then_update import FIT_YEARS, fit_map
from b4_two_neighbours import PAIRS, error_corr, fixed_gain, merge

NAME = "b36_ur14_obs_stack"


def blk(day):
    import pandas as pd
    return str(pd.Timestamp(day).toordinal() // 21)


def judge(cells):
    """cells: [(target, seed, hi, cov_stack)] -> verdict."""
    if any(c[3] < 0.80 for c in cells):
        return "KILL (coverage under 0.80)"
    return "PASS" if len(cells) == 4 and all(c[2] < 0 for c in cells) else "MISS (record, no adoption)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--fit", type=int, default=120)
    ap.add_argument("--seeds", default="4,5")
    a = ap.parse_args()
    from tempest_weather_v2 import obs as O
    from tempest_weather_v2.launch import Launch
    K.ram_gate(4.0)
    lines = [f"UR14 observation stack: map first ({a.fit} prior hours per cell, 2015-22), then the merged two-neighbour report; 2023-25, 08-20 local, {a.n} hours per target"]
    cells = []
    for seed in (int(s) for s in a.seeds.split(",")):
        rng = np.random.default_rng(seed)
        for st, (tz, (na, nb)) in PAIRS.items():
            lat, lon, elev = O.STATIONS[st]
            z = ZoneInfo(tz)

            def L_at(h, cal=None):
                return Launch(lat, lon, h.strftime("%Y-%m-%d %H:%M"), tz="UTC", n=200, seed=int(h.timestamp()) % 100000, units="si", elevation=elev, mode="ai", site_cal=cal)

            own_fit = K.asos_speed(st, FIT_YEARS)
            cand = [h for h in sorted(own_fit) if 8 <= h.astimezone(z).hour <= 20 and h.year <= 2022]
            pm = {}
            for c in sorted({cell_of(h, z) for h in cand}):
                hs = [h for h in cand if cell_of(h, z) == c]
                for i in rng.choice(len(hs), min(a.fit, len(hs)), replace=False):
                    try:
                        pm.setdefault(c, []).append(float(speed10(L_at(hs[i])).mean()))
                    except Exception:   # noqa: BLE001
                        pass
            kmap = fit_map(own_fit, pm, z)
            own = K.asos_speed(st, range(2019, 2026))
            nbs = {s: K.asos_speed(s, range(2019, 2026)) for s in (na, nb)}
            r, nfit = error_corr(own, nbs[na], nbs[nb], tz)
            geo = {s: (O.haversine_km(lat, lon, *O.STATIONS[s][:2]), O.STATIONS[s][2] - elev) for s in (na, nb)}
            res, days, skipped = {"merged": [], "map + merged": []}, [], 0
            for h in test_hours(own, tz, a.n, rng):
                assert K.day_ok(h)
                h1 = h - timedelta(hours=1)
                if any(h1 not in nbs[s] or nbs[s][h1][0] < 0.5 for s in (na, nb)):
                    continue
                try:
                    y, out = own[h][0], {}
                    for arm, cal in (("merged", None), ("map + merged", {"method": "ratio", "ratio": kmap.get(cell_of(h, z), 1.0)})):
                        L = L_at(h, cal)
                        single = {}
                        for s in (na, nb):
                            single[s] = L.observe(wind_10m=f"{nbs[s][h1][0]:.2f} m/s", wind_from_deg=float(nbs[s][h1][1]), age_hours=1.0, distance_km=float(geo[s][0]),
                                                  elevation_diff_m=float(geo[s][1]), source=s)._report_gain()
                        s1, s2 = sorted((na, nb), key=lambda s: -single[s])
                        sp, dr, G = merge(nbs[s1][h1][0], float(nbs[s1][h1][1]), single[s1], nbs[s2][h1][0], float(nbs[s2][h1][1]), single[s2], r)
                        with fixed_gain(G):
                            out[arm] = score(speed10(L.observe(wind_10m=f"{sp:.2f} m/s", wind_from_deg=dr, age_hours=1.0, distance_km=float(min(geo[s][0] for s in (na, nb))),
                                                               elevation_diff_m=float(geo[s1][1]), source=f"{s1}+{s2}")), y)
                except Exception:   # noqa: BLE001  (an hour the tool cannot serve is skipped, and counted)
                    skipped += 1
                    continue
                for k_, v in out.items():
                    res[k_].append(v)
                days.append(blk(h.date()))
            A, B = np.array(res["map + merged"]), np.array(res["merged"])
            if len(days) < 2:
                lines.append(f"  seed {seed} {st}: too few hours")
                continue
            dm, lo, hi = K.block_boot(A[:, 0] - B[:, 0], days, draws=1000)
            cells.append((st, seed, hi, A[:, 1].mean()))
            lines.append(f"  seed {seed} {st} from {na} + {nb}: {len(days)} hours ({skipped} skipped), r {r:+.2f}; map " + ", ".join(f"{c} {v:.3f}" for c, v in sorted(kmap.items()))
                         + f"; merged CRPS {B[:, 0].mean():.3f} cov {B[:, 1].mean():.2f} | map + merged CRPS {A[:, 0].mean():.3f} cov {A[:, 1].mean():.2f} | "
                         f"difference {dm:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    lines.append("Rule (pre-set, New_Plan 17.2): PASS = map + merged better than merged (21-day interval < 0) at TCS and ELP, coverage >= 0.80, both seeds; KILL = coverage < 0.80.")
    lines.append("Verdict: " + judge(cells))
    K.report(NAME, lines)


def _selfcheck():
    assert judge([("TCS", 4, -0.01, 0.82), ("ELP", 4, -0.02, 0.85), ("TCS", 5, -0.01, 0.83), ("ELP", 5, -0.01, 0.84)]) == "PASS"
    assert judge([("TCS", 4, -0.01, 0.79)]).startswith("KILL")
    assert judge([("TCS", 4, 0.01, 0.82), ("ELP", 4, -0.02, 0.85), ("TCS", 5, -0.01, 0.83), ("ELP", 5, -0.01, 0.84)]).startswith("MISS")


_selfcheck()
if __name__ == "__main__":
    main()
