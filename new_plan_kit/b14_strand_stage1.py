"""New_Plan 14.5 STRAND stage 1, climate mode (CPU, no training): moving real-day templates for a 3-hour launch window.
Question: P(10 m wind under L for 3 hours in a row), from the tool's climate-mode members, against the ERA5 truth. Three arms on the SAME per-hour
members (tempest_weather.api.atmosphere_sequence, mode 'ai', offsets 0 / 1 / 2 h):
  IND  each hour on its own (product of the three per-hour fractions) = the ordinary pool, stage 0's baseline;
  SEQ  the shipped coherent sequence (Gaussian copula with the ERA5 lag table), as the tool returns it;
  TPL  STRAND: each hour's members re-ordered by the ranks of n real consecutive 3-hour ERA5 windows (same point, month, start hour; template years
       1991-2005), whole windows only, so a member follows one real day through the window (the 'moving template', improvement 3).
Truth: ERA5 hourly store data/pilot/profiles80.zarr, u10 / v10, 2006-2020 (disjoint from the template years; no 2026 data).
Cells: 12 store points (lat 31.5 / 32.5 / 33.5 x lon -107.5 / -105.5 / -103.5 / -101.5) x 12 months x start 15 / 18 / 21 UTC; query date
2013-<month>-15 (middle of the truth years, inside the generator's training years, so the marginals sit in the truth period). Open cells only:
truth P_indep in 0.05..0.95 (stage 0's filter).

Rule (set before any result; written 2026-11-13 08:40, from the plan's stage 1 text):
  per limit L in (5, 8, 10) m/s, err(arm) = mean over open cells of |P_arm - P_real|.
  PASS: err(TPL) <= 0.5 x err(SEQ) at every limit, in both seeds (tool seed and template draw seed 0 and 1).
  STOP (STRAND not needed in climate mode): err(SEQ) < 0.02 at every limit in both seeds (stage 0's line; the shipped copula already does the job).
  KILL: err(TPL) >= err(SEQ) at every limit in both seeds, or any per-hour member set changed (per-hour CRPS clause: TPL only permutes members,
        so per-hour CRPS is identical by construction; asserted).
  Otherwise MISS (record; section 13 standing note).
  Deviations from the plan text, stated before the run: (1) the baseline that must halve is the shipped coherent sequence SEQ, not the independent
  draws (stage 0 measured against independent draws; the tool already ties hours, so beating IND alone would prove nothing); IND is reported.
  (2) 'Aged noise' is the forecast-mode half (network noise by lead); climate mode has no lead, so stage 1 here is the template half only, on the
  first target the plan names (climate mode, hourly ERA5 store). Past mode and forecast mode are not run here.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b14_strand_stage1.py
Result: docs/results/logs/kit_b14_strand_stage1.log
"""
import numpy as np
import pandas as pd
import xarray as xr

import kit_common as K

LIMITS = (5.0, 8.0, 10.0)
LATS, LONS = (31.5, 32.5, 33.5), (-107.5, -105.5, -103.5, -101.5)
STARTS = (15, 18, 21)
TEMPLATE, TRUTH = ("1991", "2005"), ("2006", "2020")
N = 1024


def windows(w, t, month, hour):
    """w (T,) hourly wind at one point, t DatetimeIndex -> (k, 3) consecutive 3-hour windows starting at `hour` UTC in `month`."""
    gap = np.diff(t.values).astype("timedelta64[h]").astype(int)
    ok = np.flatnonzero((gap[:-1] == 1) & (gap[1:] == 1) & (t.month[:-2] == month) & (t.hour[:-2] == hour))
    return np.stack([w[ok], w[ok + 1], w[ok + 2]], 1)


def template_order(members, tpl, rng):
    """members (3, n) per-hour values; tpl (k, 3) real windows -> (3, n): each hour's sorted members placed at the ranks of n drawn real windows."""
    n = members.shape[1]
    pick = tpl[rng.integers(0, len(tpl), n)]
    out = np.empty_like(members)
    for h in range(3):
        rank = np.argsort(np.argsort(pick[:, h] + 1e-9 * rng.random(n)))     # ties (resampled windows) broken at random
        out[h] = np.sort(members[h])[rank]
    return out


def probs(w3, L):
    """w3 (3, n) -> (P all three under L, product of per-hour fractions)."""
    b = w3 < L
    return b.all(0).mean(), np.prod(b.mean(1))


def judge(err):
    """err[seed][L] = (IND, SEQ, TPL) -> verdict."""
    e = [v for s in err.values() for v in s.values()]
    if all(x[1] < 0.02 for x in e):
        return "STOP (shipped sequence already within 0.02 at every limit; STRAND not needed in climate mode)"
    if all(x[2] <= 0.5 * x[1] for x in e):
        return "PASS"
    if all(x[2] >= x[1] for x in e):
        return "KILL (templates no better than the shipped sequence anywhere)"
    return "MISS (record)"


