#!/bin/bash
# LOOP3 L3-33: stack + G1-a verdict. NM/TX: p2f + range map + shuffle (2-degree templates) + shear map, as the tool ships it (IL-95).
# Denver fill-top: p2f + range map + Denver-fitted trust blend (L3-29), then the shuffle (score.py now applies trust first),
# a) without and b) with the NM/TX shear map. All with --mc. Waits for the L3-30 runner, then for an idle GPU and >= 9 GB free RAM.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
NT=data/train/pilot80_dpd.npz DEN=data/train/denver_full_fill_dpd.npz B=models/generator_80_p2f
C=$B.calib2021.npz SM=$B.shearmap2021_cell8.npz MD=models/l3_p2fden.pt MN=models/l3_stk_nmtx.pt
log() { echo "$(date '+%F %T') [L3-33] $*" >> data/l3.log; }
nproc_match() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='$1'\" | ? { \$_.CommandLine -match '$2' }).Count" | tr -d '\r'; }
free_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_room() { while [ "$(nproc_match python.exe 'generator.train|calibrate.spread|calibrate.joint|calibrate.trust|scoring.score')" != "0" ] || [ "$(free_gb)" -lt 9 ]; do sleep 120; done; }
while [ "$(nproc_match bash.exe 'scripts/ap_l3_[s]tudtclip')" != "0" ]; do sleep 120; done   # [s]: this script's own launcher never matches
log start
cp $B.pt $MN; cp $C ${MN%.pt}.calib2021.npz
run() {  # name, log, args...
  local n=$1 l=$2; shift 2; wait_room
  $PY -W ignore -u -m tempest.scoring.score --m 199 --first-test-year 2024 --last-test-year 2025 --mc "$@" > $l 2>&1 && log "$n scored" || log "FAILED $n"
}
run nmtx data/l3_stack_nmtx.log --model $MN --data $NT --calib ${MN%.pt}.calib2021.npz --shuffle --template-cell 8 --shear-map $SM
run den_trust_shuf data/l3_stack_den_a.log --model $MD --data $DEN --calib $C --trust ${MD%.pt}.trust2021.npz --shuffle --template-cell 8
run den_trust_smap_shuf data/l3_stack_den_b.log --model $MD --data $DEN --calib $C --trust ${MD%.pt}.trust2021.npz --shuffle --template-cell 8 --shear-map $SM
log done
