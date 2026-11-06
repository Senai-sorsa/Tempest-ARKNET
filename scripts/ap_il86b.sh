#!/bin/bash
# Re-runs after two found mistakes: (1) IL-86 must be judged as part of the stack (PIT recalibration sorts the samples per column, the shuffle restores the dependence): pit + shuffle(2 degree) + shear map vs the same stack without pit; (2) IL-72: the sonde scorer did not load the offset-fit years (start year fixed). Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export PYTHONPATH=.
M=models/generator_80_p2f.pt; C=models/generator_80_p2f.calib2021.npz; D=data/train/pilot80_dpd.npz; B=models/generator_80_p2f
$PY -W ignore scripts/diagnose.py $M $C $D --pit-recal $B.pitrecal2021.npz --shuffle --template-cell 8 --shear-map $B.shearmap2021_cell8.npz --out ${B}_pit_stack_diag > data/ap_il86b_diag.log 2>&1
{ echo "== IL-86 (as part of the stack) pit + shuffle cell8 + smap vs the same stack without pit"; $PY scripts/compare_shape.py ${B}_cell8_refit_diag.csv ${B}_pit_stack_diag.csv --noise models/generator_80_p2f_s1_shape_diag.csv models/generator_80_p2f_s2_shape_diag.csv; } >> data/ap_s_verdicts.txt 2>&1
$PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles data/pilot/profiles80.zarr --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras --offset-from-year 2022 --offset-to-year 2023 > data/ap_il72_sonde.log 2>&1
{ echo "== IL-72 (rerun) balloon offset (fit 2022-23) vs p2f (balloons)"; grep "balloon offset fitted" data/ap_il72_sonde.log; $PY scripts/compare_headline.py ${B}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_off_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') il86b done" >> data/ap_il86b.log
