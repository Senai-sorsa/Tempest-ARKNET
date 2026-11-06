#!/bin/bash
# L3-26 studt retry (once): the first run's Student-t draws were unbounded (chi^2 near 0) and blew some T columns to
# inf -> NaN RH and NaN calibration. model.py now clamps |t| <= 8; no retrain (only ~1e-4 of draws change).
# Recalibrate + rescore via ap_l3.sh, then the fill-top Denver score. Named *ap_l3_fill* so ap_g9.sh waits for it.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [L3 studt-retry] $*" >> data/l3.log; }
log start
while powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_lean|ap_l3\.sh|ap_l3_fill\.sh' }).Count" | tr -d '\r' | grep -qv '^0$'; do sleep 120; done
bash scripts/ap_l3.sh studt
M=models/l3_studt.pt C=models/l3_studt.calib2021.npz D=data/train/denver_full_fill_dpd.npz DM=models/l3_studt_denfill.pt
[ -f $C ] || { log "no calibration, fill score skipped"; exit 1; }
cp $M $DM
$PY -W ignore -u -m tempest.scoring.score --model $DM --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras > data/l3_score_studt_denfill.log 2>&1 || { log "FAILED fill score"; exit 1; }
{ echo "== $(date '+%F %T') DENVER fill-top zero-shot studt (retry) vs p2f"; $PY scripts/compare_headline.py models/l3_braw_fill_cal2021_headline.csv models/l3_studt_denfill_cal2021_headline.csv; } >> data/l3_verdicts.txt 2>&1
log done
