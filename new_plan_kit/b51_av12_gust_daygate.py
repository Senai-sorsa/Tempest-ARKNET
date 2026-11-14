"""New_Plan 13 AV12: P2 gust as a mixed-layer wind measurement (scripts/p2_gust_mixed.py: -2.3 % MAE at MAF 00Z, about 0 at 12Z, "too small to wire"), now with a DAYTIME GATE:
the gust predictor is used only when the launch hour is 10-18 h local SOLAR time (UTC + longitude / 15); outside the gate the plain 10 m model is used, so nothing changes at night
by construction. Same setup as P2: truth = balloon mean wind speed over 300 / 500 / 750 m; predictors at the launch hour = 10 m sustained wind (METAR minute 53) and the PHYSICAL
gust (highest 5-second peak in the 10 min before, ASOS one-minute data, scripts/gust_1min.physical_hourly); (a) speed ~ 1 + ws10, (b) ~ 1 + ws10 + (gust - ws10), least squares
fitted on 2016-2020 gated cases, tested on 2021-2023 gated cases. Interval: paired bootstrap of the test cases (2000 draws, 95 %).
Main station MAF (ASOS + IGRA 72265 at the same airport). Second station (check): EPZ balloons (72364, Santa Teresa) with El Paso ELP one-minute ASOS, about 25 km apart.
Rule written 2026-11-14 before any AV12 run (New_Plan 13 AV12 row, unchanged):
PASS: MAF gated hours MAE gain >= 2 % with the 95 % interval excluding 0, AND the second station's gated gain > 0 (the check).
KILL: MAF gated gain under 1 %.
Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b51_av12_gust_daygate.py
Result: docs/results/logs/kit_b51_av12_gust_daygate.log
"""
import glob
import os

import numpy as np
import pandas as pd

import kit_common as K

NAME = "b51_av12_gust_daygate"
AL = [300.0, 500.0, 750.0]
GATE = (10.0, 18.0)
SITES = (("MAF", "USM00072265"), ("ELP", "USM00072364"))


def solar_hour(t, lon):
    return ((t.hour + t.minute / 60.0 + lon / 15.0) % 24.0)


def gain_ci(ae_a, ae_b, rng, n=2000):
    """MAE gain of b over a in % and its paired-bootstrap 95 % interval."""
    g = 100 * (1 - ae_b.mean() / ae_a.mean())
    idx = rng.integers(0, len(ae_a), (n, len(ae_a)))
    gs = 100 * (1 - ae_b[idx].mean(1) / ae_a[idx].mean(1))
    return g, np.percentile(gs, 2.5), np.percentile(gs, 97.5)


def judge(g, lo, hi, g2):
    if g < 1.0:
        return f"KILL (MAF gated gain {g:+.2f} % < 1 %)"
    if g >= 2.0 and lo > 0 and g2 > 0:
        return f"PASS (MAF gated gain {g:+.2f} % [{lo:+.2f}, {hi:+.2f}], second station {g2:+.2f} %)"
    return f"MISS (MAF gated gain {g:+.2f} % [{lo:+.2f}, {hi:+.2f}] (needs >= 2 % and interval > 0), second station {g2:+.2f} % (needs > 0))"


def station_cases(asos, sid):
    from gust_1min import physical_hourly
    from tempest.calibrate import station
    d = np.load(os.path.join(K.REPO, "data", "igra_heights", sid + ".npz"))
    sel = [int(np.argmin(np.abs(d["heights"] - h))) for h in AL]
    t = pd.DatetimeIndex(d["time"].astype("datetime64[ns]"))
    u, v = d["u"][:, sel].astype(float), d["v"][:, sel].astype(float)
    sp = np.where((u == -32768) | (v == -32768), np.nan, np.hypot(u * 0.1, v * 0.1)).mean(1)
    bal = pd.Series(sp, index=t).dropna()
    bal = bal[(bal.index.year >= 2016) & (bal.index.year <= 2023)]
    ph = pd.concat([physical_hourly(f) for f in sorted(glob.glob(os.path.join(K.REPO, "data", "raw", "asos1min", f"{asos}_*.csv")))])
    ph = ph[~ph.index.duplicated()]
    j = pd.DataFrame({"aloft": bal}).join(ph, how="inner").dropna()
    j = j[(j.ws1 >= 1.0) & (j.gphys >= j.ws1)].copy()
    j["ex"] = j.gphys - j.ws1
    j["sh"] = solar_hour(j.index, station.STATIONS[sid][1])
    j["gate"] = (j.sh >= GATE[0]) & (j.sh < GATE[1])
    return j


