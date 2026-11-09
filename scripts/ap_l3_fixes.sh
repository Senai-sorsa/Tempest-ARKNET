#!/bin/bash
# Fix verifications (user order 2026-11-07: fixes before new ideas). Three opt-in fixes, each compared with its existing baseline on the same data and seed:
#   L3-46 (IL-143)  --mask-filled: the Denver fill-top models of L3-43 (mask OFF = l3_blf, ON = l3_blfm) rescored with the filled heights left out of the headline (no retrain)
#   L3-47 (IL-141)  trust weights smoothed over height (--smooth-w-m 700) on the Denver trust stack of L3-29, vs the unsmoothed trust headline + physics rows
#   L3-48 (IL-142)  debias in logit space for humidity (--rh-logit), alone and with trust, vs the L3-34 physical-space debias headlines
# Model files are COPIES with new names so no earlier result file is overwritten; calibration and trust files are reused (they carry the model's content hash, the copies are identical).
# Waits for no other loop-3 queue, no GPU or build job and >= 6 GB free RAM. Every step skips when its output exists and is retried once. Log: data/l3.log [FIX]; verdicts: data/l3_verdicts.txt.
# Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
VLOG=data/l3_verdicts.txt
DEN=data/train/denver_full_fill_dpd.npz DENIDX=data/train/denver_full_fill_idx_dpd.npz
log() { echo "$(date '+%F %T') [FIX] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|build_dataset|to_heights|l3_overlay|concat_npz|igra_to_heights|shear_map|debias' }).Count" | tr -d '\r'; }
queues() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_l3_(?!fixes)|ap_l3\.sh|ap_g9' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_gpu() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
verdict() {  # verdict TITLE BASE_HEADLINE NEW_HEADLINE [BASE_MC NEW_MC]
  [ -f $2 ] && [ -f $3 ] || { log "verdict skipped (missing $2 or $3)"; return 0; }
  { echo "== $(date '+%F %T') $1"; $PY scripts/compare_headline.py $2 $3
    if [ -n "$4" ] && [ -f $4 ] && [ -f $5 ]; then echo "physics rows (base | new):"; grep -E "superadiabatic|shear_gt|sfc_jump" $4 | sed 's/^/  base /'; grep -E "superadiabatic|shear_gt|sfc_jump" $5 | sed 's/^/  new  /'; fi; } >> $VLOG 2>&1
}
run_score() {  # run_score LABEL OUTPUT_HEADLINE ARGS...   (retry once)
  local label=$1 out=$2; shift 2
  [ -f $out ] && return 0
  for try in 1 2; do
    wait_gpu; log "$label score try $try"
    $PY -W ignore -u -m tempest.scoring.score --m 199 --first-test-year 2024 --last-test-year 2025 "$@" > data/l3_fix_$label.log 2>&1 && [ -f $out ] && { log "$label scored"; return 0; }
  done
  log "$label FAILED"; return 1
}

log "waiting for the loop-3 queue, GPU, builds and 6 GB RAM"
while :; do
  [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && { sleep 120; [ "$(queues)" = "0" ] && [ "$(busy)" = "0" ] && break; }
  sleep 300
done
log start

# ---------------- L3-46 / IL-143: rescore the L3-43 models with the filled heights masked
if [ -f models/l3_blf.pt ] && [ -f models/l3_blfm.pt ] && [ -f $DENIDX ]; then
  [ -f models/l3_mfa.pt ] || cp models/l3_blf.pt models/l3_mfa.pt
  [ -f models/l3_mfb.pt ] || cp models/l3_blfm.pt models/l3_mfb.pt
  run_score mfa models/l3_mfa_cal2021_headline.csv --model models/l3_mfa.pt --data $DENIDX --calib models/l3_blf.calib2021.npz --extras --mask-filled
  run_score mfb models/l3_mfb_cal2021_headline.csv --model models/l3_mfb.pt --data $DENIDX --calib models/l3_blfm.calib2021.npz --extras --mask-filled
  verdict "L3-46 fill_mask rescored with --mask-filled (IL-143): mask OFF model vs ON model, filled heights left out" models/l3_mfa_cal2021_headline.csv models/l3_mfb_cal2021_headline.csv
else
  log "L3-46 skipped: missing L3-43 models or the fill-top file"
fi

# ---------------- L3-47 / IL-141: trust weights smoothed over height (Denver trust stack of L3-29)
C=models/generator_80_p2f.calib2021.npz MS=models/l3_p2fden_sm.pt
[ -f $MS ] || cp models/generator_80_p2f.pt $MS
if [ ! -f ${MS%.pt}.trust2021.npz ]; then
  for try in 1 2; do
    wait_gpu; log "trust smoothed fit try $try"
    $PY -W ignore -u -m tempest.calibrate.trust --model $MS --data $DEN --calib $C --from-year 2021 --year 2023 --m 199 --smooth-w-m 700 > data/l3_fix_trust_fit.log 2>&1 && [ -f ${MS%.pt}.trust2021.npz ] && break
  done
fi
if [ -f ${MS%.pt}.trust2021.npz ]; then
  run_score trustsm models/l3_p2fden_sm_cal2021_trust_headline.csv --model $MS --data $DEN --calib $C --trust ${MS%.pt}.trust2021.npz --mc
  verdict "L3-47 trust weights smoothed over height sigma 700 m (IL-141) vs the L3-29 step weights, Denver" models/l3_p2fden_cal2021_trust_headline.csv models/l3_p2fden_sm_cal2021_trust_headline.csv models/l3_p2fden_cal2021_trust_mc.csv models/l3_p2fden_sm_cal2021_trust_mc.csv
else
  log "L3-47 FAILED trust fit"
fi

# ---------------- L3-48 / IL-142: humidity debias in logit space
MR=models/l3_p2fden_rl.pt T=models/l3_p2fden.trust2021.npz
[ -f $MR ] || cp models/l3_p2fden.pt $MR
if [ ! -f ${MR%.pt}.debias2021.npz ]; then
  for try in 1 2; do
    wait_gpu; log "debias rh-logit fit try $try"
    $PY -W ignore -u -m tempest.scoring.debias --model $MR --calib $C --data $DEN --from-year 2021 --year 2023 --rh-logit > data/l3_fix_debias_fit.log 2>&1 && [ -f ${MR%.pt}.debias2021.npz ] && break
  done
fi
if [ -f ${MR%.pt}.debias2021.npz ]; then
  run_score rlalone models/l3_p2fden_rl_cal2021_debias_headline.csv --model $MR --data $DEN --calib $C --debias ${MR%.pt}.debias2021.npz --mc
  verdict "L3-48 humidity debias in logit space (IL-142) ALONE vs the L3-34 physical-space debias, Denver" models/l3_p2fden_cal2021_debias_headline.csv models/l3_p2fden_rl_cal2021_debias_headline.csv models/l3_p2fden_cal2021_debias_mc.csv models/l3_p2fden_rl_cal2021_debias_mc.csv
  run_score rltrust models/l3_p2fden_rl_cal2021_debias_trust_headline.csv --model $MR --data $DEN --calib $C --debias ${MR%.pt}.debias2021.npz --trust $T --mc
  verdict "L3-48 humidity debias in logit space (IL-142) + trust vs the L3-34 debias + trust, Denver" models/l3_p2fden_cal2021_debias_trust_headline.csv models/l3_p2fden_rl_cal2021_debias_trust_headline.csv models/l3_p2fden_cal2021_debias_trust_mc.csv models/l3_p2fden_rl_cal2021_debias_trust_mc.csv
else
  log "L3-48 FAILED debias fit"
fi
log done
