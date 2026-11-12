"""G1-5 spread tracker replay (README Part 5, recipe 'Innovative idea review.md' line 166). Measurement only; nothing in the tool changes.

The runtime hook (tempest_weather/bias.py, bias_dir) acts on the live ECMWF IFS ensemble feed; that feed is logged only since 2026-11 (2026 data is off limits), so the
replay uses the nearest history on disk: WeatherBench2 IFS ENS (data/raw/wb2_ifs_ens, 50 members, issued 00Z about every 8 days, 2016-2024, leads 1-7 d, valid 00 UTC)
at the grid points nearest TCS and MAF, against the ASOS 00 UTC report (scripts/bias_backtest.obs_series). Variables: 10 m wind speed (member sqrt(u10^2 + v10^2)) and 2 m temperature.

Tracker per site, variable, lead (recipe step 1): r = (obs - ens mean)^2 / ens variance; EWMA rbar, start 1, alpha 1/60 PER DAY (= 1 - (59/60)^gap per case, gap = days since
the last case of that lead), alpha 1/20 per day when r > rbar (widen fast); n = days covered by cases seen (8 per case: the recipe's n counts daily cases).
Factor = sqrt(clip(1 + n / (n + 60) (rbar - 1), 0.8^2, 1.5^2)), set from cases before this one only; members -> mean + factor (member - mean).
Scores: CRPS (fair ensemble CRPS, K.crps1) and 90 % coverage error |cov(5-95 % of members) - 0.90|, raw vs tracked, scored 2023-01-01..2024-12-31 (tracker runs online from 2016).
PASS (set 2026-11-12 07:40, before any result; recipe step 2 + New_Plan CPU-C rule): over the 4 site x variable cells (leads pooled), coverage error falls in >= 3 of 4 AND tracked
mean CRPS is not worse than raw by more than 0.0009 in any cell. Otherwise FAIL (no tracker). Day-block bootstrap intervals on the CRPS change are printed for reading.

    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b3_g15_spread_replay.py        # a few minutes, < 2 GB
Result: docs/results/logs/kit_b3_g15_spread_replay.log
"""
import glob

import numpy as np
import pandas as pd
import xarray as xr

import kit_common as K
from bias_backtest import obs_series

SITES = {"TCS": (33.2369, -107.2672), "MAF": (31.9425, -102.2019)}
SCORE_FROM, SCORE_TO = "2023-01-01", "2024-12-31"


def factors(r, gaps):
    """r (cases,) ratios in time order, gaps (cases,) days since the previous case -> factor usable for each case (from earlier cases only)."""
    rbar, n, out = 1.0, 0.0, []
    for x, g in zip(r, gaps):
        out.append(np.sqrt(np.clip(1 + n / (n + 60) * (rbar - 1), 0.8 ** 2, 1.5 ** 2)))
        if np.isfinite(x):
            a = 1 - (1 - (1 / 20 if x > rbar else 1 / 60)) ** g
            rbar += a * (x - rbar)
            n += g
    return np.array(out)


def ens_crps(m, y):
    """Fair CRPS of each row: m (cases, members), y (cases,)."""
    return np.array([K.crps1(mi, yi) for mi, yi in zip(m, y)])


