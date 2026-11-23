"""Earth-GRAM wind-spread sensitivity (ruscale) without rerunning GRAM. REPORT ONLY.
GRAM's ruscale multiplies the wind perturbation about GRAM's own mean: with the same seed, a real ruscale=1.4 run equals
mean + 1.4 * (member - mean) to 0.012 m/s (output rounding; checked on 2 cases, b9_earthgram_run.py --ruscale 1.4 --limit 2).
Writes data/kit/earthgram_<variant>_ru<s>.npz in the kit's --extra format.

    .venv/Scripts/python new_plan_kit/b9_earthgram_scale.py --variant ncep --ruscale 1.2 1.3 1.5
"""
import argparse
import os

import numpy as np

KIT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "kit")


def scale(m, mean, s):
    return mean + s * (m - mean)


if __name__ == "__main__":
    assert np.allclose(scale(np.array([1.0, 3.0]), 2.0, 1.5), [0.5, 3.5])
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="ncep")
    ap.add_argument("--ruscale", type=float, nargs="+", required=True)
    a = ap.parse_args()
    d, c = np.load(os.path.join(KIT, f"earthgram_{a.variant}.npz")), np.load(os.path.join(KIT, f"earthgram_{a.variant}_clim.npz"))
    assert (d["case"] == c["case"]).all()
    for s in a.ruscale:
        out = {k: d[k] for k in ("case", "T", "p")}
        out |= {q: scale(d[q], c[f"{q}_mean"][:, None].astype(np.float32), np.float32(s)) for q in ("u", "v")}
        np.savez_compressed(os.path.join(KIT, f"earthgram_{a.variant}_ru{s:g}.npz"), **out)
        print(f"wrote earthgram_{a.variant}_ru{s:g}.npz")
