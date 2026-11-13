"""A3-fix v2: a neighbour's wind report is over-trusted because the DEFAULT speed-space update (W6) ignores distance. PASS RULE BELOW.
Found 2026-11-11 while building A3-fix: tempest_weather_v2/launch.py _conditioned_pool sets rho = SPEED_RHO_PER_HOUR ** age for every soft report,
own station or 200 km away alike, then rescales the 10 m speed toward the report. The component update before it does use the distance gain
(obs.effective_gain), but the speed-space step overwrites the 10 m speed. b1_observe_loso.py: neighbours cover 0.67-0.82 (no report 0.80 / 0.92).
So the README's planned fix (a factor on observation_sigma) cannot reach the 10 m speed. Variants, all IN MEMORY ONLY (nothing on disk changes):
    A shipped            today's default (speed space, rho from age only)
    B rho=gain           speed space with rho = obs.effective_gain(age, distance, dz, night) for reports >= 5 km away (the tool's own fitted gain;
                         no new number). Own-station reports unchanged (checked: the own-station row must be identical to A).
    C component          speed_space=False (only the distance-aware Gaussian update)
    D rho=gain + qmap    B, and the neighbour's speed first mapped to the same quantile of the TARGET's prior (F_target^-1(F_neighbour(s)),
                         F from the tool's own prior pools at both places and the same hour): a 6 m/s at a windy site is not a 6 m/s at the pad.
Data: targets TCS and MAF, test hours 2023-25, 08-20 local, report 1 h old, the same hours and seeds for every variant (paired). No fitting
(REP_TABLE was fitted earlier on station pairs by scripts/obs_loso.py), so no fit window is needed.
PASS (per variant): coverage 0.85-0.95 for EVERY neighbour (or, at TCS where no report covers only 0.80, at least the no-report coverage minus 0.03),
      AND CRPS minus shipped on the same hours not above +0.02 m/s with its day-block interval for any neighbour (it may give back a little CRPS
      for honest spread), AND the own-station row equal to shipped.
PASS -> core change: a switch in launch.py (default off), one test, full suite; adopting it as the default is permitted by New_Plan section 8.
FAIL for all -> report; the cause is then the target's own spread (TCS 0.80), not observe.

    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b3_a3fix_neighbour_rho.py          # 200 hours per target, about 60-80 min, 3 threads
    KIT_SMOKE=1 PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b3_a3fix_neighbour_rho.py --n 4   # smoke test
Result: docs/results/logs/kit_b3_a3fix_neighbour_rho.log
"""
import argparse
from contextlib import contextmanager
from datetime import timedelta

import numpy as np

import kit_common as K
from b1_observe_loso import TARGETS, neighbours, score, speed10, test_hours

_GAIN = {}          # the last (gain, distance) seen by obs.effective_gain inside Launch._sensor_sigma


@contextmanager
def rho_from_gain(on):
    """In memory only: when on, the speed-space step uses rho = the distance gain for reports >= OWN_STATION_KM. Always restored."""
    from tempest_weather_v2 import launch as LM
    from tempest_weather_v2 import obs as O
    old_gain, old_upd = O.effective_gain, LM._speed_space_update

    def gain(age_hours=0.0, distance_km=0.0, dz_m=0.0, night=0.0):
        g = old_gain(age_hours, distance_km, dz_m, night)
        _GAIN.update(g=g, km=float(distance_km))
        return g

    def upd(cond_u, cond_v, prior_speed, obs_speed, rho, z, rng):
        if on and _GAIN.get("km", 0.0) >= O.OWN_STATION_KM:
            rho = min(float(_GAIN["g"]), 0.97)
        return old_upd(cond_u, cond_v, prior_speed, obs_speed, rho, z, rng)

    O.effective_gain, LM._speed_space_update = gain, upd
    try:
        yield
    finally:
        O.effective_gain, LM._speed_space_update = old_gain, old_upd
        _GAIN.clear()


