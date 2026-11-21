"""28.5 freeze check: compare the frozen assets with the shipped ones array by array. Only the planned swaps may differ
(X4-R net + meta, calib, shear / lapse maps, new ur5 table, new ENSF2 network); every other array must be identical.
    PYTHONPATH=. python scripts/freeze_diff.py SHIPPED_DIR FROZEN_DIR"""
import re
import sys

import numpy as np

ALLOWED = re.compile(r"^(m\d+|norm\d+|meta|x4r)/|^meta$|^calib/|^post/(smap|lmap|ur5)_|^modefens")


def main(a, b):
    A, B = np.load(f"{a}/model.npz"), np.load(f"{b}/model.npz")
    ka, kb = set(A.files), set(B.files)
    gone = sorted(ka - kb)
    new, changed, same = sorted(kb - ka), [], 0
    for k in sorted(ka & kb):
        if np.array_equal(A[k], B[k]):
            same += 1
        elif re.match(r"^modef_ridge/L\d+/W$", k) and np.allclose(A[k], B[k], rtol=1e-5, atol=1e-6):
            same += 1                                                              # BLAS solve order: float32 rounding only (2026-11-21: rel <= 5e-7)
            print(f"note: {k} equal within rtol 1e-5 (max abs {np.abs(A[k].astype(float) - B[k]).max():.2e})")
        else:
            changed.append(k)
    bad = [k for k in gone + new + changed if not ALLOWED.search(k)]
    print(f"identical {same}, changed {len(changed)}, new {len(new)}, removed {len(gone)}")
    print("changed:", sorted({k.split('/')[0] for k in changed}), "new:", sorted({k.rsplit('/', 1)[0] for k in new}), "removed:", gone)
    for f in ("indices.npz", "grid.npz"):
        x, y = np.load(f"{a}/{f}"), np.load(f"{b}/{f}")
        if not (set(x.files) == set(y.files) and all(np.array_equal(x[k], y[k]) for k in x.files)):
            if f == "grid.npz":
                bad.append(f)
            else:                                                                  # indices are re-read from data/raw/indices: newer months are expected
                print(f"note: {f} differs (months shipped {x['months'][-1]}, frozen {y['months'][-1]})")
    assert any(k.startswith("post/ur5_") for k in new) and any(k.startswith("modefens") for k in new), "ur5 / ENSF2 missing"
    assert "post/rank" not in changed and "post/rank_extra" not in changed, "templates differ from shipped"
    if bad:
        print("UNEXPECTED differences:", bad)
        sys.exit(1)
    print("OK: only the planned swaps differ")


if __name__ == "__main__":
    main(*sys.argv[1:3])
