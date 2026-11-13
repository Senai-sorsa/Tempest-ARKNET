"""New_Plan 13 AV26 (variation of AV24, b12_av24.py; MISS 2026-11-13: mix retrained better at every lead in all 4 box x seed runs, 1 and 3 d intervals
below 0 in all 4, 5 and 7 d intervals cross 0 on one test year). Same networks, no training: the AV24 mix networks (models/av24_mix*) scored also on
2021 (il6_modeF.py --test-year 2021: range map fit on mixed 2022, AV1's confirmation-year protocol) against the newest-run networks' 2021 scores from AV1
(models/modeF_n2_base*_t2021_rows.npz, range map on 2022). Per-row scores of 2021 and 2022 pooled per lead; point estimates = pooled row means;
intervals = block bootstrap over 21-day blocks of the valid day spanning both years. Runs: scripts/cpu_av26.sh.

Rule (set before any result; written 2026-11-13 07:30; AV24's rule on the pooled two years):
  PASS: mix minus newest < 0 with the whole interval below 0 at 5 and 7 d, AND mix / newest <= 1.005 at 1 and 3 d, in all 4 box x seed runs.
  KILL: no lead has a lower mix point estimate in any run. Otherwise MISS (record).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b13_av26.py
Result: docs/results/logs/kit_b13_av26.log
"""
import os

import numpy as np

import kit_common as K
from b5_modeF_world import LEADS
from b9_chorus_stage1 import BLOCK, judge

M = os.path.join(K.REPO, "models")
RUNS = [(box, s, [os.path.join(M, f"chorus_new{tag}{x}"), os.path.join(M, f"modeF_n2_base{tag}{x}_t2021")],
         [os.path.join(M, f"av24_mix{tag}{x}"), os.path.join(M, f"av24_mix{tag}{x}_t2021")])
        for box, tag in (("NM/TX", ""), ("Denver", "_den")) for s, x in ((0, ""), (1, "_s1"))]


def pooled(stems):
    r = [np.load(v + "_rows.npz") for v in stems]
    return {k: np.concatenate([x[k] for x in r]) for k in ("lead", "day", "crps")}


def compare(rn, rm, draws=2000):
    """Pooled rows of both arms -> (ratio per lead, interval-below-0 per lead, text)."""
    assert (rn["day"] == rm["day"]).all() and (rn["lead"] == rm["lead"]).all(), "arms scored on different rows"
    ratio, bl, iv = [], [], []
    for L in LEADS:
        k = rn["lead"] == L
        dm, lo, hi = K.block_boot(rm["crps"][k] - rn["crps"][k], list(rn["day"][k] // BLOCK), draws=draws)
        ratio.append(rm["crps"][k].mean() / rn["crps"][k].mean())
        bl.append(hi < 0)
        iv.append(f"{L}d {100 * (ratio[-1] - 1):+.2f} % {dm:+.4f} [{lo:+.4f}, {hi:+.4f}]")
    return np.array(ratio), bl, ", ".join(iv)


def main():
    lines = [f"AV26: AV24 networks, newest vs mix retrained, 2021 + 2022 pooled; row-mean CRPS by lead {LEADS}; {BLOCK}-day blocks over both years"]
    ratio, below, missing = {}, {}, []
    for box, s, new, mix in RUNS:
        if not all(os.path.exists(v + "_rows.npz") for v in new + mix):
            missing.append(f"{box} s{s}")
            continue
        rn, rm = pooled(new), pooled(mix)
        ratio[(box, s)], below[(box, s)], txt = compare(rn, rm)
        lines.append(f"  {box:<6} seed {s} ({len(rn['crps'])} rows, {len(np.unique(rn['day'] // BLOCK))} blocks): mix minus newest {txt}")
    lines.append("Incomplete, missing: " + ", ".join(missing) if missing else "Verdict: " + judge(ratio, below))
    K.report("b13_av26", lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    n = 2000
    rn = {"lead": np.tile([1, 3, 5, 7], n // 4), "day": np.repeat(np.arange(18633, 18633 + n // 4), 4), "crps": rng.uniform(1, 3, n)}
    r, b, _ = compare(rn, {**rn, "crps": rn["crps"] - 0.1}, draws=200)
    assert all(b) and (r < 1).all()
    r, b, _ = compare(rn, {**rn, "crps": rn["crps"] + 0.1}, draws=200)
    assert not any(b) and (r > 1).all()


_selfcheck()
if __name__ == "__main__":
    main()
