#!/bin/bash
# GLOBAL_PLAN §9 Monte Carlo checks (user, 2026-11-06: "tested after the current tests whenever there is space on
# the GPU and memory"). Waits for the loop-3 queue and the fill-top rescore, then for an idle GPU (no train/score/
# calibrate python) and >= 9 GB free RAM before each score. Scores p2f and every loop-3 candidate with --mc at NM/TX
# and on the fill-top Denver set; model copies are named g9_* so no existing score file is overwritten.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
NT0=data/train/pilot80_dpd.npz DEN=data/train/denver_full_fill_dpd.npz
log() { echo "$(date '+%F %T') [G9] $*" >> data/l3.log; }
nproc_match() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='$1'\" | ? { \$_.CommandLine -match '$2' }).Count" | tr -d '\r'; }
free_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_room() {  # one GPU job at a time + RAM headroom (the 15:04 crash was RAM pressure)
  while [ "$(nproc_match python.exe 'generator.train|calibrate.spread|calibrate.joint|scoring.score')" != "0" ] || [ "$(free_gb)" -lt 9 ]; do sleep 300; done
}
log start
while [ "$(nproc_match bash.exe 'ap_l3_lean|ap_l3.sh|ap_l3_fill')" != "0" ]; do sleep 300; done
log "loop-3 queue done; scoring"
for V in p2f siren w768 terrain ctxsep sirenw15 studt; do
  if [ $V = p2f ]; then M=models/generator_80_p2f.pt C=models/generator_80_p2f.calib2021.npz X=
  else M=models/l3_$V.pt C=models/l3_$V.calib2021.npz; grep -q '^# l3-data: l3x' configs/generator_l3_$V.toml 2>/dev/null && X=_l3x || X=; fi
  [ -f $M ] && [ -f $C ] || { log $V "no model/calibration, skipped"; continue; }
  for S in nmtx den; do
    [ $S = nmtx ] && D=${NT0%.npz}$X.npz || D=${DEN%.npz}$X.npz
    G=models/g9_${V}_$S.pt
    [ -f $D ] || { log $V $S "no data $D, skipped"; continue; }
    [ -f ${G%.pt}_cal2021_mc.csv ] && continue
    wait_room
    cp $M $G
    $PY -W ignore -u -m tempest.scoring.score --model $G --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C --mc > data/g9_score_${V}_$S.log 2>&1 \
      && log $V $S "mc scored" || log $V $S "FAILED mc score"
  done
done
$PY - <<'EOF' > data/g9_verdicts.txt 2>&1
import glob, pandas as pd
fs = sorted(glob.glob("models/g9_*_cal2021_mc.csv"))
t = pd.concat([pd.read_csv(f).assign(run=f.split("g9_")[1].split("_cal2021")[0]) for f in fs])
t.to_csv("data/g9_mc_all.csv", index=False)
k = t[t.check.isin(["phys", "es", "derived", "filled"]) | ((t.check == "blend") & t.group.str.endswith("km"))]
k = k[(k.check != "es") | (k.group == "all")]
with pd.option_context("display.width", 250, "display.max_rows", 500, "display.float_format", "{:.4f}".format):
    print(k.pivot_table(index=["check", "group", "metric"], columns="run", values="model", sort=False).to_string())
EOF
log done
