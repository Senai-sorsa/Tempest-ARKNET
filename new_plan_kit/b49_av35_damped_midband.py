"""New_Plan 13 AV35: AV16 (PASS 2026-11-14, aloft-only IL-103 balloon shear map) plus the IL-103 5-12 km band with its gain damped to half (g -> 1 + 0.5 (g - 1)).
Bands 0-1 km and 1-5 km get gain 1, and every height below 5 km (u and v) is copied back bit-exact from the tool's output. Same test as AV16: 2021-22 EPZ + MAF balloons,
00Z + 12Z, 800 per station-hour, installed tool, climate mode, same sampling seed (194), so the 12-18 km numbers are comparable with kit_b48.
Rule written 2026-11-14 before any AV35 run (New_Plan 13 AV35 row, unchanged):
PASS: 5-12 km shear p99 within 10 % of the 2021-22 balloons' p99, 12-18 km p99 still within 10 %, bands below 5 km bit-identical, CRPS change within 0.1 % (mean CRPS of u
      and v over all 44 heights).
KILL: 5-12 km or 12-18 km CRPS worse by more than 0.1 % (mean of u and v at those heights).
Otherwise MISS: record, no adoption. Adoption / export needs the user in any case.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b49_av35_damped_midband.py
Result: docs/results/logs/kit_b49_av35_damped_midband.log
"""
import numpy as np

import kit_common as K

NAME = "b49_av35_damped_midband"
TABLE = "models/il103_balloon_shearmap.npz"
LO = 5000.0
DAMP = 0.5


def mid_table(table):
    """Bands 0/1 gain 1, band 2 (5-12 km) damped to DAMP, band 3 (12-18 km) full."""
    t = {k: np.array(v) for k, v in table.items()}
    t["gain"][:2] = 1.0
    t["gain"][2] = 1.0 + DAMP * (t["gain"][2] - 1.0)
    return t


def apply_above(table, x, heights, apply):
    out = apply(mid_table(table), x)
    nh = len(heights)
    low = np.flatnonzero(heights < LO)
    cols = np.concatenate([low, nh + low])
    out[..., cols] = x[..., cols]
    return out


def judge(r_mid, r_top, identical, d_all, d_mid, d_top):
    """r_* = p99 tool+map / balloons; d_* = CRPS change in % (positive = worse)."""
    if d_mid > 0.1 or d_top > 0.1:
        return f"KILL (CRPS worse beyond 0.1 %: 5-12 km {d_mid:+.3f} %, 12-18 km {d_top:+.3f} %)"
    if abs(r_mid - 1) <= 0.10 and abs(r_top - 1) <= 0.10 and identical and abs(d_all) <= 0.1:
        return f"PASS (p99 / balloons 5-12 km {r_mid:.3f}, 12-18 km {r_top:.3f}, lower bands identical, CRPS {d_all:+.3f} %)"
    return (f"MISS (p99 / balloons 5-12 km {r_mid:.3f}, 12-18 km {r_top:.3f} (need 0.90-1.10), below 5 km identical: {identical}, CRPS all {d_all:+.3f} % "
            f"(needs within 0.1 %), 5-12 km {d_mid:+.3f} %, 12-18 km {d_top:+.3f} %)")


def main():
    import il103_balloon_shearmap as B
    from tempest.calibrate import shear_map
    table = dict(np.load(TABLE))
    xt, yt = B.collect((2021, 2022), 800, np.random.default_rng(194))
    xb = apply_above(table, xt, B.H, shear_map.apply)
    low = np.flatnonzero(B.H < LO)
    identical = bool(np.array_equal(xb[..., np.concatenate([low, B.NH + low])], xt[..., np.concatenate([low, B.NH + low])]))
    qs = [0.5, 0.99, 0.999]
    qm, qb, qo = B.shear_q(xt, qs), B.shear_q(xb, qs), B.shear_q(yt[:, None, :], qs)
    lines = [f"AV35 AV16 + damped 5-12 km balloon shear map (damp {DAMP}): {len(yt)} balloons 2021-22 (EPZ + MAF, 00Z + 12Z), installed tool, climate mode",
             "shear (m/s per km) p50 / p99 / p99.9 by band: tool | tool + map | balloons"]
    for b, name in enumerate(("0-1 km", "1-5 km", "5-12 km", "12-18 km")):
        lines.append(f"  {name:8s} " + " | ".join("/".join(f"{x:.1f}" for x in q[b]) for q in (qm, qb, qo)))
    c0, c1 = B.crps_ensemble(xt, yt), B.crps_ensemble(xb, yt)

    def d(lo, hi):
        j = np.flatnonzero((B.H >= lo) & (B.H < hi))
        c = np.concatenate([j, B.NH + j])
        return 100 * (c1[:, c].mean() / c0[:, c].mean() - 1)
    d_all, d_mid, d_top = d(0, 1e9), d(5000, 12000), d(12000, 1e9)
    lines.append(f"  CRPS u+v change: all heights {d_all:+.3f} %, 5-12 km {d_mid:+.3f} %, 12-18 km {d_top:+.3f} %")
    lines.append(f"  heights below 5 km bit-identical: {identical}")
    r_mid, r_top = qb[2][1] / qo[2][1], qb[3][1] / qo[3][1]
    lines.append("AV35 rule (pre-set): PASS = 5-12 km and 12-18 km p99 within 10 % of 2021-22 balloons, below 5 km bit-identical, CRPS within 0.1 %; "
                 "KILL = 5-12 or 12-18 km CRPS worse > 0.1 %; else MISS.")
    lines.append("AV35 verdict: " + judge(r_mid, r_top, identical, d_all, d_mid, d_top))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(0.95, 1.02, True, 0.02, 0.05, 0.07).startswith("PASS")
    assert judge(0.88, 1.02, True, 0.02, 0.05, 0.07).startswith("MISS")
    assert judge(0.95, 1.02, False, 0.02, 0.05, 0.07).startswith("MISS")
    assert judge(0.95, 1.02, True, 0.2, 0.05, 0.07).startswith("MISS")
    assert judge(0.95, 1.02, True, 0.0, 0.2, 0.0).startswith("KILL")
    t = mid_table({"grid": np.zeros((4, 2)), "gain": np.full((4, 2), 3.0)})
    assert (t["gain"][:2] == 1).all() and (t["gain"][2] == 2).all() and (t["gain"][3] == 3).all()
    h = np.array([0.0, 6000.0])
    x = np.arange(8, dtype=np.float32).reshape(2, 4)
    y = apply_above({"gain": np.ones((4, 1))}, x, h, lambda t, a: a + 1)
    assert (y[:, [0, 2]] == x[:, [0, 2]]).all() and (y[:, [1, 3]] == x[:, [1, 3]] + 1).all()


_selfcheck()
if __name__ == "__main__":
    main()
