#!/bin/bash
# L3-43 fill_mask (review 2026-11-07, GLOBAL_PLAN §7.1/§9.7): does ignoring the fill_top-filled heights in the loss help?
# Rebuilds the Denver fill-top day file (same command as ap_l3_lean.sh, new name, so it carries fill_top_idx; nothing is
# overwritten), then trains the B-local config (p2f, Denver 1991-2023) twice on it: mask OFF (l3_blf) and mask ON
# (l3_blfm), calibrates on 2021-23 and scores 2024-25 on the same file. Verdict: mask ON vs OFF.
# Caveat: the score targets above each row's top are the filled values themselves, so the OFF model is favoured there;
# read the bands below the fill (0-12 km) and the coverage, not only the mean.
# Starts when no loop-3 queue, GPU or build job runs and >= 6 GB RAM is free (was 9; lowered 13:25 Nov 7: available sits at 6-7 GB with 23 GB commit free, and Denver jobs ran at 6.5 GB before). Every step skips when its output exists.
# Log: data/l3.log [L3-43]; verdicts: data/l3_verdicts.txt. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
D=data/train/denver_full_fill_idx_dpd.npz VLOG=data/l3_verdicts.txt
log() { echo "$(date '+%F %T') [L3-43] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!fillmask)|ap_l3\.sh|ap_g9' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }

log "waiting for the loop-3 queue, GPU, builds and 6 GB RAM"
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 120; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 300
done
log start

for try in 1 2; do
  [ -f $D ] && break
  wait_gpu; log "fill-top build try $try"
  TEMPEST_REGION=configs/region_denver.toml CUDA_VISIBLE_DEVICES=-1 $PY -W ignore -u -m tempest.generator.build_dataset --profiles data/pilot/profiles_denver_full.zarr \
    --out $D.part --rows 4000000 --first-year 1991 --last-year 2025 --station-map models/station_map_denver_full.npz \
    --features base --rh-target dpd --fill-top >> data/l3_fillmask_build.log 2>&1 && mv $D.part $D
done
[ -f $D ] || { log "FAILED build twice"; exit 2; }

fit() {  # fit NAME CONFIG
  local M=models/l3_$1.pt C=models/l3_$1.calib2021.npz H=models/l3_$1_cal2021_headline.csv
  [ -f $H ] && return 0
  if [ ! -f $M ]; then
    for try in 1 2; do
      wait_gpu; log "$1 train try $try"
      $PY -u -m tempest.generator.train --data $D --out $M.part --max-year 2023 --min-year 1991 --config $2 > data/l3_train_$1.log 2>&1 && mv $M.part $M && break
    done
    [ -f $M ] || { log "$1 FAILED train twice"; return 1; }
  fi
  if [ ! -f $C ]; then
    wait_gpu
    $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $D --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_$1.log 2>&1 || { log "$1 FAILED spread"; return 1; }
  fi
  wait_gpu
  $PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras \
    > data/l3_score_$1.log 2>&1 && log "$1 scored" || { log "$1 FAILED score"; return 1; }
}
fit blf configs/generator_l3_blocal.toml || exit 3
fit blfm configs/generator_l3_blocal_fillmask.toml || exit 3
{ echo "== $(date '+%F %T') L3-43 DENVER fill_mask ON vs OFF (B-local config, fill-top file)"
  $PY scripts/compare_headline.py models/l3_blf_cal2021_headline.csv models/l3_blfm_cal2021_headline.csv; } >> $VLOG 2>&1
log done
