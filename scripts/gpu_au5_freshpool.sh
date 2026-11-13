#!/bin/bash
# AU-5 step 0 (New_Plan 15.2): score the shipped l3_c4w stack (seed 0, the gpu_au7 flags without --gauss15) against two
# 2024-25 ERA5 truths that differ ONLY in the station correction's leftover pool:
#   OLD   the shipped map models/station_map_mix.npz (pool from 1991-2020 balloons, the noise the model trained on)
#   FRESH the same a, b with a pool from 2021-23 balloons (scripts/au5_fresh_pool.py)
#   FRESHDM (step 1) FRESH with each group x tercile's mean leftover removed (--demean): new noise without the 2021-23 drift
# Same 2024-25 day store (to_heights --first-year 2024), same build seed and row density as pilot80_l21_day_dpd
# (6.81 M rows over 35 years -> 389 k for 2 years), so the rows and the draws match; training years 1991-2023 are the
# shipped file's own rows (scripts/au5_splice.py). Pass rule: cov99, cov90 and CRPS within 0.003 in every band -> close.
# Log: data/l3.log [AU5]. Every step skips when its output exists. Needs ~12 GB free RAM for a splice, ~25 GB disk.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
export PYTHONPATH=.
RAW=data/raw/era5_em80 CDS=data/raw/era5_cds
ST=data/pilot/profiles80_l21_2425.zarr
DA=data/train/pilot80_l21_day_dpd.npz C=models/l3_c4w
CAL=$C.calib2021.npz SM=$C.shearmap2021_cell8.npz LM=$C.lapsemap2021.npz
OLD=models/station_map_mix.npz FRESH=models/station_map_mix_pool2123.npz FRESHDM=models/station_map_mix_pool2123dm.npz
log() { echo "$(date '+%F %T') [AU5] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt $1 ]; do sleep 60; done; }
log start

[ -f $FRESH ] || { $PY -W ignore -u scripts/au5_fresh_pool.py --out $FRESH >> data/au5.log 2>&1 && log "fresh pool fitted" || { log "FAILED fresh pool"; exit 1; }; }
[ -f $FRESHDM ] || { $PY -W ignore -u scripts/au5_fresh_pool.py --demean --out $FRESHDM >> data/au5.log 2>&1 && log "demeaned fresh pool fitted" || { log "FAILED demeaned pool"; exit 1; }; }

if [ ! -f $ST/COMPLETE ]; then
  CUDA_VISIBLE_DEVICES=-1 $PY -W ignore -u -m tempest.profiles.to_heights --raw $RAW --cds $CDS --out $ST --hours 12-23,0-4 \
    --first-year 2024 --last-year 2025 >> data/au5.log 2>&1 && touch $ST/COMPLETE && log "2024-25 store built" || { log "FAILED store"; exit 2; }
fi

for k in old fresh freshdm; do
  M=$OLD; [ $k = fresh ] && M=$FRESH; [ $k = freshdm ] && M=$FRESHDM
  N=data/train/au5_2425_$k.npz
  [ -f $N ] || { CUDA_VISIBLE_DEVICES=-1 $PY -W ignore -u -m tempest.generator.build_dataset --profiles $ST --out $N.part --rows 389000 \
    --first-year 2024 --last-year 2025 --station-map $M --features base --rh-target dpd --all-hours >> data/au5.log 2>&1 && mv $N.part $N && log "$k rows built" \
    || { log "FAILED $k build"; exit 3; }; }
  S=data/train/au5_l21_$k.npz
  [ -f $S ] || { wait_ram 12; $PY -u scripts/au5_splice.py $S.part $DA $N >> data/au5.log 2>&1 && mv $S.part $S && log "$k spliced" || { log "FAILED $k splice"; exit 4; }; }
done

for k in old fresh freshdm; do
  cp models/l3_c4wl_s0.pt models/au5${k}_l3_c4wl_s0.pt
  [ -f models/au5${k}_l3_c4wl_s0_cal2021_smap_shufc8_lmap_headline.csv ] && continue
  wait_ram 8
  $PY -W ignore -u -m tempest.scoring.score --model models/au5${k}_l3_c4wl_s0.pt --data data/train/au5_l21_$k.npz --m 199 --first-test-year 2024 --last-test-year 2025 \
    --mc --seed 0 --calib $CAL --shuffle --template-cell 8 --shear-map $SM --lapse-map $LM > data/au5_score_$k.log 2>&1 && log "$k scored" || { log "FAILED $k score"; exit 5; }
done
log done
