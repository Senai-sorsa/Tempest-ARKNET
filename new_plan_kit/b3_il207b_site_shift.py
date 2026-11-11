"""IL-207b: IL-207 found the tool too calm at TCS with no report (obs above the 95 % in 0.15 of hours, bias +1.44 m/s, worst MAM/JJA afternoons;
MAF fine). Test the fix the pre-set reading names: a per-site multiplicative factor on the 10 m speed samples, k = mean(obs) / mean(prior mean),
one per cell (hour block 08-11 / 12-15 / 16-20 local x warm MAM-JJA / cool SON-DJF = 6 cells per site), fitted on 2021-22, scored on 2023-25.
In memory only; nothing in the tool changes. Applied to both sites (MAF is the guard: a fix that only helps where it is needed must not hurt elsewhere).
PASS (pre-set): at TCS CRPS minus shipped < 0 with the upper end of its day-block interval < 0, AND |coverage - 0.90| smaller than shipped;
      at MAF CRPS minus shipped lower end <= +0.02 and coverage still 0.85-0.95.
CAVEAT for any adoption: TCS is the proxy truth for Spaceport America (30 km away); a TCS-only offset may be the station's exposure, not the
tool's error at the pad. PASS -> report and ASK before any core change (a site table in launch.py, default off).
    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b3_il207b_site_shift.py              # 300 fit + 300 test hours per site, about 20-30 min
    KIT_SMOKE=1 PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b3_il207b_site_shift.py --n 8
Result: docs/results/logs/kit_b3_il207b_site_shift.log
"""
import argparse
from zoneinfo import ZoneInfo

import numpy as np

import kit_common as K
from b1_observe_loso import TARGETS, score, speed10, test_hours


def cell_of(h, z):
    loc = h.astimezone(z)
    return ("08-11" if loc.hour < 12 else "12-15" if loc.hour < 16 else "16-20") + ("/warm" if 3 <= loc.month <= 8 else "/cool")


def fit_factors(pairs):
    """pairs: [(cell, prior mean, obs)] -> {cell: k}; a cell with fewer than 10 hours keeps k = 1 (shortcut: no pooling, upgrade if cells are thin)."""
    out = {}
    for c in {p[0] for p in pairs}:
        sub = np.array([(m, y) for cc, m, y in pairs if cc == c])
        out[c] = float(sub[:, 1].mean() / max(sub[:, 0].mean(), 1e-6)) if len(sub) >= 10 else 1.0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    from tempest_weather_v2 import obs as O
    from tempest_weather_v2.launch import Launch
    K.ram_gate(4.0)
    rng = np.random.default_rng(a.seed)
    lines = [f"IL-207b per-site speed factor (6 cells: hour block x warm/cool), fit 2021-22, test 2023-25, 08-20 local, {a.n} hours each, hour seed {a.seed}, no report"]
    ok_all = True
    for st, tz in TARGETS.items():
        lat, lon, elev = O.STATIONS[st]
        z = ZoneInfo(tz)
        own = K.asos_speed(st, range(2021, 2026))

        def pool(h):
            return speed10(Launch(lat, lon, h.strftime("%Y-%m-%d %H:%M"), tz="UTC", n=200, seed=int(h.timestamp()) % 100000, units="si", elevation=elev, mode="ai"))

        fit, skipped = [], 0
        for h in test_hours(own, tz, a.n, rng, years=(2021, 2022)):
            try:
                fit.append((cell_of(h, z), float(pool(h).mean()), own[h][0]))
            except Exception:   # noqa: BLE001  (an hour the tool cannot serve is skipped, and counted)
                skipped += 1
        k = fit_factors(fit)
        lines.append(f"{st}: fit {len(fit)} hours ({skipped} skipped); factors " + ", ".join(f"{c} {v:.2f}" for c, v in sorted(k.items())))
        base, new, days, skipped = [], [], [], 0
        for h in test_hours(own, tz, a.n, rng):
            assert K.day_ok(h)
            try:
                w = pool(h)
            except Exception:   # noqa: BLE001
                skipped += 1
                continue
            y = own[h][0]
            base.append(score(w, y))
            new.append(score(w * k.get(cell_of(h, z), 1.0), y))
            days.append(h.date().isoformat())
        if not base:
            lines.append(f"{st}: no test hours"); ok_all = False
            continue
        b, n_ = np.array(base), np.array(new)
        dm, dlo, dhi = K.block_boot(n_[:, 0] - b[:, 0], days, draws=1000)
        cb, cn = b[:, 1].mean(), n_[:, 1].mean()
        if st == "TCS":
            ok = dhi < 0 and abs(cn - 0.90) < abs(cb - 0.90)
        else:
            ok = dlo <= 0.02 and 0.85 <= cn <= 0.95
        ok_all &= bool(ok)
        lines.append(f"  test {len(b)} hours ({skipped} skipped): shipped CRPS {b[:, 0].mean():.3f} cov {cb:.2f} | factor CRPS {n_[:, 0].mean():.3f} cov {cn:.2f} | "
                     f"minus shipped {dm:+.3f} [{dlo:+.3f}, {dhi:+.3f}]  {'ok' if ok else 'fail'}")
    lines.append("Rule: TCS CRPS better (interval upper < 0) and coverage nearer 0.90; MAF CRPS lower end <= +0.02 and coverage 0.85-0.95.")
    lines.append("VERDICT: " + ("PASS -> a per-site factor fixes the TCS shortfall; ASK the user before any core change (TCS is a proxy for the pad, 30 km away)."
                                if ok_all else "FAIL -> a site factor does not fix it; record, keep the tool as is; TCS spread stays a known limitation."))
    K.report("b3_il207b_site_shift", lines)


def _selfcheck():
    k = fit_factors([("a", 2.0, 3.0)] * 10 + [("b", 2.0, 9.0)] * 3)
    assert abs(k["a"] - 1.5) < 1e-9 and k["b"] == 1.0


_selfcheck()
if __name__ == "__main__":
    main()
