#!/bin/bash
# F-V2 step 3 (CPU): NM/TX mode F retrained on the 00Z + 12Z rows (data/modeF_v2, all three valid hours, leads grouped by modeF.lead_bin) = models/modeF_v3, and the SHIPPED modeF_v2
# evaluated on the same rows (copy models/modeF_v2_onv2rows.pt, so the shipped calibration file is never rewritten), both with scripts/il6_modeF.py (same recipe as modeF_v2:
# width 128, depth 2, coarse 4, 1500 steps, lr 3e-4, wd 1e-2, 2 members; range map 2021, TEST 2022). Waits for the Denver mode F run ([FDEN] done). Log: data/l3.log [FV2T].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export OMP_NUM_THREADS=6 PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [FV2T] $*" >> data/l3.log; }
until grep -q '\[FDEN\] done' data/l3.log; do sleep 60; done
log start
R="--rows-dir data/modeF_v2 --width 128 --depth 2 --coarse 4 --steps 1500 --lr 3e-4 --wd 1e-2 --members 2"
$PY -W ignore -u scripts/il6_modeF.py $R --out models/modeF_v3.pt > data/il6_modeF_v3.log 2>&1 && log "v3 trained + evaluated" || log "FAILED v3"
[ -f models/modeF_v2_onv2rows.pt ] || cp models/modeF_v2.pt models/modeF_v2_onv2rows.pt
$PY -W ignore -u scripts/il6_modeF.py $R --out models/modeF_v2_onv2rows.pt > data/il6_modeF_v2_onv2rows.log 2>&1 && log "shipped v2 evaluated on v2 rows" || log "FAILED v2 on v2 rows"
log done
