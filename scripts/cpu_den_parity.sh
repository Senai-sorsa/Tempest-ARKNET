#!/bin/bash
# IL-181 / IL-184 CPU chain (2026-11-10): after the Denver correlation refits ([CDEN2]): (1) regression check, the NM/TX distance table refitted with the NaN-aware fitter (defaults) must equal
# the shipped models/coherence_distcorr.npz; (2) Denver w targets from the Earthmover omega store for the Denver all-hours / day / night files (build_wdata --from-cond).
# Log: data/l3.log [DENPAR].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
export PYTHONPATH=.
PY=.venv/Scripts/python
log() { echo "$(date '+%F %T') [DENPAR] $*" >> data/l3.log; }
until grep -q 'CDEN2\] done' data/l3.log; do sleep 30; done
S=/c/Users/Senai/AppData/Local/Temp/claude/7aa02992b551459b/b8aae288-f9e2-487c-9fb5-53d906f61b26/scratchpad
$PY -W ignore -u scripts/c2_fit_distcorr.py --out $S/distcorr_regress.npz > data/c2_regress.log 2>&1
$PY -c "import numpy as np; a=np.load('models/coherence_distcorr.npz'); b=np.load('$S/distcorr_regress.npz'); print('NM/TX distance table regression: same km', np.array_equal(a['km'], b['km']), 'max |rho diff|', float(np.nanmax(np.abs(a['rho']-b['rho']))))" >> data/c2_regress.log 2>&1
log "$(tail -1 data/c2_regress.log)"
for f in fill_all24 "" fill_night; do
  D=data/train/denver_full${f:+_$f}_dpd.npz O=data/train/denver_full${f:+_$f}_w.npz
  [ -f $O ] || $PY -W ignore -u -m tempest.generator.build_wdata --from-cond --data $D --w data/raw/era5_em_denver_full/w.zarr --out $O > data/wden_${f:-day}.log 2>&1 && log "w built $O" || log "FAILED w $D"
done
log done
