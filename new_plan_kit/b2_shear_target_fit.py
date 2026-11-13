"""Shear target (G1-1 ratio form, or C1 wave-law form): a second shear map that aims at REAL (balloon-like) shear, not ERA5 shear. PASS RULE BELOW.
ERA5 is smoother than balloons, so the shipped shear map (fitted to ERA5) leaves the tool's shear too small aloft.
How it is built WITHOUT touching tempest/calibrate/shear_map.py: shear_map.fit(samples, truth) only uses the truth's layer shear. So we hand it a
"sharpened truth": ERA5 rows whose wind steps between neighbouring heights are multiplied by a factor per layer.
    --form ratio (default)   factor = 1 below 1 km, --ratio above (12-18 km uses the same number, never more than 5-12 km)
    --form c1                factor = sqrt(1 + k c N2 / shear2) per layer, c per band from data/kit/c1_wave_law.npz (b1_c1_wave_law.py must have
                             said PASS), k chosen so the mean factor in 1-5 km equals --ratio; 0-1 km unchanged
    --ratio                  C5's lower bound. 2026-11-10 result: 1.33 (b1_c5_triple.py, biased high). Default 1.33. Use 1.7 only if C5 is re-run and killed.
Steps: (1) 2021 rows: shipped range map + shuffle, fit the new shear map to the sharpened truth, then refit the lapse map on top (plain truth).
       (2) test like scripts/il103_balloon_shearmap.py: the installed tool at EPZ + MAF, balloons 2024-25, same cases and seeds with the shipped
           maps and with the new maps (swapped in memory only; nothing on disk changes).
PASS: tool p99 shear within 10 % of the balloons in BOTH 1-5 km and 5-12 km, AND mean CRPS of u, v against balloons not worse by more than 0.15 %
      (= 0.0006 on the standardised headline of 0.4165). The ERA5 shear score gets worse by design: do not gate on it.
PASS -> tables stay in data/kit/shear_map_balloon_<form>.npz and lapse_map_on_balloon_<form>.npz (opt-in assets). Shipping them is a core / asset change: report, do not do it here.
FAIL -> log it; try the other --form once; if both fail the shear target is closed.

    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b2_shear_target_fit.py --device cpu                 # about 25 min, 6 GB RAM, 3 threads
    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b2_shear_target_fit.py --device cpu --form c1
    KIT_SMOKE=1 PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b2_shear_target_fit.py --device cpu --fit-rows 40 --per-group 5   # smoke test
Result: docs/results/logs/kit_b2_shear_target_fit.log
"""
import argparse
import os

import numpy as np

import kit_common as K

NH = K.NH
MID = K.H[1:]                                          # a layer belongs to the band of its upper height (as tempest/calibrate/shear_map.py)
BAND = np.array([next(i for i, (_, lo, hi) in enumerate(K.BANDS) if lo <= z < hi or (i == 3 and z >= hi)) for z in MID])


def sharpen(truth, factor):
    """truth (S, D) physical, factor (S, 43) or (43,) -> copy whose u, v steps between neighbouring heights are multiplied by factor (10 m wind kept)."""
    out = truth.astype(np.float64).copy()
    for j in (0, 1):
        w = out[:, j * NH:(j + 1) * NH]
        out[:, j * NH + 1:(j + 1) * NH] = w[:, :1] + np.cumsum(np.diff(w, axis=1) * factor, axis=1)
    return out


