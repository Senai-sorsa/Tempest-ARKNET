"""New_Plan 10.1 S1: site map first, update second. The per-site speed map is applied to the prior pool BEFORE the observe update
(Launch(site_cal=...) runs _apply_site_cal at the end of _ensure_pool, and observe reads its prior after that), and neighbour reports use
the variant B gain (rho = obs.effective_gain, `b3_a3fix_neighbour_rho.rho_from_gain`). In memory only; nothing in the tool changes.
Map: one factor per cell (hour block 08-11 / 12-15 / 16-20 local x warm MAM-JJA / cool SON-DJF), k = mean(ASOS speed, ALL hours of the
cell 2015-22) / mean(tool prior mean, --fit hours per cell drawn from 2015-22). Distributions matched by their means, not paired hours.
Arms (paired, same hours, report 1 h old): A shipped update / B alone / map + A ("map alone") / map + B; no-report rows with and without map.
Pairs: TCS <- own, LRU, ONM; MAF <- own, FST, PEQ. Test 2023-25, 08-20 local, --n hours per target.
PASS (pre-set, New_Plan 10.1): map + B coverage >= 0.80 at every pair in BOTH seeds, CRPS(map + B) - CRPS(B) <= +0.0009 at every pair,
      and each cell factor within 0.05 between seeds (the seed-1 run reads the seed-0 factors from data/kit/s1_factors_seed0.json).
KILL: either seed misses 0.80 at any pair -> closed, keep B and the map as separate opt-ins.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b4_debias_then_update.py --seed 0     # then --seed 1; about 2 h each
    KIT_SMOKE=1 PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b4_debias_then_update.py --n 3 --fit 2
Result: docs/results/logs/kit_b4_debias_then_update.log
"""
import argparse
import json
import os
from datetime import timedelta
from zoneinfo import ZoneInfo

import numpy as np

import kit_common as K
from b1_observe_loso import TARGETS, neighbours, score, speed10, test_hours
from b3_a3fix_neighbour_rho import rho_from_gain
from b3_il207b_site_shift import cell_of

PAIRS = {"TCS": ("LRU", "ONM"), "MAF": ("FST", "PEQ")}
FIT_YEARS = range(2015, 2023)


