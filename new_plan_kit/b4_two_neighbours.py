"""New_Plan 10.2 O1: two neighbours at once. observe_latest stops at the first usable station; here the reports of TWO neighbour stations are
merged into one report and observe is called once:
    w1 = g1, w2 = g2 * (1 - r)       g = the shipped variant-B gain of each report (Launch._report_gain: distance, height, 1 h age, night),
                                     station 1 = the larger gain; r = correlation of the two stations' errors vs the target (s_i - s_target),
                                     fitted on 2019-22, 08-20 local (before the 2023-25 test hours)
    speed = (w1 s1 + w2 s2) / (w1 + w2), direction = weighted vector mean, merged gain G = 1 - (1 - g1)(1 - w2) (G = g1 when r = 1)
The merged report's gain is set to G in memory (Launch._report_gain patched for that one call, always restored); nothing on disk changes.
With the map on: TCS uses the opt-in sitecal.tcs_speed_factor (ASK_LATER 24); ELP has no map.
Pairs: TCS from LRU + ONM, ELP from LRU + ALM. Test hours 2023-25, 08-20 local, report 1 h old, the same hours and seeds for every arm (paired).
PASS (pre-set): merged CRPS better than the best single neighbour with a day-block interval that excludes 0, coverage >= 0.80, at both
      targets, both seeds. Else closed.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b4_two_neighbours.py --seed 0     # then --seed 1
    KIT_SMOKE=1 PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b4_two_neighbours.py --n 3
Result: docs/results/logs/kit_b4_two_neighbours.log
"""
import argparse
from contextlib import contextmanager
from datetime import timedelta
from zoneinfo import ZoneInfo

import numpy as np

import kit_common as K
from b1_observe_loso import score, speed10, test_hours

PAIRS = {"TCS": ("America/Denver", ("LRU", "ONM")), "ELP": ("America/Denver", ("LRU", "ALM"))}


def error_corr(own, a, b, tz, years=(2019, 2022)):
    """Correlation of (s_a - s_target) and (s_b - s_target) over hours with all three speeds, 08-20 local, fit years only."""
    z = ZoneInfo(tz)
    hs = [h for h in own if years[0] <= h.year <= years[1] and h in a and h in b and 8 <= h.astimezone(z).hour <= 20]
    ea = np.array([a[h][0] - own[h][0] for h in hs])
    eb = np.array([b[h][0] - own[h][0] for h in hs])
    return float(np.corrcoef(ea, eb)[0, 1]), len(hs)


def merge(s1, d1, g1, s2, d2, g2, r):
    """-> (speed, direction from, merged gain); report 1 must be the larger gain."""
    w1, w2 = g1, g2 * (1.0 - max(r, 0.0))
    sp = (w1 * s1 + w2 * s2) / (w1 + w2)
    u = w1 * np.sin(np.radians(d1)) + w2 * np.sin(np.radians(d2))
    v = w1 * np.cos(np.radians(d1)) + w2 * np.cos(np.radians(d2))
    return float(sp), float(np.degrees(np.arctan2(u, v)) % 360.0), float(min(1.0 - (1.0 - g1) * (1.0 - w2), 0.97))


