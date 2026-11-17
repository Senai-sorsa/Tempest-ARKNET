"""23.T3 time-coherence score (MAF, June 2024): lag-k correlation of wind between hour h and h+k, observed (NEXRAD KMAF VAD, first volume each hour, data/raw/nexrad_nvw_t3)
vs the tool's atmosphere_sequence (climate-lag table). REPORT + pre-set rule.
Observed: per UTC hour demeaned over the 30 days (no diurnal leakage), pair (h, h+k) over days, start hours 13, 15, 17 UTC, u and v, heights 0-3.5 km above ground with >= 20 pairs; mean of per-height correlations.
Tool: 12 days of June 2024 at 15 UTC start, 200 members, offsets 0..6, correlation across members between offset 0 and k per height, u and v, mean over heights and days (members are climate draws, so this is the model's climatological lag correlation).
Not exactly alike (obs: across days; tool: across members; start hours differ); one month, one radar.
PRE-SET RULE (before the run): PASS if |tool - obs| <= 0.10 at each of k = 1, 3, 6. MISS otherwise (sign says too coherent / too incoherent). No kill.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b73_t3_time_coherence.py      Result: docs/results/logs/kit_b73_t3_time_coherence.log
"""
import glob, os
import numpy as np, pandas as pd
KFRAC = os.environ.get("T3_KFRAC")      # nugget experiment (in memory only): kappa_u,v -> 1 - (1 - kappa) * KFRAC for the wind columns; unset = shipped
SITE = os.environ.get("T3_SITE", "MAF")      # other radar (HDX 32.8506 -106.1228 1287 m); tool run at the radar position
RADAR = {"HDX": (32.8506, -106.1228, 1287.0)}
MONTH = os.environ.get("T3_MONTH", "2024-06")      # e.g. 2024-01; the pulled hours are enough (13-23 UTC)
import kit_common as K
from p3_vad_vs_balloon import parse

LAGS = (1, 2, 3, 4, 6)


def observed(elev):
    fs = sorted(glob.glob("data/raw/nexrad_nvw_t3/" + SITE + "_NVW_" + MONTH.replace("-", "_") + "_*"))
    first = {}
    for f in fs:
        t = pd.to_datetime(os.path.basename(f)[8:], format="%Y_%m_%d_%H_%M_%S").floor("h")
        first.setdefault(t, f)
    W = {}
    for t, f in first.items():
        try:
            W[t] = np.stack(parse(f, elev))          # (2, 44)
        except Exception:
            pass
    nh = np.sum(K.H <= 3500)
    res = {k: [] for k in LAGS}
    for k in LAGS:
        for h0 in (13, 15, 17):
            ts = [t for t in W if t.hour == h0 and (t + pd.Timedelta(hours=k)) in W]
            if len(ts) < 8:
                continue
            a = np.stack([W[t][:, :nh] for t in ts]); b = np.stack([W[t + pd.Timedelta(hours=k)][:, :nh] for t in ts])
            for c in range(2):
                for j in range(nh):
                    x, y = a[:, c, j], b[:, c, j]
                    m = np.isfinite(x) & np.isfinite(y)
                    if m.sum() >= 20 and x[m].std() > 0 and y[m].std() > 0:
                        res[k].append(np.corrcoef(x[m], y[m])[0, 1])
    return {k: (float(np.mean(v)) if v else np.nan, len(v)) for k, v in res.items()}


def tool(lat, lon, elev):
    from tempest_weather import api
    A = api._assets()
    kap0 = A.get("coherence_kappa")
    if KFRAC is not None:
        k = np.array(kap0, float)
        k[:88] = 1 - (1 - k[:88]) * float(KFRAC)
        A["coherence_kappa"] = k
    nh = int(np.sum(K.H <= 3500))
    offs = (0,) + LAGS
    res = {k: [] for k in LAGS}
    for d in range(2, 30, 2):
        when = f"{MONTH}-{d:02d}T15:00:00+00:00"
        atms, _ = api.atmosphere_sequence(lat, lon, when, offsets=offs, n=200, seed=d, mode="ai", elevation=elev)
        for k in LAGS:
            a, b = atms[0], atms[offs.index(k)]
            for q in ("u", "v"):
                x, y = np.asarray(a[q])[:, :nh], np.asarray(b[q])[:, :nh]
                x, y = x - x.mean(0), y - y.mean(0)
                res[k].append(np.mean((x * y).sum(0) / np.sqrt((x ** 2).sum(0) * (y ** 2).sum(0))))
    return {k: float(np.mean(v)) for k, v in res.items()}


def main():
    lat, lon, elev = RADAR[SITE] if SITE in RADAR else K.station_pos(K.MAF)
    ob, tl = observed(elev), tool(lat, lon, elev)
    L = [f"23.T3 time coherence, {SITE} {MONTH}: lag correlation of 0-3.5 km wind (mean over u, v, heights); observed = KMAF VAD, tool = atmosphere_sequence climate-lag table",
         "lag h   observed (n pairs)   tool    tool - obs"]
    for k in LAGS:
        L.append(f"  {k}     {ob[k][0]:.3f} ({ob[k][1]})        {tl[k]:.3f}   {tl[k] - ob[k][0]:+.3f}")
    have = all(np.isfinite(ob[k][0]) for k in (1, 3, 6))
    ok = have and all(abs(tl[k] - ob[k][0]) <= 0.10 for k in (1, 3, 6))
    L.append("VERDICT (pre-set rule, |diff| <= 0.10 at lags 1, 3, 6): " + ("NO DATA (too few observed pairs)" if not have else "PASS" if ok else "MISS"))
    L.append("Notes: lag 6 absent from LAGS-based obs if too few pairs. Observed pairs share days, so the effective sample is smaller than the pair count. One month, one radar, first VAD volume of each hour (clear-air hours hold no wind).")
    K.report("b73_t3_time_coherence" + ("" if SITE == "MAF" else "_" + SITE) + ("" if MONTH == "2024-06" else "_" + MONTH) + ("" if KFRAC is None else "_kfrac" + KFRAC), L)


if __name__ == "__main__":
    main()
