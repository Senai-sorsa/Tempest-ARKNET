"""CPU-C: widen the RH 12-18 km station correction (Limitations 5.2.19 c) toward 0.99 coverage.

    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b3_rh_widen.py

The past-mode hybrid serves RH 12-18 km from the station correction (a + b ERA5 + leftover profile, F-11).
On 2024-25 00Z its 99 % coverage is 0.948 (models/modeP_eval.csv). Widening: each sounding's draws are
stretched around their own median, x' = med + k (x - med), clipped to 0-100 %. k is picked on the 2021-23
00Z soundings (outside the map's fit years, 1991-2020, and outside the test): the smallest k on a 0.05 grid
whose 99 % coverage there is >= 0.99. Then scored once on 2024-25 00Z.

Rule (written before any result):
  PASS if on 2024-25 the 99 % coverage at RH 12-18 km is >= 0.975 AND the CRPS change is <= +1.5 % (point).
  NO CHANGE if the chosen k is 1.0 (the 2021-23 years are already covered: the gap is a year shift, not width).
  FAIL otherwise.
Report only; a tool change would be an opt-in flag (default unchanged) and needs a separate step.
"""
import numpy as np

import kit_common as K
from tempest.calibrate import station
from tempest.forecast import modeP as P
from tempest.forecast.modeP import D
from tempest.scoring.score import coverage90, crps_ensemble

M = 199
GRID = np.round(np.arange(1.0, 3.001, 0.05), 2)


def widen(x, k):
    """x (S, m, c) draws -> stretched around each (sounding, column) median by k, held to 0-100 %."""
    med = np.median(x, 1, keepdims=True)
    return np.clip(med + k * (x - med), 0, 100)


def draws(tmap, dd, cols):
    g = station.group_id(dd["station"], dd["time"].month, np.zeros(len(dd["era"]), int))
    out = np.empty((len(dd["era"]), M, len(cols)), np.float32)
    for j in range(M):
        out[:, j] = station.apply(tmap, dd["era"], g, np.random.default_rng(j)).reshape(len(dd["era"]), -1)[:, cols]
    return out


def _selfcheck():
    x = np.array([[[10.0], [20.0], [30.0]]])
    assert np.allclose(widen(x, 1.0), x)
    assert np.allclose(widen(x, 2.0)[0, :, 0], [0.0, 20.0, 40.0])
    assert widen(np.array([[[1.0], [2.0], [9.0]]]), 3.0).min() == 0.0


def main():
    _selfcheck()
    K.ram_gate(4.0)
    d = P.load_pairs("data/pilot/profiles80.zarr", "data/raw/igra")
    yr, hr = d["time"].year.to_numpy(), d["time"].hour.to_numpy()
    cols = next(np.flatnonzero(s) for v, b, s in P.names() if v == "RH" and b == "12-18 km")
    tmap = station.load("models/station_map_mix.npz")
    out = ["b3_rh_widen: RH 12-18 km station correction, spread factor k picked on 2021-23 00Z, scored on 2024-25 00Z"]
    res = {}
    for name, m in (("cal", (yr >= 2021) & (yr <= 2023) & (hr == 0)), ("test", (yr >= 2024) & (hr == 0))):
        dd = {k_: v[m] for k_, v in d.items()}
        x = draws(tmap, dd, cols)
        y = dd["obs"].reshape(len(dd["era"]), -1)[:, cols]
        day = dd["time"].year.to_numpy() * 1000 + dd["time"].dayofyear.to_numpy()
        res[name] = (x, y, day)
        out.append(f"{name}: {len(y)} soundings, {len(cols)} heights")
    x, y, _ = res["cal"]
    covs = {k: coverage90(widen(x, k), y, 0.99).mean() for k in GRID}
    out.append("2021-23 cov99 by k: " + ", ".join(f"{k:.2f}:{c:.3f}" for k, c in covs.items() if k <= 2.0 or c < 0.995))
    ok = [k for k in GRID if covs[k] >= 0.99]
    k = ok[0] if ok else GRID[-1]
    out.append(f"chosen k = {k:.2f}" + ("" if ok else " (grid end: 0.99 not reached)"))
    x, y, day = res["test"]
    c0, c1 = crps_ensemble(x, y).mean(1), crps_ensemble(widen(x, k), y).mean(1)
    v0, v1 = coverage90(x, y, 0.99).mean(1), coverage90(widen(x, k), y, 0.99).mean(1)
    b0, b1, bd = K.block_boot(c0, day), K.block_boot(c1, day), K.block_boot(c1 - c0, day)
    q0, q1 = K.block_boot(v0, day), K.block_boot(v1, day)
    pct = 100 * (b1[0] - b0[0]) / b0[0]
    out += [f"2024-25 cov99: {q0[0]:.3f} [{q0[1]:.3f}, {q0[2]:.3f}] -> {q1[0]:.3f} [{q1[1]:.3f}, {q1[2]:.3f}]",
            f"2024-25 CRPS: {b0[0]:.3f} -> {b1[0]:.3f} ({pct:+.1f} %; paired diff {bd[0]:+.3f} [{bd[1]:+.3f}, {bd[2]:+.3f}])"]
    if k == 1.0:
        verdict = "NO CHANGE (2021-23 already covered at k = 1)"
    elif q1[0] >= 0.975 and pct <= 1.5:
        verdict = "PASS"
    else:
        verdict = "FAIL"
    out.append(f"VERDICT: {verdict} (rule: test cov99 >= 0.975 and CRPS change <= +1.5 %)")
    K.report("b3_rh_widen", out)


if __name__ == "__main__":
    main()
