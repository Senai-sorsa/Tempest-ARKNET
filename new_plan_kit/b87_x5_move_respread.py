"""New_Plan 29.5 X5 (2026-11-19): ground wind "move then respread". b36's stack (site map, then the merged two-neighbour report) with two changes:
  MOVE     the site map is used only where it earns it: a gate on 2023 hours (map vs no map, same hours, merged report, mean CRPS) decides per target. Gate hours are
           2023 only; test hours are 2024-25 only (27.6 guard: fit knob and verdict period do not overlap). The map itself is fitted on 2015-22 as in b36.
  RESPREAD the final observe call runs with t_update=True (G2-2 Student-t widening; ground reports only).
Targets TCS (LRU + ONM) and ELP (LRU + ALM), 08-20 local, report 1 h old, hour seeds 4 and 5, 21-day block interval (b36's machinery).
Arms on the same test hours: "merged" (control: no map, no widening = b36's merged arm), "X5" (gated map + merged + t_update=True; the verdict arm).
Information arm (not in the verdict): "X5 + gap": X5 members with one independent N(0, 1.54 m/s) draw per component added (the UR3 measured 10 m gap).
Stated deviation: UR3's gap was measured on the RAW ensemble; the tool prior already carries its own calibrated spread, so adding the gap on top of a posterior
double-counts. It is shown, not judged. The verdict arm uses G2-2 alone for the spread step.
PRE-SET RULE (written before any run; UR14's rule plus coverage 0.85):
  PASS: X5 CRPS better than merged with a 21-day block interval below 0 at both targets, coverage of X5 >= 0.85 at both targets, in both seeds.
  KILL: coverage of X5 under 0.80 at either target in either seed.   Otherwise MISS and close. PASS -> ASK_LATER only, never shipped.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b87_x5_move_respread.py [--n 300 --fit 60 --gate 100]
    KIT_SMOKE=1 PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b87_x5_move_respread.py --n 3 --fit 3 --gate 3
Result: docs/results/logs/kit_b87_x5_move_respread.log
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
from b36_ur14_obs_stack import blk

NAME = "b87_x5_move_respread"
GAP = 1.54


def judge(cells):
    """cells: [(target, seed, hi, cov_x5)] -> verdict."""
    if any(c[3] < 0.80 for c in cells):
        return "KILL (coverage under 0.80)"
    return "PASS" if len(cells) == 4 and all(c[2] < 0 and c[3] >= 0.85 for c in cells) else "MISS (record, no adoption)"


def with_gap(L, rng, gap=GAP):
    """members' 10 m speed with the UR3 gap added per component."""
    s = L._ensure_pool()["samples"]
    u, v = np.asarray(s["u"])[:, 0], np.asarray(s["v"])[:, 0]
    return np.hypot(u + rng.normal(0, gap, u.shape), v + rng.normal(0, gap, v.shape))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--fit", type=int, default=60)
    ap.add_argument("--gate", type=int, default=100)
    ap.add_argument("--seeds", default="4,5")
    a = ap.parse_args()
    from tempest_weather_v2 import obs as O
    from tempest_weather_v2.launch import Launch
    K.ram_gate(4.0)
    lines = [f"X5 move then respread: map gated on {a.gate} 2023 hours, test 2024-25 08-20 local, {a.n} hours per target, map from {a.fit} prior hours per cell (2015-22)"]
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

            def posterior(h, cal, t_update):
                """merged two-neighbour report observed on the launch with site calibration cal; returns the Launch."""
                h1 = h - timedelta(hours=1)
                L = L_at(h, cal)
                single = {s: L.observe(wind_10m=f"{nbs[s][h1][0]:.2f} m/s", wind_from_deg=float(nbs[s][h1][1]), age_hours=1.0, distance_km=float(geo[s][0]),
                                       elevation_diff_m=float(geo[s][1]), source=s)._report_gain() for s in (na, nb)}
                s1, s2 = sorted((na, nb), key=lambda s: -single[s])
                sp, dr, G = merge(nbs[s1][h1][0], float(nbs[s1][h1][1]), single[s1], nbs[s2][h1][0], float(nbs[s2][h1][1]), single[s2], r)
                with fixed_gain(G):
                    L.observe(wind_10m=f"{sp:.2f} m/s", wind_from_deg=dr, age_hours=1.0, distance_km=float(min(geo[s][0] for s in (na, nb))),
                              elevation_diff_m=float(geo[s1][1]), source=f"{s1}+{s2}", t_update=t_update)
                return L

            def usable(h):
                h1 = h - timedelta(hours=1)
                return all(h1 in nbs[s] and nbs[s][h1][0] >= 0.5 for s in (na, nb))

            # gate on 2023: map vs no map, merged report, same hours
            g_gain, g_n = [], 0
            for h in test_hours(own, tz, a.gate, rng, years=(2023, 2023)):
                if not usable(h):
                    continue
                try:
                    cal = {"method": "ratio", "ratio": kmap.get(cell_of(h, z), 1.0)}
                    g_gain.append(score(speed10(posterior(h, cal, False)), own[h][0])[0] - score(speed10(posterior(h, None, False)), own[h][0])[0])
                except Exception:   # noqa: BLE001
                    continue
            use_map = bool(len(g_gain) >= 10 and np.mean(g_gain) < 0)
            res, days, skipped = {"merged": [], "X5": [], "X5 + gap": []}, [], 0
            for h in test_hours(own, tz, a.n, rng, years=(2024, 2025)):
                assert K.day_ok(h)
                if not usable(h):
                    continue
                try:
                    y = own[h][0]
                    cal = {"method": "ratio", "ratio": kmap.get(cell_of(h, z), 1.0)} if use_map else None
                    out = {"merged": score(speed10(posterior(h, None, False)), y)}
                    Lx = posterior(h, cal, True)
                    out["X5"] = score(speed10(Lx), y)
                    out["X5 + gap"] = score(with_gap(Lx, rng), y)
                except Exception:   # noqa: BLE001  (an hour the tool cannot serve is skipped, and counted)
                    skipped += 1
                    continue
                for k_, v in out.items():
                    res[k_].append(v)
                days.append(blk(h.date()))
            if len(days) < 2:
                lines.append(f"  seed {seed} {st}: too few hours")
                continue
            B, X, XG = (np.array(res[k]) for k in ("merged", "X5", "X5 + gap"))
            dm, lo, hi = K.block_boot(X[:, 0] - B[:, 0], days, draws=1000)
            cells.append((st, seed, hi, X[:, 1].mean()))
            lines.append(f"  seed {seed} {st} from {na} + {nb}: {len(days)} hours ({skipped} skipped), r {r:+.2f}; gate on {len(g_gain)} 2023 hours: map minus no map CRPS "
                         f"{np.mean(g_gain) if g_gain else float('nan'):+.3f} -> map {'USED' if use_map else 'not used'}; map " + ", ".join(f"{c} {v:.3f}" for c, v in sorted(kmap.items()))
                         + f"; merged CRPS {B[:, 0].mean():.3f} cov {B[:, 1].mean():.2f} | X5 CRPS {X[:, 0].mean():.3f} cov {X[:, 1].mean():.2f} | difference {dm:+.3f} [{lo:+.3f}, {hi:+.3f}]"
                         f" | information: X5 + gap CRPS {XG[:, 0].mean():.3f} cov {XG[:, 1].mean():.2f}")
    lines.append("Rule (pre-set, New_Plan 29.5 X5): PASS = X5 better than merged (21-day interval < 0) at TCS and ELP, X5 coverage >= 0.85 at both, both seeds; KILL = coverage < 0.80.")
    lines.append("Verdict: " + judge(cells))
    K.report(NAME, lines)


def _selfcheck():
    ok = [("TCS", 4, -0.01, 0.86), ("ELP", 4, -0.02, 0.87), ("TCS", 5, -0.01, 0.85), ("ELP", 5, -0.01, 0.86)]
    assert judge(ok) == "PASS"
    assert judge(ok[:3] + [("ELP", 5, -0.01, 0.79)]).startswith("KILL")
    assert judge(ok[:3] + [("ELP", 5, -0.01, 0.84)]).startswith("MISS")
    assert judge([("TCS", 4, 0.01, 0.86)] + ok[1:]).startswith("MISS")
    assert judge(ok[:3]).startswith("MISS")
    class _L:
        def _ensure_pool(self):
            return {"samples": {"u": np.zeros((500, 3)), "v": np.zeros((500, 3))}}
    w = with_gap(_L(), np.random.default_rng(0))
    assert w.shape == (500,) and 1.5 < w.mean() < 2.5            # Rayleigh with sigma 1.54: mean about 1.93


_selfcheck()
if __name__ == "__main__":
    main()
