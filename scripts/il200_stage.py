"""IL-200 step 3 (CPU): which stage of the tool adds the excess 100-300 m shear? Same 2021-22 balloon sample as scripts/il200_lowlayer_shear.py (same rng, same seeds), the tool run four ways IN PROCESS
(nothing on disk is changed; the post-processing stages are removed from the cached asset dict, then restored): (a) shipped, (b) without the shear map, (c) without the shear map and the lapse map,
(d) the pre-C4w asset set models/assets_backup_2026-11-09 (it has its own post stages, which stay). Median / p99 shear (m/s per km) per layer 100-500 m, balloons for reference.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/il200_stage.py [--per-group 80] [--out docs/results/logs/il200_stage.log]"""
import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import il103_balloon_shearmap as M   # noqa: E402
from tempest.calibrate import shear_map   # noqa: E402
from tempest_weather import api   # noqa: E402
from tempest.calibrate import station   # noqa: E402


def run(per_group, assets, drop):
    A0 = api._assets(assets)
    post0 = A0.get("post")
    if post0 is not None and drop:
        A0["post"] = {k: v for k, v in post0.items() if k not in drop}
    orig = M.tool_uv

    def tool_uv(sid, t, seed):
        if t.hour != 0:                                    # the pre-C4w set is a 06-21 h model (refuses 12Z = 05 h solar): every config uses the 00Z balloons only, so all see the same sample
            raise ValueError('12Z skipped')
        lat, lon = station.STATIONS[sid]
        atm, _ = api.atmosphere_set(lat, lon, t.isoformat() + "+00:00", n=199, seed=seed, mode="ai", elevation=station.ELEV[sid], assets=assets)
        return np.concatenate([np.asarray(atm["u"]), np.asarray(atm["v"])], 1)
    M.tool_uv = tool_uv
    try:
        xt, yt = M.collect((2021, 2022), per_group, np.random.default_rng(0))
    finally:
        M.tool_uv = orig
        if post0 is not None:
            A0["post"] = post0
    st = shear_map.shears(xt.reshape(*xt.shape[:-1], 2, M.NH).astype(np.float64))[1]
    sb = shear_map.shears(yt.reshape(yt.shape[0], 2, M.NH).astype(np.float64))[1]
    return st, sb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-group", type=int, default=80)
    ap.add_argument("--out", default="docs/results/logs/il200_stage.log")
    a = ap.parse_args()
    H = np.asarray(M._core.HEIGHTS, float)
    layers = [2, 3, 4, 5]                                  # 100-150, 150-200, 200-300, 300-500 m
    lines = ["IL-200 step 3: median / p99 shear (m/s per km) by layer, tool stages vs balloons 2021-22 (same 00Z balloons only)", "  config" + " " * 44 + "".join(f"{H[k]:.0f}-{H[k + 1]:.0f} m".rjust(16) for k in layers)]
    bal = None
    cfgs = [("shipped", None, ()), ("no shear map", None, ("smap",)), ("no shear map, no lapse map", None, ("smap", "lmap")), ("pre-C4w assets (own post)", os.path.join(REPO, "models", "assets_backup_2026-11-09"), ()), ("C4w day set before all-hours (2026-11-10 backup)", os.path.join(REPO, "models", "assets_backup_2026-11-10_day"), ())]
    for name, assets, drop in cfgs:
        try:
            st, sb = run(a.per_group, assets, drop)
        except Exception as e:  # noqa: BLE001
            lines.append(f"  {name:50s} FAILED {repr(e)[:90]}")
            print(lines[-1], flush=True)
            continue
        bal = sb
        lines.append(f"  {name:50s}" + "".join(f"{np.median(st[..., k]):7.1f} /{np.quantile(st[..., k], .99):6.1f}" for k in layers))
        print(lines[-1], flush=True)
    if bal is not None:
        lines.append(f"  {'balloons':34s}" + "".join(f"{np.median(bal[..., k]):7.1f} /{np.quantile(bal[..., k], .99):6.1f}" for k in layers))
        print(lines[-1], flush=True)
    with open(os.path.join(REPO, a.out), "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
