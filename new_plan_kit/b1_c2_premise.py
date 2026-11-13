"""C2 premise check: is the excess shear / unstable air made by the SHUFFLE or by the NETWORK? DECISION RULE BELOW.
Rows of 2023 (truth). For every row, sample sets of 199 members, all scored the same way:
  real rows              199 real profiles of the row's group (grid block x month x hour bin, years before 2023) = a perfect model
  real rows + shuffle    the same set after the shuffle with 199 OTHER real profiles as template
  model                  the shipped network after the range map
  model + shuffle        the same after the shuffle
Scores = the two "phys" rates of tempest/scoring/mc.py (violations): share of members with
  unstable   a layer above 200 m that is more than 1 K beyond dry-adiabatic
  shear      a layer whose shear is beyond the 99.99th percentile of 2023 truth rows
Old numbers (IL-160, unstable | shear): network 0.152|0.0004, + range map 0.239|0.0027, + shuffle 0.324|0.0387, shipped 0.324|0.0145, ERA5 0.199|0.0082.
DECISION: fraction = (real+shuffle minus real) / (model+shuffle minus real), per score. A score whose denominator is under its noise floor
(0.02 unstable, 0.005 shear) is ignored.
  both ignored          -> NO EXCESS: C2 is not needed. Skip the C2 GPU fine-tune and b2_group_rank_shuffle.py.
  mean fraction >= 0.5  -> the fault is the SHUFFLE: run b2_group_rank_shuffle.py on the CPU, skip the GPU fine-tune.
  mean fraction <  0.5  -> the fault is the NETWORK: do the C2 GPU fine-tune (not built; recipe in new_plan_kit/README.md).

    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_c2_premise.py --device cpu     # about 10 min, 3 GB RAM
    KIT_SMOKE=1 PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_c2_premise.py --device cpu --rows 30   # smoke test
Result: docs/results/logs/kit_b1_c2_premise.log
"""
import argparse

import numpy as np

import kit_common as K
from b1_build_pool import stages

FLOOR = (0.02, 0.005)     # noise floor of (unstable, shear) rate differences at 1500 rows


def scores(x, thr):
    """x (..., 179) physical -> (unstable rate, shear rate) over all leading axes."""
    from tempest.scoring import mc
    v = mc.violations(x, thr)
    return float(v["superadiabatic_gt1K"].mean()), float(v["shear_gt_era5_9999"].mean())


def thresholds(d):
    """d = open dataset -> (thr dict for mc.violations, the truth rows used): from up to 40000 truth rows of 2023 (mc.write uses the scored truth rows)."""
    from tempest.generator.sample import to_physical
    from tempest.scoring import mc
    all23 = np.flatnonzero(np.asarray(d["year"]) == 2023)
    t = to_physical(np.asarray(d["target"][np.sort(np.random.default_rng(3).choice(all23, min(40000, len(all23)), replace=False))])).astype(np.float64)
    T, u, v = t[:, mc.IT:mc.IT + mc.N], t[:, mc.IU:mc.IU + mc.N], t[:, mc.IV:mc.IV + mc.N]
    return dict(shear=np.quantile(np.hypot(np.diff(u, axis=-1), np.diff(v, axis=-1)) / mc.DZ, 0.9999, axis=0), sfc=np.quantile(np.abs(t[:, 4 * mc.N] - T[:, 0]), 0.999)), t


def decide(real, real_s, model_s):
    """Each = (unstable, shear). -> (mean fraction or None when both scores are under the floor, list of per-score fractions / None)."""
    fr = [float(np.clip((real_s[i] - real[i]) / (model_s[i] - real[i]), 0.0, 1.0)) if model_s[i] - real[i] > FLOOR[i] else None for i in range(2)]
    used = [f for f in fr if f is not None]
    return (float(np.mean(used)) if used else None), fr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1500)
    ap.add_argument("--device")
    a = ap.parse_args()
    from tempest.calibrate import shuffle
    K.ram_gate(8.0)
    s = stages(rows=a.rows, years=(2023, 2023), before_year=2023, device=a.device)
    d, idx = s["d"], s["idx"]
    year, n_lon = np.asarray(d["year"]), shuffle.grid_n_lon(d["cond"])
    real = shuffle.group_template(d["target"], s["keys"], year, idx, 199, np.random.default_rng(11), 2023, cell=8, n_lon=n_lon)
    tpl = shuffle.group_template(d["target"], s["keys"], year, idx, 199, np.random.default_rng(12), 2023, cell=8, n_lon=n_lon)
    thr, t = thresholds(d)
    rows = {"truth (2023 rows)": scores(t, thr), "real rows": scores(real, thr), "real rows + shuffle": scores(shuffle.apply(real, tpl), thr),
            "model": scores(s["x_cal"], thr), "model + shuffle": scores(s["x_shuf"], thr), "model + shuffle + maps": scores(s["x_lmap"], thr)}
    lines = [f"C2 premise check: {len(idx)} rows of 2023, 199 members, thresholds from {len(t)} truth rows", f"{'set':<25}unstable rate   shear rate"]
    lines += [f"{k:<25}{v[0]:<16.4f}{v[1]:.4f}" for k, v in rows.items()]
    frac, fr = decide(rows["real rows"], rows["real rows + shuffle"], rows["model + shuffle"])
    lines.append("share of the excess (model + shuffle over real rows) that the shuffle alone makes: " +
                 ", ".join(f"{n} {'under noise floor' if f is None else format(f, '.2f')}" for n, f in zip(("unstable", "shear"), fr)))
    lines.append("VERDICT: NO EXCESS over real rows. C2 is not needed: skip the C2 GPU fine-tune and b2_group_rank_shuffle.py." if frac is None else
                 "VERDICT: SHUFFLE is the main fault -> run b2_group_rank_shuffle.py (CPU). Do NOT do the C2 GPU fine-tune." if frac >= 0.5 else
                 "VERDICT: NETWORK is the main fault -> do the C2 GPU fine-tune (not built; recipe in new_plan_kit/README.md). b2_group_rank_shuffle.py is optional.")
    K.report("b1_c2_premise", lines)


def _selfcheck():
    a, b, c = (0.20, 0.008), (0.25, 0.018), (0.30, 0.028)
    assert np.isclose(decide(a, b, c)[0], 0.5) and decide(a, a, c)[0] == 0.0 and decide(a, c, c)[0] == 1.0
    assert decide(a, a, a)[0] is None and decide(a, b, (0.30, 0.009))[1][1] is None


_selfcheck()
if __name__ == "__main__":
    main()
