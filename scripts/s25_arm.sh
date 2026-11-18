#!/bin/bash
# New_Plan 25.1 generic arm runner: one arm x one seed, train -> range calibration -> shear map -> lapse map -> score (a) and (b)
# -> shape diag (a) and (b) -> s25 extra shape metrics (a) and (b) -> Denver fill-top report. Steps skip when their output exists.
#   bash scripts/s25_arm.sh NAME SEED DELTA.toml [key=value ...]
# env: STEPS=n (training steps, default from the delta / c4w 6000)  STAGE=train (stop after training: GF2 screens)
#      INIT=model.pt (fine-tune start, F2)  NOSHUF=1 (maps fit and score without the shuffle: F3)  DRY=1 (print commands only)
#      PRE=1 (model already built by another script, e.g. GT2 pool / H5 compose: never train)
# Train 1991-2023 with the last 3 years held out for validation (val_years = 3 -> 2021-23), verdict years 2024-25 only.
# Outputs: models/s25/NAME_sSEED.* ; log lines: docs/results/logs/s25.log ; step logs: docs/results/logs/s25_NAME_sSEED_*.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
NAME=$1 SEED=$2 DELTA=$3
[ -n "$NAME" ] && [ -n "$SEED" ] && [ -f "$DELTA" ] || { echo "usage: s25_arm.sh NAME SEED DELTA.toml [key=value ...]"; exit 1; }
shift 3
A21=data/train/pilot80_l21_all24_dpd.npz DA=data/train/pilot80_l21_day_dpd.npz DEN=data/train/denver_full_fill_dpd.npz
T=${NAME}_s${SEED} D=models/s25 L=docs/results/logs
M=$D/$T.pt C=$D/$T.calib2021.npz CFG=configs/s25/gen/$T.toml
if [ "$NOSHUF" = "1" ]; then SH="" TAG=noshuf; else SH="--shuffle --template-cell 8" TAG=cell8; fi
SM=$D/${T}_smap_$TAG.npz LM=$D/${T}_lmap_$TAG.npz
mkdir -p $D configs/s25/gen
SHAPE_ARGS=${SHAPE_ARGS---blocks 7}   # HAR-block metrics for every arm and the base (GT1 compares them)
log() { [ "$DRY" = "1" ] && return; echo "$(date '+%F %T') [S25 $T] $*" >> $L/s25.log; }
# S25_PARALLEL=1: do not wait for a Mode F evaluation (UR15), only for other s25 jobs; RAM gate 4 GB instead of 6
if [ "$S25_PARALLEL" = "1" ]; then BUSYRE='generator.train|calibrate|scoring|pytest|diagnose|s25_'; RAMMIN=4; else BUSYRE='generator.train|calibrate|scoring|il6_modeF|pytest|diagnose|s25_'; RAMMIN=6; fi
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match '$BUSYRE' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
gpu_c() { nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | head -1 | tr -d '\r '; }
wait_free() { [ "$DRY" = "1" ] && return; while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt "$RAMMIN" ] || [ "${GPU_GATE:-0}" = "1" -a "$(gpu_c)" -ge 85 ]; do sleep 60; done; }
run() {  # run OUT LOGNAME cmd...  (skip when OUT exists)
  local out=$1 lg=$2; shift 2
  [ -e "$out" ] && return 0
  if [ "$DRY" = "1" ]; then echo "$*"; return 0; fi
  wait_free
  "$@" > $L/s25_${T}_$lg.log 2>&1 && log "$lg ok" || { log "FAILED $lg"; exit 2; }
}

# 1. config copy + train (GPU)
EXTRA=("seed=$SEED")
[ -n "$STEPS" ] && EXTRA+=("steps=$STEPS")
[ -n "$INIT" ] && EXTRA+=("init=\"$INIT\"")
PYTHONPATH=. $PY scripts/s25_cfg.py $DELTA $CFG "${EXTRA[@]}" "$@" > /dev/null || { log "FAILED config"; exit 2; }
if [ ! -f $M ]; then
  [ "$PRE" = "1" ] && { log "FAILED missing prebuilt model $M"; exit 2; }
  if [ "$DRY" = "1" ]; then echo "train $CFG -> $M"; else
    GPU_GATE=1 wait_free
    $PY -u -m tempest.generator.train --data $A21 --out $M.part --max-year 2023 --min-year 1991 --config $CFG > $L/s25_${T}_train.log 2>&1 \
      && mv $M.part $M && log trained || { log "FAILED train"; exit 2; }
  fi
fi
[ "$STAGE" = "train" ] && exit 0

# 2-4. range calibration on 2021-23, then the shear and lapse maps refit in order on the calibrated samples
run $C spread $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $A21 --year 2023 --from-year 2021 --rows 60000 --m 199
run $SM smap $PY -W ignore -u -m tempest.calibrate.shear_map --model $M --data $A21 --calib $C $SH --full --out $SM
run $LM lmap $PY -W ignore -u -m tempest.calibrate.lapse_map --model $M --data $A21 --calib $C --shear-map $SM $SH --out $LM

# 5-6. score (a) raw + range calibration, (b) full stack; verdict years 2024-25
run $D/${T}_cal2021_headline.csv score_a $PY -W ignore -u -m tempest.scoring.score --model $M --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 --seed 0 --calib $C --extras
if [ "$NOSHUF" = "1" ]; then BH=$D/${T}_cal2021_smap_lmap_headline.csv; else BH=$D/${T}_cal2021_smap_shufc8_lmap_headline.csv; fi
run $BH score_b $PY -W ignore -u -m tempest.scoring.score --model $M --data $DA --m 199 --first-test-year 2024 --last-test-year 2025 --seed 0 --calib $C $SH --shear-map $SM --lapse-map $LM

# 7-8. shape (diagnose metrics + s25 extras: shear p99 ratio, Ri<1, vcorr by separation, variogram) for (a) and (b)
run $D/${T}_diag_a.csv diag_a env PYTHONPATH=. $PY -W ignore scripts/diagnose.py $M $C $DA --out $D/${T}_diag_a
run $D/${T}_diag_b_$TAG.csv diag_b env PYTHONPATH=. $PY -W ignore scripts/diagnose.py $M $C $DA --out $D/${T}_diag_b_$TAG $SH --shear-map $SM --lapse-map $LM
run $D/${T}_s25shape_a.csv shape_a env PYTHONPATH=. $PY -W ignore scripts/s25_shape.py $M $C $DA --out $D/${T}_s25shape_a ${SHAPE_ARGS}
run $D/${T}_s25shape_b_$TAG.csv shape_b env PYTHONPATH=. $PY -W ignore scripts/s25_shape.py $M $C $DA --out $D/${T}_s25shape_b_$TAG $SH --shear-map $SM --lapse-map $LM ${SHAPE_ARGS}

# 9. Denver fill-top: a report, not a gate (score writes next to the model name, so score a copy; the calib hash is content based)
if [ ! -f $D/${T}_den_cal2021_headline.csv ]; then
  [ "$DRY" = "1" ] || cp $M $D/${T}_den.pt
  run $D/${T}_den_cal2021_headline.csv denver $PY -W ignore -u -m tempest.scoring.score --model $D/${T}_den.pt --data $DEN --m 199 --first-test-year 2024 --last-test-year 2025 --seed 0 --calib $C --extras
fi
log done
