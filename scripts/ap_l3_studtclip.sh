#!/bin/bash
# LOOP3 L3-30: studt with its Student-t noise clipped at |t| <= 3 instead of 8 (model noise_t["clip"]), no retraining:
# a copy of l3_studt.pt with the clip set, recalibrated on 2021-23 and scored with --mc at NM/TX and on the fill-top Denver set.
# Waits for the L3-29 runner, then for an idle GPU and >= 9 GB free RAM before each step.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
NT=data/train/pilot80_dpd.npz DEN=data/train/denver_full_fill_dpd.npz M=models/l3_studtc3.pt
log() { echo "$(date '+%F %T') [L3-30] $*" >> data/l3.log; }
nproc_match() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='$1'\" | ? { \$_.CommandLine -match '$2' }).Count" | tr -d '\r'; }
free_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_room() { while [ "$(nproc_match python.exe 'generator.train|calibrate.spread|calibrate.joint|calibrate.trust|scoring.score')" != "0" ] || [ "$(free_gb)" -lt 9 ]; do sleep 120; done; }
while [ "$(nproc_match bash.exe 'ap_l3_trustdi')" != "0" ]; do sleep 120; done
log start
$PY - <<'PY' || { log "FAILED clip copy"; exit 1; }
import torch
ck = torch.load("models/l3_studt.pt", map_location="cpu", weights_only=False)
for mb in ck["members"]:  # ensemble checkpoint: model_kw per member
    mb["model_kw"]["noise_t"]["clip"] = 3.0
torch.save(ck, "models/l3_studtc3.pt")
print([mb["model_kw"]["noise_t"] for mb in ck["members"]])
PY
wait_room
$PY -W ignore -u -m tempest.calibrate.spread --model $M --data $NT --year 2023 --from-year 2021 --rows 60000 --m 199 > data/l3_calib_studtc3.log 2>&1 \
  && log "calibrated" || { log "FAILED spread"; exit 1; }
C=${M%.pt}.calib2021.npz
for S in nmtx den; do
  [ $S = nmtx ] && D=$NT G=$M || { D=$DEN; G=models/l3_studtc3_den.pt; cp $M $G; cp $C ${G%.pt}.calib2021.npz; }
  wait_room
  $PY -W ignore -u -m tempest.scoring.score --model $G --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --extras --mc > data/l3_score_studtc3_$S.log 2>&1 \
    && log "$S scored" || log "FAILED $S score"
done
log done
