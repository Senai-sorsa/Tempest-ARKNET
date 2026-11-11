"""New_Plan 10.4 N5 full run: one Mode F network from day 1 to climate. Runs: scripts/cpu_n5_full.sh (seeds 0 and 1, boxes NM/TX and Denver, rows
data/modeF_v2{,_denver}, the only stores with leads 7.5-10 d). Both arms score the same test rows, binned 1 / 3 / 5 / 7 and 9 (= beyond 7.5 d):
    binned   models/modeF_n5_bin{,_den}_s{0,1}   fit on leads <= 7.5 d only, as shipped (at bin 9 used beyond its range)
    all      models/modeF_n5_all{,_den}_s{0,1}   fit on all leads (lead is a continuous input) + 10 % climate-anchor rows at a 15 d lead
Metric: mean CRPS over the 16 variable x band cells, 'network + PIT recal + range map + Schaake shuffle' (<stem>_eval.csv); intervals: paired day-block
bootstrap on the per-row scores (<stem>_rows.npz). Climate = the script's 'climatology (2016-20 pool)' on the same rows (crps_clim in the rows file).
Router stand-in: at 7.5-10 d the shipped router uses the live ensemble (mode F2), which these rows do not carry; the binned network extended to the lead stands in.
PASS (pre-set, New_Plan 10.4): leads 1-7 within 0.5 % of the binned model at every lead; beyond 7.5 d better than the binned model and than climate
      (interval < 0 for both); never worse than climate at lead day 8, 9 or 10 (mean); all boxes and seeds.
KILL: worse by more than 1 % at leads 1-3 (mean of leads 1 and 3) at both boxes in both seeds. Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b5_modeF_alllead.py
Result: docs/results/logs/kit_b5_modeF_alllead.log
"""
import os

import numpy as np
import pandas as pd

import kit_common as K

METHOD = "network + PIT recal + range map + Schaake shuffle"
NEAR, BEYOND = (1, 3, 5, 7), 9


def by_lead(stem):
    t = pd.read_csv(stem + "_eval.csv")
    return t[t.method == METHOD].groupby("lead").crps.mean().reindex(NEAR + (BEYOND,))


def judge(near, beyond_ok, days_ok):
    """near[(box, seed)] = ratio all / binned at leads 1-7; beyond_ok = both intervals < 0; days_ok = not worse than climate at day 8 / 9 / 10 -> verdict."""
    ok = all((r <= 1.005).all() for r in near.values()) and all(beyond_ok.values()) and all(days_ok.values())
    boxes = {k[0] for k in near}
    kill = all(all(near[(b, s)].loc[[1, 3]].mean() > 1.01 for s in (0, 1)) for b in boxes)
    return "PASS" if ok else "KILL" if kill else "MISS (record, no adoption)"


def main():
    M = os.path.join(K.REPO, "models")
    lines = [f"N5 one Mode F network from day 1 to climate vs the binned model; mean CRPS by lead {NEAR} and {BEYOND} (= 7.5-10 d), {METHOD}"]
    near, bok, dok, missing = {}, {}, {}, []
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        for s in (0, 1):
            st = {k: os.path.join(M, f"modeF_n5_{k}{tag}_s{s}") for k in ("bin", "all")}
            if not all(os.path.exists(v + "_eval.csv") and os.path.exists(v + "_rows.npz") for v in st.values()):
                missing.append(f"{box} s{s}")
                continue
            sc = {k: by_lead(v) for k, v in st.items()}
            rw = {k: np.load(v + "_rows.npz") for k, v in st.items()}
            assert all((rw["all"][f] == rw["bin"][f]).all() for f in ("day", "lead", "lead_days")), f"{box} s{s}: arms scored on different rows"
            r = sc["all"] / sc["bin"]
            near[(box, s)] = r.loc[list(NEAR)]
            lines.append(f"  {box:<6} seed {s}: binned " + " / ".join(f"{v:.3f}" for v in sc["bin"]) + "; all-lead " + " / ".join(f"{v:.3f}" for v in sc["all"])
                         + "; change " + " / ".join(f"{100 * (v - 1):+.1f}" for v in r) + " %")
            k = rw["all"]["lead"] == BEYOND
            day = list(rw["all"]["day"][k])
            iv = {}
            for ref, x in (("binned", rw["bin"]["crps"][k]), ("climate", rw["all"]["crps_clim"][k])):
                iv[ref] = K.block_boot(rw["all"]["crps"][k] - x, day, draws=1000)
            bok[(box, s)] = all(hi < 0 for _, _, hi in iv.values())
            ld = np.ceil(rw["all"]["lead_days"][k] - 1e-6).astype(int)                 # 7.75-8.0 -> day 8, ..., 9.25-10 -> day 10
            per = {d: (rw["all"]["crps"][k][ld == d].mean(), rw["all"]["crps_clim"][k][ld == d].mean()) for d in (8, 9, 10) if (ld == d).any()}
            dok[(box, s)] = all(a_ <= c_ for a_, c_ in per.values())
            lines.append("    beyond 7.5 d, all-lead minus: " + ", ".join(f"{ref} {m:+.3f} [{lo:+.3f}, {hi:+.3f}]" for ref, (m, lo, hi) in iv.items())
                         + "; all-lead / climate by lead day: " + ", ".join(f"{d} d {a_:.3f} / {c_:.3f}" for d, (a_, c_) in per.items()))
    if missing:
        lines.append("Incomplete, missing: " + ", ".join(missing))
        K.report("b5_modeF_alllead", lines)
        return
    lines.append("Rule (pre-set): PASS = leads 1-7 within +0.5 % of binned at every lead, beyond 7.5 d better than binned and climate with interval < 0, "
                 "never worse than climate at day 8 / 9 / 10 (all boxes, seeds); KILL = leads 1 and 3 mean > +1 % at both boxes in both seeds.")
    lines.append("Verdict: " + judge(near, bok, dok))
    K.report("b5_modeF_alllead", lines)


def _selfcheck():
    one = pd.Series([1.0] * 4, index=NEAR)
    keys = [(b, s) for b in ("A", "B") for s in (0, 1)]
    t, f = {k: True for k in keys}, {k: False for k in keys}
    assert judge({k: one * 1.004 for k in keys}, t, t) == "PASS"
    assert judge({k: one * 1.004 for k in keys}, f, t).startswith("MISS")
    assert judge({k: one * 1.004 for k in keys}, t, {**t, ("A", 0): False}).startswith("MISS")
    assert judge({k: one * 1.02 for k in keys}, t, t) == "KILL"
    assert judge({k: one * (1.02 if k[0] == "A" else 1.0) for k in keys}, t, t).startswith("MISS")


_selfcheck()
if __name__ == "__main__":
    main()
