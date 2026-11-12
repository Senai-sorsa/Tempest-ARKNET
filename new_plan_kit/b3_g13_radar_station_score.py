"""G1-3 radar + station score (README Part 5, recipe 'Innovative idea review.md' lines 183-186). REPORT ONLY; nothing in the tool changes.

Co-extreme ratio CX = P(10 m speed > its q95 AND 0.5-1.5 km vector shear > its q95) / 0.05 (= P(shear extreme | speed extreme): 0.05 = independent, 1 = always together; `coext` of scripts/a3_coextremes.py with
the shear taken between 500 and 1500 m instead of 10 m and one height). El Paso, balloon hours 00 / 12 UTC 2021-23 (radar cache years; never 2026).
Step 1 (truth check): CX from the balloons (Santa Teresa USM00072364: 10 m and 500 / 1500 m winds) and from radar + ASOS (ELP hourly report for the 10 m speed; EPZ radar
volume <= 65 min before the hour for 500 / 1500 m) on the SAME hours. If the two disagree beyond their day-block 95 % intervals (intervals do not overlap): STOP, write so.
Step 2 (model side, only for those radar hours): CX from the tool's climate-mode pool (K.tool, n members per hour, pooled over hours), with radar-like noise added to the model
500 / 1500 m winds: normal, sd 2.37 m/s per component (C4, kit_b2_c4_innovation_fit.log), correlation exp(-1000 / 901) between the two heights (C4's L = 901 m). Also printed
without noise. Thresholds q95 are set within each source.

    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b3_g13_radar_station_score.py        # about 10-20 min, < 3 GB
Result: docs/results/logs/kit_b3_g13_radar_station_score.log
"""
import numpy as np
import pandas as pd

import kit_common as K

SD, L = 2.37, 901.0
J5, J15 = int(np.flatnonzero(K.H == 500)[0]), int(np.flatnonzero(K.H == 1500)[0])


def cx(w, sh, q=0.95):
    return float(((w > np.quantile(w, q)) & (sh > np.quantile(sh, q))).mean() / (1 - q))


def cx_boot(w, sh, days, draws=1000, seed=0):
    """CX and a day-block 95 % interval (quantiles recomputed in each draw)."""
    u, inv = np.unique(days, return_inverse=True)
    groups = [np.flatnonzero(inv == k) for k in range(len(u))]
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(draws):
        idx = np.concatenate([groups[k] for k in rng.integers(0, len(u), len(u))])
        bs.append(cx(w[idx], sh[idx]))
    return cx(w, sh), np.percentile(bs, 2.5), np.percentile(bs, 97.5)


def shear(u5, v5, u15, v15):
    return np.hypot(u15 - u5, v15 - v5)


def main(n=100):
    lat, lon, elev = K.station_pos(K.EPZ)
    bt, b = K.balloon(K.EPZ)
    index = K.radar_files("EPZ")
    asos = K.asos_speed("ELP", range(2021, 2024))
    rows = []  # t, balloon (w, sh), radar + ASOS (w, sh)
    for k, t in enumerate(bt):
        if not (2021 <= t.year <= 2023) or t.hour not in (0, 12):
            continue
        assert K.day_ok(t)
        bw = np.hypot(b["u"][k, 0], b["v"][k, 0])
        bs = shear(b["u"][k, J5], b["v"][k, J5], b["u"][k, J15], b["v"][k, J15])
        a = asos.get(pd.Timestamp(t).tz_localize("UTC"))
        rad = K.radar_uv("EPZ", t, elev, index=index)
        if a is None or rad is None or not np.isfinite([bw, bs, a[0], rad[0][J5], rad[0][J15], rad[1][J5], rad[1][J15]]).all():
            continue
        rows.append((t, bw, bs, a[0], shear(rad[0][J5], rad[1][J5], rad[0][J15], rad[1][J15])))
    t = pd.DatetimeIndex([r[0] for r in rows])
    X = np.array([r[1:] for r in rows], float)
    days = t.normalize().values
    lines = [f"G1-3 radar + station score, El Paso 2021-23, balloon hours 00/12 UTC with balloon + ELP ASOS + EPZ radar (500 and 1500 m) all present: {len(rows)} hours, {len(set(days))} days"]
    cb, cr = cx_boot(X[:, 0], X[:, 1], days), cx_boot(X[:, 2], X[:, 3], days)
    lines.append("CX balloon            %.2f [%.2f, %.2f]" % cb)
    lines.append("CX radar + ASOS       %.2f [%.2f, %.2f]" % cr)
    lines.append("corr balloon vs radar+ASOS: 10 m speed %.2f, 0.5-1.5 km shear %.2f" % (np.corrcoef(X[:, 0], X[:, 2])[0, 1], np.corrcoef(X[:, 1], X[:, 3])[0, 1]))
    if cb[2] < cr[1] or cr[2] < cb[1]:
        lines.append("VERDICT: STOP at step 1: balloon and radar + ASOS disagree beyond their day-block intervals; no model score (recipe step 1).")
        K.report("b3_g13_radar_station_score", lines)
        return
    rng = np.random.default_rng(13)
    rho = np.exp(-1000.0 / L)
    W, S0, S1, D = [], [], [], []
    skipped = 0
    for tt in t:
        try:
            atm = K.tool(lat, lon, tt, seed=int(tt.value // 3600e9) % 100000, n=n, elevation=elev)
        except (ValueError, LookupError):
            skipped += 1
            continue
        u, v = np.asarray(atm["u"], float), np.asarray(atm["v"], float)
        W.append(np.hypot(u[:, 0], v[:, 0]))
        S0.append(shear(u[:, J5], v[:, J5], u[:, J15], v[:, J15]))
        e5 = rng.normal(0, SD, (2, n))
        e15 = rho * e5 + np.sqrt(1 - rho ** 2) * rng.normal(0, SD, (2, n))
        S1.append(shear(u[:, J5] + e5[0], v[:, J5] + e5[1], u[:, J15] + e15[0], v[:, J15] + e15[1]))
        D.append(np.full(n, tt.normalize().value))
    W, S0, S1, D = (np.concatenate(x) for x in (W, S0, S1, D))
    lines.append("CX tool, no noise     %.2f [%.2f, %.2f]   (%d hours x %d members, %d hours refused)" % (*cx_boot(W, S0, D, draws=300), len(W) // n, n, skipped))
    lines.append("CX tool + radar noise %.2f [%.2f, %.2f]   (sd %.2f m/s per component, corr %.2f between 500 and 1500 m)" % (*cx_boot(W, S1, D, draws=300), SD, rho, ))
    lines.append("q95 thresholds (10 m speed, shear): balloon %.1f, %.1f; radar+ASOS %.1f, %.1f; tool+noise %.1f, %.1f m/s" % (
        np.quantile(X[:, 0], .95), np.quantile(X[:, 1], .95), np.quantile(X[:, 2], .95), np.quantile(X[:, 3], .95), np.quantile(W, .95), np.quantile(S1, .95)))
    lines.append("VERDICT: REPORT ONLY (step 1 passed: balloon and radar + ASOS agree within their intervals); compare the tool + noise row with radar + ASOS.")
    K.report("b3_g13_radar_station_score", lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    a = rng.normal(size=20000)
    assert abs(cx(a, rng.normal(size=20000)) - 0.05) < 0.03    # independent -> about 0.05
    assert cx(a, a) > 0.99                                       # identical -> 1


_selfcheck()
if __name__ == "__main__":
    main()
