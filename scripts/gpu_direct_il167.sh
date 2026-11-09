#!/bin/bash
# IL-167 (2026-11-09): column-wise model blend before the shuffle. Main model = base (T, RH, surface), wind columns u, v from the C4w model, each range-calibrated with its own table
# (score --blend-wind / --blend-calib), then the base's shuffle, shear map and lapse map. In-box (l21, DAY seeds 0 / 1 / 2, NIGHT) against both parents: l21 + lapse map (models/l3_lapse*)
# and C4w + its lapse map (models/l3_c4wl_*). Denver zero-shot (shipped base + Denver trust, wind from generator_80_c4w) against generator_80_p2f + trust (l3_p2fden_fx) and the C4w
# version (l3_c4wden). Chained after gpu_direct_c4w80_t100.sh by "[T100X] done" (B27). Log: data/l3.log [IL167]; verdicts data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz NI=data/train/pilot80_l21_night_dpd.npz DEN=data/train/denver_full_fill_dpd.npz
B=models/l3_h_l21 W=models/l3_c4w LM=models/l3_lapse.lapsemap2021.npz
log() { echo "$(date '+%F %T') [IL167] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 8 ]; do sleep 60; done; }
until grep -q '\[T100X\] done' data/l3.log; do sleep 60; done
log start
H() { echo models/$1_cal2021_smap_shufc8_lmap_bw_headline.csv; }
for spec in "l3_bw_s0 $DA 0 l3_lapse l3_c4wl_s0" "l3_bw_s1 $DA 1 l3_lapse_s1 l3_c4wl_s1" "l3_bw_s2 $DA 2 l3_lapse_s2 l3_c4wl_s2" "l3_bw_night $NI 0 l3_lapse_night l3_c4wl_night"; do
  set -- $spec; P=models/$1.pt; [ -f $P ] || cp $B.pt $P
  if [ ! -f $(H $1) ]; then wait_ram; $PY -W ignore -u -m tempest.scoring.score --model $P --data $2 --m 199 --first-test-year 2024 --last-test-year 2025 --mc --seed $3 --calib $B.calib2021.npz \
      --blend-wind $W.pt --blend-calib $W.calib2021.npz --shuffle --template-cell 8 --shear-map $B.shearmap2021_cell8.npz --lapse-map $LM > data/l3_il167_$1.log 2>&1 && log "$1 scored" || { log "FAILED $1"; continue; }; fi
  for ref in $4 $5; do { echo "== $(date '+%F %T') IL167 blend (base T/RH + C4w wind) vs $ref ($1)"; $PY scripts/compare_headline.py models/${ref}_cal2021_smap_shufc8_lmap_headline.csv $(H $1); } >> data/l3_verdicts.txt 2>&1; done
done
P=models/l3_bwden.pt; [ -f $P ] || cp models/generator_80_p2f.pt $P
HD=models/l3_bwden_cal2021_trust_smap_shufc8_bw_headline.csv
if [ ! -f $HD ]; then wait_ram; $PY -W ignore -u -m tempest.scoring.score --m 199 --first-test-year 2024 --last-test-year 2025 --mc --model $P --data $DEN --calib models/generator_80_p2f.calib2021.npz \
    --trust models/l3_p2fden.trust2021.npz --blend-wind models/generator_80_c4w.pt --blend-calib models/generator_80_c4w.calib2021.npz --shuffle --template-cell 8 --shear-map models/generator_80_p2f.shearmap2021_cell8.npz > data/l3_il167_den.log 2>&1 && log "Denver scored" || log "FAILED Denver"; fi
for ref in l3_p2fden_fx l3_c4wden; do [ -f $HD ] && { echo "== $(date '+%F %T') IL167 Denver blend vs $ref"; $PY scripts/compare_headline.py models/${ref}_cal2021_trust_smap_shufc8_headline.csv $HD; } >> data/l3_verdicts.txt 2>&1; done
log done