@contextmanager
def fixed_gain(g):
    """In memory only: every Launch's soft-report gain = g inside the block. Always restored."""
    from tempest_weather_v2 import launch as LM
    old = LM.Launch._report_gain
    LM.Launch._report_gain = lambda self: g
    try:
        yield
    finally:
        LM.Launch._report_gain = old


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--report", default="b4_two_neighbours", help="log name (AV7 writes its own log; default = as before)")
    a = ap.parse_args()
    from tempest_weather_v2 import obs as O
    from tempest_weather_v2 import sitecal
    from tempest_weather_v2.launch import Launch
    K.ram_gate(4.0)
    rng = np.random.default_rng(a.seed)
    lines = [f"O1 two neighbours at once: CRPS (m/s) and 90 % coverage of the 10 m speed, 2023-25, 08-20 local, report 1 h old, {a.n} hours per target, paired, seed {a.seed}"]
    verdict = True
    for st, (tz, (na, nb)) in PAIRS.items():
        lat, lon, elev = O.STATIONS[st]
        own = K.asos_speed(st, range(2019, 2026))
        nbs = {s: K.asos_speed(s, range(2019, 2026)) for s in (na, nb)}
        r, nfit = error_corr(own, nbs[na], nbs[nb], tz)
        geo = {s: (O.haversine_km(lat, lon, *O.STATIONS[s][:2]), O.STATIONS[s][2] - elev) for s in (na, nb)}
        arms = ("no report", na, nb, "merged")
        res, days, skipped, gains = {k: [] for k in arms}, [], [], []
        for h in test_hours(own, tz, a.n, rng):
            assert K.day_ok(h)
            h1 = h - timedelta(hours=1)
            if any(h1 not in nbs[s] or nbs[s][h1][0] < 0.5 for s in (na, nb)):
                continue
            when, seed = h.strftime("%Y-%m-%d %H:%M"), int(h.timestamp()) % 100000
            try:
                cal = sitecal.tcs_speed_factor(h) if st == "TCS" else None
                L = Launch(lat, lon, when, tz="UTC", n=200, seed=seed, units="si", elevation=elev, mode="ai", site_cal=cal)
                y, out, single = own[h][0], {}, {}
                out["no report"] = score(speed10(L), y)
                for s in (na, nb):
                    Ls = L.observe(wind_10m=f"{nbs[s][h1][0]:.2f} m/s", wind_from_deg=float(nbs[s][h1][1]), age_hours=1.0, distance_km=float(geo[s][0]), elevation_diff_m=float(geo[s][1]), source=s)
                    single[s] = Ls._report_gain()
                    out[s] = score(speed10(Ls), y)
                s1, s2 = sorted((na, nb), key=lambda s: -single[s])
                sp, dr, G = merge(nbs[s1][h1][0], float(nbs[s1][h1][1]), single[s1], nbs[s2][h1][0], float(nbs[s2][h1][1]), single[s2], r)
                with fixed_gain(G):
                    out["merged"] = score(speed10(L.observe(wind_10m=f"{sp:.2f} m/s", wind_from_deg=dr, age_hours=1.0, distance_km=float(min(geo[s][0] for s in (na, nb))),
                                                            elevation_diff_m=float(geo[s1][1]), source=f"{s1}+{s2}")), y)
            except Exception as e:   # noqa: BLE001  (an hour the tool cannot serve is skipped, and counted)
                skipped.append(repr(e)[:80])
                continue
            for k in arms:
                res[k].append(out[k])
            days.append(h.date().isoformat())
            gains.append((single[na], single[nb], G))
        n = len(days)
        lines.append(f"{st} from {na} + {nb}: {n} hours, {len(skipped)} skipped" + (f" (first: {skipped[0]})" if skipped else "")
                     + f"; error correlation r {r:+.2f} ({nfit} fit hours 2019-22)" + (f"; mean gains {na} {np.mean([g[0] for g in gains]):.2f}, {nb} {np.mean([g[1] for g in gains]):.2f}, merged {np.mean([g[2] for g in gains]):.2f}" if gains else "")
                     + ("; map on (tcs_speed_factor)" if st == "TCS" else "; no map"))
        if n < 2:
            verdict = False
            continue
        arr = {k: np.array(v) for k, v in res.items()}
        for k in arms:
            lines.append(f"  {k:<10} CRPS {arr[k][:, 0].mean():.3f}  coverage {arr[k][:, 1].mean():.2f}")
        best = min((na, nb), key=lambda s: arr[s][:, 0].mean())
        dm, dlo, dhi = K.block_boot(arr["merged"][:, 0] - arr[best][:, 0], days, draws=1000)
        cov = arr["merged"][:, 1].mean()
        ok = dhi < 0 and cov >= 0.80
        verdict &= bool(ok)
        lines.append(f"  merged minus best single ({best}) {dm:+.3f} [{dlo:+.3f}, {dhi:+.3f}], merged coverage {cov:.2f}  {'ok' if ok else 'fail'}")
    lines.append("Rule (pre-set): merged CRPS better than the best single neighbour, interval excludes 0, coverage >= 0.80; both targets, both seeds.")
    lines.append("Seed verdict: " + ("PASS (needs the other seed)" if verdict else "FAIL -> O1 closed; observe_latest keeps one station"))
    K.report(a.report, lines)


def _selfcheck():
    sp, dr, G = merge(4.0, 90.0, 0.5, 4.0, 90.0, 0.4, 1.0)
    assert abs(sp - 4.0) < 1e-9 and abs(dr - 90.0) < 1e-6 and abs(G - 0.5) < 1e-9      # fully shared error: nothing gained
    sp, dr, G = merge(2.0, 0.0, 0.5, 6.0, 90.0, 0.5, 0.0)
    assert abs(sp - 4.0) < 1e-9 and abs(dr - 45.0) < 1e-6 and abs(G - 0.75) < 1e-9
    from tempest_weather_v2 import launch as LM
    f0 = LM.Launch._report_gain
    with fixed_gain(0.3):
        assert LM.Launch._report_gain(None) == 0.3
    assert LM.Launch._report_gain is f0


_selfcheck()
if __name__ == "__main__":
    main()
