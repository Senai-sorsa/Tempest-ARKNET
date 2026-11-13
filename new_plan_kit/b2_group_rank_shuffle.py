"""C2 fallback (CPU): group-rank shuffle. RUN ONLY IF b1_c2_premise.py said "SHUFFLE is the main fault" (it did, 2026-11-10). KILL RULE BELOW.
Today's shuffle gives member k, in every column, the value whose rank among the 199 samples equals the rank of template profile k among the
199 template profiles. Ranks among only 199 profiles are noisy, and the noise differs a little from one height to the next: that makes
false shear and false unstable layers.
DISCOVERY (2026-11-10): the recipe as written in "Innovative idea review.md" ("order members by the template's rank fraction within its whole
group") changes NOTHING: a rank fraction within the group rises with the value, so sorting by it gives the same order as sorting by the value.
The self-check below proves it. What is built instead uses the fraction as a POSITION, not as an order:
    member k, column c  =  the sample quantile of column c at fraction f(k, c),
    f(k, c) = rank fraction of template profile k inside --group real profiles of its group (not inside the 199 drawn).
This moves each column's values a little (they are read between sorted samples), so CRPS is checked too.

Steps: (1) fit rows of 2021: new shuffle, then refit the shear map and the lapse map on top (templates before 2021).
       (2) test rows of 2024-25, same network draw for both stacks (paired): shipped stack against new stack.
Scores: unstable rate | shear rate (tempest/scoring/mc.py violations, thresholds from 2023 truth rows) and CRPS (each column divided by the
truth's standard deviation, mean over u, v, T columns).
KILL (measured BEFORE the shear and lapse maps, row "new shuffle" against row "shipped shuffle"):
    unstable rate must be under 0.26, shear rate at most half the shipped one, CRPS not worse by more than 0.0006.
PASS -> the two new map tables are kept in data/kit/ (group_rank_smap.npz, group_rank_lmap.npz). Wiring into the tool is a core change
        (tempest_weather/api.py reads a stored rank table): write the result to the log and stop; do not edit the core without a new task.
KILL -> write "C2 fallback killed" to the log. C2 is then closed: the shipped maps already bring the rates near truth (0.213 | 0.0066 against 0.206 | 0.0031).

    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b2_group_rank_shuffle.py --device cpu          # about 30 min, 6 GB RAM, 3 threads
    KIT_SMOKE=1 PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b2_group_rank_shuffle.py --device cpu --rows 40 --fit-rows 40 --group 400
Result: docs/results/logs/kit_b2_group_rank_shuffle.log
"""
import argparse
import os

import numpy as np

import kit_common as K
from b1_build_pool import stages
from b1_c2_premise import scores, thresholds

NCOL = 3 * K.NH        # u, v, T columns


def group_fractions(d, keys, idx, m, group, rng, before_year):
    """For each row of idx: m real template profiles of its group and their rank fraction (0-1) per column inside `group` real profiles of that group.
    -> frac (len(idx), m, D) float32. Group = block of 8 x 8 grid points x month x 2-hour bin, years before before_year (as the shipped templates)."""
    from tempest.calibrate import shuffle
    from tempest.generator.sample import to_physical
    year = np.asarray(d["year"])
    ck = shuffle.cell_keys(keys, 8, shuffle.grid_n_lon(d["cond"]))
    tr = np.flatnonzero(year < before_year)
    tr = tr[np.argsort(ck[tr], kind="stable")]
    lo, hi = np.searchsorted(ck[tr], ck[idx], "left"), np.searchsorted(ck[tr], ck[idx], "right")
    out = None
    for i in range(len(idx)):
        n = hi[i] - lo[i]
        assert n >= m, f"group of row {idx[i]} has only {n} training rows"
        pick = np.sort(tr[lo[i] + rng.choice(n, min(group, n), replace=False)])
        g = to_physical(np.asarray(d["target"][pick]))                     # (G, D) real profiles of the group
        r = (g.argsort(0).argsort(0)[rng.permutation(len(g))[:m]] + 0.5) / len(g)
        if out is None:
            out = np.empty((len(idx), m, g.shape[1]), np.float32)
        out[i] = r
    return out


def apply_frac(x, frac):
    """x (N, m, D) samples, frac (N, m, D) in 0-1 -> each column's sample quantile at those fractions (straight line between sorted samples)."""
    m = x.shape[1]
    xs = np.sort(x, axis=1)
    pos = np.clip(frac * m - 0.5, 0, m - 1)
    lo = np.floor(pos).astype(np.int64)
    w = (pos - lo).astype(np.float32)
    return (1 - w) * np.take_along_axis(xs, lo, 1) + w * np.take_along_axis(xs, np.minimum(lo + 1, m - 1), 1)


