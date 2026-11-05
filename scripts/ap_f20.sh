#!/bin/bash
# F-20 + F-35 (+ the dataset half of F-24): rebuild the training set with the blended station correction and provenance sidecar, retrain the p2f configuration on it, judge on balloons (independent truth)
# and on its own ERA5-type targets (different truth: the blend changes the targets, so ERA5 numbers are not comparable one to one with p2f). Build runs now (CPU/disk); training waits for the GPU chain. Never edit while running.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
source scripts/cap_cpu.sh
PY=.venv/Scripts/python
D=data/train/pilot80_dpdblend.npz
[ -f $D ] || PYTHONPATH=. $PY -W ignore -u -m tempest.generator.build_dataset --profiles data/pilot/profiles80.zarr --out $D.part --first-year 1980 --last-year 2026 --station-map models/station_map_mix.npz --features base --rh-target dpd --station-blend --sidecar > data/ap_f20_build.log 2>&1 && mv $D.part $D
echo "$(date '+%F %T') f20 build done" >> data/ap_f20.log
until grep -q "fgpu done" data/ap_fgpu.log 2>/dev/null; do sleep 60; done
sleep 60
cp configs/generator_p2f.toml configs/generator_p2fblend.toml
VAR=p2fblend FEAT=base DS=pilot80_dpdblend bash scripts/phase2_variant.sh >> data/ap_f20_chain.log 2>&1
A=models/generator_80_p2f; B=models/generator_80_p2fblend
{ echo "== F-20 p2fblend vs p2f (balloons: independent truth)"; $PY scripts/compare_headline.py ${A}_sonde_cal2021_headline.csv ${B}_sonde_cal2021_headline.csv | tail -5
  echo "== F-20 p2fblend vs p2f (ERA5-type targets of its OWN dataset: different truth, indicative only)"; $PY scripts/compare_headline.py ${A}_cal2021_headline.csv ${B}_cal2021_headline.csv | tail -5; } >> data/ap_s_verdicts.txt 2>&1
echo "$(date '+%F %T') f20 done" >> data/ap_f20.log
