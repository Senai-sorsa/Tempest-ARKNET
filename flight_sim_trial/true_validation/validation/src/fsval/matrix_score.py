"""Score results/matrix.json against measured truth and RAS. The combos are picked from on the same 23 flights they are
scored on, so the best-combo line is optimistic: the held-out test re-picks on random halves and scores the other half."""
import json
from statistics import mean, median

import numpy as np
from scipy import stats

from . import ROOT
from .matrix import FACTORS, combos, tag

SPLITS = 2000


def main() -> None:
    base = {r["case"]: r for r in json.loads((ROOT / "results" / "ras_cases.json").read_text()) if "fs_plain_ft" in r}
    cells = json.loads((ROOT / "results" / "matrix.json").read_text())
    cases = sorted(base)
    assert not set(cases) ^ {c["case"] for c in cells}
    idx = {c: i for i, c in enumerate(cases)}
    tags = [tag(c) for c in combos()]
    err = np.full((len(tags), len(cases)), np.nan)
    for c in cells:
        t = base[c["case"]]["truth_ft"]
        err[tags.index(c["tag"]), idx[c["case"]]] = 100 * (c["ft"] - t) / t
    assert not np.isnan(err).any()
    ras = np.array([100 * (base[c]["ras_ft"] - base[c]["truth_ft"]) / base[c]["truth_ft"] for c in cases])
    rpy = np.array([100 * (base[c]["rpy_ft"] - base[c]["truth_ft"]) / base[c]["truth_ft"] for c in cases])

    rows = []
    for t, e in zip(tags, err):
        p = stats.wilcoxon(abs(e), abs(ras)).pvalue if (abs(e) != abs(ras)).any() else 1.0
        rows.append({"tag": t, "median": float(np.median(abs(e))), "mean": float(abs(e).mean()), "bias": float(e.mean()),
                     "closer": int((abs(e) < abs(ras)).sum()), "p": float(p), "within5": int((abs(e) <= 5).sum())})
    rows.sort(key=lambda r: r["mean"])
    print(f"{'RAS':28} median {np.median(abs(ras)):.2f} mean {abs(ras).mean():.2f} bias {ras.mean():+.2f} within5 {(abs(ras) <= 5).sum()}")
    print(f"{'RocketPy':28} median {np.median(abs(rpy)):.2f} mean {abs(rpy).mean():.2f} bias {rpy.mean():+.2f} within5 {(abs(rpy) <= 5).sum()}")
    for r in rows[:8] + rows[-3:]:
        print(f"{r['tag']:28} median {r['median']:.2f} mean {r['mean']:.2f} bias {r['bias']:+.2f} within5 {r['within5']} closer-than-RAS {r['closer']}/23 wilcoxon p {r['p']:.3f}")
    n = len(rows)
    print("combos beating RAS on mean:", sum(r["mean"] < abs(ras).mean() for r in rows), "of", n,
          "| on median:", sum(r["median"] < np.median(abs(ras)) for r in rows),
          "| Bonferroni p<0.05:", sum(r["p"] * n < 0.05 and r["mean"] < abs(ras).mean() for r in rows))

    print("\nMain effect: mean change in |err| (pct pts), averaged over the other factors")
    all_c = combos()
    for f, levels in FACTORS.items():
        ref = np.array([abs(err[i]).mean() for i, c in enumerate(all_c) if c[f] == levels[0]])
        for lv in levels[1:]:
            on = np.array([abs(err[i]).mean() for i, c in enumerate(all_c) if c[f] == lv])
            print(f"  {f} {levels[0]} -> {lv}: {(on - ref).mean():+.2f} (range {(on - ref).min():+.2f} to {(on - ref).max():+.2f})")

    rng = np.random.default_rng(0)
    gains, wins = [], 0
    picks = {}
    for _ in range(SPLITS):
        p = rng.permutation(len(cases))
        train, test = p[: len(p) // 2], p[len(p) // 2 :]
        b = int(np.argmin(abs(err[:, train]).mean(axis=1)))
        picks[tags[b]] = picks.get(tags[b], 0) + 1
        gain = abs(ras[test]).mean() - abs(err[b, test]).mean()
        gains.append(gain)
        wins += gain > 0
    print(f"\nHeld-out ({SPLITS} random half splits): best-on-train beats RAS on test in {100 * wins / SPLITS:.0f} % of splits; "
          f"mean gain {mean(gains):+.2f} pts, median {median(gains):+.2f}")
    print("  picked most:", sorted(picks.items(), key=lambda kv: -kv[1])[:4])

    best = np.array([abs(err[tags.index(rows[0]["tag"])])]).ravel()
    print("\nBest combo by flight (err %):", rows[0]["tag"])
    for i, c in enumerate(cases):
        print(f"  {c[:26]:26} RAS {ras[i]:+6.1f}  best {err[tags.index(rows[0]['tag']), i]:+6.1f}")
    (ROOT / "results" / "matrix_scores.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