def errors(j):
    """Absolute test errors of (a) ws10 and (b) gated gust model, on the test years; gate off -> (b) = (a)."""
    fit, test = j[j.index.year <= 2020], j[j.index.year >= 2021]
    out = {}
    for name, cols in (("a", ["ws1"]), ("b", ["ws1", "ex"])):
        X = lambda df: np.column_stack([np.ones(len(df))] + [df[c].values for c in cols])   # noqa: E731
        f = fit[fit.gate]
        b = np.linalg.lstsq(X(f), f.aloft.values, rcond=None)[0]
        out[name] = (b, np.abs(X(test) @ b - test.aloft.values))
    return test, out


def main():
    rng = np.random.default_rng(0)
    lines, res = [], {}
    for asos, sid in SITES:
        j = station_cases(asos, sid)
        test, out = errors(j)
        g = test.gate.values
        ae_a, ae_b = out["a"][1][g], out["b"][1][g]
        gain, lo, hi = gain_ci(ae_a, ae_b, rng)
        res[asos] = (gain, lo, hi)
        lines.append(f"{asos} ASOS + {sid} balloons: {len(j)} matched launches 2016-23, gated (solar {GATE[0]:.0f}-{GATE[1]:.0f} h) {int(j.gate.sum())}; "
                     f"test 2021-23 gated {int(g.sum())}, outside the gate {int((~g).sum())} (unchanged by construction)")
        lines.append(f"  solar hour of gated launches: {j.sh[j.gate].min():.1f}-{j.sh[j.gate].max():.1f} h; mean speed aloft (test, gated) {test.aloft.values[g].mean():.2f} m/s")
        lines.append(f"  MAE ws10 {ae_a.mean():.3f} -> ws10 + gust excess {ae_b.mean():.3f} m/s; gain {gain:+.2f} % (95 % interval {lo:+.2f} to {hi:+.2f}); "
                     f"coefficients b {np.round(out['b'][0], 3)}")
    lines.append("AV12 rule (pre-set): PASS = MAF gated gain >= 2 % with interval > 0 AND second station (ELP / EPZ) gated gain > 0; KILL = MAF gated gain < 1 %; else MISS.")
    lines.append("AV12 verdict: " + judge(*res["MAF"], res["ELP"][0]))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(2.5, 0.5, 4.0, 0.3).startswith("PASS")
    assert judge(2.5, -0.1, 4.0, 0.3).startswith("MISS")
    assert judge(2.5, 0.5, 4.0, -0.1).startswith("MISS")
    assert judge(1.5, 0.5, 4.0, 0.3).startswith("MISS")
    assert judge(0.5, 0.1, 1.0, 0.3).startswith("KILL")
    t = pd.DatetimeIndex(["2021-06-01 00:00", "2021-06-01 12:00"])
    sh = solar_hour(t, -102.2)
    assert abs(sh[0] - 17.19) < 0.01 and abs(sh[1] - 5.19) < 0.01
    a = np.ones(50) * 2.0
    g, lo, hi = gain_ci(a, a * 0.9, np.random.default_rng(0), 100)
    assert abs(g - 10) < 1e-9 and abs(lo - 10) < 1e-9


_selfcheck()
if __name__ == "__main__":
    main()