def fit_map(own, prior_mean, z):
    """own: {hour: (speed, dir)}; prior_mean: {cell: [tool prior means]} -> {cell: k}. A cell with < 5 prior hours keeps k = 1."""
    obs = {}
    for h, (s, _) in own.items():
        if 8 <= h.astimezone(z).hour <= 20 and h.year <= 2022:
            obs.setdefault(cell_of(h, z), []).append(s)
    return {c: (float(np.mean(obs[c]) / max(np.mean(v), 1e-6)) if len(v) >= 5 and c in obs else 1.0) for c, v in prior_mean.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--fit", type=int, default=40, help="tool prior hours per cell for the map")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    from tempest_weather_v2 import obs as O
    from tempest_weather_v2.launch import Launch
    K.ram_gate(4.0)
    rng = np.random.default_rng(a.seed)
    lines = [f"S1 map first, update second: test 2023-25, 08-20 local, report 1 h old, {a.n} hours per target, map from {a.fit} prior hours per cell (2015-22), seed {a.seed}"]
    ok_all, factors = True, {}
    for st, tz in TARGETS.items():
        lat, lon, elev = O.STATIONS[st]
        z = ZoneInfo(tz)
        own_fit = K.asos_speed(st, FIT_YEARS)

        def L_at(h, cal=None):
            return Launch(lat, lon, h.strftime("%Y-%m-%d %H:%M"), tz="UTC", n=200, seed=int(h.timestamp()) % 100000, units="si", elevation=elev, mode="ai", site_cal=cal)

        cand = [h for h in sorted(own_fit) if 8 <= h.astimezone(z).hour <= 20 and h.year <= 2022]
        pm = {}
        for c in sorted({cell_of(h, z) for h in cand}):
            hs = [h for h in cand if cell_of(h, z) == c]
            for i in rng.choice(len(hs), min(a.fit, len(hs)), replace=False):
                try:
                    pm.setdefault(c, []).append(float(speed10(L_at(hs[i])).mean()))
                except Exception:   # noqa: BLE001  (an hour the tool cannot serve is skipped)
                    pass
        k = fit_map(own_fit, pm, z)
        factors[st] = k
        lines.append(f"{st}: map " + ", ".join(f"{c} {v:.3f}" for c, v in sorted(k.items())))

        own = K.asos_speed(st, range(2023, 2026))
        nb = {s: v for s, v in neighbours(st).items() if s in PAIRS[st]}
        other = {s: K.asos_speed(s, range(2023, 2026)) for s in nb}
        res, days, skipped = {}, {}, 0
        for h in test_hours(own, tz, a.n, rng):
            assert K.day_ok(h)
            h1 = h - timedelta(hours=1)
            try:
                cal = {"method": "ratio", "ratio": k.get(cell_of(h, z), 1.0)}
                Ls = {"": L_at(h), "map ": L_at(h, cal)}
                y, out = own[h][0], {}
                for mp, L in Ls.items():
                    out[("no report", mp + "-")] = score(speed10(L), y)
                    reps = [("own", own.get(h1), 0.0, 0.0)] + [(s, other[s].get(h1), km, dz) for s, (km, dz) in nb.items()]
                    for src, rep, km, dz in reps:
                        if rep is None or rep[0] < 0.5:
                            continue
                        for v in ("A", "B"):
                            with rho_from_gain(v == "B"):
                                w = speed10(L.observe(wind_10m=f"{rep[0]:.2f} m/s", wind_from_deg=float(rep[1]), age_hours=1.0, distance_km=float(km),
                                                      elevation_diff_m=float(dz), source=st if src == "own" else src))
                            out[(src, mp + v)] = score(w, y)
            except Exception:   # noqa: BLE001
                skipped += 1
                continue
            for key, val in out.items():
                res.setdefault(key, []).append(val)
                days.setdefault(key, []).append(h.date().isoformat())
        lines.append(f"  {len(res.get(('no report', '-'), []))} test hours, {skipped} skipped")
        for src in ["no report", "own"] + list(nb):
            arms = ["-", "map -"] if src == "no report" else ["A", "B", "map A", "map B"]
            for arm in arms:
                if (src, arm) not in res:
                    continue
                arr = np.array(res[(src, arm)])
                row = f"  {src:<9} {arm:<6} n {len(arr):4d}  CRPS {arr[:, 0].mean():.3f}  coverage {arr[:, 1].mean():.2f}"
                if arm == "map B":
                    ref = np.array(res[(src, "B")])
                    dm, dlo, dhi = K.block_boot(arr[:, 0] - ref[:, 0], days[(src, arm)], draws=1000)
                    ok = arr[:, 1].mean() >= 0.80 and dm <= 0.0009
                    ok_all &= bool(ok)
                    row += f"  minus B {dm:+.3f} [{dlo:+.3f}, {dhi:+.3f}]  {'ok' if ok else 'fail'}"
                lines.append(row)
        for nbr in nb:
            if (nbr, "map B") not in res:
                ok_all = False
                lines.append(f"  {nbr}: no usable reports -> counts as fail")
    os.makedirs(K.OUT, exist_ok=True)
    if not os.environ.get("KIT_SMOKE"):
        with open(os.path.join(K.OUT, f"s1_factors_seed{a.seed}.json"), "w") as fh:
            json.dump(factors, fh)
    other_seed = os.path.join(K.OUT, f"s1_factors_seed{1 - a.seed}.json")
    if a.seed in (0, 1) and os.path.exists(other_seed):
        with open(other_seed) as fh:
            prev = json.load(fh)
        gap = max(abs(factors[s][c] - prev[s][c]) for s in factors for c in factors[s] if c in prev.get(s, {}))
        ok_f = gap <= 0.05
        lines.append(f"Factor stability vs seed {1 - a.seed}: largest cell gap {gap:.3f} ({'ok' if ok_f else 'fail'}, rule <= 0.05)")
        lines.append("Rule (pre-set): map + B coverage >= 0.80 at every pair, CRPS(map + B) - CRPS(B) <= +0.0009 at every pair, both seeds; factors within 0.05.")
        lines.append("VERDICT (both seeds now on file; read the other seed's rows too): " + ("this seed PASSES and factors are stable" if ok_all and ok_f else "FAIL -> S1 closed; keep B and the map as separate opt-ins"))
    else:
        lines.append("Seed verdict: " + ("pairs PASS (needs the other seed and the factor check)" if ok_all else "FAIL -> S1 closed (kill rule: a seed misses)"))
    K.report("b4_debias_then_update", lines)


def _selfcheck():
    from datetime import datetime, timezone
    z = ZoneInfo("America/Denver")
    h = datetime(2020, 7, 1, 19, tzinfo=timezone.utc)        # 13 local, warm
    c = cell_of(h, z)
    k = fit_map({h: (6.0, 0.0)}, {c: [4.0] * 5, "x": [1.0]}, z)
    assert abs(k[c] - 1.5) < 1e-9 and k["x"] == 1.0


_selfcheck()
if __name__ == "__main__":
    main()
