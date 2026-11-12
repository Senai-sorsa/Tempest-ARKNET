"""New_Plan 10.4 N2 modification C: the world Mode F network with 12 climate descriptors per grid point instead of lat / lon
(il6_modeF.py --place-clim; runs scripts/cpu_n2c_place.sh, seeds 0 and 1), scored on each box's own 2022 test rows, against the N2 runs:
    own model      models/modeF_n2_base{,_den}{,_s1}
    world / ft     models/modeF_n2w{,_den}_s{0,1} / modeF_n2ft{,_den}_s{0,1}      (no place input)
    world-C / ft-C models/modeF_n2cw{,_den}_s{0,1} / modeF_n2cft{,_den}_s{0,1}    (climate descriptors)
Metric and intervals as new_plan_kit/b5_modeF_world.py (mean CRPS by lead; paired day-block bootstrap on the per-row scores).
Rule (written before any run):
PASS: world-C within 1 % of the own model at every lead (the half N2 missed) and ft-C better than the own model with an interval excluding 0
      at >= 3 of 4 leads, in both boxes and both seeds.
KILL: the descriptors do not help: world-C not better than world (mean of leads) in 2 or more of the 4 box x seed cases, and the same for
      ft-C against ft. Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b5_modeF_place.py
Result: docs/results/logs/kit_b5_modeF_place.log
"""
import os

import numpy as np

import kit_common as K
from b5_modeF_world import LEADS, METHOD, by_lead


def judge(asis, ft_wins, w_gain, f_gain):
    """Per (box, seed): asis = per-lead world-C / own; ft_wins = leads where ft-C beats own with interval < 0;
    w_gain / f_gain = mean over leads of world-C / world - 1 and ft-C / ft - 1 (negative = the descriptors help)."""
    if all((np.asarray(r) <= 1.01).all() for r in asis.values()) and all(n >= 3 for n in ft_wins.values()):
        return "PASS"
    if sum(g >= 0 for g in w_gain.values()) >= 2 and sum(g >= 0 for g in f_gain.values()) >= 2:
        return "KILL"
    return "MISS (record, no adoption)"


def main():
    M = os.path.join(K.REPO, "models")
    lines = [f"N2 modification C (climate descriptors instead of lat / lon); mean CRPS by lead {LEADS}, {METHOD}"]
    asis, wins, wg, fg, missing = {}, {}, {}, {}, []
    fmt = lambda v: " / ".join(f"{x:.3f}" for x in v)
    pct = lambda r: " / ".join(f"{100 * (x - 1):+.1f}" for x in r) + " %"
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        for s in (0, 1):
            st = {"own": f"modeF_n2_base{tag}{'' if s == 0 else '_s1'}", "world": f"modeF_n2w{tag}_s{s}", "ft": f"modeF_n2ft{tag}_s{s}",
                  "world-C": f"modeF_n2cw{tag}_s{s}", "ft-C": f"modeF_n2cft{tag}_s{s}"}
            st = {k: os.path.join(M, v) for k, v in st.items()}
            if not all(os.path.exists(v + e) for v in st.values() for e in ("_eval.csv", "_rows.npz")):
                missing.append(f"{box} s{s}")
                continue
            sc, rw = {k: by_lead(v) for k, v in st.items()}, {k: np.load(v + "_rows.npz") for k, v in st.items()}
            assert all((rw[k]["day"] == rw["own"]["day"]).all() and (rw[k]["lead"] == rw["own"]["lead"]).all() for k in rw), f"{box} s{s}: arms scored on different rows"
            n, iv = 0, []
            for L in LEADS:
                k = rw["own"]["lead"] == L
                dm, lo, hi = K.block_boot(rw["ft-C"]["crps"][k] - rw["own"]["crps"][k], list(rw["own"]["day"][k]), draws=1000)
                n += hi < 0
                iv.append(f"{L}d {dm:+.3f} [{lo:+.3f}, {hi:+.3f}]")
            key = (box, s)
            asis[key], wins[key] = (sc["world-C"] / sc["own"]).values, n
            wg[key], fg[key] = float((sc["world-C"] / sc["world"]).mean() - 1), float((sc["ft-C"] / sc["ft"]).mean() - 1)
            lines += [f"  {box:<6} seed {s}: own " + fmt(sc["own"]),
                      f"    world-C {fmt(sc['world-C'])}  vs own {pct(sc['world-C'] / sc['own'])}; vs world {pct(sc['world-C'] / sc['world'])}",
                      f"    ft-C    {fmt(sc['ft-C'])}  vs own {pct(sc['ft-C'] / sc['own'])}; vs ft {pct(sc['ft-C'] / sc['ft'])}; minus own: " + ", ".join(iv) + f"; better at {n} of 4 leads"]
    if missing:
        lines.append("Incomplete, missing: " + ", ".join(missing))
    else:
        lines.append("Rule (pre-set): PASS = world-C within 1 % of own at every lead and ft-C better than own (interval < 0) at >= 3 of 4 leads, everywhere; "
                     "KILL = descriptors help neither arm (mean of leads) in 2 or more of 4 cases.")
        lines.append("Verdict: " + judge(asis, wins, wg, fg))
    K.report("b5_modeF_place", lines)


def _selfcheck():
    keys = [(b, s) for b in ("A", "B") for s in (0, 1)]
    good, bad = {k: [1.0, 1.005, 0.99, 1.01] for k in keys}, {k: [1.02] * 4 for k in keys}
    w4, neg, pos = {k: 4 for k in keys}, {k: -0.01 for k in keys}, {k: 0.01 for k in keys}
    assert judge(good, w4, neg, neg) == "PASS"
    assert judge(bad, w4, neg, neg).startswith("MISS")
    assert judge(good, {k: 2 for k in keys}, neg, pos).startswith("MISS")
    assert judge(bad, w4, pos, pos) == "KILL"


_selfcheck()
if __name__ == "__main__":
    main()
