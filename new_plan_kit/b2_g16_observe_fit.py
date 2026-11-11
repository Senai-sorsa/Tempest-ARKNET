"""G1-6: fit the two numbers of `observe` (own-station wind report) on old data, then test on 2023-25. PASS RULE BELOW.
The two numbers:
    tau    how fast a report loses value with age. Shipped: tempest_weather_v2/obs.py TAU_H = 6.3 hours (gain = exp(-age / tau)).
    scale  a factor on the report's error (obs.py observation_sigma). Shipped: 1.0. Above 1 = trust the report less = wider answer.
Neither is a switch in the core, so this script changes them IN MEMORY ONLY (set(tau, scale) below, always put back). No core file is edited.
It tests the plain update (observe(..., speed_space=False)). The shipped default for station reports is the speed-space update (W6);
the test prints that too, because the fitted plain update must beat it to be worth anything.
Steps: (1) FIT, 2015-22, all nine stations of obs.py STATIONS, 08-20 local, report age 1, 3, 6 h: grid tau x scale;
           score = CRPS of the 10 m speed, and 90 % coverage. The bias (median minus measured) is printed first:
           if it is beyond 0.2 m/s the centre is wrong and no spread number can fix it -> say so in the report.
           Choice = lowest CRPS among grid points with coverage 0.88-0.92 (if none: the one with coverage nearest 0.90, and the log says so).
       (2) TEST, 2023-25, TCS and MAF, report 1 h old, same hours for every row (paired).
PASS: fitted plain update minus shipped default, CRPS, whole day-block 95 % interval below 0, AND coverage 0.85-0.95 at both stations.
PASS -> report the two numbers; changing TAU_H / adding a scale is a core change, a separate task.
FAIL -> G1-6 closed: the shipped default stays. (Linear persistence, the old reference: TCS 1.035, MAF 0.923 m/s.)

    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b2_g16_observe_fit.py           # about 1 h, 3 GB RAM, 3 threads
    KIT_SMOKE=1 PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b2_g16_observe_fit.py --n 3 --n-test 5 --quick    # smoke test
Result: docs/results/logs/kit_b2_g16_observe_fit.log
"""
import argparse
from contextlib import contextmanager
from datetime import timedelta

import numpy as np

import kit_common as K
from b1_observe_loso import score, speed10, test_hours

TZ = {"MAF": "America/Chicago", "FST": "America/Chicago", "PEQ": "America/Chicago"}       # every other station: America/Denver
TAUS, SCALES, LAGS = (3.0, 4.5, 6.3, 9.0, 13.0, 20.0), (0.6, 0.8, 1.0, 1.3, 1.7, 2.2), (1, 3, 6)


@contextmanager
def set_obs(tau, scale):
    """In memory only: own-station decay time `tau` and a factor `scale` on the report's error. Always restored."""
    from tempest_weather_v2 import obs as O
    old_def, old_sig = O.persistence_gain.__defaults__, O.observation_sigma
    O.persistence_gain.__defaults__ = (float(tau),)
    O.observation_sigma = lambda prior_sd, gain: scale * old_sig(prior_sd, gain)
    try:
        yield
    finally:
        O.persistence_gain.__defaults__, O.observation_sigma = old_def, old_sig


def launch(st, h):
    from tempest_weather_v2 import obs as O
    from tempest_weather_v2.launch import Launch
    lat, lon, elev = O.STATIONS[st]
    return Launch(lat, lon, h.strftime("%Y-%m-%d %H:%M"), tz="UTC", n=200, seed=int(h.timestamp()) % 100000, units="si", elevation=elev, mode="ai")


