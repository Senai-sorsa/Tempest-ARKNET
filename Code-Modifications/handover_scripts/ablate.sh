#!/bin/bash
# Members ablation: E12 with its first k members (no retrain); range map refitted per k as E12's was.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
export OMP_NUM_THREADS=12 PYTHONPATH=.
PY=.venv/Scripts/python
D=data/train/pilot80_smix.npz
for k in 1 2; do
  M=models/ablate_mem$k.pt
  [ -f $M ] || $PY -c "import torch,sys; c=torch.load('models/generator_80_b0smix.pt',map_location='cpu',weights_only=True); torch.save({'members': c['members'][:$k]}, sys.argv[1])" $M
  C=models/ablate_mem$k.calib2021.npz
  [ -f $C ] || $PY -W ignore -u -m tempest.calibrate.spread --model $M --data $D --year 2023 --from-year 2021 --rows 60000 --m 199 > data/abl${k}_spread.log 2>&1 || { echo "k=$k spread failed" >> data/abl.err; continue; }
  $PY -W ignore -u -m tempest.scoring.score --model $M --data $D --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C > data/abl${k}_era.log 2>&1 || echo "k=$k score failed" >> data/abl.err
  $PY -W ignore -u -m tempest.scoring.sonde --model $M --data $D --profiles data/pilot/profiles80.zarr --m 199 --first-test-year 2024 --last-test-year 2025 --calib $C > data/abl${k}_sonde.log 2>&1 || echo "k=$k sonde failed" >> data/abl.err
done
echo done >> data/abl.err