def crps_std(x, truth, sd):
    from tempest.scoring.score import crps_ensemble
    return float((crps_ensemble(x[..., :NCOL], truth[:, :NCOL]) / sd).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1500)
    ap.add_argument("--fit-rows", type=int, default=1500)
    ap.add_argument("--group", type=int, default=2000, help="real profiles per group used for the rank fractions")
    ap.add_argument("--device")
    a = ap.parse_args()
    from tempest.calibrate import lapse_map, shear_map
    K.ram_gate(8.0)
    f = stages(rows=a.fit_rows, years=(2021, 2021), before_year=2021, device=a.device)
    xf = apply_frac(f["x_cal"], group_fractions(f["d"], f["keys"], f["idx"], 199, a.group, np.random.default_rng(21), 2021))
    smap = shear_map.fit(xf, f["truth"])
    lmap = lapse_map.fit(shear_map.apply(smap, xf), f["truth"])
    del f, xf
    s = stages(rows=a.rows, years=(2024, 2025), device=a.device)
    thr, t23 = thresholds(s["d"])
    sd = t23[:, :NCOL].std(0)
    xn = apply_frac(s["x_cal"], group_fractions(s["d"], s["keys"], s["idx"], 199, a.group, np.random.default_rng(22), 2024))
    xn_maps = lapse_map.apply(lmap, shear_map.apply(smap, xn))
    sets = {"range map only": s["x_cal"], "shipped shuffle": s["x_shuf"], "shipped shuffle + maps": s["x_lmap"], "new shuffle": xn, "new shuffle + new maps": xn_maps}
    res = {k: scores(v, thr) + (crps_std(v, s["truth"], sd),) for k, v in sets.items()}
    lines = [f"C2 fallback, group-rank shuffle: fit {a.fit_rows} rows of 2021, test {len(s['idx'])} rows of 2024-25, group size {a.group}, 199 members, paired draw",
             f"{'set':<26}unstable rate   shear rate   CRPS (standardised, u v T)", f"{'truth (2023 rows)':<26}{scores(t23, thr)[0]:<16.4f}{scores(t23, thr)[1]:<13.4f}-"]
    lines += [f"{k:<26}{v[0]:<16.4f}{v[1]:<13.4f}{v[2]:.4f}" for k, v in res.items()]
    old, new = res["shipped shuffle"], res["new shuffle"]
    ok = (new[0] < 0.26, new[1] <= 0.5 * old[1], new[2] - old[2] <= K.NOISE)
    lines.append(f"kill rule before the maps: unstable under 0.26 {'yes' if ok[0] else 'NO'}; shear rate halved {'yes' if ok[1] else 'NO'}; CRPS not worse by more than {K.NOISE} {'yes' if ok[2] else 'NO'} ({new[2] - old[2]:+.4f})")
    if all(ok):
        os.makedirs(K.OUT, exist_ok=True)
        np.savez(os.path.join(K.OUT, "group_rank_smap.npz"), **smap)
        np.savez(os.path.join(K.OUT, "group_rank_lmap.npz"), **lmap)
        lines.append("VERDICT: PASS. New map tables saved in data/kit/ (group_rank_smap.npz, group_rank_lmap.npz). Wiring into the tool is a core change: stop here and report.")
    else:
        lines.append("VERDICT: C2 fallback KILLED. C2 is closed; the shipped shuffle + maps stay.")
    K.report("b2_group_rank_shuffle", lines)


def _selfcheck():
    from tempest.calibrate import shuffle
    rng = np.random.default_rng(0)
    x, tpl = rng.standard_normal((3, 199, 5)).astype(np.float32), rng.standard_normal((3, 199, 5))
    r = tpl.argsort(1).argsort(1)
    assert np.array_equal(apply_frac(x, (r + 0.5) / 199), shuffle.apply(x, tpl))          # fractions = ranks among the 199 -> exactly today's shuffle
    big = rng.standard_normal((5000, 5))                                                   # the recipe as written: order by group fraction = order by value
    fr = np.searchsorted(np.sort(big, 0)[:, 0], tpl[0, :, 0]) / 5000
    assert (np.diff(fr[np.argsort(tpl[0, :, 0])]) >= 0).all()                             # so with ties broken by the old rank the order is unchanged


_selfcheck()
if __name__ == "__main__":
    main()
