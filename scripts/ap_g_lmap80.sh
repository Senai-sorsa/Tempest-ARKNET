#!/bin/bash
# L21b step 1: the lapse map (IL-162, kept on the l21 stack) fitted on the SHIPPED tool's stack: models/generator_80_p2f + its calibration + its shear map + shuffle (template cell 8),
# on data/train/pilot80_dpd.npz (the data the bundled assets were exported from). Then the shipped stack scored with and without it, seed 0, --mc (physics rows), same rows.
# Accept for the tool export if the superadiabatic row moves toward ERA5 with skill15 within the paired tolerance (as on the l21 stack: 0.324 -> 0.217, ERA5 0.199).
# Waits for no other queue (the stuck copy of ap_g_c4b_stack.sh is ignored), no GPU/build/pytest job and >= 6 GB free RAM; steps skip when their output exists, retried once.
# Log: data/l3.log [LMAP80]; verdicts: data/l3_verdicts.txt. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
D=data/train/pilot80_dpd.npz B=models/generator_80_p2f
CAL=$B.calib2021.npz SM=$B.shearmap2021_cell8.npz LM=$B.lapsemap2021.npz
log() { echo "$(date '+%F %T') [LMAP80] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights|pytest' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'bash.exe.? scripts/ap_(?!g_lmap80|g_c4b_stack\.sh)' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $D $B.pt $CAL $SM; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 60; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 120
done
log start
if [ ! -f $LM ]; then
  for try in 1 2; do
    wait_gpu
    $PY -W ignore -u -m tempest.calibrate.lapse_map --model $B.pt --data $D --calib $CAL --shear-map $SM --shuffle --template-cell 8 --out $LM > data/l3_lmap80_fit.log 2>&1 && [ -f $LM ] && { log "lapse map fitted"; break; }
    log "lapse fit try $try failed"
  done
  [ -f $LM ] || { log "FAILED lapse fit twice"; exit 2; }
fi
H0=models/g80lm_base_s0_cal2021_smap_shufc8_headline.csv H1=models/g80lm_lmap_s0_cal2021_smap_shufc8_lmap_headline.csv
score() {  # score STEM HEADLINE extra-args
  local P=models/$1.pt; [ -f $P ] || cp $B.pt $P; [ -f $2 ] && return 0
  for try in 1 2; do
    wait_gpu
    $PY -W ignore -u -m tempest.scoring.score --model $P --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed 0 \
      --calib $CAL --shuffle --template-cell 8 --shear-map $SM "${@:3}" > data/l3_lmap80_$1.log 2>&1 && [ -f $2 ] && { log "$1 scored"; return 0; }
    log "$1 try $try failed"
  done
  log "FAILED $1"; return 1
}
score g80lm_base_s0 $H0
score g80lm_lmap_s0 $H1 --lapse-map $LM
[ -f $H0 ] && [ -f $H1 ] && { echo "== $(date '+%F %T') LMAP80 shipped stack + lapse map vs shipped stack, seed 0 (pilot80_dpd)"; $PY scripts/compare_headline.py $H0 $H1
  echo "physics rows (base | lapse map):"; grep -E "superadiabatic|shear_gt|sfc_jump" ${H0%_headline.csv}_mc.csv | sed 's/^/  base /'; grep -E "superadiabatic|shear_gt|sfc_jump" ${H1%_headline.csv}_mc.csv | sed 's/^/  lmap /'; } >> data/l3_verdicts.txt 2>&1
log done
