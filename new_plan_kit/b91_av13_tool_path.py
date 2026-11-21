"""New_Plan 28.11 item 8: AV13 port check through the TOOL PATH. api._gust_params with the SHIPPED Denver asset gust law (tempest_weather/assets_denver, IL-183, fitted <= 2020
pooled DEN + APA) and the query's own built-in station flag (_gust_station), scored on DEN + APA 2021-23 against the physical gust, same joins / filters / uniforms as b52.
Arms: built-in law only, region law everywhere (OPTIONS['gust_speed_switch'] = False, the tool before the port), switch (default). Port check (no rule): the switch should beat
both (b52 cross-station +1.09 % vs built-in; here the region law is in-sample by station, so the gain may be larger) and equal the built-in law below 5 m/s exactly.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b91_av13_tool_path.py
Result: docs/results/logs/kit_b91_av13_tool_path.log
"""
import os

import numpy as np
import pandas as pd

import kit_common as K
from b52_av13_gust_speed_switch import M, STATIONS, gain_ci, load


def main():
    from tempest.scoring.score import crps_ensemble
    from tempest_weather import api
    g_asset = api._assets(os.path.join(K.REPO, "tempest_weather", "assets_denver"))["gust"]
    assert "phys_model" in g_asset
    m = load()
    t = pd.DatetimeIndex(m.index)
    doy, hr, yr = t.dayofyear.to_numpy(), (t.hour + t.minute / 60).to_numpy(), t.year.to_numpy()
    o = (yr >= 2021) & (yr <= 2023)
    wo, g, era = m.ws1.values[o], m.gphys.values[o], m.ws_era.values[o]
    st = api._gust_station(*STATIONS[0][1:])
    rng = np.random.default_rng(0)
    L = -np.log(-np.log(rng.random((int(o.sum()), M)).clip(1e-12, 1 - 1e-12)))
    draw = lambda p: np.maximum(p[0][:, None] + p[1][:, None] * L, wo[:, None])   # noqa: E731
    crps = lambda x: crps_ensemble(x[..., None], g[:, None])[:, 0]                 # noqa: E731
    out = {}
    try:
        api.OPTIONS["gust_speed_switch"] = False
        out["region everywhere"] = crps(draw(api._gust_params(g_asset, era, doy[o], hr[o], st)))
        api.OPTIONS["gust_speed_switch"] = True
        out["switch"] = crps(draw(api._gust_params(g_asset, era, doy[o], hr[o], st)))
    finally:
        api.OPTIONS["gust_speed_switch"] = True
    out["built-in"] = crps(draw(api._gust_params(None, era, doy[o], hr[o], st)))
    lo5 = era < api.GUST_SWITCH_WS
    lines = [f"AV13 through api._gust_params, shipped Denver asset law, built-in station flag {st:g}: DEN + APA 2021-23, {int(o.sum())} hours ({int((~lo5).sum())} at model wind >= 5); {M} members"]
    lines += [f"  {k:<17} CRPS {v.mean():.4f}  (< 5 m/s {v[lo5].mean():.4f}, >= 5 m/s {v[~lo5].mean():.4f})" for k, v in out.items()]
    for b in ("built-in", "region everywhere"):
        gg, lo, hi = gain_ci(out[b], out["switch"], rng)
        lines.append(f"  switch gain over {b}: {gg:+.2f} % [{lo:+.2f}, {hi:+.2f}]")
    same = np.array_equal(out["switch"][lo5], out["built-in"][lo5])
    lines.append(f"  below 5 m/s identical to the built-in law: {same}")
    lines.append("Port check: switch gain over built-in > 0 (b52 cross-station +1.09 % [+0.91, +1.27]) and identical below 5 m/s -> " +
                 ("REPRODUCES" if same and gain_ci(out["built-in"], out["switch"], rng)[1] > 0 else "DOES NOT REPRODUCE"))
    K.report("b91_av13_tool_path", lines)


if __name__ == "__main__":
    main()
