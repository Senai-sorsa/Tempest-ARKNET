#!/bin/bash
# Denver export check (2026-11-10): the user approved re-exporting the Denver tool assets with the Denver-trained C4w (l3_blocal_c4w), but its PASS was against the Denver-trained p2f
# (l3_blocal), while the shipped Denver assets come from generator_denver.pt (tiny model, 2016-21, never scored on this footing). Before the export: score generator_denver.pt with its own
# calibration (calib2023) on the same rows (data/train/denver_full_dpd.npz, 2024-25, m 199, --extras) and compare it with l3_blocal_c4w. Export only if l3_blocal_c4w is not worse.
# Waits for [G3B] done (one GPU job, B27). Log: data/l3.log [DENEXP]; verdict data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
D=data/train/denver_full_dpd.npz
log() { echo "$(date '+%F %T') [DENEXP] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
until grep -q '\[G3B\] done' data/l3.log; do sleep 60; done
while [ "$(ram_gb)" -lt 6 ]; do sleep 60; done
log start
S=models/den_shipped_check
[ -f $S.pt ] || cp models/generator_denver.pt $S.pt
$PY -W ignore -u -m tempest.scoring.score --model $S.pt --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib models/generator_denver.calib2023.npz --extras > data/l3_score_den_shipped_check.log 2>&1 && log "den_shipped_check scored" || log "FAILED den_shipped_check score"
H=$(ls ${S}_*headline.csv 2>/dev/null | head -1)
{ echo "== $(date '+%F %T') DENEXP shipped Denver model (generator_denver.pt + calib2023) vs Denver-trained C4w (l3_blocal_c4w), denver_full_dpd 2024-25"
  [ -n "$H" ] && $PY scripts/compare_headline.py $H models/l3_blocal_c4w_cal2021_headline.csv || echo "  no headline for the shipped Denver model (see data/l3_score_den_shipped_check.log)"; } >> data/l3_verdicts.txt 2>&1
log done
