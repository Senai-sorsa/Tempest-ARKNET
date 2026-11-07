#!/bin/bash
# L3-42 NM/TX stack on all hours. The NM/TX stack (p2f + shear map + shuffle c8, L3-33 +0.0278) is still p2f. Rebuild it on
# l3_h_all24 with its own shear map (fitted in L3-40) and score, all --mc:
#   DAY   seeds 0/1/2, paired with the p2f stack on the same seed (seed 0 = models/l3_stk_nmtx_cal2021_smap_shufc8_headline.csv)
#   NIGHT seed 0, vs the p2f stack extrapolating into the night
# Model copies carry run names so headline files never collide. One GPU job at a time, waits for >= 9 GB free RAM.
# Log: data/l3.log [L3-42]; verdicts: data/l3_verdicts.txt. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
NT=data/train/pilot80_dpd.npz NI=data/train/pilot80_night_dpd.npz
B=models/generator_80_p2f C=$B.calib2021.npz SM=$B.shearmap2021_cell8.npz
A=models/l3_h_all24 CA=$A.calib2021.npz SMA=$A.shearmap2021_cell8.npz
log() { echo "$(date '+%F %T') [L3-42] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 9 ]; do sleep 60; done; }
H() { echo models/$1_cal2021_smap_shufc8_headline.csv; }
run() {  # run STEM SRC DATA SEED CALIB SHEARMAP
  local M=models/$1.pt; cp $2 $M; [ -f $(H $1) ] && return 0; wait_gpu
  $PY -W ignore -u -m tempest.scoring.score --model $M --data $3 --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $4 \
    --calib $5 --shuffle --template-cell 8 --shear-map $6 > data/l3_nmtxh_$1.log 2>&1 && log "$1 scored" || { log "FAILED $1"; return 1; }
}
verdict() { [ -f $(H $1) ] && [ -f $(H $2) ] && { echo "== $(date '+%F %T') L3-42 $3"; $PY scripts/compare_headline.py $(H $1) $(H $2); } >> data/l3_verdicts.txt 2>&1; }
log start
run l3_a24nm_s0 $A.pt $NT 0 $CA $SMA
verdict l3_stk_nmtx l3_a24nm_s0 "NM/TX all24 stack DAY seed 0 vs p2f stack seed 0"
for s in 1 2; do
  run l3_stk_nmtx_s$s $B.pt $NT $s $C $SM
  run l3_a24nm_s$s $A.pt $NT $s $CA $SMA
  verdict l3_stk_nmtx_s$s l3_a24nm_s$s "NM/TX all24 stack DAY seed $s vs p2f stack seed $s"
done
run l3_stk_nmtx_night $B.pt $NI 0 $C $SM
run l3_a24nm_night $A.pt $NI 0 $CA $SMA
verdict l3_stk_nmtx_night l3_a24nm_night "NM/TX all24 stack NIGHT vs p2f stack extrapolating"
log done