def qmap(s, prior_from, prior_to):
    """Speed s at quantile F_from(s) of prior_from -> the same quantile of prior_to (mid-rank, clipped inside the sample)."""
    a, b = np.sort(prior_from), np.sort(prior_to)
    f = np.clip((np.searchsorted(a, s) + 0.5) / (len(a) + 1.0), 0.5 / (len(a) + 1), 1 - 0.5 / (len(a) + 1))
    return float(np.quantile(b, f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0, help="hour draw; 1 = replicate on new hours (same rule)")
    a = ap.parse_args()
    from tempest_weather_v2 import obs as O
    from tempest_weather_v2.launch import Launch
    K.ram_gate(4.0)
    rng = np.random.default_rng(a.seed)
    V = ("A shipped", "B rho=gain", "C component", "D rho=gain+qmap")
    lines = [f"A3-fix v2, neighbour reports: CRPS (m/s) and 90 % coverage of the 10 m speed at the target, 2023-25, 08-20 local, report 1 h old, {a.n} hours per target, paired, hour seed {a.seed}"]
    allpass = {v: True for v in V}
    for st, tz in TARGETS.items():
        lat, lon, elev = O.STATIONS[st]
        own = K.asos_speed(st, range(2023, 2026))
        nb = neighbours(st)
        other = {s: K.asos_speed(s, range(2023, 2026)) for s in nb}
        res, days, skipped, nomap = {}, {}, [], {}
        for h in test_hours(own, tz, a.n, rng):
            assert K.day_ok(h)
            h1, when, seed = h - timedelta(hours=1), h.strftime("%Y-%m-%d %H:%M"), int(h.timestamp()) % 100000
            try:
                L = Launch(lat, lon, when, tz="UTC", n=200, seed=seed, units="si", elevation=elev, mode="ai")
                p_t = speed10(L)
                y, out = own[h][0], {}
                out[("no report", "-")] = score(p_t, y)
                for v in V[:3]:
                    with rho_from_gain(v.startswith("B")):
                        out[("own station", v)] = score(speed10(L.observe(wind_10m=f"{own[h1][0]:.2f} m/s", wind_from_deg=float(own[h1][1]), age_hours=1.0,
                                                                          distance_km=0.0, elevation_diff_m=0.0, source=st, speed_space=not v.startswith("C"))), y)
                for s, (km, dz) in nb.items():
                    if h1 not in other[s] or other[s][h1][0] < 0.5:
                        continue
                    sp, dr, key = other[s][h1][0], float(other[s][h1][1]), f"{s} ({km:.0f} km)"
                    nlat, nlon, nel = O.STATIONS[s]
                    try:     # shortcut: a neighbour outside the trained area has no prior, so D = B there (counted in the log)
                        p_n = speed10(Launch(nlat, nlon, when, tz="UTC", n=200, seed=seed, units="si", elevation=nel, mode="ai"))
                    except ValueError:
                        p_n = None
                        nomap[key] = nomap.get(key, 0) + 1
                    for v in V:
                        val = qmap(sp, p_n, p_t) if v.startswith("D") and p_n is not None else sp
                        with rho_from_gain(v[0] in "BD"):
                            w = speed10(L.observe(wind_10m=f"{val:.2f} m/s", wind_from_deg=dr, age_hours=1.0, distance_km=float(km), elevation_diff_m=float(dz),
                                                  source=s, speed_space=not v.startswith("C")))
                        out[(key, v)] = score(w, y)
            except Exception as e:   # noqa: BLE001  (an hour the tool cannot serve is skipped, and counted)
                skipped.append(repr(e)[:80])
                continue
            for k, val in out.items():
                res.setdefault(k, []).append(val)
                days.setdefault(k, []).append(h.date().isoformat())
        base_cov = np.mean([c for _, c in res.get(("no report", "-"), [(0, 0)])])
        lines.append(f"{st}: {len(res.get(('no report', '-'), []))} hours, {len(skipped)} skipped" + (f" (first: {skipped[0]})" if skipped else "") + f"; no report coverage {base_cov:.2f}"
                     + (f"; D used no quantile map (neighbour outside the trained area) for {nomap}" if nomap else ""))
        if not res:
            allpass = {v: False for v in V}
        lo_cov = min(0.85, base_cov - 0.03)
        for where in dict.fromkeys(k[0] for k in res):
            for v in ([None] if where == "no report" else V if where != "own station" else V[:3]):
                k = (where, v or "-")
                arr = np.array(res[k])
                m = K.block_boot(arr[:, 0], days[k], draws=1000)[0]
                row = f"  {where:<14} {v or '':<16} n {len(arr):4d}  CRPS {m:.3f}  coverage {arr[:, 1].mean():.2f}"
                if v and v != "A shipped":
                    ref = np.array(res[(where, "A shipped")])
                    assert len(ref) == len(arr)
                    dm, dlo, dhi = K.block_boot(arr[:, 0] - ref[:, 0], days[k], draws=1000)
                    row += f"  minus shipped {dm:+.3f} [{dlo:+.3f}, {dhi:+.3f}]"
                    if where == "own station":
                        ok = v.startswith("C") or np.allclose(arr, ref)
                        row += "" if v.startswith("C") else ("  (identical: OK)" if ok else "  NOT IDENTICAL")
                    else:
                        ok = lo_cov <= arr[:, 1].mean() <= 0.95 and dlo <= 0.02
                        row += "   ok" if ok else "   fail"
                    if not v.startswith("C") or where != "own station":
                        allpass[v] &= bool(ok)
                lines.append(row)
    winners = [v for v in V[1:] if allpass[v]]
    lines.append(f"Coverage rule per neighbour: 0.85-0.95 (TCS: at least its no-report coverage minus 0.03). CRPS rule: lower end of the interval vs shipped <= +0.02 m/s.")
    lines.append("VERDICT: " + (f"PASS for {', '.join(winners)} -> add the simplest passing variant to launch.py behind a switch (default off), one test, full suite; then adopt (New_Plan section 8)."
                                if winners else "no variant passes -> the neighbour problem is not the speed-space rho alone; report, keep the shipped default."))
    K.report("b3_a3fix_neighbour_rho", lines)


def _selfcheck():
    a = np.arange(1.0, 101.0)
    assert abs(qmap(50.0, a, a) - 50.0) < 1.0 and abs(qmap(50.0, a, 2 * a) - 100.0) < 2.0
    from tempest_weather_v2 import launch as LM
    from tempest_weather_v2 import obs as O
    f0 = LM._speed_space_update
    with rho_from_gain(True):
        assert LM._speed_space_update is not f0 and O.effective_gain(1.0, 150.0, 0.0, 0.0) < 0.6
    assert LM._speed_space_update is f0 and not _GAIN


_selfcheck()
if __name__ == "__main__":
    main()
