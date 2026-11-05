import sys, numpy as np, pandas as pd, io
for f in sys.argv[1:]:
    L = open(f, encoding="utf-8").read().splitlines()
    i = next(k for k, s in enumerate(L) if "coverage by month" in s)
    rows = [s.split() for s in L[i + 3:i + 15]]
    cols = L[i + 1].split()[1:]
    t = pd.DataFrame([r[1:] for r in rows], columns=cols, dtype=float)
    rng = np.random.default_rng(0)
    b = t.to_numpy()[rng.integers(0, 12, (20000, 12))].mean(1)  # resample months (equal weight; shortcut: ignores row counts)
    lo, hi = np.percentile(b, [2.5, 97.5], axis=0)
    print(f, " ".join(f"{c}={m:.4f}[{l:.4f},{h:.4f}]" for c, m, l, h in zip(cols, t.mean(), lo, hi)))
