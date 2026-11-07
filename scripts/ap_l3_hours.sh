#!/bin/bash
# L3-38 all solar hours (user, 2026-11-07): the NM/TX training file only holds solar 06-21 h (to_heights keeps UTC
# 12-04), so the generator has never seen a night. Builds the missing UTC 05-11 hours from the raw store, retrains
# p2f on all 24 hours at the SAME row count (8.0 M, so each day hour gets ~37 % fewer rows), and scores day accuracy
# (vs p2f, the usual rules) and night accuracy (vs p2f extrapolating). If the day loss is significant
# (mean skill15 drop > 0.0006 seed tolerance, or a band WORSE), it tries two ways to keep it:
#   x     all hours at p2f's row density (12.6 M rows: day rows as many as p2f has)
#   split p2f unchanged for the day + a night-only model (p2f config) for solar ~22-05 h
# Starts when no other loop-3 queue or GPU/build job runs and >= 80 GB is free. Every step skips when its output
# exists, so a relaunch resumes. Log: data/l3.log [HOURS ...]; verdicts: data/l3_verdicts.txt. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
NT=data/train/pilot80_dpd.npz; RAW=data/raw/era5_em80; PN=data/pilot/profiles80_night.zarr
NI=data/train/pilot80_night_dpd.npz; DA=data/train/pilot80_dayall_dpd.npz
A24=data/train/pilot80_all24_dpd.npz; A24X=data/train/pilot80_all24x_dpd.npz
P2F=models/generator_80_p2f; DENF=data/train/denver_full_fill_dpd.npz; DENB=models/l3_braw_fill_cal2021_headline.csv
VLOG=data/l3_verdicts.txt
log() { echo "$(date '+%F %T') [HOURS $1] $2" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!hours)|ap_l3\.sh' }).Count" | tr -d '\r'; }
free_gb() { df -BG --output=avail /c | tail -1 | tr -dc '0-9'; }
wait_gpu() { while [ "$(busy)" != "0" ]; do sleep 60; done; }
wait_room() { while [ "$(free_gb)" -lt "$1" ]; do log all "waiting for disk: $(free_gb) GB free, need $1"; sleep 1800; done; }
# densities: p2f kept 8,001,979 of 96,259,644 window rows (0.0831); all-hours 1980-2025 = 107.7 M day-store rows
# (-> 8.95 M) + 44.3 M night rows (-> 3.69 M) = 12.64 M; the same-count file keeps 8.0/12.64 = 0.633 of them.
ROWS_DAY=8950000 ROWS_NIGHT=3690000 FRAC=0.633

log all "waiting for the loop-3 queue, GPU and builds to finish"
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 600; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 300
done
wait_room 80
log all start

# 1. night store (UTC 05-11 = solar ~22-05 h), plain 13 levels like profiles80, no 2026
n_blk() { cat $PN/done.txt 2>/dev/null | wc -l; }
for try in 1 2; do
  [ -f $PN/COMPLETE ] && break
  wait_gpu
  log night "to_heights try $try ($(n_blk) blocks done)"
  $PY -W ignore -u -m tempest.profiles.to_heights --raw $RAW --cds data/raw/empty_cds --out $PN --hours 5-11 --last-year 2025 >> data/l3_hours_heights.log 2>&1 && touch $PN/COMPLETE
done
[ -f $PN/COMPLETE ] || { log night "FAILED to_heights twice"; exit 2; }

# 2. builds (CPU only; same station map / features / humidity target as pilot80_dpd)
build() {  # build OUT PROFILES ROWS
  [ -f $1 ] && return 0
  wait_gpu; wait_room 30
  log build "$1 start"
  CUDA_VISIBLE_DEVICES=-1 $PY -W ignore -u -m tempest.generator.build_dataset --profiles $2 --out $1.part --rows $3 --first-year 1980 --last-year 2025 \
    --station-map models/station_map_mix.npz --features base --rh-target dpd --all-hours >> data/l3_hours_build.log 2>&1 && mv $1.part $1
}
build $NI $PN $ROWS_NIGHT || build $NI $PN $ROWS_NIGHT || { log build "FAILED night build"; exit 3; }
build $DA data/pilot/profiles80.zarr $ROWS_DAY || build $DA data/pilot/profiles80.zarr $ROWS_DAY || { log build "FAILED day build"; exit 3; }
if [ ! -f $A24 ]; then
  wait_gpu
  $PY -u scripts/concat_npz.py $A24.part $DA $NI --frac $FRAC >> data/l3_hours_build.log 2>&1 && mv $A24.part $A24 || { log build "FAILED concat"; exit 3; }
fi

