#!/bin/bash
# LOOP3 L3-34 (climatology debias) + L3-35 (shuffle blocks with the real grid width), Denver fill-top, all with --mc; then the
# data-needs queue (scripts/ap_l3_data.sh), chained here so the two never race for the GPU (replaces data/l3_queue_data.sh).
# L3-34: per point x month x 4-hour-bin mean error of p2f + range map, fitted on 2021-23 (tempest.scoring.debias), subtracted.
# L3-35: cell_keys assumed 29 longitudes (NM/TX); Denver is 9 x 9, so its c8 blocks were mixed strips. Rescored under a model
# copy (l3_p2fden_fx) so the old L3-33 files stay. Waits for the L3-30 runner, then for an idle GPU and >= 9 GB free RAM.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DEN=data/train/denver_full_fill_dpd.npz B=models/generator_80_p2f
C=$B.calib2021.npz SM=$B.shearmap2021_cell8.npz MD=models/l3_p2fden.pt MF=models/l3_p2fden_fx.pt
T=models/l3_p2fden.trust2021.npz DB=models/l3_p2fden.debias2021.npz
log() { echo "$(date '+%F %T') [L3-34] $*" >> data/l3.log; }
nproc_match() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='$1'\" | ? { \$_.CommandLine -match '$2' }).Count" | tr -d '\r'; }
free_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_room() { while [ "$(nproc_match python.exe 'generator.train|calibrate.spread|calibrate.joint|calibrate.trust|scoring.score|scoring.debias')" != "0" ] || [ "$(free_gb)" -lt 9 ]; do sleep 60; done; }
while [ "$(nproc_match bash.exe 'scripts/ap_l3_[s]tudtclip')" != "0" ]; do sleep 60; done
log start
run() {  # name, log, args...
  local n=$1 l=$2; shift 2; wait_room
  $PY -W ignore -u -m tempest.scoring.score --m 199 --first-test-year 2024 --last-test-year 2025 --mc "$@" > $l 2>&1 && log "$n scored" || log "FAILED $n"
}
wait_room
if [ -f $DB ] || $PY -W ignore -u -m tempest.scoring.debias --model $MD --calib $C --data $DEN --from-year 2021 --year 2023 > data/l3_debias_fit.log 2>&1; then
  log "debias fitted ($(tail -1 data/l3_debias_fit.log))"
  run den_debias data/l3_debias_den.log --model $MD --data $DEN --calib $C --debias $DB
  run den_debias_trust data/l3_debias_den_trust.log --model $MD --data $DEN --calib $C --debias $DB --trust $T
else
  log "FAILED debias fit"
fi
cp $MD $MF
echo "$(date '+%F %T') [L3-35] start" >> data/l3.log
run den_fx_trust_smap_shufc8 data/l3_fx_den_c8.log --model $MF --data $DEN --calib $C --trust $T --shuffle --template-cell 8 --shear-map $SM
run den_fx_trust_smap_shufc3 data/l3_fx_den_c3.log --model $MF --data $DEN --calib $C --trust $T --shuffle --template-cell 3 --shear-map $SM
[ -f $DB ] && run den_fx_debias_trust_smap_shufc8 data/l3_fx_den_debias_c8.log --model $MF --data $DEN --calib $C --debias $DB --trust $T --shuffle --template-cell 8 --shear-map $SM
log done
while [ "$(free_gb)" -lt 6 ]; do sleep 300; done
echo "$(date '+%F %T') [DATA all] start (reaped-job recovery, after L3-34/35)" >> data/l3.log
exec bash scripts/ap_l3_data.sh > data/l3_data_runner.log 2>&1