def report(L, own, h, lag, st, speed_space):
    r = own[h - timedelta(hours=lag)]
    return speed10(L.observe(wind_10m=f"{r[0]:.2f} m/s", wind_from_deg=float(r[1]), age_hours=float(lag), distance_km=0.0, elevation_diff_m=0.0, source=f"ASOS {st}", speed_space=speed_space))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="fit hours per station")
    ap.add_argument("--n-test", type=int, default=300, help="test hours per station")
    ap.add_argument("--quick", action="store_true", help="2 x 2 grid (smoke test only)")
    a = ap.parse_args()
    from tempest_weather_v2 import obs as O
    taus, scales = (TAUS[2:4], SCALES[2:4]) if a.quick else (TAUS, SCALES)
    rng = np.random.default_rng(0)
    crps, cov, bias, nfit = np.zeros((len(taus), len(scales))), np.zeros((len(taus), len(scales))), [], 0
    for st in O.STATIONS:
        own = K.asos_speed(st, range(2015, 2023))
        for h in test_hours(own, TZ.get(st, "America/Denver"), a.n, rng, years=(2015, 2022)):
            lags = [g for g in LAGS if (h - timedelta(hours=g)) in own and own[h - timedelta(hours=g)][0] >= 0.5]
            c1, k1, b1 = np.zeros_like(crps), np.zeros_like(cov), []
            try:
                L = launch(st, h)
                for i, tau in enumerate(taus):
                    for j, sc in enumerate(scales):
                        with set_obs(tau, sc):
                            for g in lags:
                                w = report(L, own, h, g, st, False)
                                c, k = score(w, own[h][0])
                                c1[i, j] += c
                                k1[i, j] += k
                                if tau == 6.3 and sc == 1.0:
                                    b1.append(np.median(w) - own[h][0])
            except Exception:   # noqa: BLE001  (an hour the tool cannot serve is skipped whole, so no half-filled grid)
                continue
            crps, cov, bias, nfit = crps + c1, cov + k1, bias + b1, nfit + len(lags)
    assert nfit > 0, "no fit hour could be used"
    crps, cov = crps / nfit, cov / nfit
    lines = [f"G1-6 observe fit (plain update): {nfit} reports of 2015-22 at {len(O.STATIONS)} stations, ages {LAGS} h",
             f"bias at the shipped numbers (median minus measured): {np.mean(bias):+.2f} m/s" + ("   BEYOND 0.2: the centre is wrong; fix the centre before any spread number" if abs(np.mean(bias)) > 0.2 else ""),
             "CRPS m/s / coverage; rows tau (h), columns scale " + "  ".join(f"{s:>9}" for s in scales)]
    lines += [f"  tau {t:<5}" + "  ".join(f"{crps[i, j]:.3f}/{cov[i, j]:.2f}" for j in range(len(scales))) for i, t in enumerate(taus)]
    good = (cov >= 0.88) & (cov <= 0.92)
    i, j = np.unravel_index(np.argmin(np.where(good, crps, np.inf)) if good.any() else np.argmin(np.abs(cov - 0.90)), crps.shape)
    tau, sc = taus[i], scales[j]
    lines.append(f"choice: tau {tau} h, scale {sc} (CRPS {crps[i, j]:.3f}, coverage {cov[i, j]:.2f})" + ("" if good.any() else "   NO grid point has coverage 0.88-0.92: nearest to 0.90 taken"))
    lines.append("TEST 2023-25, report 1 h old: CRPS m/s / coverage")
    passed = []
    for st, ref in (("TCS", 1.035), ("MAF", 0.923)):
        own, res, days = K.asos_speed(st, range(2023, 2026)), {}, []
        for h in test_hours(own, TZ.get(st, "America/Denver"), a.n_test, rng):
            assert K.day_ok(h)
            try:
                L = launch(st, h)
                out = {"no report": speed10(L), "shipped default (speed-space)": report(L, own, h, 1, st, None), "plain, shipped numbers": report(L, own, h, 1, st, False)}
                with set_obs(tau, sc):
                    out[f"plain, tau {tau} scale {sc}"] = report(L, own, h, 1, st, False)
            except Exception:   # noqa: BLE001
                continue
            for k, w in out.items():
                res.setdefault(k, []).append(score(w, own[h][0]))
            days.append(h.date().isoformat())
        res = {k: np.array(v) for k, v in res.items()}
        lines.append(f"  {st}: {len(days)} hours (linear persistence, old reference: {ref})")
        lines += [f"    {k:<32}{v[:, 0].mean():.3f} / {v[:, 1].mean():.2f}" for k, v in res.items()]
        new, old = res[f"plain, tau {tau} scale {sc}"], res["shipped default (speed-space)"]
        dm, dlo, dhi = K.block_boot(new[:, 0] - old[:, 0], days, draws=1000)
        passed.append(dhi < 0 and 0.85 <= new[:, 1].mean() <= 0.95)
        lines.append(f"    fitted minus shipped default: {dm:+.3f} [{dlo:+.3f}, {dhi:+.3f}]  {'PASS' if passed[-1] else 'FAIL'}")
    lines.append(f"VERDICT: PASS. Report tau {tau}, scale {sc}; putting them into obs.py is a core change, a separate task." if all(passed) else
                 "VERDICT: G1-6 CLOSED. The fitted plain update does not beat the shipped default at both stations; nothing changes.")
    K.report("b2_g16_observe_fit", lines)


def _selfcheck():
    from tempest_weather_v2 import obs as O
    g, s = O.persistence_gain(3.0), O.observation_sigma(2.0, 0.5)
    with set_obs(3.0, 2.0):
        assert np.isclose(O.persistence_gain(3.0), np.exp(-1.0)) and np.isclose(O.effective_gain(3.0, 0.0), np.exp(-1.0)) and np.isclose(O.observation_sigma(2.0, 0.5), 2 * s)
    assert O.persistence_gain(3.0) == g and O.observation_sigma(2.0, 0.5) == s          # restored
    assert 6.3 in TAUS and 1.0 in SCALES


_selfcheck()
if __name__ == "__main__":
    main()
