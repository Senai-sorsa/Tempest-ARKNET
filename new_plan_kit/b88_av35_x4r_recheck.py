"""New_Plan 28.11 item 11 (b): AV35 re-check on the final climate stack (shipped c4w + X4-R variant e). The installed tool is swapped in memory only:
network = models/s25/c4wx4r_s0.pt exported with tempest.export_tool.pack, range calibration = models/s25/c4wx4r_s0.calib2021.npz, shear / lapse maps =
c4wx4r_s0_smap_cell8 / _lmap_cell8 (the s25 arm refits, PRE=1). Everything else (head, Mode P/F, AV35 map itself) stays the shipped asset.
Same test and the same rule as b49 (AV35, pre-set 2026-11-14): 2021-22 EPZ + MAF balloons, 00Z + 12Z, 800 per station-hour, sampling seed 194,
tool with the AV35 map off vs on. PASS = 5-12 and 12-18 km p99 within 10 % of the balloons, below 5 km bit-identical, CRPS within 0.1 %;
KILL = 5-12 or 12-18 km CRPS worse > 0.1 %; else MISS. Swap self-check: the shipped l3_c4w.pt through pack gives the shipped net's samples exactly.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b88_av35_x4r_recheck.py
Result: docs/results/logs/kit_b88_av35_x4r_recheck.log
"""
import os
import tempfile

import numpy as np
import torch

import kit_common as K
from b49_av35_damped_midband import judge

NAME = "b88_av35_x4r_recheck"
D = "models/s25/c4wx4r_s0"


def net_of(path):
    from tempest.export_tool import pack
    from tempest_weather.engine import Net
    arr = {}
    pack(torch.load(path, map_location="cpu", weights_only=True), "", arr)
    f = os.path.join(tempfile.mkdtemp(), "net.npz")
    np.savez(f, **arr)
    return Net.load(f)


def main():
    import il103_balloon_shearmap as B
    from tempest_weather import api
    A = api._assets()
    probe = lambda: B.tool_uv("USM00072364", __import__("pandas").Timestamp("2021-07-01 00:00"), 7)
    x0 = probe()
    ship_net = A["net"]
    A["net"] = net_of("models/l3_c4w.pt")
    assert np.array_equal(probe(), x0), "swap self-check: re-exported shipped net differs from the installed one"
    A["net"] = net_of(D + ".pt")
    assert A["net"].x4r is not None
    c = np.load(D + ".calib2021.npz")
    A["calib"] = dict(qz=c["qz"], qu=c["qu"], m=c["m"])
    sm, lm = np.load(D + "_smap_cell8.npz"), np.load(D + "_lmap_cell8.npz")
    post_on = dict(A["post"], smap=dict(grid=sm["grid"], gain=sm["gain"]), lmap=dict(xk=lm["xk"], yk=lm["yk"]))
    post_off = {k: v for k, v in post_on.items() if k != "amap"}
    assert "amap" in post_on and not np.array_equal(probe(), x0)
    A["post"] = post_off
    xt, yt = B.collect((2021, 2022), 800, np.random.default_rng(194))
    A["post"] = post_on
    xb, yb = B.collect((2021, 2022), 800, np.random.default_rng(194))
    A["net"] = ship_net
    assert np.array_equal(yt, yb)
    low = np.flatnonzero(B.H < 5000.0)
    cols = np.concatenate([low, B.NH + low])
    identical = bool(np.array_equal(xb[..., cols], xt[..., cols]))
    qs = [0.5, 0.99, 0.999]
    qm, qb, qo = B.shear_q(xt, qs), B.shear_q(xb, qs), B.shear_q(yt[:, None, :], qs)
    lines = [f"AV35 re-check on c4w + X4-R (variant e, k 3), tool swapped in memory (net / calib / smap / lmap = {D}): {len(yt)} balloons 2021-22 (EPZ + MAF, 00Z + 12Z)",
             "shear (m/s per km) p50 / p99 / p99.9 by band: stack, AV35 off | stack, AV35 on | balloons"]
    for b, name in enumerate(("0-1 km", "1-5 km", "5-12 km", "12-18 km")):
        lines.append(f"  {name:8s} " + " | ".join("/".join(f"{x:.1f}" for x in q[b]) for q in (qm, qb, qo)))
    c0, c1 = B.crps_ensemble(xt, yt), B.crps_ensemble(xb, yt)

    def d(lo, hi):
        j = np.flatnonzero((B.H >= lo) & (B.H < hi))
        cc = np.concatenate([j, B.NH + j])
        return 100 * (c1[:, cc].mean() / c0[:, cc].mean() - 1)
    d_all, d_mid, d_top = d(0, 1e9), d(5000, 12000), d(12000, 1e9)
    lines.append(f"  CRPS u+v change: all heights {d_all:+.3f} %, 5-12 km {d_mid:+.3f} %, 12-18 km {d_top:+.3f} %")
    lines.append(f"  heights below 5 km bit-identical: {identical}; swap self-check ok (re-exported shipped net = installed)")
    r_mid, r_top = qb[2][1] / qo[2][1], qb[3][1] / qo[3][1]
    lines.append("AV35 rule (pre-set, b49): PASS = 5-12 km and 12-18 km p99 within 10 % of balloons, below 5 km bit-identical, CRPS within 0.1 %; "
                 "KILL = 5-12 or 12-18 km CRPS worse > 0.1 %; else MISS.")
    lines.append("AV35 on X4-R verdict: " + judge(r_mid, r_top, identical, d_all, d_mid, d_top))
    K.report(NAME, lines)


if __name__ == "__main__":
    main()
