"""New_Plan 10.4 N3 step 0: does Mode F still gain from more real years? Runs of scripts/cpu_n3_step0.sh (ENSF2 HRES-only recipe, seed 0, trained on
the last 1-4 years before the fixed 2020 validation year; range map 2021, test 2022): models/modeF_n3_fy{1..4}_eval.csv.
Change from the plan row (recorded in New_Plan section 9): the plan says 1, 2, 3, 5 real years, but only 2016-20 exist before the range-map year and
one year is needed for validation, so the most is 4 fit years (+ 2020 validation = the shipped split). The rule uses 3 -> 4 in place of 3 -> 5,
which is stricter (one year less of gain to see).
Metric: mean CRPS over the 16 variable x band cells by lead 1/3/5/7 d, method 'network + PIT recal + range map + Schaake shuffle'.
Rule (pre-set, plan): 3 -> 4 years gains under 0.5 % (mean of leads) -> N3 closed; else the full N3 run. Seed 1 (fit years 3 and 4,
`cpu_n3_step0.sh 1`) was added because the seed 0 gain (+0.66 %) is the size of seed noise; the gain must hold in both seeds.
Context only: models/modeF_ensbase_eval.csv (an older run of the same recipe, its log shows 4,000 range-map / test rows, so not the same split).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b5_n3_step0.py
Result: docs/results/logs/kit_b5_n3_step0.log
"""
import os

import pandas as pd

import kit_common as K

METHOD = "network + PIT recal + range map + Schaake shuffle"
LEADS = (1, 3, 5, 7)


def by_lead(path):
    t = pd.read_csv(path)
    return t[t.method == METHOD].groupby("lead").crps.mean().reindex(LEADS)


def judge(c3, c4):
    gain = 100 * (1 - (c4 / c3).mean())
    return gain, ("FULL N3 RUN (gain >= 0.5 %)" if gain >= 0.5 else "CLOSED (gain under 0.5 %)")


def main():
    M = os.path.join(K.REPO, "models")
    c = {n: by_lead(os.path.join(M, f"modeF_n3_fy{n}_eval.csv")) for n in (1, 2, 3, 4)}
    ref = by_lead(os.path.join(M, "modeF_ensbase_eval.csv"))
    lines = [f"N3 step 0: Mode F (ENSF2 HRES-only recipe, seed 0) trained on 1-4 real years before the 2020 validation year; mean CRPS by lead {LEADS}, {METHOD}"]
    for n in c:
        lines.append(f"  {n} fit years: " + " / ".join(f"{v:.3f}" for v in c[n]) + (f"  change vs {n - 1}: " + " / ".join(f"{100 * (v - 1):+.1f}" for v in c[n] / c[n - 1]) + " %" if n > 1 else ""))
    lines.append("  context: models/modeF_ensbase_eval.csv (older run, other row draw) " + " / ".join(f"{v:.3f}" for v in ref))
    res = [judge(c[3], c[4])]
    s1 = {n: os.path.join(M, f"modeF_n3_fy{n}_s1_eval.csv") for n in (3, 4)}
    if all(map(os.path.exists, s1.values())):
        d = {n: by_lead(f) for n, f in s1.items()}
        lines.append("  seed 1, 3 fit years: " + " / ".join(f"{v:.3f}" for v in d[3]) + "   4 fit years: " + " / ".join(f"{v:.3f}" for v in d[4]))
        res.append(judge(d[3], d[4]))
    lines.append("Rule (pre-set, 3 -> 4 years in place of 3 -> 5): gain under 0.5 % (mean of leads) -> closed; must hold in both seeds. Gain 3 -> 4: "
                 + ", ".join(f"seed {i} {g:+.2f} %" for i, (g, _) in enumerate(res)))
    lines.append("Verdict: " + ("needs seed 1 (cpu_n3_step0.sh 1)" if len(res) < 2 else "FULL N3 RUN (gain >= 0.5 % in both seeds)" if all(g >= 0.5 for g, _ in res) else "CLOSED (gain under 0.5 % in a seed)"))
    K.report("b5_n3_step0", lines)


def _selfcheck():
    one = pd.Series([1.0] * 4, index=LEADS)
    assert judge(one, one * 0.99)[1].startswith("FULL") and judge(one, one * 0.997)[1].startswith("CLOSED")


_selfcheck()
if __name__ == "__main__":
    main()
