"""New_Plan 13 AV30: SIGMA stage 3 NEST + Student-t noise (il6_modeF.py --sigma --nest --noise-t-dims 8 --noise-t-nu 4), GPU.
Why: NEST missed (2026-11-13) with every interval < 0 but cov99 ~0.01 low at 1-3 d (short-lead tails too narrow). One change against NEST:
the first 8 of the 16 noise numbers are Student-t, nu = 4 (unit variance), to give heavier tails.
Runs: scripts/gpu_av30.sh -> models/modeF_n5_nestt{,_den}_s{0,1} (same rows, seeds, recipe as NEST).
Rule written 2026-11-13 before any AV30 result (SIGMA stage 3's rule unchanged, from b20_sigma_stage3.judge):
PASS: >= 1 % better than N5 binned at every lead 1/3/5/7 with an interval excluding 0, both boxes, both seeds, and cov99 within 0.003 of binned
      at every lead. KILL: lead 7 d worse than binned (seed mean) in both boxes. Otherwise MISS: record, no adoption.
Information: change vs NEST by lead; cov99 differences by lead are printed in the binned comparison.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b21_av30_nest_t.py
Result: docs/results/logs/kit_b21_av30_nest_t.log
"""
from b20_sigma_stage3 import main

if __name__ == "__main__":
    main(arm="nestt", ref2="nest", name="b21_av30_nest_t", title="AV30 (NEST + Student-t noise, 8 dims, nu 4)")
