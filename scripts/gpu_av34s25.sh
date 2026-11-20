#!/bin/bash
# New_Plan 28.8 step 2: AV34 trust layer (IL-10 settings, --min-gain 0.001, RH 5-12 / 12-18 km, T and u 12-18 km at w = 1, no second map,
# fit 2021-23 on the DAY l21 file, exactly as scripts/gpu_av34.sh) refit on the s25 paired base (step 1 N1 was dropped, so the stack is unchanged),
# then stack (b) score + shape (diag b, s25_shape b) with --trust, seeds 0 and 100. Rule: new_plan_kit/s25_judges.py av34s25 (written before the run).
# The model, range map and shear / lapse maps are copies of models/s25/base_s<S>.* (same weights and content, so the hash checks pass);
# the maps are not refit on blended samples (as AV34: trust sits before the shuffle and the maps). Steps skip when their output exists.
# shortcut: no Denver report (the Denver file has no 2021-23 rows for a trust fit); score (a) skipped (the judge uses stack (b) only).
# Waits for no other scorer / s25 job and >= 6 GB free RAM (2 GB floor + ~4 GB peak) before each step.
# Launch: nohup bash scripts/gpu_av34s25.sh > /dev/null 2>&1 &   Log: data/l3.log [AV34S25]; step logs docs/results/logs/s25_av34s25_s<S>_*.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz D=models/s25 L=docs/results/logs
SH="--shuffle --template-cell 8"
log() { echo "$(date '+%F %T') [AV34S25] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|il6_modeF|pytest|diagnose|s25_|n1_crossfit' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
gpu_c() { nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | head -1 | tr -d '\r '; }
wait_free() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ] || [ "$(gpu_c)" -ge 85 ]; do sleep 60; done; }
run() {  # run OUT LOGNAME cmd...
  local out=$1 lg=$2; shift 2
  [ -e "$out" ] && return 0
  wait_free
  "$@" > $L/s25_${T}_$lg.log 2>&1 && log "$T $lg ok" || { log "FAILED $T $lg"; exit 2; }
}
until grep -q "\[N1C4W\] done" data/l3.log; do sleep 60; done   # step 1's stack first (no interleaving with its steps)
log start
for S in 0 100; do
  B=$D/base_s$S T=av34s25_s$S
  M=$D/$T.pt C=$D/$T.calib2021.npz SM=$D/${T}_smap_cell8.npz LM=$D/${T}_lmap_cell8.npz TR=$D/$T.trust2021.npz
  for f in $B.pt $B.calib2021.npz ${B}_smap_cell8.npz ${B}_lmap_cell8.npz $DA; do [ -e $f ] || { log "FAILED missing $f"; exit 1; }; done
  [ -f $M ] || cp $B.pt $M; [ -f $C ] || cp $B.calib2021.npz $C; [ -f $SM ] || cp ${B}_smap_cell8.npz $SM; [ -f $LM ] || cp ${B}_lmap_cell8.npz $LM
  run $TR trust $PY -W ignore -u -m tempest.calibrate.trust --model $M --data $DA --calib $C --from-year 2021 --year 2023 --m 199 \
    --min-gain 0.001 --skip "RH:5-12 km" "RH:12-18 km" "T:12-18 km" "u:12-18 km" --no-second-map
  run $D/${T}_cal2021_trust_smap_shufc8_lmap_headline.csv score_b $PY -W ignore -u -m tempest.scoring.score --model $M --data $DA --m 199 \
    --first-test-year 2024 --last-test-year 2025 --seed 0 --calib $C $SH --shear-map $SM --lapse-map $LM --trust $TR
  # the judge reads <name>_s<S>_cal2021_smap_shufc8_lmap_headline.csv (stack (b) name without the _trust tag)
  [ -f $D/${T}_cal2021_smap_shufc8_lmap_headline.csv ] || cp $D/${T}_cal2021_trust_smap_shufc8_lmap_headline.csv $D/${T}_cal2021_smap_shufc8_lmap_headline.csv
  run $D/${T}_diag_b_cell8.csv diag_b env PYTHONPATH=. $PY -W ignore scripts/diagnose.py $M $C $DA --out $D/${T}_diag_b_cell8 $SH --shear-map $SM --lapse-map $LM --trust $TR
  run $D/${T}_s25shape_b_cell8.csv shape_b env PYTHONPATH=. $PY -W ignore scripts/s25_shape.py $M $C $DA --out $D/${T}_s25shape_b_cell8 $SH --shear-map $SM --lapse-map $LM --trust $TR --blocks 7
  log "$T done"
done
PYTHONPATH=".;new_plan_kit;scripts" $PY -W ignore new_plan_kit/s25_judges.py av34s25 >> data/l3.log 2>&1 && log done || log "FAILED verdict"
