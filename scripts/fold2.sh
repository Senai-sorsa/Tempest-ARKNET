#!/bin/bash
# Walk-forward fold 2 (PHASED_PLAN 5.3 E4): train 1991-2020 (validation 2018-20), calibrate 2018-20, test 2021-23, for the E12-style baseline and the adopted p2f
# configuration. Waits for the GPU to be free. Log: data/fold2.log. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
P=data/pilot/profiles80.zarr
log() { echo "$(date '+%F %T') $*" >> data/fold2.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights' }).Count" | tr -d '\r'; }
until grep -q "phase2 p35 done\|\[p35\] FAILED" data/phase2.log; do sleep 60; done
run() {  # name config data
  V=$1; CFG=$2; D=$3; M=models/generator_f2_$V.pt; C=models/generator_f2_$V.calib2018.npz
  while [ "$(busy)" != "0" ]; do sleep 30; done
  log "$V start"
  [ -f $M ] || { $PY -u -m tempest.generator.train --data $D --out $M.part --max-year 2020 --min-year 1991 --config $CFG > data/fold2_train_$V.log 2>&1 && mv $M.part $M; } || { log "FAILED train $V"; return 1; }
  log "$V trained"
  [ -f $C ] || $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $D --year 2020 --from-year 2018 --rows 60000 --m 199 >> data/fold2_$V.log 2>&1 || { log "FAILED spread $V"; return 1; }
  $PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2021 --last-test-year 2023 --calib $C > data/fold2_score_$V.log 2>&1 || { log "FAILED score $V"; return 1; }
  $PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles $P --m 199 --first-test-year 2021 --last-test-year 2023 --calib $C > data/fold2_sonde_$V.log 2>&1 || { log "FAILED sonde $V"; return 1; }
  log "$V done"
}
run e12 configs/generator.toml data/train/pilot80_smix.npz
run p2f configs/generator_p2f.toml data/train/pilot80_dpd.npz
log "fold2 done"
