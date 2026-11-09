#!/bin/bash
# L21 Denver part (2026-11-09): the Denver box is served zero-shot by the NM/TX model + a trust layer fitted on Denver 2021-23 (+ NM/TX shear map + shuffle c8): reference
# models/l3_p2fden_fx_cal2021_trust_smap_shufc8_headline.csv (generator_80_p2f; ap_l3_debias.sh). Same recipe with the C4w shipped-model retrain (models/generator_80_c4w, its own
# calibration and shear map, trust fitted on Denver 2021-23 the same way), scored on the same Denver day rows. One runner (B27). Log: data/l3.log [DENC4W]; verdicts data/l3_verdicts.txt.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DEN=data/train/denver_full_fill_dpd.npz M=models/generator_80_c4w P=models/l3_c4wden
log() { echo "$(date '+%F %T') [DENC4W] $*" >> data/l3.log; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_ram() { while [ "$(ram_gb)" -lt 8 ]; do sleep 60; done; }
log start
[ -f $P.pt ] || cp $M.pt $P.pt
[ -f $P.trust2021.npz ] || { wait_ram; $PY -W ignore -u -m tempest.calibrate.trust --model $P.pt --data $DEN --calib $M.calib2021.npz --from-year 2021 --year 2023 --m 199 > data/l3_denc4w_trust.log 2>&1 && log "trust fitted" || { log "FAILED trust"; exit 2; }; }
H1=${P}_cal2021_trust_smap_shufc8_headline.csv H0=models/l3_p2fden_fx_cal2021_trust_smap_shufc8_headline.csv
[ -f $H1 ] || { wait_ram; $PY -W ignore -u -m tempest.scoring.score --m 199 --first-test-year 2024 --last-test-year 2025 --mc --model $P.pt --data $DEN --calib $M.calib2021.npz --trust $P.trust2021.npz \
  --shuffle --template-cell 8 --shear-map $M.shearmap2021_cell8.npz > data/l3_denc4w_score.log 2>&1 && log "scored" || { log "FAILED score"; exit 3; }; }
[ -f $H0 ] && [ -f $H1 ] && { echo "== $(date '+%F %T') DENC4W Denver zero-shot: shipped-model C4w + Denver trust vs generator_80_p2f + Denver trust (day)"; $PY scripts/compare_headline.py $H0 $H1; } >> data/l3_verdicts.txt 2>&1
log done