def main():
    files = sorted(glob.glob(K.REPO + "/data/raw/wb2_ifs_ens/*_00z.nc"))
    lines = ["G1-5 spread tracker replay: WB2 IFS ENS 50 members, 00Z every ~8 days, %s..%s, valid 00 UTC vs ASOS; scored %s..%s" % (
        files[0][-13:-7], files[-1][-13:-7], SCORE_FROM, SCORE_TO)]
    lines.append("%-4s %-5s %4s %5s %9s %9s %8s %18s %8s %8s %7s" % ("site", "var", "lead", "n", "crps raw", "crps trk", "d crps", "95 % (day blocks)", "cov raw", "cov trk", "fac med"))
    cells = {}
    for st, (lat, lon) in SITES.items():
        obs = obs_series(st)
        ds = xr.open_mfdataset(files, combine="by_coords")[["u10", "v10", "t2m"]].sel(latitude=lat, longitude=lon % 360, method="nearest").load()
        for var in ("ws", "t"):
            ens_all = np.hypot(ds.u10, ds.v10) if var == "ws" else ds.t2m - 273.15
            acc = []
            for li, td in enumerate(ds.prediction_timedelta.values):
                e = ens_all.isel(prediction_timedelta=li).transpose("time", "number").values.astype(float)
                valid = pd.DatetimeIndex(ds.time.values) + pd.Timedelta(td)
                y = obs[var].reindex(valid).to_numpy()
                ok = np.isfinite(y) & np.isfinite(e).all(1)
                e, y, valid = e[ok], y[ok], valid[ok]
                mu, sd = e.mean(1), e.std(1, ddof=1)
                r = (y - mu) ** 2 / np.maximum(sd, 1e-6) ** 2
                gaps = np.r_[8.0, np.diff(valid.values).astype("timedelta64[h]").astype(float) / 24]
                f = factors(r, gaps)
                et = mu[:, None] + f[:, None] * (e - mu[:, None])
                sel = (valid >= SCORE_FROM) & (valid <= SCORE_TO)
                c0, c1 = ens_crps(e[sel], y[sel]), ens_crps(et[sel], y[sel])
                cov = lambda m: float(np.mean((y[sel] >= np.percentile(m, 5, 1)) & (y[sel] <= np.percentile(m, 95, 1))))
                days = valid[sel].normalize().values
                dm, lo, hi = K.block_boot(c1 - c0, days, draws=1000)
                lead = int(pd.Timedelta(td).days)
                lines.append("%-4s %-5s %4d %5d %9.3f %9.3f %+8.4f [%+7.4f %+7.4f] %8.2f %8.2f %7.2f" % (
                    st, var, lead, sel.sum(), c0.mean(), c1.mean(), dm, lo, hi, cov(e[sel]), cov(et[sel]), np.median(f[sel])))
                acc.append((c0, c1, (y[sel] >= np.percentile(e[sel], 5, 1)) & (y[sel] <= np.percentile(e[sel], 95, 1)),
                            (y[sel] >= np.percentile(et[sel], 5, 1)) & (y[sel] <= np.percentile(et[sel], 95, 1))))
            c0, c1, k0, k1 = (np.concatenate(x) for x in zip(*acc))
            cells[(st, var)] = (c0.mean(), c1.mean(), abs(k0.mean() - 0.90), abs(k1.mean() - 0.90))
    lines.append("cells (leads pooled): " + "  ".join("%s %s crps %.3f->%.3f coverr %.3f->%.3f" % (s, v, *x) for (s, v), x in cells.items()))
    cov_better = sum(x[3] < x[2] for x in cells.values())
    crps_ok = all(x[1] - x[0] <= 0.0009 for x in cells.values())
    lines.append("VERDICT: %s (coverage error falls in %d of %d cells; CRPS not worse by > 0.0009 in every cell: %s)" % (
        "PASS" if cov_better >= 3 and crps_ok else "FAIL, no tracker", cov_better, len(cells), "yes" if crps_ok else "no"))
    K.report("b3_g15_spread_replay", lines)


def _selfcheck():
    # ensemble twice too narrow (r ~ 4): factor grows towards 1.5 after enough cases
    rng = np.random.default_rng(0)
    f = factors(rng.chisquare(1, 300) * 4, np.full(300, 8.0))
    assert f[0] == 1.0 and f[-50:].mean() > 1.4
    # well calibrated (r ~ 1): factor stays near 1
    f = factors(rng.chisquare(1, 300), np.full(300, 8.0))
    assert 0.85 < f[-100:].mean() < 1.25


_selfcheck()
if __name__ == "__main__":
    main()
