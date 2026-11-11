"""N2 modification B (user 2026-11-11 17:30): world start when the box has only 1 fit year. Runs: scripts/cpu_n2b_scarce.sh (seeds 0, 1; boxes NM/TX, Denver):
    own1      models/modeF_n2b_own1{,_den}_s{0,1}       box's own model, --fit-years 1
    own1p300  models/modeF_n2b_own1p300{,_den}_s{0,1}   own1 + 300 more steps (extra-training control)
    ft1       models/modeF_n2b_ft1{,_den}_s{0,1}        world network (N2, no lat / lon) + 300 steps on the 1-year box rows
Metric as N2: mean CRPS over 16 cells by lead 1/3/5/7 d, 'network + PIT recal + range map + Schaake shuffle'; paired day-block bootstrap on per-row scores.
PASS (set 2026-11-11 18:00, before any result): ft1 better than own1 AND than own1p300 with interval < 0 at >= 3 of 4 leads, both boxes, both seeds.
KILL: ft1 not better than own1p300 on the mean of leads at both boxes in both seeds. Otherwise MISS. Adoption stays with the user.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b5_modeF_scarce.py
Result: docs/results/logs/kit_b5_modeF_scarce.log
"""
import os

import numpy as np
import pandas as pd

import kit_common as K

METHOD = "network + PIT recal + range map + Schaake shuffle"
LEADS = (1, 3, 5, 7)


def by_lead(stem):
    t = pd.read_csv(stem + "_eval.csv")
    return t[t.method == METHOD].groupby("lead").crps.mean().reindex(LEADS)


def judge(wins_own, wins_ctl, mean_vs_ctl):
    """wins_*[(box, seed)] = leads where ft1 beats that arm with interval < 0; mean_vs_ctl = ft1 / own1p300 mean of leads -> verdict."""
    if all(n >= 3 for n in wins_own.values()) and all(n >= 3 for n in wins_ctl.values()):
        return "PASS"
    return "KILL" if all(r >= 1.0 for r in mean_vs_ctl.values()) else "MISS (record, no adoption)"


def main():
    M = os.path.join(K.REPO, "models")
    lines = [f"N2-B world start with 1 box fit year; mean CRPS by lead {LEADS}, {METHOD}"]
    wo, wc, mc, missing = {}, {}, {}, []
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        for s in (0, 1):
            st = {k: os.path.join(M, f"modeF_n2b_{k}{tag}_s{s}") for k in ("own1", "own1p300", "ft1")}
            if not all(os.path.exists(v + "_eval.csv") and os.path.exists(v + "_rows.npz") for v in st.values()):
                missing.append(f"{box} s{s}")
                continue
            sc = {k: by_lead(v) for k, v in st.items()}
            rw = {k: np.load(v + "_rows.npz") for k, v in st.items()}
            assert all((rw[k]["day"] == rw["own1"]["day"]).all() and (rw[k]["lead"] == rw["own1"]["lead"]).all() for k in rw), f"{box} s{s}: arms on different rows"
            lines.append(f"  {box:<6} seed {s}: own1 " + " / ".join(f"{v:.3f}" for v in sc["own1"]) + "; own1p300 " + " / ".join(f"{v:.3f}" for v in sc["own1p300"])
                         + "; ft1 " + " / ".join(f"{v:.3f}" for v in sc["ft1"]))
            for ref, store in (("own1", wo), ("own1p300", wc)):
                n, iv = 0, []
                for L in LEADS:
                    k = rw[ref]["lead"] == L
                    dm, lo, hi = K.block_boot(rw["ft1"]["crps"][k] - rw[ref]["crps"][k], list(rw[ref]["day"][k]), draws=1000)
                    n += hi < 0
                    iv.append(f"{L}d {dm:+.3f} [{lo:+.3f}, {hi:+.3f}]")
                store[(box, s)] = n
                lines.append(f"    ft1 vs {ref:<8} change " + " / ".join(f"{100 * (v - 1):+.1f}" for v in sc["ft1"] / sc[ref]) + " %; minus: " + ", ".join(iv)
                             + f"; better at {n} of 4 leads")
            mc[(box, s)] = sc["ft1"].mean() / sc["own1p300"].mean()
    if missing:
        lines.append("Incomplete, missing: " + ", ".join(missing))
        K.report("b5_modeF_scarce", lines)
        return
    lines.append("Rule (pre-set): PASS = ft1 better than own1 and own1p300 with interval < 0 at >= 3 of 4 leads (both boxes, seeds); "
                 "KILL = ft1 not better than own1p300 on the mean of leads at both boxes in both seeds.")
    lines.append("Verdict: " + judge(wo, wc, mc))
    K.report("b5_modeF_scarce", lines)


def _selfcheck():
    keys = [(b, s) for b in ("A", "B") for s in (0, 1)]
    assert judge({k: 3 for k in keys}, {k: 4 for k in keys}, {k: 0.98 for k in keys}) == "PASS"
    assert judge({k: 4 for k in keys}, {k: 2 for k in keys}, {k: 0.99 for k in keys}).startswith("MISS")
    assert judge({k: 4 for k in keys}, {k: 0 for k in keys}, {k: 1.01 for k in keys}) == "KILL"


_selfcheck()
if __name__ == "__main__":
    main()
