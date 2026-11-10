"""IL-187 (2026-11-10): would BALLOON shuffle templates for the 0-3 km wind lift the wind / shear co-extremes toward the real rate (balloons 0.17, ERA5 templates 0.07, the shuffle hands on
about 78 % of what its templates hold: IL-169)? Offline, against held-out balloons only (B30: ERA5 shares the deficit):
for EPZ (72364) and MAF (72265) soundings of 2024-25 at 00Z and 12Z, the tool's atmospheres for the station, date and UTC hour (climate mode, as shipped: ERA5 templates), then the same
samples with the u / v columns at <= 3 km re-ranked by 199 training-year balloons (<= 2020) of the same station, month and launch hour (a Schaake shuffle of those columns only).
Scores: the pooled co-extreme ratio P(10 m wind > q95 and 0-1 km shear > q95) / 0.05 (model pool vs the balloon pool) and the variogram score of the 0-3 km wind per sounding (lower = better
joint shape; the marginals, hence CRPS, are identical by construction).
    PYTHONPATH=. python -W ignore scripts/il187_balloon_templates.py [--per-group 120] [--out docs/results/logs/il187_balloon_templates.log]"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest.calibrate import station   # noqa: E402
from tempest.scoring.score import variogram_score   # noqa: E402
from tempest_weather import _core, api   # noqa: E402

H = np.asarray(_core.HEIGHTS, float)
LOW = np.flatnonzero(H <= 3000.0)
J1 = int(np.argmin(np.abs(H - 1000.0)))


def balloons(sid):
    d = np.load(os.path.join(REPO, "data", "igra_heights", sid + ".npz"))
    sel = np.array([int(np.argmin(np.abs(d["heights"] - h))) for h in H[LOW]])
    u, v = d["u"][:, sel].astype(float), d["v"][:, sel].astype(float)
    ok = ~((u == -32768) | (v == -32768)).any(1)
    return pd.DatetimeIndex(d["time"].astype("datetime64[ns]"))[ok], u[ok] * 0.1, v[ok] * 0.1


def coextreme(u, v):
    w = np.hypot(u[:, 0], v[:, 0])
    sh = np.hypot(u[:, J1] - u[:, 0], v[:, J1] - v[:, 0])
    return float(((w > np.quantile(w, 0.95)) & (sh > np.quantile(sh, 0.95))).mean() / 0.05)


def reshuffle(x, tpl):
    """x (m, k) samples, tpl (m, k) template values -> x with each column in the template's rank order."""
    r = np.argsort(np.argsort(tpl, axis=0), axis=0)
    return np.take_along_axis(np.sort(x, axis=0), r, axis=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-group", type=int, default=120, help="soundings per station x launch hour")
    ap.add_argument("--out", default="docs/results/logs/il187_balloon_templates.log")
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    lines = ["IL-187 balloon templates for the 0-3 km wind, held-out balloons 2024-25 (EPZ, MAF): co-extreme ratio (model pool | balloon pool) and mean variogram score of the 0-3 km u / v"]
    for sid in ("USM00072364", "USM00072265"):
        lat, lon = station.STATIONS[sid]
        t, U, V = balloons(sid)
        for hh in (0, 12):
            test = np.flatnonzero((t.year >= 2024) & (t.year <= 2025) & (t.hour == hh))
            test = np.sort(rng.choice(test, min(a.per_group, len(test)), replace=False))
            pools = {"ERA5 templates (shipped)": ([], []), "balloon templates 0-3 km": ([], [])}
            truth_u, truth_v, vs = [], [], {k: [] for k in pools}
            for k in test:
                tr = np.flatnonzero((t.year <= 2020) & (t.month == t[k].month) & (t.hour == hh))
                if len(tr) < 60:
                    continue
                try:
                    atm, info = api.atmosphere_set(lat, lon, t[k].isoformat() + "+00:00", n=199, seed=int(k), mode="ai", elevation=station.ELEV[sid])
                except ValueError:
                    continue
                xu, xv = np.asarray(atm["u"])[:, LOW], np.asarray(atm["v"])[:, LOW]
                pick = rng.choice(tr, 199, replace=len(tr) < 199)
                bu, bv = reshuffle(xu, U[pick]), reshuffle(xv, V[pick])
                for name, (pu, pv) in (("ERA5 templates (shipped)", (xu, xv)), ("balloon templates 0-3 km", (bu, bv))):
                    pools[name][0].append(pu)
                    pools[name][1].append(pv)
                    vs[name].append(variogram_score(pu[None], U[k][None])[0] + variogram_score(pv[None], V[k][None])[0])
                truth_u.append(U[k])
                truth_v.append(V[k])
            if len(truth_u) < 30:
                continue
            tu, tv = np.array(truth_u), np.array(truth_v)
            txt = [f"{sid} {hh:02d}Z n {len(tu)}: balloon pool co-extreme {coextreme(tu, tv):.3f}"]
            for name, (pu, pv) in pools.items():
                txt.append(f"{name} {coextreme(np.concatenate(pu), np.concatenate(pv)):.3f}, VS {np.mean(vs[name]):.2f}")
            lines.append("  " + " | ".join(txt))
            print(lines[-1], flush=True)
    with open(a.out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n\n")


if __name__ == "__main__":
    main()
