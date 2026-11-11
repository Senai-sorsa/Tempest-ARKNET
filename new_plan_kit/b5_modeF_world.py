"""New_Plan 10.4 N2 full run: one Mode F network fit on HRES / ERA5 pairs at the 7,483 world points (no lat / lon; rows from
scripts/il6_build_world.py), scored on each box's own 2022 test rows. Runs: scripts/cpu_n2_full.sh (seeds 0 and 1):
    own model     models/modeF_n2_base{,_den}{,_s1}     (ENSF2 HRES-only recipe, as shipped)
    world as is   models/modeF_n2w{,_den}_s{0,1}
    fine-tuned    models/modeF_n2ft{,_den}_s{0,1}       (world network + 300 steps on the box rows)
Metric: mean CRPS over the 16 variable x band cells by lead 1/3/5/7 d, 'network + PIT recal + range map + Schaake shuffle' (<stem>_eval.csv);
intervals: paired day-block bootstrap (valid days) on the per-row scores (<stem>_rows.npz, same test rows in every arm of a box).
PASS (pre-set): world as is within 1 % of the own model at every lead, both boxes (both seeds); and fine-tuned better than the own model with an
      interval excluding 0 at >= 3 of 4 leads (both boxes, both seeds).
KILL: world as is worse by more than 3 % (mean of leads) at both boxes (both seeds). Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b5_modeF_world.py
Result: docs/results/logs/kit_b5_modeF_world.log
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


def judge(asis, ft_wins):
    """asis[(box, seed)] = per-lead ratio world / own; ft_wins[(box, seed)] = leads where fine-tuned beats own with interval < 0 -> verdict."""
    ok_a = all((r <= 1.01).all() for r in asis.values())
    ok_f = all(n >= 3 for n in ft_wins.values())
    boxes = {k[0] for k in asis}
    kill = all(all(asis[(b, s)].mean() > 1.03 for s in (0, 1)) for b in boxes)
    return "PASS" if ok_a and ok_f else "KILL" if kill else "MISS (record, no adoption)"


def main():
    M = os.path.join(K.REPO, "models")
    lines = [f"N2 world Mode F (7,483 points, no lat / lon) vs each box's own model; mean CRPS by lead {LEADS}, {METHOD}"]
    asis, wins, missing = {}, {}, []
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        for s in (0, 1):
            st = {"own": f"modeF_n2_base{tag}{'' if s == 0 else '_s1'}", "world": f"modeF_n2w{tag}_s{s}", "fine-tuned": f"modeF_n2ft{tag}_s{s}"}
            st = {k: os.path.join(M, v) for k, v in st.items()}
            if not all(os.path.exists(v + "_eval.csv") and os.path.exists(v + "_rows.npz") for v in st.values()):
                missing.append(f"{box} s{s}")
                continue
            sc = {k: by_lead(v) for k, v in st.items()}
            rw = {k: np.load(v + "_rows.npz") for k, v in st.items()}
            assert all((rw[k]["day"] == rw["own"]["day"]).all() and (rw[k]["lead"] == rw["own"]["lead"]).all() for k in rw), f"{box} s{s}: arms scored on different rows"
            asis[(box, s)] = sc["world"] / sc["own"]
            lines.append(f"  {box:<6} seed {s}: own " + " / ".join(f"{v:.3f}" for v in sc["own"]))
            for arm in ("world", "fine-tuned"):
                row = f"    {arm:<10} " + " / ".join(f"{v:.3f}" for v in sc[arm]) + "  change " + " / ".join(f"{100 * (v - 1):+.1f}" for v in sc[arm] / sc["own"]) + " %"
                if arm == "fine-tuned":
                    n, iv = 0, []
                    for L in LEADS:
                        k = rw["own"]["lead"] == L
                        dm, lo, hi = K.block_boot(rw[arm]["crps"][k] - rw["own"]["crps"][k], list(rw["own"]["day"][k]), draws=1000)
                        n += hi < 0
                        iv.append(f"{L}d {dm:+.3f} [{lo:+.3f}, {hi:+.3f}]")
                    wins[(box, s)] = n
                    row += f"; minus own: " + ", ".join(iv) + f"; better at {n} of 4 leads"
                lines.append(row)
    if missing:
        lines.append("Incomplete, missing: " + ", ".join(missing))
        K.report("b5_modeF_world", lines)
        return
    lines.append("Rule (pre-set): PASS = world as is within +1 % of own at every lead (both boxes, seeds) and fine-tuned better with interval < 0 at >= 3 of 4 leads; "
                 "KILL = world as is > +3 % (mean of leads) at both boxes in both seeds.")
    lines.append("Verdict: " + judge(asis, wins))
    K.report("b5_modeF_world", lines)


def _selfcheck():
    one = pd.Series([1.0] * 4, index=LEADS)
    keys = [(b, s) for b in ("A", "B") for s in (0, 1)]
    assert judge({k: one * 1.005 for k in keys}, {k: 3 for k in keys}) == "PASS"
    assert judge({k: one * 1.005 for k in keys}, {k: 2 for k in keys}).startswith("MISS")
    assert judge({k: one * 1.04 for k in keys}, {k: 4 for k in keys}) == "KILL"
    assert judge({k: one * (1.04 if k[0] == "A" else 1.02) for k in keys}, {k: 4 for k in keys}).startswith("MISS")


_selfcheck()
if __name__ == "__main__":
    main()
