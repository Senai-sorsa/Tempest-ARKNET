"""New_Plan 14.3 SIGMA stage 2 (13.5 step 3): Mode F with the lead read as a noise level, at the shipped size (width 128, depth 2), fit on all
leads to 10 d. Runs: scripts/cpu_sigma2.sh (il6_modeF.py --sigma; seeds 0 and 1; boxes NM/TX and Denver, rows data/modeF_v2{,_denver}).
    sig     models/modeF_n5_sig{,_den}_s{0,1}   member = climate + beta x forecast anomaly + s x network; beta, s tabled per lead day 1-10
                                                 (SIGMA stage 1: the two-number curves had the wrong shape, so the table), all from 2016-2020 rows
    binned  models/modeF_n5_bin{,_den}_s{0,1}   N5's binned model (as shipped: fit on leads <= 7.5 d), same recipe, same test rows (asserted)
Rule (set before any result; written 2026-11-13 13:20) = N5's rule unchanged (b5_modeF_alllead.judge), as the plan says:
  PASS: leads 1-7 within +0.5 % of binned at every lead; beyond 7.5 d better than binned (the router stand-in) and than climate, interval < 0 for
        both; never worse than climate at lead day 8 / 9 / 10 (mean); all boxes and seeds.
  KILL: mean of leads 1 and 3 worse than binned by more than 1 % at both boxes in both seeds.  Otherwise MISS (record; section 13 note).
  Deviations from the plan text, stated before the run: (1) no world start. N2's world start is not adopted (AV5 KILL 2026-11-13; AV28 open) and
  the N2 world network was fit on the plain residual, not on the SIGMA target, so starting from it would mix two targets; both arms here start
  fresh on the box rows, which isolates SIGMA. (2) beta and s are tables, not curves (stage 1's finding). (3) climate = the box's own fit-row
  climate (place x month x UTC hour), not the climate generator's pool (improvement 2; needed only at new places). Improvements 3-7 not in stage 2.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b18_sigma_stage2.py
Result: docs/results/logs/kit_b18_sigma_stage2.log
"""
from b5_modeF_alllead import main as b5_main


def main():
    b5_main(arm="sig", label="SIGMA", log="b18_sigma_stage2", head="SIGMA stage 2 (lead as a noise level, beta / s tabled, all leads)")


if __name__ == "__main__":
    main()