# 3. train + calibrate + score (one GPU job at a time)
fit() {  # fit NAME DATA [train args]: train, calibrate on DATA 2021-23; returns 1 on failure
  local V=$1 D=$2; shift 2
  local M=models/l3_h_$V.pt C=models/l3_h_$V.calib2021.npz
  if [ ! -f $M ]; then
    for try in 1 2; do
      wait_gpu; log $V "train try $try ($*)"
      $PY -u -m tempest.generator.train --data $D --out $M.part --max-year 2023 --min-year 1991 --config configs/generator_p2f.toml "$@" > data/l3_train_h_$V.log 2>&1 && mv $M.part $M && break
    done
    [ -f $M ] || { log $V "FAILED train twice"; return 1; }
  fi
  if [ ! -f $C ]; then
    wait_gpu
    $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $D --year 2023 --from-year 2021 --rows 60000 --m 199 >> data/l3_calib_h_$V.log 2>&1 || { log $V "FAILED spread"; return 1; }
  fi
}
score() {  # score MODEL CALIB DATA TAG BASELINE_HEADLINE LABEL: copy the model to <stem>_TAG.pt (headline names follow the model)
  local S=${1%.pt}_$4.pt H=${1%.pt}_$4_cal2021_headline.csv
  cp $1 $S
  if [ ! -f $H ]; then
    wait_gpu
    $PY -W ignore -u -m tempest.scoring.score --model $S --data $3 --m 199 --first-test-year 2024 --last-test-year 2025 --calib $2 --extras > data/l3_score_h_$(basename ${S%.pt}).log 2>&1 || { log $4 "FAILED score $S"; return 1; }
  fi
  [ -n "$5" ] && { echo "== $(date '+%F %T') HOURS $6"; $PY scripts/compare_headline.py $5 $H; } >> $VLOG 2>&1
  log $4 "$(basename $S) scored"
}
dropped() {  # dropped VERDICT_LABEL: 0 if that comparison lost > 0.0006 mean skill15 or has a WORSE band
  awk -v L="HOURS $1" 'index($0, L) {f=1; next} f && /^== / {f=0} f' $VLOG | tail -40 \
    | awk '/^mean skill15/ {d = $4 - $6} /rule \(b\) FAIL/ {b = 1} END {exit !((d > 0.0006) || b)}'
}

# p2f at night: the baseline the all-hours models must beat there (p2f extrapolating into hours it never saw)
score $P2F.pt $P2F.calib2021.npz $NI night "" ""
PN_H=${P2F}_night_cal2021_headline.csv
fit all24 $A24 || exit 4
score models/l3_h_all24.pt models/l3_h_all24.calib2021.npz $NT day   ${P2F}_cal2021_headline.csv "all24 DAY (solar 06-21) vs p2f"
score models/l3_h_all24.pt models/l3_h_all24.calib2021.npz $NI night $PN_H "all24 NIGHT (solar 22-05) vs p2f extrapolating"
[ -f $DENF ] && [ -f $DENB ] && score models/l3_h_all24.pt models/l3_h_all24.calib2021.npz $DENF denfill $DENB "all24 DENVER fill zero-shot DAY vs p2f"

# 4. only if the day accuracy dropped significantly: two ways to keep it
if dropped "all24 DAY"; then
  log all "all24 day loss significant: trying x (p2f row density) and split (night-only model)"
  if [ ! -f $A24X ]; then
    wait_gpu; wait_room 30
    $PY -u scripts/concat_npz.py $A24X.part $DA $NI --frac 1 >> data/l3_hours_build.log 2>&1 && mv $A24X.part $A24X || log x "FAILED concat"
  fi
  if [ -f $A24X ] && fit all24x $A24X; then
    score models/l3_h_all24x.pt models/l3_h_all24x.calib2021.npz $NT day   ${P2F}_cal2021_headline.csv "all24x DAY (solar 06-21) vs p2f"
    score models/l3_h_all24x.pt models/l3_h_all24x.calib2021.npz $NI night $PN_H "all24x NIGHT (solar 22-05) vs p2f extrapolating"
  fi
  if fit night $NI; then
    score models/l3_h_night.pt models/l3_h_night.calib2021.npz $NI night $PN_H "split night-only NIGHT vs p2f extrapolating"
    [ -f models/l3_h_all24_night_cal2021_headline.csv ] && { echo "== $(date '+%F %T') HOURS split night-only NIGHT vs all24 NIGHT"; $PY scripts/compare_headline.py models/l3_h_all24_night_cal2021_headline.csv models/l3_h_night_night_cal2021_headline.csv; } >> $VLOG 2>&1
  fi
else
  log all "all24 day loss within tolerance: no alternatives needed"
fi
log all done