def factors(truth, form, ratio):
    if form == "ratio":
        return np.where(BAND == 0, 1.0, ratio)[None]
    c1 = np.load(os.path.join(K.OUT, "c1_wave_law.npz"))
    assert bool(c1["passed"]), "b1_c1_wave_law.py did not say PASS: use --form ratio"
    u, v, T, sp = truth[:, :NH], truth[:, NH:2 * NH], truth[:, 2 * NH:3 * NH].astype(np.float64), truth[:, 4 * NH + 1].astype(np.float64)
    dlnp = -9.81 * np.diff(K.H) / (287.0 * 0.5 * (T[:, 1:] + T[:, :-1]))                     # pressure from the surface pressure and T (the 10 m level is taken as the surface)
    p = sp[:, None] * np.exp(np.concatenate([np.zeros((len(T), 1)), np.cumsum(dlnp, 1)], 1))
    n2 = np.maximum(K.n2(T, p), 0.0)
    s2 = np.maximum((K.shear_mag(u.astype(np.float64), v.astype(np.float64)) / 1000.0) ** 2, 1e-8)   # floor 0.1 m/s per km: calm layers must not get a huge factor
    c = np.asarray(c1["c"], float)[BAND]
    f = lambda k: np.where(BAND == 0, 1.0, np.minimum(np.sqrt(1 + k * c * n2 / s2), 3.0))     # noqa: E731  (cap 3 = the shear map's own largest gain)
    ks = np.geomspace(0.01, 100, 200)
    k = ks[int(np.argmin([abs(f(x)[:, BAND == 1].mean() - ratio) for x in ks]))]
    return f(k)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--form", choices=["ratio", "c1"], default="ratio")
    ap.add_argument("--ratio", type=float, default=1.33)
    ap.add_argument("--fit-rows", type=int, default=1500)
    ap.add_argument("--per-group", type=int, default=300, help="test balloons per station and hour (4 groups)")
    ap.add_argument("--device")
    a = ap.parse_args()
    assert 1.0 <= a.ratio <= 1.7, "ratio must be in 1.0-1.7"
    import il103_balloon_shearmap as il
    from b1_build_pool import stages
    from tempest.calibrate import lapse_map, shear_map
    from tempest.scoring.score import crps_ensemble
    from tempest_weather import api
    K.ram_gate(8.0)
    f = stages(rows=a.fit_rows, years=(2021, 2021), before_year=2021, device=a.device)
    fac = factors(f["truth"], a.form, a.ratio)
    smap = shear_map.fit(f["x_shuf"], sharpen(f["truth"], fac).astype(np.float32))
    lmap = lapse_map.fit(shear_map.apply(smap, f["x_shuf"]), f["truth"])
    os.makedirs(K.OUT, exist_ok=True)
    np.savez(os.path.join(K.OUT, f"shear_map_balloon_{a.form}.npz"), **smap)
    np.savez(os.path.join(K.OUT, f"lapse_map_on_balloon_{a.form}.npz"), **lmap)
    del f
    x0, y = il.collect((2024, 2025), a.per_group, np.random.default_rng(0))                  # shipped maps
    post = api._assets()["post"]
    old = {k: post[k] for k in ("smap", "lmap")}
    try:                                                                                     # in memory only; put back whatever happens
        post["smap"], post["lmap"] = {k: np.asarray(v) for k, v in smap.items()}, {k: np.asarray(v) for k, v in lmap.items()}
        x1, y1 = il.collect((2024, 2025), a.per_group, np.random.default_rng(0))             # same cases, same seeds
    finally:
        post.update(old)
    assert np.array_equal(y, y1), "the two runs did not use the same balloons"
    qs = [0.5, 0.99, 0.999]
    q0, q1, qb = il.shear_q(x0, qs), il.shear_q(x1, qs), il.shear_q(y[:, None, :], qs)
    lines = [f"Shear target, form {a.form}, ratio {a.ratio}: mean factor per band {', '.join(f'{np.broadcast_to(fac, (1, 43))[:, BAND == b].mean() if fac.shape[0] == 1 else fac[:, BAND == b].mean():.2f}' for b in range(4))}; "
             f"fit {a.fit_rows} rows of 2021; test {len(y)} balloons 2024-25 (EPZ + MAF, 00Z + 12Z)", "shear (m/s per km) p50 / p99 / p99.9: shipped maps | new maps | balloons"]
    for b, (name, _, _) in enumerate(K.BANDS):
        lines.append(f"  {name:<9}" + " | ".join("/".join(f"{x:.1f}" for x in q[b]) for q in (q0, q1, qb)) + f"   p99 new / balloon {q1[b][1] / qb[b][1]:.2f}")
    c0, c1 = crps_ensemble(x0, y).mean(), crps_ensemble(x1, y).mean()
    lines.append(f"mean CRPS of u, v against balloons: shipped {c0:.4f}, new {c1:.4f} ({100 * (c1 / c0 - 1):+.2f} %)")
    ok = all(abs(q1[b][1] / qb[b][1] - 1) <= 0.10 for b in (1, 2)), c1 / c0 - 1 <= 0.0015
    lines.append(f"VERDICT: {'PASS' if all(ok) else 'FAIL'} (p99 within 10 % in 1-5 and 5-12 km: {'yes' if ok[0] else 'NO'}; CRPS not worse by more than 0.15 %: {'yes' if ok[1] else 'NO'}). "
                 + (f"Tables kept in data/kit/ (*_balloon_{a.form}.npz). Report; shipping them is a separate task." if all(ok) else "Try the other --form once; if both fail, close the shear target."))
    K.report("b2_shear_target_fit", lines)


def _selfcheck():
    from tempest.calibrate import shear_map
    rng = np.random.default_rng(0)
    t = rng.standard_normal((50, 4 * NH + 3)).cumsum(1)
    s0 = shear_map.shears(t[:, :2 * NH].reshape(50, 2, NH))[1]
    s1 = shear_map.shears(sharpen(t, np.where(BAND == 0, 1.0, 1.5)[None])[:, :2 * NH].reshape(50, 2, NH))[1]
    assert np.allclose(s1[:, BAND > 0], 1.5 * s0[:, BAND > 0]) and np.allclose(s1[:, BAND == 0], s0[:, BAND == 0])
    assert np.array_equal(BAND, shear_map.BAND_OF_LAYER), "band of each layer differs from tempest/calibrate/shear_map.py"
    assert np.allclose(sharpen(t, np.ones(43))[:, :2 * NH], t[:, :2 * NH])


_selfcheck()
if __name__ == "__main__":
    main()
