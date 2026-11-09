#!/bin/bash
# Confirmation of C4W80 (2026-11-09): the shipped stack + lapse map (generator_80_p2f, L21b) and the C4w retrain of the shipped model with its own stack + lapse map, both scored on DAY score
# seeds 1 and 2 on data/train/pilot80_dpd.npz, paired. Chained after gpu_direct_c4w80.sh by its "[C4W80] done" line (B27). Waits for >= 8 GB free RAM before each score (they hold ~14 GB).
# Log: data/l3.log [C4W80C]; verdicts data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
D=data/train/pilot80_dpd.npz B=models/generator_80_p2f M=models/generator_80_c4w
log() { echo "$(date '+%F %T') [C4W80C] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 8 ]; do sleep 60; done; }
until grep -q '\[C4W80\] done' data/l3.log; do sleep 60; done
[ -f $M.lapsemap2021.npz ] || { log "FAILED: no C4W80 stack"; exit 1; }
log start
H() { echo models/$1_cal2021_smap_shufc8_lmap_headline.csv; }
score() {  # score STEM SRC_MODEL_STEM SEED
  local P=models/$1.pt; [ -f $P ] || cp $2.pt $P; [ -f $(H $1) ] && return 0; wait_ram
  $PY -W ignore -u -m tempest.scoring.score --model $P --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $3 --calib $2.calib2021.npz --shuffle --template-cell 8 \
    --shear-map $2.shearmap2021_cell8.npz --lapse-map $2.lapsemap2021.npz > data/l3_c4w80c_$1.log 2>&1 && log "$1 scored" || log "FAILED $1"
}
for s in 1 2; do
  score g80lm_lmap_s$s $B $s
  score g80c4w_s$s $M $s
  [ -f $(H g80lm_lmap_s$s) ] && [ -f $(H g80c4w_s$s) ] && { echo "== $(date '+%F %T') C4W80C shipped-model C4w + lapse map vs shipped + lapse map, DAY seed $s (pilot80_dpd)"; $PY scripts/compare_headline.py $(H g80lm_lmap_s$s) $(H g80c4w_s$s); } >> data/l3_verdicts.txt 2>&1
done
log done
