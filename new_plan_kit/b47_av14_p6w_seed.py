"""New_Plan 13 AV14: P6W (C4w near-ground vector-wind loss term only up to 150 m, configs/generator_c4w_p6.toml) confirmation that IL-180 asked for: a second TRAINING
seed plus the night score. Four pairs, each P6W stack vs C4w stack (to 300 m) with the same training seed, data, scoring seed and full stack (calib + shuffle cell 8 + own
shear map + own lapse map):
  training seed 0:   DAY  p6w_d21_s0 vs a24_all21_s0 (= installed l3_c4w);   NIGHT p6w_night vs a24_allnight   (existing, P6W 2026-11-10)
  training seed 100: DAY  av14_p6w_t100_day vs av14_c4w_t100_day;            NIGHT av14_p6w_t100_night vs av14_c4w_t100_night   (not run, see note)
Rule written 2026-11-14 before any AV14 run (New_Plan 13 AV14 row; reading fixed here: "10-300 m wind columns gain" = the mean CRPS skill15 change over the u and v
columns at 10-300 m, per pair; per-column values are reported):
PASS: in all four pairs that mean gain >= 0.001 AND no headline band worse than -0.0009 (compare_headline d_skill15, the paired tolerance).
Otherwise closed for good (MISS). No KILL condition in the row.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b47_av14_p6w_seed.py
Result: docs/results/logs/kit_b47_av14_p6w_seed.log
Note 2026-11-14 11:05: the rule needs all four pairs; the two training-seed-0 pairs (already scored 2026-11-10) fail it (night wind -0.0009, bands below -0.0009 day
and night), so the seed-100 training (40 min GPU) cannot change the verdict and was not run. judge() now returns MISS as soon as one present pair fails.
"""
import os

import pandas as pd

import kit_common as K

NAME = "b47_av14_p6w_seed"
STK = "models/{}_cal2021_smap_shufc8_lmap"
PAIRS = [("train seed 0 DAY", "a24_all21_s0", "p6w_d21_s0"), ("train seed 0 NIGHT", "a24_allnight", "p6w_night"),
         ("train seed 100 DAY", "av14_c4w_t100_day", "av14_p6w_t100_day"), ("train seed 100 NIGHT", "av14_c4w_t100_night", "av14_p6w_t100_night")]
TOL = 0.0009
GAIN = 0.001


def low_wind(score):
    """CRPS skill15 per u/v column at 10-300 m -> Series indexed by column."""
    s = score[score.column.map(lambda c: c.split("_")[0] in ("u", "v") and c.split("_")[-1].isdigit() and 10 <= int(c.split("_")[-1]) <= 300)]
    return pd.Series(1 - s.crps_unknown.values / s.crps_clim.values, index=s.column.values)


def judge(results):
    """results = list of (label, mean low-wind gain, list of worse bands) or None per pair."""
    miss = [lab for lab, r in zip([p[0] for p in PAIRS], results) if r is None]
    bad = [f"{lab}: wind {g:+.4f}" + (f", worse {', '.join(w)}" if w else "") for (lab, g, w) in (r for r in results if r) if g < GAIN or w]
    if bad:   # all four must pass, so one failing pair settles it whatever the missing pairs would show
        return "MISS, closed for good (" + "; ".join(bad) + (f"; not run, cannot change the verdict: {', '.join(miss)}" if miss else "") + ")"
    if miss:
        return "INCOMPLETE (" + ", ".join(miss) + " missing)"
    if not bad:
        return "PASS (10-300 m wind gain >= 0.001 and no band worse than -0.0009 in all four pairs)"
    return "MISS, closed for good (" + "; ".join(bad) + ")"


def pair(label, base, new, lines):
    from compare_headline import compare
    b, n = STK.format(base), STK.format(new)
    if not all(os.path.exists(f) for f in (b + "_headline.csv", n + "_headline.csv", b + ".score.csv", n + ".score.csv")):
        lines.append(f"{label}: files missing")
        return None
    t, m = compare(pd.read_csv(b + "_headline.csv"), pd.read_csv(n + "_headline.csv"))
    worse = [f"{r.var} {r.band} {r.d_skill15:+.4f}" for r in t.itertuples() if r.d_skill15 < -TOL]
    d = low_wind(pd.read_csv(n + ".score.csv")) - low_wind(pd.read_csv(b + ".score.csv"))
    g = float(d.mean())
    lines.append(f"{label} ({new} vs {base}): mean skill15 {m['mean_skill15_base']:+.4f} -> {m['mean_skill15_new']:+.4f}; 10-300 m wind mean gain {g:+.4f} "
                 f"(min {d.min():+.4f}, max {d.max():+.4f}); bands worse than -{TOL}: {', '.join(worse) or 'none'}")
    lines.append("  per column: " + "; ".join(f"{c} {v:+.4f}" for c, v in d.items()))
    return (label, g, worse)


def main():
    lines = []
    res = [pair(*p, lines) for p in PAIRS]
    lines.append("AV14 rule (pre-set): PASS = in all four pairs 10-300 m wind mean gain >= 0.001 and no band worse than -0.0009; else closed for good.")
    lines.append("AV14 verdict: " + judge(res))
    K.report(NAME, lines)


def _selfcheck():
    ok = ("x", 0.0012, [])
    assert judge([ok] * 4).startswith("PASS")
    assert judge([ok] * 3 + [("x", 0.0005, [])]).startswith("MISS")
    assert judge([ok] * 3 + [("x", 0.002, ["T 0-1km -0.0012"])]).startswith("MISS")
    assert judge([ok] * 3 + [None]).startswith("INCOMPLETE")
    assert judge([ok, ("x", -0.001, []), None, None]).startswith("MISS")
    sc = pd.DataFrame({"column": ["u_10", "v_300", "u_500", "t_10"], "crps_unknown": [0.5, 0.8, 0.5, 0.5], "crps_clim": [1.0, 1.0, 1.0, 1.0]})
    w = low_wind(sc)
    assert list(w.index) == ["u_10", "v_300"] and abs(w["u_10"] - 0.5) < 1e-9


_selfcheck()
if __name__ == "__main__":
    main()
