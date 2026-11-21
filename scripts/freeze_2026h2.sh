#!/usr/bin/env bash
# New_Plan 28.5 freeze (user go 2026-11-21): the shipped tool stack (sources identified array-by-array against tempest_weather/assets) with the
# final-model swaps of 28.11: X4-R variant e net (models/s25/c4wx4r_s0) + its calib / shear / lapse refits, ENSF2 network, WD1 ur5 table built on THIS stack.
# Step 1 stage export (no ur5) -> step 2 build_ur5 on the stage -> step 3 freeze export into tempest_weather/assets_final_2026h2 -> step 4 array diff vs shipped.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/cap_cpu.sh
PY=.venv/Scripts/python.exe
export PYTHONPATH=.
STAGE=data/freeze_stage_assets
FINAL=tempest_weather/assets_final_2026h2
UR5=models/ur5_final_2026h2.npz
LOG=data/freeze_2026h2.log
log() { echo "[FREEZE] $(date '+%F %T') $*" | tee -a $LOG; }
[ -e $FINAL/manifest.json ] && { log "refusing: $FINAL already exists (freeze is one run)"; exit 1; }
D=models/s25/c4wx4r_s0
ARGS=(--model $D.pt --calib $D.calib2021.npz --head models/whead_a24.pt --wcalib models/whead_a24.wcalib2021.npz --gust models/gust_model.npz
      --coherence models/coherence_lagcorr.npz --coherence-dist models/coherence_distcorr.npz --coherence-regimes models/coherence_regimes.npz
      --post-templates ${FREEZE_TEMPLATES:-data/train/pilot80_l21_all24_dpd.npz} --post-template-sets 3 --post-cell 8
      --post-smap ${D}_smap_cell8.npz --post-lmap ${D}_lmap_cell8.npz --post-amap models/av35_shearmap_aloft.npz
      --modef models/modeF_v3.pt --modef-rows data/modeF_v2 --modef-ridge --modef-ens models/modeF_ens.pt --modep models/modeP.pt --modep-sfc models/modeP_sfc_pool.npz
      --modep-sta models/station_map_mix.npz --solar-hours 0-24)
log "start, git $(git rev-parse --short HEAD)"
if [ ! -e $STAGE/manifest.json ]; then $PY -W ignore -m tempest.export_tool "${ARGS[@]}" --out $STAGE >> $LOG 2>&1; log "stage export done"; fi
if [ ! -e $UR5 ]; then $PY -W ignore -u scripts/build_ur5.py $UR5.part.npz --assets $STAGE >> $LOG 2>&1 && mv $UR5.part.npz $UR5; log "ur5 table built on the stage"; fi
$PY -W ignore -m tempest.export_tool "${ARGS[@]}" --post-ur5 $UR5 --out $FINAL >> $LOG 2>&1
log "freeze export done"
$PY -W ignore scripts/freeze_diff.py tempest_weather/assets $FINAL >> $LOG 2>&1 && log "diff vs shipped OK" || { log "diff vs shipped FAILED"; exit 3; }
sha256sum $FINAL/* $UR5 $D.pt $D.calib2021.npz ${D}_smap_cell8.npz ${D}_lmap_cell8.npz models/av35_shearmap_aloft.npz models/modeF_ens.pt models/modeF_ens.calib.npz | tee -a $LOG
log "done"
