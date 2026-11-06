#!/bin/bash
# Loop 2 H6: monthly median shift for T (shrunk by half), fitted 2021-23, on top of H1b (c4); ERA5 headline 2024-25 vs c4 alone. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python; export PYTHONPATH=.
B=models/generator_80_p2f; D=data/train/pilot80_dpd.npz
[ -f $B.shift2021_bymonth.npz ] || $PY -W ignore -u -m tempest.calibrate.shift --model $B.pt --data $D --calib $B.calib2021.npz --rows 24000 --by-month --shrink 0.5 --vars T > data/ap_h6_fit.log 2>&1 || { echo "$(date '+%F %T') h6 FAILED fit" >> data/ap_h6.log; exit 3; }
$PY -W ignore -u -m tempest.scoring.score --model $B.pt --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $B.calib2021.npz --shuffle --template-cell 8 --shear-map $B.shearmap2021_cell8.npz --pit-recal $B.pitrecal2021.npz --pit-damp 0.5 --seasonal $B.seasonal2021_rhprof1km.npz --shift $B.shift2021_bymonth.npz > data/ap_h6_score.log 2>&1 || { echo "$(date '+%F %T') h6 FAILED score" >> data/ap_h6.log; exit 4; }
{ echo "== LOOP2 H6 monthly T shift on top of c4 (ERA5)"; $PY scripts/compare_headline.py ${B}_cal2021_seas_smap_shufc8_pit_headline.csv ${B}_cal2021_seas_shift_smap_shufc8_pit_headline.csv | tail -22; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') h6 done" >> data/ap_h6.log
