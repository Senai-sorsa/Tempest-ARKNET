"""A3: does `observe` still help when the wind report comes from ANOTHER station? REPORT + PASS RULE BELOW.
(A1, the same-station measurement, is already done: scripts/w6_observe_eval.py. Its numbers, CRPS m/s of the 10 m speed one hour later:
 TCS no report 1.636 / observe 1.148 / speed-space 1.140; MAF 1.480 / 1.016 / 0.987; linear persistence 1.035 / 0.923.)
Here: targets TCS and MAF, test hours 2023-25, 08-20 local. For each hour the tool's 10 m wind speed at the target is scored against the
target's own measured speed, after one of:
    no report            the tool alone
    own station, 1 h old the reference (as w6)
    <neighbour>, 1 h old Launch.observe(...) with the neighbour's wind of one hour earlier, its true distance and height difference
Neighbours = every station of tempest_weather_v2/obs.py STATIONS within 250 km of the target (TCS: ONM, LRU, ALM, ELP, ABQ; MAF: FST, PEQ).
PASS per neighbour: CRPS minus the no-report CRPS of the same hours is below 0 with its whole day-block 95 % interval AND 90 % coverage between 0.85 and 0.95.
FAIL (a neighbour makes it worse, or coverage leaves 0.85-0.95): write it to the log; the fix is the distance table in obs.py (REP_TABLE),
which is a core change: report, do not edit.

    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_observe_loso.py            # 300 hours per target, about 30-40 min, 3 threads
    KIT_SMOKE=1 PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_observe_loso.py --n 6      # smoke test
Result: docs/results/logs/kit_b1_observe_loso.log
"""
import argparse
from datetime import timedelta
from zoneinfo import ZoneInfo

import numpy as np

import kit_common as K

TARGETS = {"TCS": "America/Denver", "MAF": "America/Chicago"}


def neighbours(target, max_km=250.0):
    """-> {station: (distance km, height of the neighbour minus height of the target, m)} without the target itself, nearest first."""
    from tempest_weather_v2 import obs as O
    lat, lon, elev = O.STATIONS[target]
    d = {s: (O.haversine_km(lat, lon, p[0], p[1]), p[2] - elev) for s, p in O.STATIONS.items() if s != target}
    return dict(sorted(((s, v) for s, v in d.items() if v[0] <= max_km), key=lambda kv: kv[1][0]))


def test_hours(obs, tz, n, rng, years=(2023, 2025)):
    """Hours with a measured speed now and one hour earlier (earlier speed at least 0.5 m/s), 08-20 local, never 2026."""
    z = ZoneInfo(tz)
    ok = [h for h in sorted(obs) if years[0] <= h.year <= years[1] and (h - timedelta(hours=1)) in obs and 8 <= h.astimezone(z).hour <= 20 and obs[h - timedelta(hours=1)][0] >= 0.5]
    return [ok[i] for i in np.sort(rng.choice(len(ok), min(n, len(ok)), replace=False))]


def speed10(L):
    s = L._ensure_pool()["samples"]
    return np.hypot(np.asarray(s["u"])[:, 0], np.asarray(s["v"])[:, 0])


def score(w, y):
    lo, hi = np.percentile(w, [5, 95])
    return K.crps1(w, y), float(lo <= y <= hi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    a = ap.parse_args()
    from tempest_weather_v2 import obs as O
    from tempest_weather_v2.launch import Launch
    rng = np.random.default_rng(0)
    lines = ["A3 observe from another station: CRPS (m/s) / 90 % coverage of the 10 m speed at the target, 2023-25, 08-20 local"]
    for st, tz in TARGETS.items():
        lat, lon, elev = O.STATIONS[st]
        own = K.asos_speed(st, range(2023, 2026))
        nb = neighbours(st)
        other = {s: K.asos_speed(s, range(2023, 2026)) for s in nb}
        res, days = {}, {}
        for h in test_hours(own, tz, a.n, rng):
            assert K.day_ok(h)
            h1 = h - timedelta(hours=1)
            try:
                L = Launch(lat, lon, h.strftime("%Y-%m-%d %H:%M"), tz="UTC", n=200, seed=int(h.timestamp()) % 100000, units="si", elevation=elev, mode="ai")
                runs = {"no report": L, "own station, 1 h old": L.observe(wind_10m=f"{own[h1][0]:.2f} m/s", wind_from_deg=float(own[h1][1]), age_hours=1.0, distance_km=0.0, elevation_diff_m=0.0, source=f"ASOS {st}")}
                for s, (km, dz) in nb.items():
                    if h1 in other[s] and other[s][h1][0] >= 0.5:
                        runs[f"{s} ({km:.0f} km), 1 h old"] = L.observe(wind_10m=f"{other[s][h1][0]:.2f} m/s", wind_from_deg=float(other[s][h1][1]), age_hours=1.0, distance_km=float(km), elevation_diff_m=float(dz), source=f"ASOS {s}")
                out = {k: score(speed10(v), own[h][0]) for k, v in runs.items()}
            except Exception as e:   # noqa: BLE001  (an hour the tool cannot serve is skipped, and counted)
                res.setdefault("skipped", []).append(repr(e)[:80])
                continue
            for k, v in out.items():
                res.setdefault(k, []).append(v + (out["no report"][0],))        # third number: the no-report CRPS of the SAME hour (paired)
                days.setdefault(k, []).append(h.date().isoformat())
        skipped = res.pop("skipped", [])
        lines.append(f"{st}: {len(res.get('no report', []))} hours used, {len(skipped)} skipped" + (f" (first reason: {skipped[0]})" if skipped else ""))
        for k, v in res.items():
            v = np.array(v)
            m, lo, hi = K.block_boot(v[:, 0], days[k], draws=1000)
            dm, dlo, dhi = K.block_boot(v[:, 0] - v[:, 2], days[k], draws=1000)
            verdict = "" if k in ("no report", "own station, 1 h old") else ("   PASS" if dhi < 0 and 0.85 <= v[:, 1].mean() <= 0.95 else "   FAIL")
            lines.append(f"  {k:<26} n {len(v):4d}  CRPS {m:.3f}  minus no report on the same hours {dm:+.3f} [{dlo:+.3f}, {dhi:+.3f}]  coverage {v[:, 1].mean():.2f}{verdict}")
    lines.append("Read it like this: PASS = the neighbour's report helps and the spread is honest. Any FAIL -> report it; the distance table (obs.py REP_TABLE) is a core change, not part of this kit.")
    K.report("b1_observe_loso", lines)


def _selfcheck():
    nb = neighbours("MAF")
    assert "MAF" not in nb and "FST" in nb and all(v[0] <= 250 for v in nb.values()) and "ONM" in neighbours("TCS")
    assert score(np.arange(101.0), 50.0)[1] == 1.0 and score(np.arange(101.0), 99.0)[1] == 0.0


_selfcheck()
if __name__ == "__main__":
    main()
