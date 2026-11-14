"""New_Plan 13 AV16: the IL-103 balloon-fitted shear map (models/il103_balloon_shearmap.npz, fitted on EPZ + MAF balloons 2005-20) applied ALOFT ONLY.
IL-103 alone: CRPS unchanged, 12-18 km p99 24.6 -> 29.0 vs 28.5 for pre-2023 balloons, but 5-12 km overshoots (22.8 vs 21.6) and 0-1 km is not fixable.
Aloft only = the balloon map's gains at 12-18 km (gains of the three lower bands set to 1), and every height below 12 km is copied back from the tool's own output
(the map's high-pass smoothing would otherwise leak a little change below 12 km), so the bands below 12 km keep the shipped map exactly.
Test: held-out pre-2023-sonde balloons 2021-22 (EPZ + MAF, 00Z + 12Z, 800 per station-hour), installed tool in climate mode (scripts/il103_balloon_shearmap.collect).
Rule written 2026-11-14 before any AV16 run (New_Plan 13 AV16 row, unchanged):
PASS: 12-18 km shear p99 within 10 % of the 2021-22 balloons' p99, bands below 12 km bit-identical, CRPS change within 0.1 % (mean CRPS of u and v over all 44 heights).
KILL: 12-18 km CRPS worse by more than 0.1 % (mean of u and v at heights 12-18 km).
Otherwise MISS: record, no adoption. Export / adoption needs the user in any case.
Also reported (no rule): the E5 bar, bank shear p99 at 12-18 km = 0.85 of the 2024-25 balloons (kit_b9_gram_compare.log).
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b48_av16_aloft_shearmap.py
Result: docs/results/logs/kit_b48_av16_aloft_shearmap.log
"""
import os

import numpy as np

import kit_common as K

NAME = "b48_av16_aloft_shearmap"
TABLE = "models/il103_balloon_shearmap.npz"
LO = 12000.0


def aloft_only(table):
    """Copy of the shear table with every band but 12-18 km (band 3) set to gain 1."""
    t = {k: np.array(v) for k, v in table.items()}
    t["gain"][:3] = 1.0
    return t


def apply_aloft(table, x, heights, apply):
    """Balloon map at 12-18 km only; heights below 12 km (u and v) copied back bit-exact from x."""
    out = apply(aloft_only(table), x)
    nh = len(heights)
    low = np.flatnonzero(heights < LO)
    cols = np.concatenate([low, nh + low])
    out[..., cols] = x[..., cols]
    return out


def judge(p99_new, p99_obs, identical, d_all, d_top):
    """d_all / d_top = CRPS change in % (all heights / 12-18 km), positive = worse."""
    if d_top > 0.1:
        return f"KILL (12-18 km CRPS worse by {d_top:+.3f} % > 0.1 %)"
    ratio = p99_new / p99_obs
    if abs(ratio - 1.0) <= 0.10 and identical and abs(d_all) <= 0.1:
        return f"PASS (12-18 km p99 {p99_new:.1f} vs balloons {p99_obs:.1f} = {ratio:.3f}, lower bands identical, CRPS {d_all:+.3f} %)"
    return (f"MISS (12-18 km p99 ratio {ratio:.3f} (needs 0.90-1.10), lower bands identical: {identical}, CRPS all {d_all:+.3f} % (needs within 0.1 %), "
            f"12-18 km {d_top:+.3f} %)")


def main():
    import il103_balloon_shearmap as B
    from tempest.calibrate import shear_map
    table = dict(np.load(TABLE))
    rng = np.random.default_rng(194)
    xt, yt = B.collect((2021, 2022), 800, rng)
    xb = apply_aloft(table, xt, B.H, shear_map.apply)
    low = np.flatnonzero(B.H < LO)
    cols = np.concatenate([low, B.NH + low])
    identical = bool(np.array_equal(xb[..., cols], xt[..., cols]))
    qs = [0.5, 0.99, 0.999]
    qm, qb, qo = B.shear_q(xt, qs), B.shear_q(xb, qs), B.shear_q(yt[:, None, :], qs)
    lines = [f"AV16 aloft-only balloon shear map: {len(yt)} balloons 2021-22 (EPZ + MAF, 00Z + 12Z), installed tool, climate mode",
             "shear (m/s per km) p50 / p99 / p99.9 by band: tool | tool + aloft balloon map | balloons"]
    for b, name in enumerate(("0-1 km", "1-5 km", "5-12 km", "12-18 km")):
        lines.append(f"  {name:8s} " + " | ".join("/".join(f"{x:.1f}" for x in q[b]) for q in (qm, qb, qo)))
    c0, c1 = B.crps_ensemble(xt, yt), B.crps_ensemble(xb, yt)
    top = np.flatnonzero(B.H >= LO)
    tcols = np.concatenate([top, B.NH + top])
    uv = slice(0, 2 * B.NH)
    d_all = 100 * (c1[:, uv].mean() / c0[:, uv].mean() - 1)
    d_top = 100 * (c1[:, tcols].mean() / c0[:, tcols].mean() - 1)
    lines.append(f"  CRPS u+v all heights {c0[:, uv].mean():.4f} -> {c1[:, uv].mean():.4f} ({d_all:+.3f} %); 12-18 km {c0[:, tcols].mean():.4f} -> {c1[:, tcols].mean():.4f} ({d_top:+.3f} %)")
    lines.append(f"  heights below 12 km bit-identical: {identical}")
    p99_new, p99_obs = qb[3][1], qo[3][1]
    lines.append(f"  E5 bar (report only): 12-18 km p99 / balloons = tool {qm[3][1] / p99_obs:.3f}, tool + aloft map {p99_new / p99_obs:.3f}; bank was 0.85 on 2024-25")
    lines.append("AV16 rule (pre-set): PASS = 12-18 km p99 within 10 % of 2021-22 balloons, lower bands bit-identical, CRPS within 0.1 %; KILL = 12-18 km CRPS worse > 0.1 %; else MISS.")
    lines.append("AV16 verdict: " + judge(p99_new, p99_obs, identical, d_all, d_top))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(28.0, 28.5, True, 0.0, 0.0).startswith("PASS")
    assert judge(24.6, 28.5, True, 0.0, 0.0).startswith("MISS")
    assert judge(28.0, 28.5, False, 0.0, 0.0).startswith("MISS")
    assert judge(28.0, 28.5, True, 0.2, 0.0).startswith("MISS")
    assert judge(28.0, 28.5, True, 0.0, 0.2).startswith("KILL")
    t = aloft_only({"grid": np.zeros((4, 3)), "gain": np.full((4, 3), 2.0)})
    assert (t["gain"][:3] == 1).all() and (t["gain"][3] == 2).all()
    h = np.array([0.0, 6000.0, 13000.0])
    x = np.arange(12, dtype=np.float32).reshape(2, 6)
    y = apply_aloft({"gain": np.ones((4, 1))}, x, h, lambda t, a: a + 1)
    assert (y[:, [0, 1, 3, 4]] == x[:, [0, 1, 3, 4]]).all() and (y[:, [2, 5]] == x[:, [2, 5]] + 1).all()


_selfcheck()
if __name__ == "__main__":
    main()
