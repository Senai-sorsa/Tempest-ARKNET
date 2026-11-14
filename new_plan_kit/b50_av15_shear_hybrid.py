"""New_Plan 13 AV15: shear target HYBRID of the two B2 forms (new_plan_kit/b2_shear_target_fit.py, both FAIL 2026-11-11 on 2024-25 balloons):
c1 wave-law factors in 1-5 km (c1 gave p99 / balloon 0.97 there), ratio 1.33 in 5-12 km and 12-18 km (ratio gave 1.03 there); 0-1 km unchanged (factor 1).
The hybrid was chosen by looking at the 2024-25 test balloons, so it is judged only on a FRESH balloon block neither form was scored on: EPZ + MAF balloons of
2022 (00Z + 12Z, up to 300 per station-hour). 2022 also avoids the fit year (ERA5 rows of 2021) and is before the 2023 sonde change.
Build exactly as B2: 2021 rows, shipped range map + shuffle, shear map fitted to the sharpened truth, lapse map refitted on top; tool tested with shipped maps and
with the new maps swapped in memory (same cases, same seeds). Tables go to data/kit/shear_map_balloon_hybrid.npz / lapse_map_on_balloon_hybrid.npz (opt-in, not shipped).
Rule written 2026-11-14 before any AV15 run (New_Plan 13 AV15 row, unchanged):
PASS: p99 new / balloon within 0.90-1.10 in both 1-5 km and 5-12 km on the fresh block, mean CRPS of u, v not worse by more than 0.1 %.
KILL: either band outside 0.85-1.15.
Otherwise MISS: record, no adoption. Shipping is a core / asset change and needs the user in any case.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b50_av15_shear_hybrid.py --device cpu
Result: docs/results/logs/kit_b50_av15_shear_hybrid.log
"""
import argparse
import os

import numpy as np

import kit_common as K

NAME = "b50_av15_shear_hybrid"
TEST = (2022, 2022)


def hybrid(f_c1, ratio, band):
    """c1 factors (S, 43) in band 1 (1-5 km), ratio in bands 2-3, 1 in band 0."""
    return np.where(band[None] == 1, f_c1, np.where(band[None] == 0, 1.0, ratio))


def judge(r1, r2, d_crps_pct):
    if not (0.85 <= r1 <= 1.15 and 0.85 <= r2 <= 1.15):
        return f"KILL (p99 new / balloon 1-5 km {r1:.3f}, 5-12 km {r2:.3f}: outside 0.85-1.15)"
    if 0.90 <= r1 <= 1.10 and 0.90 <= r2 <= 1.10 and d_crps_pct <= 0.1:
        return f"PASS (p99 new / balloon 1-5 km {r1:.3f}, 5-12 km {r2:.3f}, CRPS {d_crps_pct:+.3f} %)"
    return f"MISS (p99 new / balloon 1-5 km {r1:.3f}, 5-12 km {r2:.3f} (need 0.90-1.10), CRPS {d_crps_pct:+.3f} % (needs <= +0.1 %))"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratio", type=float, default=1.33)
    ap.add_argument("--fit-rows", type=int, default=1500)
    ap.add_argument("--per-group", type=int, default=300)
    ap.add_argument("--device")
    a = ap.parse_args()
    import b2_shear_target_fit as B2
    import il103_balloon_shearmap as il
    from b1_build_pool import stages
    from tempest.calibrate import lapse_map, shear_map
    from tempest.scoring.score import crps_ensemble
    from tempest_weather import api
    K.ram_gate(8.0)
    f = stages(rows=a.fit_rows, years=(2021, 2021), before_year=2021, device=a.device)
    fac = hybrid(B2.factors(f["truth"], "c1", a.ratio), a.ratio, B2.BAND)
    smap = shear_map.fit(f["x_shuf"], B2.sharpen(f["truth"], fac).astype(np.float32))
    lmap = lapse_map.fit(shear_map.apply(smap, f["x_shuf"]), f["truth"])
    os.makedirs(K.OUT, exist_ok=True)
    np.savez(os.path.join(K.OUT, "shear_map_balloon_hybrid.npz"), **smap)
    np.savez(os.path.join(K.OUT, "lapse_map_on_balloon_hybrid.npz"), **lmap)
    del f
    x0, y = il.collect(TEST, a.per_group, np.random.default_rng(0))
    post = api._assets()["post"]
    old = {k: post[k] for k in ("smap", "lmap")}
    try:                                                                                     # in memory only; put back whatever happens
        post["smap"], post["lmap"] = {k: np.asarray(v) for k, v in smap.items()}, {k: np.asarray(v) for k, v in lmap.items()}
        x1, y1 = il.collect(TEST, a.per_group, np.random.default_rng(0))
    finally:
        post.update(old)
    assert np.array_equal(y, y1), "the two runs did not use the same balloons"
    qs = [0.5, 0.99, 0.999]
    q0, q1, qb = il.shear_q(x0, qs), il.shear_q(x1, qs), il.shear_q(y[:, None, :], qs)
    lines = [f"AV15 shear target hybrid (c1 at 1-5 km, ratio {a.ratio} at 5-18 km): mean factor per band "
             + ", ".join(f"{fac[:, B2.BAND == b].mean():.2f}" for b in range(4))
             + f"; fit {a.fit_rows} rows of 2021; FRESH test block {len(y)} balloons {TEST[0]} (EPZ + MAF, 00Z + 12Z)",
             "shear (m/s per km) p50 / p99 / p99.9: shipped maps | hybrid maps | balloons"]
    for b, (name, _, _) in enumerate(K.BANDS):
        lines.append(f"  {name:<9}" + " | ".join("/".join(f"{x:.1f}" for x in q[b]) for q in (q0, q1, qb)) + f"   p99 new / balloon {q1[b][1] / qb[b][1]:.3f}")
    c0, c1 = crps_ensemble(x0, y).mean(), crps_ensemble(x1, y).mean()
    d = 100 * (c1 / c0 - 1)
    lines.append(f"mean CRPS of u, v against balloons: shipped {c0:.4f}, hybrid {c1:.4f} ({d:+.3f} %)")
    lines.append("AV15 rule (pre-set): PASS = p99 new / balloon 0.90-1.10 in 1-5 and 5-12 km on the fresh block, CRPS not worse > 0.1 %; KILL = either band outside 0.85-1.15; else MISS.")
    lines.append("AV15 verdict: " + judge(q1[1][1] / qb[1][1], q1[2][1] / qb[2][1], d))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(1.0, 0.95, 0.0).startswith("PASS")
    assert judge(1.0, 0.95, 0.2).startswith("MISS")
    assert judge(1.12, 0.95, 0.0).startswith("MISS")
    assert judge(0.84, 1.0, 0.0).startswith("KILL")
    assert judge(1.0, 1.16, -1.0).startswith("KILL")
    band = np.array([0, 1, 2, 3])
    h = hybrid(np.full((2, 4), 1.2), 1.33, band)
    assert np.allclose(h, [[1.0, 1.2, 1.33, 1.33]] * 2)


_selfcheck()
if __name__ == "__main__":
    main()
