#!/bin/bash
# G5 packaging (docs/plans/GLOBAL_PLAN.md G5). Never G6 (scripts/final_test_global.sh, run once, not from here).
# Usage: scripts/global/g5.sh [MODEL]          default: the first pooled G4 model results/G4/pool_*.pt
#   (1) ONNX export of the generator: FP32 + dynamic INT8 (+ FP16 when onnxconverter-common is installed)
#   (2) gates (tempest.export_onnx): INT8 vs FP32 CRPS within 0.3 %, 99.9th shear within 1 %, 100 samples < 250 ms on
#       4 threads, INT8 graph < 75 MB -> models/global/onnx/gates.json
#   (3) bundle: INT8 graph + spread calibration + climatology + Koppen + AOA + EGPD + balloon correction + tropopause
#       tables copied to models/global/bundle, total < 75 MB -> results/G5/bundle.csv
# Needs: uv pip install onnx onnxruntime onnxconverter-common
G=G5; . "$(dirname "$0")/g_common.sh"
M=${1:-$(ls results/G4/pool_*_s*.pt 2>/dev/null | head -1)}
[ -n "$M" ] && { [ -f "$M" ] || [ -n "${DRY:-}" ]; } || { echo "no G4 model (run scripts/global/g4.sh first, or pass MODEL)" >&2; exit 1; }
[ -n "${DRY:-}" ] || $PY -c "import onnx, onnxruntime" || { echo "missing onnx / onnxruntime: uv pip install onnx onnxruntime onnxconverter-common" >&2; exit 1; }
ONNX=models/global/onnx; B=models/global/bundle
step export $PY -W ignore -u -m tempest.export_onnx --model "$M" --data data/train/g4_global.npz --out $ONNX --first-year 2024
step bundle $PY -c "
import json, os, shutil, sys
m, onnx_dir, b, out = sys.argv[1:5]
parts = [os.path.join(onnx_dir, 'generator_int8.onnx'), os.path.join(onnx_dir, 'gates.json'), m[:-3] + '.calib2021.npz'] + \
        ['models/global/' + f for f in ('clim_2deg.npz', 'koppen.npz', 'aoa.npz', 'egpd.npz', 'balloon_cov.npz', 'tropo_clim.npz')]
miss = [p for p in parts if not os.path.exists(p)]
if miss:
    sys.exit('bundle: missing ' + ', '.join(miss))
os.makedirs(b, exist_ok=True)
rows = [(os.path.basename(p), os.path.getsize(p) / 1e6) for p in parts]
for p in parts:
    shutil.copy2(p, b)
tot = sum(s for _, s in rows)
gates = json.load(open(os.path.join(onnx_dir, 'gates.json')))
with open(out, 'w') as fh:
    fh.write('file,mb\n' + ''.join(f'{n},{s:.2f}\n' for n, s in rows) + f'TOTAL,{tot:.2f}\n')
ok = tot < 75 and gates.get('pass_all')
print(f'bundle {tot:.1f} MB (< 75), export gates {\"PASS\" if gates.get(\"pass_all\") else \"FAIL\"}: G5', 'PASS' if ok else 'FAIL')
" "$M" $ONNX $B $OUT/bundle.csv
log "G5 finished for $M; bundle in $B, sizes in $OUT/bundle.csv; return results/G5 + $ONNX/gates.json (docs/global/RESULTS_FORMAT.md)"