def main():
    from tempest_weather import api
    ds = xr.open_zarr(K.REPO + "/data/pilot/profiles80.zarr")
    la, lo = ds.lat.values, ds.lon.values
    pts = [int(np.argmin((la - a) ** 2 + (lo - b) ** 2)) for a in LATS for b in LONS]
    sub = ds[["u10", "v10"]].isel(point=pts).sel(time=slice(TEMPLATE[0], TRUTH[1])).load()
    t = pd.DatetimeIndex(sub.time.values)
    assert t.year.max() <= 2020, "no data after 2020 here"
    W = np.hypot(sub.u10.values, sub.v10.values)                           # (P, T)
    lines = [f"STRAND stage 1 (climate mode): P(10 m wind under L for 3 h), tool members re-ordered three ways; {len(pts)} points x 12 months x "
             f"start {STARTS} UTC; templates {TEMPLATE[0]}-{TEMPLATE[1]}, truth {TRUTH[0]}-{TRUTH[1]}; n {N}"]
    err, skipped = {}, 0
    for seed in (0, 1):
        rng = np.random.default_rng(100 + seed)
        rows = {L: [] for L in LIMITS}
        for pi, p in enumerate(pts):
            ty = t.year
            for m in range(1, 13):
                for h in STARTS:
                    tpl = windows(W[pi][(ty >= int(TEMPLATE[0])) & (ty <= int(TEMPLATE[1]))], t[(ty >= int(TEMPLATE[0])) & (ty <= int(TEMPLATE[1]))], m, h)
                    tru = windows(W[pi][(ty >= int(TRUTH[0]))], t[ty >= int(TRUTH[0])], m, h)
                    if len(tpl) < 100 or len(tru) < 100:
                        skipped += 1
                        continue
                    try:
                        atms, _ = api.atmosphere_sequence(float(la[p]), float(lo[p]), f"2013-{m:02d}-15T{h:02d}:00:00+00:00", offsets=(0, 1, 2), n=N, seed=seed, mode="ai")
                    except ValueError:
                        skipped += 1
                        continue
                    seq = np.stack([np.hypot(a["u"][:, 0], a["v"][:, 0]) for a in atms]).astype(float)
                    tp = template_order(seq, tpl, rng)
                    assert np.allclose(np.sort(tp, 1), np.sort(seq, 1)), "templates changed a per-hour member set"
                    for L in LIMITS:
                        pr, pir = probs(tru.T, L)
                        if not 0.05 <= pir <= 0.95:
                            continue
                        ps, pind = probs(seq, L)
                        rows[L].append((pr, pind, ps, probs(tp, L)[0], pir))
        err[seed] = {}
        for L in LIMITS:
            r = np.array(rows[L])
            e = tuple(float(np.abs(r[:, j] - r[:, 0]).mean()) for j in (1, 2, 3))
            err[seed][L] = e
            lines.append(f"  seed {seed} L {L:>4.0f} m/s: {len(r)} open cells; mean P real {r[:, 0].mean():.3f}, IND {r[:, 1].mean():.3f}, SEQ {r[:, 2].mean():.3f}, "
                         f"TPL {r[:, 3].mean():.3f}; mean |error| IND {e[0]:.4f}, SEQ {e[1]:.4f}, TPL {e[2]:.4f} (TPL / SEQ {e[2] / e[1]:.2f}); "
                         f"marginal check |P_indep tool - truth| {np.abs(r[:, 1] - r[:, 4]).mean():.4f}")
    lines.append(f"  cells skipped (outside the served hours / too few windows): {skipped}")
    lines.append("Verdict: " + judge(err))
    K.report("b14_strand_stage1", lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    base = rng.uniform(0, 10, 3000)
    tpl = np.stack([base, base + rng.normal(0, 0.3, 3000), base + rng.normal(0, 0.6, 3000)], 1)    # strongly linked hours
    mem = rng.uniform(0, 10, (3, 1024))                                                             # independent members
    out = template_order(mem, tpl, rng)
    assert np.allclose(np.sort(out, 1), np.sort(mem, 1))
    assert np.corrcoef(out[0], out[1])[0, 1] > 0.9 and abs(np.corrcoef(mem[0], mem[1])[0, 1]) < 0.1
    pr, pi = probs(tpl.T, 5.0)
    assert abs(probs(out, 5.0)[0] - pr) < 0.05 and pr - pi > 0.2
    t = pd.date_range("2001-01-01", periods=24 * 60, freq="h")
    assert windows(np.arange(len(t), dtype=float), t, 1, 15).shape == (31, 3)
    e = lambda a, b, c: {0: {5.0: (0.2, a, b)}, 1: {5.0: (0.2, a, c)}}
    assert judge(e(0.01, 0.005, 0.004)).startswith("STOP")
    assert judge(e(0.10, 0.04, 0.05)) == "PASS"
    assert judge(e(0.10, 0.12, 0.11)).startswith("KILL")
    assert judge(e(0.10, 0.07, 0.04)).startswith("MISS")


_selfcheck()
if __name__ == "__main__":
    main()
