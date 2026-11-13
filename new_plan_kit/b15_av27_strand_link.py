"""New_Plan 13 AV27, variation of STRAND stage 1 (b14_strand_stage1.py, MISS 2026-11-13 08:41: templates cut the shipped sequence's run-probability
error to 0.50-0.65 of it, but every arm sits on a per-hour floor: the tool's climate-mode 10 m wind is windier than ERA5 u10 at these points,
|P_indep tool - truth| 0.12-0.19, which no re-ordering can change).
What changes: only the score. Same arms, cells, seeds and members (b14.collect, re-run). Each arm's hour-to-hour LINK is scored on the truth's own
per-hour probabilities: lift = P_arm(3 h under L) / P_IND(product of the arm's per-hour fractions; the same members for all three arms), and the
arm's linked probability is min(1, lift x truth P_indep). IND therefore scores stage 0's gap; the per-hour marginal error drops out.
Cells where the tool's P_IND is 0 are skipped (counted).

Rule (set before any result; written 2026-11-13 08:55): b14's rule unchanged, on the linked probabilities:
  per L in (5, 8, 10) m/s, err(arm) = mean over open cells of |linked P_arm - P_real|.
  PASS: err(TPL) <= 0.5 x err(SEQ) at every limit in both seeds.
  STOP: err(SEQ) < 0.02 at every limit in both seeds (the shipped copula already carries the link).
  KILL: err(TPL) >= err(SEQ) at every limit in both seeds.  Otherwise MISS.
  Note (pitfall 14): second try on STRAND stage 1; the metric was changed after seeing the per-hour floor in stage 1's diagnostic line, not after
  seeing a linked-probability result. Adoption would also need the marginal question (is the windier 10 m intended?) answered separately.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b15_av27_strand_link.py
Result: docs/results/logs/kit_b15_av27_strand_link.log
"""
import numpy as np

import kit_common as K
from b14_strand_stage1 import LIMITS, collect, judge


def linked(r):
    """r (cells, 5) = (P real, P IND, P SEQ, P TPL, truth P_indep) -> (keep mask, (cells, 3) linked P for IND, SEQ, TPL)."""
    keep = r[:, 1] > 0
    r = r[keep]
    lift = r[:, 1:4] / r[:, 1:2]
    return keep, np.minimum(1.0, lift * r[:, 4:5])


def main():
    rows, skipped, npts = collect()
    lines = [f"AV27: STRAND stage 1 arms scored on the link only (lift x truth P_indep); {npts} points x 12 months x 3 start hours, seeds 0 / 1"]
    err = {}
    for seed in (0, 1):
        err[seed] = {}
        for L in LIMITS:
            r = rows[seed][L]
            keep, p = linked(r)
            e = tuple(float(np.abs(p[:, j] - r[keep, 0]).mean()) for j in range(3))
            err[seed][L] = e
            lift = (r[keep, 2:4] / r[keep, 1:2]).mean(0)
            lines.append(f"  seed {seed} L {L:>4.0f} m/s: {keep.sum()} cells ({(~keep).sum()} skipped, tool P_IND 0); mean lift truth {(r[keep, 0] / r[keep, 4]).mean():.3f}, "
                         f"SEQ {lift[0]:.3f}, TPL {lift[1]:.3f}; mean |linked error| IND {e[0]:.4f}, SEQ {e[1]:.4f}, TPL {e[2]:.4f} (TPL / SEQ {e[2] / e[1]:.2f})")
    lines.append(f"  cells skipped in collect: {skipped}")
    lines.append("Verdict: " + judge(err))
    K.report("b15_av27_strand_link", lines)


def _selfcheck():
    r = np.array([[0.6, 0.3, 0.45, 0.6, 0.4], [0.5, 0.0, 0.1, 0.2, 0.3]])
    keep, p = linked(r)
    assert keep.tolist() == [True, False]
    assert np.allclose(p[0], [0.4, 0.6, 0.8])                   # IND -> truth P_indep; SEQ lift 1.5; TPL lift 2
    assert np.allclose(linked(np.array([[0.9, 0.2, 0.9, 0.9, 0.5]]))[1][0, 1], 1.0)      # capped at 1


_selfcheck()
if __name__ == "__main__":
    main()
