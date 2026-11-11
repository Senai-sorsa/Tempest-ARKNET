"""New_Plan 10.4 N2 step 0, box checks: would a world forecast-error model lose too much from the world store's coarser input?
Runs of scripts/cpu_n2_step0.sh (ENSF2 HRES-only recipe, seed 0, per box): base, --levels13 (forecast profile only at the heights nearest the 13
pressure levels, standard atmosphere minus median ground height), --no-place (lat / lon 0). models/modeF_n2_{base,l13,nop}{,_den}_eval.csv.
Metric: mean CRPS over the 16 variable x band cells by lead 1/3/5/7 d, method 'network + PIT recal + range map + Schaake shuffle'.
Rule (pre-set, plan): 13-level input loses under 1 % and no lat / lon loses under 0.5 % (mean of leads), both boxes; else N2 stops.
(The pair count part, >= 300,000, passed: 63.6 M, New_Plan section 9.)
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b5_n2_step0.py
Result: docs/results/logs/kit_b5_n2_step0.log
"""
import os

import pandas as pd

import kit_common as K

METHOD = "network + PIT recal + range map + Schaake shuffle"
LEADS = (1, 3, 5, 7)
LIMIT = {"l13": 1.0, "nop": 0.5}


def by_lead(path):
    t = pd.read_csv(path)
    return t[t.method == METHOD].groupby("lead").crps.mean().reindex(LEADS)


def loss(arm, base):
    return 100 * ((arm / base).mean() - 1)


def main():
    M = os.path.join(K.REPO, "models")
    lines = [f"N2 step 0 box checks: Mode F (ENSF2 HRES-only recipe, seed 0) with the world store's input limits; mean CRPS by lead {LEADS}, {METHOD}"]
    ok = True
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        c = {k: by_lead(os.path.join(M, f"modeF_n2_{k}{tag}_eval.csv")) for k in ("base", "l13", "nop")}
        lines.append(f"  {box:<6} base       " + " / ".join(f"{v:.3f}" for v in c["base"]))
        for k, name in (("l13", "13 levels "), ("nop", "no lat/lon")):
            l = loss(c[k], c["base"])
            good = l < LIMIT[k]
            ok &= bool(good)
            lines.append(f"  {box:<6} {name} " + " / ".join(f"{v:.3f}" for v in c[k]) + f"  loss {l:+.2f} % (limit {LIMIT[k]} %)  {'ok' if good else 'fail'}")
    lines.append("Rule (pre-set): 13-level input loses under 1 %, no lat / lon under 0.5 % (mean of leads), both boxes. One seed; seed noise is about 1 %.")
    lines.append("Verdict: " + ("PASS -> N2 full run (world pairs)" if ok else "FAIL -> N2 stops"))
    K.report("b5_n2_step0", lines)


def _selfcheck():
    one = pd.Series([1.0] * 4, index=LEADS)
    assert abs(loss(one * 1.01, one) - 1.0) < 1e-9 and loss(one * 0.99, one) < 0


_selfcheck()
if __name__ == "__main__":
    main()
