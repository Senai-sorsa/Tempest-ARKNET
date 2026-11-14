"""New_Plan 13 AV37: AV13 (PASS 2026-11-14: Denver region gust law where ERA5 10 m wind >= 5 m/s, built-in below; cross-station CRPS +1.09 % [+0.91, +1.27]) with a SMOOTH weight
instead of the step: member quantiles blended x = (1 - w) built-in + w region with the same Gumbel uniforms, w = logistic((ERA5 10 m wind - 5) / 1 m/s); centre 5 and width 1 m/s
fixed in the New_Plan row before the run. Same data, laws (built-in flag 1), cross-station DEN <-> APA test, uniforms and bootstrap as AV13 (new_plan_kit/b52_av13_gust_speed_switch.py).
Rule written 2026-11-14 before any AV37 run (New_Plan 13 AV37 row, unchanged):
PASS: cross-station CRPS better than the AV13 step switch with the 95 % interval excluding 0, AND gain over the built-in law below 5 m/s >= 0.
KILL: worse than the step switch (gain vs step < 0).
Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b54_av37_gust_smooth_weight.py
Result: docs/results/logs/kit_b54_av37_gust_smooth_weight.log
"""
import numpy as np
import pandas as pd

import kit_common as K
from b52_av13_gust_speed_switch import M, STATIONS, SWITCH, gain_ci, load, switch

NAME = "b54_av37_gust_smooth_weight"
WIDTH = 1.0


def weight(w_model):
    return 1.0 / (1.0 + np.exp(-(w_model - SWITCH) / WIDTH))


def judge(g, lo, hi, g_low):
    if g < 0:
        return f"KILL (smooth weight worse than the step switch: {g:+.2f} % [{lo:+.2f}, {hi:+.2f}])"
    if lo > 0 and g_low >= 0:
        return f"PASS (vs step {g:+.2f} % [{lo:+.2f}, {hi:+.2f}], below {SWITCH:g} m/s vs built-in {g_low:+.2f} %)"
    return f"MISS (vs step {g:+.2f} % [{lo:+.2f}, {hi:+.2f}] (interval must exclude 0), below {SWITCH:g} m/s vs built-in {g_low:+.2f} % (needs >= 0))"


def main():
    from gust_measured_fit import feats, fit_gumbel
    from tempest.scoring.score import crps_ensemble
    from tempest_weather import api
    m = load()
    t = pd.DatetimeIndex(m.index)
    doy, hr, yr = t.dayofyear.to_numpy(), (t.hour + t.minute / 60).to_numpy(), t.year.to_numpy()
    wo, g, era, sid = m.ws1.values, m.gphys.values, m.ws_era.values, m.sid.values
    Xe = feats(era, doy, hr, np.zeros(len(m)), "add2")[1]
    fit, val = yr <= 2020, (yr >= 2021) & (yr <= 2023)
    rng = np.random.default_rng(0)            # same seed and draw order as AV13, so the step switch reproduces kit_b52
    lines = [f"AV37 smooth weight w = logistic((ERA5 10 m wind - {SWITCH:g}) / {WIDTH:g}) vs AV13 step: {len(m)} hours DEN + APA, test 2021-23 {int(val.sum())}"]
    cb, cs, cw, low = [], [], [], []
    for (a, *_), (b, *_) in ((STATIONS[0], STATIONS[1]), (STATIONS[1], STATIONS[0])):
        f, o = fit & (sid == a), val & (sid == b)
        th = fit_gumbel(Xe[f], g[f])
        L = -np.log(-np.log(rng.random((int(o.sum()), M)).clip(1e-12, 1 - 1e-12)))

        def draw(mu, beta):
            return np.maximum(mu[:, None] + beta[:, None] * L, wo[o][:, None])
        xb = draw(*api._gust_physical(api.GUST_PHYS_MODEL, api.GUST_PHYS_MODEL_CAP, era[o], doy[o], hr[o], 1.0))
        xr_ = draw(Xe[o] @ th[0], np.exp(np.clip(Xe[o] @ th[1], -6, 4)))
        wt = weight(era[o])[:, None]
        xw = (1 - wt) * xb + wt * xr_
        crps = lambda x: crps_ensemble(x[..., None], g[o][:, None])[:, 0]   # noqa: E731
        c_b, c_s, c_w = crps(xb), crps(switch(xb, xr_, era[o])), crps(xw)
        lines.append(f"  law fitted on {a}, scored on {b} ({int(o.sum())} h): CRPS built-in {c_b.mean():.4f}, step {c_s.mean():.4f}, smooth {c_w.mean():.4f}")
        cb.append(c_b), cs.append(c_s), cw.append(c_w), low.append(era[o] < SWITCH)
    cb, cs, cw, low = map(np.concatenate, (cb, cs, cw, low))
    g_step, lo, hi = gain_ci(cs, cw, rng)
    g_low = 100 * (1 - cw[low].mean() / cb[low].mean())
    lines.append(f"  pooled: step vs built-in {100 * (1 - cs.mean() / cb.mean()):+.2f} % (AV13 reported +1.09 %); smooth vs built-in {100 * (1 - cw.mean() / cb.mean()):+.2f} %; "
                 f"smooth vs step {g_step:+.2f} % (95 % interval {lo:+.2f} to {hi:+.2f}); below {SWITCH:g} m/s smooth vs built-in {g_low:+.3f} % ({int(low.sum())} h)")
    lines.append("AV37 rule (pre-set): PASS = better than the step with interval excluding 0 AND below 5 m/s not worse than built-in; KILL = worse than the step; else MISS.")
    lines.append("AV37 verdict: " + judge(g_step, lo, hi, g_low))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(0.5, 0.1, 0.9, 0.1).startswith("PASS")
    assert judge(0.5, 0.1, 0.9, -0.1).startswith("MISS")
    assert judge(0.5, -0.1, 0.9, 0.1).startswith("MISS")
    assert judge(-0.1, -0.3, 0.1, 0.1).startswith("KILL")
    w = weight(np.array([-100.0, SWITCH, 100.0]))
    assert w[0] < 1e-9 and abs(w[1] - 0.5) < 1e-12 and w[2] > 1 - 1e-9


_selfcheck()
if __name__ == "__main__":
    main()
