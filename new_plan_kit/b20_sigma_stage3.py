"""New_Plan 14.3 SIGMA stage 3 (NEST): SIGMA stage 2's network at width 512 with nested widths per lead day (--sigma --nest, GPU).
Runs: scripts/gpu_sigma3.sh (seeds 0 and 1, boxes NM/TX and Denver, rows data/modeF_v2{,_denver}). All arms score the same test rows:
    binned    models/modeF_n5_bin{,_den}_s{0,1}    N5's small binned model (the bar)
    stage 2   models/modeF_n5_sig{,_den}_s{0,1}    SIGMA stage 2, width 128 (information)
    NEST      models/modeF_n5_nest{,_den}_s{0,1}   this trial
Metric: mean CRPS over the 16 variable x band cells by lead 1/3/5/7 d, 'network + PIT recal + range map + Schaake shuffle' (<stem>_eval.csv);
intervals: paired day-block bootstrap (valid days, 1000 draws) on the per-row scores (<stem>_rows.npz).
Rule written 2026-11-13 before any stage 3 result (New_Plan 14.3: N6's rule unchanged):
PASS: NEST at least 1 % better than binned at every lead 1/3/5/7 with an interval excluding 0, both boxes, both seeds, and mean cov99 within 0.003
      of binned at every lead.
KILL: lead 7 d worse than binned (mean over both seeds) in both boxes. Otherwise MISS: record, no adoption.
Reported as information only: NEST vs stage 2 by lead, and beyond 7.5 d (bin 9) vs binned.
Stated deviation from N6: depth 2 / coarse 4 / 2 members (stage 2's recipe) instead of N6's depth 4 / all heights / 4 members, so the only change
against stage 2 is width 512 + NEST.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b20_sigma_stage3.py
Result: docs/results/logs/kit_b20_sigma_stage3.log
"""
import os

import numpy as np

import kit_common as K
from b5_modeF_alllead import BEYOND, NEAR, by_lead
from b5_modeF_big import cov99


def judge(ratio, sig, dcov):
    """ratio[(box, seed)] = NEST / binned at leads 1/3/5/7; sig = intervals < 0; dcov = |cov99 difference| -> verdict."""
    ok = all((np.asarray(ratio[k]) <= 0.99).all() and all(sig[k]) and (np.asarray(dcov[k]) <= 0.003).all() for k in ratio)
    boxes = {k[0] for k in ratio}
    kill = all(np.mean([ratio[(b, s)][-1] for s in (0, 1)]) > 1 for b in boxes)
    return "PASS" if ok else "KILL" if kill else "MISS (record, no adoption)"


def main(arm="nest", ref2="sig", name="b20_sigma_stage3", title="SIGMA stage 3 (NEST, width 512)"):
    M = os.path.join(K.REPO, "models")
    lines = [f"{title} vs N5 binned; mean CRPS by lead {NEAR} (+ {BEYOND} = beyond 7.5 d, information)"]
    ratio, sig, dcov, missing = {}, {}, {}, []
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        for s in (0, 1):
            b, g, n = (os.path.join(M, f"modeF_n5_{a}{tag}_s{s}") for a in ("bin", ref2, arm))
            if not all(os.path.exists(v + e) for v in (b, n) for e in ("_eval.csv", "_rows.npz")):
                missing.append(f"{box} s{s}")
                continue
            sb, sn, rb, rn = by_lead(b), by_lead(n), np.load(b + "_rows.npz"), np.load(n + "_rows.npz")
            assert (rb["day"] == rn["day"]).all() and (rb["lead"] == rn["lead"]).all(), f"{box} s{s}: arms scored on different rows"
            iv, sg = [], []
            for L in NEAR + (BEYOND,):
                k = rb["lead"] == L
                dm, lo, hi = K.block_boot(rn["crps"][k] - rb["crps"][k], list(rb["day"][k]), draws=1000)
                if L in NEAR:
                    sg.append(hi < 0)
                iv.append(f"{L}d {dm:+.3f} [{lo:+.3f}, {hi:+.3f}]")
            r = (sn / sb).values
            dc = (cov99(n) - cov99(b)).reindex(list(NEAR))
            ratio[(box, s)], sig[(box, s)], dcov[(box, s)] = r[:len(NEAR)], sg, dc.abs().values
            lines.append(f"  {box:<6} seed {s}: binned " + " / ".join(f"{v:.3f}" for v in sb) + "; NEST " + " / ".join(f"{v:.3f}" for v in sn)
                         + "  change " + " / ".join(f"{100 * (v - 1):+.1f}" for v in r) + " %; NEST minus binned: " + ", ".join(iv)
                         + "; cov99 difference " + " / ".join(f"{v:+.4f}" for v in dc))
            if os.path.exists(g + "_eval.csv"):
                lines.append(f"           vs {ref2} (information): " + " / ".join(f"{100 * (v - 1):+.1f}" for v in (sn / by_lead(g)).values) + " %")
    if missing:
        lines.append("Incomplete, missing: " + ", ".join(missing))
        K.report(name, lines)
        return
    lines.append("Rule (pre-set): PASS = NEST >= 1 % better than binned at every lead 1/3/5/7 with interval < 0, both boxes and seeds, cov99 within 0.003; "
                 "KILL = 7 d worse (seed mean) in both boxes.")
    lines.append("Verdict: " + judge(ratio, sig, dcov))
    K.report(name, lines)


def _selfcheck():
    keys = [(b, s) for b in ("A", "B") for s in (0, 1)]
    yes, cov = {k: [True] * 4 for k in keys}, {k: [0.001] * 4 for k in keys}
    assert judge({k: [0.98] * 4 for k in keys}, yes, cov) == "PASS"
    assert judge({k: [0.995] * 4 for k in keys}, yes, cov).startswith("MISS")
    assert judge({k: [0.98] * 4 for k in keys}, {k: [True, True, True, False] for k in keys}, cov).startswith("MISS")
    assert judge({k: [0.98] * 4 for k in keys}, yes, {k: [0.004] * 4 for k in keys}).startswith("MISS")
    assert judge({k: [0.98, 0.98, 0.98, 1.01] for k in keys}, yes, cov) == "KILL"
    assert judge({k: ([0.98, 0.98, 0.98, 1.01] if k[0] == "A" else [0.98] * 4) for k in keys}, yes, cov).startswith("MISS")


_selfcheck()
if __name__ == "__main__":
    main()
