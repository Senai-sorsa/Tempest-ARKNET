"""IL-207: why does the tool's 10 m speed cover only ~0.80 at TCS (MAF ~0.92) with NO report? Diagnosis only, nothing changes.
For each target (same hours rule as b1_observe_loso: 2023-25, 08-20 local) the tool's prior 10 m speed is scored against ASOS:
  below = share of obs under the 5 % quantile, above = share over the 95 % quantile (each 0.05 if calibrated),
  bias = mean(obs - prior median), ratio = mean |obs - median| / mean prior half-width(25-75 %) x 0.74 (about 1 if spread fits),
split by local hour block (08-11, 12-15, 16-20) and season (DJF/MAM/JJA/SON). Day-block intervals on coverage.
Pre-set reading (written before the run):
  one tail >= 2x the other and >= 0.08         -> BIAS (median shifted): fix = per-site location correction, not spread
  both tails >= 0.07                            -> TOO NARROW: fix = per-site spread factor (the A2 x1.2 idea, airports only)
  coverage >= 0.85 at both sites                 -> no site problem (the 0.80 was sampling)
  otherwise                                      -> MIXED: report the worst cells only.
    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b3_il207_site_spread.py            # 300 hours per site, about 15-25 min
    KIT_SMOKE=1 PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b3_il207_site_spread.py --n 6
Result: docs/results/logs/kit_b3_il207_site_spread.log
"""
import argparse
from zoneinfo import ZoneInfo

import numpy as np

import kit_common as K
from b1_observe_loso import TARGETS, speed10, test_hours


def reading(below, above, cov):
    if one_sided(below, above):
        return "BIAS (" + ("obs too often BELOW the 5 %: tool too windy" if below > above else "obs too often ABOVE the 95 %: tool too calm") + ")"
    if below >= 0.07 and above >= 0.07:
        return "TOO NARROW"
    if cov >= 0.85:
        return "fine"
    return "MIXED"


def one_sided(below, above):
    hi, lo = max(below, above), min(below, above)
    return hi >= 0.08 and hi >= 2 * lo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    from tempest_weather_v2 import obs as O
    from tempest_weather_v2.launch import Launch
    K.ram_gate(4.0)
    rng = np.random.default_rng(a.seed)
    lines = [f"IL-207 site spread diagnosis: tool prior 10 m speed vs ASOS, 2023-25, 08-20 local, {a.n} hours per site, hour seed {a.seed}, no report"]
    verdicts = {}
    for st, tz in TARGETS.items():
        lat, lon, elev = O.STATIONS[st]
        own = K.asos_speed(st, range(2023, 2026))
        z = ZoneInfo(tz)
        rows, skipped = [], 0
        for h in test_hours(own, tz, a.n, rng):
            assert K.day_ok(h)
            try:
                L = Launch(lat, lon, h.strftime("%Y-%m-%d %H:%M"), tz="UTC", n=200, seed=int(h.timestamp()) % 100000, units="si", elevation=elev, mode="ai")
                w = speed10(L)
            except Exception:   # noqa: BLE001  (an hour the tool cannot serve is skipped, and counted)
                skipped += 1
                continue
            y = own[h][0]
            q5, q25, q50, q75, q95 = np.percentile(w, [5, 25, 50, 75, 95])
            loc = h.astimezone(z)
            rows.append(dict(day=loc.date().isoformat(), hb=("08-11" if loc.hour < 12 else "12-15" if loc.hour < 16 else "16-20"),
                             se=("DJF", "DJF", "MAM", "MAM", "MAM", "JJA", "JJA", "JJA", "SON", "SON", "SON", "DJF")[loc.month - 1],
                             below=float(y < q5), above=float(y > q95), err=y - q50, hw=max((q75 - q25) / 2 * 1.4826, 1e-6),
                             crps=K.crps1(w, y)))
        lines.append(f"{st}: {len(rows)} hours, {skipped} skipped")
        if not rows:
            verdicts[st] = "no data"
            continue

        def cell(name, sub):
            b, ab = np.mean([r["below"] for r in sub]), np.mean([r["above"] for r in sub])
            cv = 1 - np.array([r["below"] + r["above"] for r in sub])
            m, lo, hi = K.block_boot(cv, [r["day"] for r in sub], draws=1000)
            ratio = np.mean([abs(r["err"]) for r in sub]) / np.mean([r["hw"] for r in sub]) / 0.7979
            return (f"  {name:<10} n {len(sub):4d}  coverage {m:.2f} [{lo:.2f}, {hi:.2f}]  below5 {b:.3f}  above95 {ab:.3f}  "
                    f"bias(obs-median) {np.mean([r['err'] for r in sub]):+.2f} m/s  |err|/spread {ratio:.2f}  CRPS {np.mean([r['crps'] for r in sub]):.3f}  -> {reading(b, ab, m)}"), (b, ab, m)

        txt, (b, ab, m) = cell("all", rows)
        lines.append(txt)
        verdicts[st] = reading(b, ab, m)
        for key, vals in (("hb", ("08-11", "12-15", "16-20")), ("se", ("DJF", "MAM", "JJA", "SON"))):
            for v in vals:
                sub = [r for r in rows if r[key] == v]
                if len(sub) >= 10:
                    lines.append(cell(v, sub)[0])
    lines.append("Reading rule (pre-set): one tail >= 2x the other and >= 0.08 -> BIAS; both tails >= 0.07 -> TOO NARROW; coverage >= 0.85 -> fine; else MIXED. "
                 "|err|/spread is about 1 when the spread fits (normal approximation).")
    lines.append("VERDICT: " + "; ".join(f"{s} {v}" for s, v in verdicts.items())
                 + " -> BIAS: test a per-site location correction (fitted 2021-22, scored 2023-25); TOO NARROW: per-site spread factor; fine/MIXED: no site fix, close IL-207.")
    K.report("b3_il207_site_spread", lines)


def _selfcheck():
    assert reading(0.12, 0.03, 0.85).startswith("BIAS") and reading(0.08, 0.08, 0.84) == "TOO NARROW"
    assert reading(0.04, 0.05, 0.91) == "fine" and reading(0.06, 0.06, 0.84) == "MIXED"


_selfcheck()
if __name__ == "__main__":
    main()
