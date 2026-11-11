"""New_Plan 10.1 S3: whole radar profile, thinned. Condition on the radar wind up to 5 km at one level per error length (1000 m: 500, 1500,
2500, 3500, 4500 m) with a larger sigma (3.0 / 4.5 / 6.0 m/s), instead of the shipped four levels 500-2000 m at 3.0 m/s. Engine, pool,
inflation 1.5 and scoring as scripts/p3_vad_condition.py (00Z balloon, radar volume near 23:30 UTC the day before; files cached in
data/raw/nexrad_nvw). Also "thin to 3500" (the 4500 m level dropped: the radar is biased +1.3 m/s near 5 km, C4).
Choice: the setting with 2.5-5 km coverage in 0.85-0.95 and the best 5-12 km CRPS, chosen on EPZ 2021-22 only.
Score once on EPZ 2023 and on MAF 2021-23 (MAF takes no part in the choice). "Points" = CRPS skill vs free in %, setting minus shipped.
PASS (pre-set, New_Plan 10.1): chosen setting has coverage 0.85-0.95 at 2.5-5 km AND >= 2 points better CRPS at 5-12 km than the shipped
      four levels, at EPZ 2023 and MAF, in both seeds.
KILL: no setting reaches 0.85 at 2.5-5 km on the EPZ choice hours -> closed for good.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b4_radar_thinned.py --seed 0     # then --seed 1; ~1 h each
    KIT_SMOKE=1 PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b4_radar_thinned.py --n 3
Result: docs/results/logs/kit_b4_radar_thinned.log
"""
import argparse
import os

import numpy as np
import pandas as pd

import kit_common as K
from p3_vad_vs_balloon import fetch, parse
from tempest.calibrate import station
from tempest.scoring.score import crps_ensemble
from tempest_weather import _core
from tempest_weather.flight import TempestFlightSimEngine

H = np.asarray(_core.HEIGHTS, float)
SHIPPED = (500.0, 1000.0, 1500.0, 2000.0)
THIN = (500.0, 1500.0, 2500.0, 3500.0, 4500.0)
SETTINGS = {"shipped 4 lv s3.0": (SHIPPED, 3.0)}
SETTINGS.update({f"thin5 s{s}": (THIN, s) for s in (3.0, 4.5, 6.0)})
SETTINGS.update({f"thin4 s{s}": (THIN[:-1], s) for s in (3.0, 4.5, 6.0)})
BANDS = (("2.5-5 km", 2500, 5000), ("5-12 km", 5000, 12000))
SITES = {"EPZ": ("USM00072364", None), "MAF": ("USM00072265", (2021, 2023))}


def obs_at(levels, ur, vr):
    """Radar u, v at the given levels where finite -> the observation dict condition_on_observations takes."""
    obs = {}
    for j, h in enumerate(H):
        if h in levels and np.isfinite(ur[j]) and np.isfinite(vr[j]):
            obs[("wind_u", float(h))], obs[("wind_v", float(h))] = float(ur[j]), float(vr[j])
    return obs


def site_rows(radar, balloon, years, n, seed):
    d = np.load(os.path.join(K.REPO, "data", "igra_heights", balloon + ".npz"))
    sel = np.array([int(np.argmin(np.abs(d["heights"] - h))) for h in H])
    t = pd.DatetimeIndex(d["time"].astype("datetime64[ns]"))
    keep = np.flatnonzero((t.year >= years[0]) & (t.year <= years[1]) & (t.hour == 0))
    assert not (t[keep].year >= 2026).any()
    lat, lon = station.STATIONS[balloon]
    rows, done = [], 0
    for k in np.random.default_rng(seed).permutation(keep):
        if done >= n:
            break
        ub, vb = d["u"][k][sel].astype(float), d["v"][k][sel].astype(float)
        if ((ub == -32768) | (vb == -32768)).any():
            continue
        ub, vb = ub * 0.1, vb * 0.1
        try:
            p = fetch(t[k] - pd.Timedelta(days=1), radar)
            r = parse(p, station.ELEV[balloon]) if p else None
            eng = TempestFlightSimEngine(lat, lon, t[k].tz_localize("UTC").isoformat(), n_pool=1024, seed=int(k) + 100000 * seed, elevation=station.ELEV[balloon])
        except Exception:   # noqa: BLE001  (a day without a radar file or an engine pool is skipped, as p3_vad_condition.py)
            continue
        if r is None:
            continue
        ur, vr = r
        U = np.random.default_rng(1 + seed).random((400, 12))
        out = {"free": eng.sample_sobol(U)}
        for name, (levels, sig) in SETTINGS.items():
            obs = obs_at(levels, ur, vr)
            if not obs:
                break
            eng.condition_on_observations(obs, sensor_sigma={"wind_u": sig, "wind_v": sig}, inflate=1.5)
            out[name] = eng.sample_sobol(U)
            eng.clear_observations()
        if len(out) != len(SETTINGS) + 1:
            continue
        done += 1
        day = str(t[k].date())
        for name, b in out.items():
            for band, lo_, hi_ in BANDS:
                m = (H >= lo_) & (H < hi_)
                cr, cv = [], []
                for key, y in (("u", ub), ("v", vb)):
                    x = b[key][:, m]
                    cr.append(crps_ensemble(x[None], y[m][None])[0].mean())
                    q = np.quantile(x, [0.05, 0.95], axis=0)
                    cv.append(((y[m] >= q[0]) & (y[m] <= q[1])).mean())
                rows.append(dict(day=day, year=t[k].year, method=name, band=band, crps=float(np.mean(cr)), cov90=float(np.mean(cv))))
    return pd.DataFrame(rows)


def summary(df):
    """-> {(band, method): (crps, cov90, skill % vs free)}"""
    g = df.groupby(["band", "method"])[["crps", "cov90"]].mean()
    return {(b, m): (r.crps, r.cov90, 100 * (1 - r.crps / g.loc[(b, "free"), "crps"])) for (b, m), r in g.iterrows()}


def choose(s):
    """Settings with 2.5-5 km coverage in 0.85-0.95, best 5-12 km CRPS first -> chosen name or None."""
    ok = [m for m in SETTINGS if m != "shipped 4 lv s3.0" and 0.85 <= s[("2.5-5 km", m)][1] <= 0.95]
    return min(ok, key=lambda m: s[("5-12 km", m)][0]) if ok else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150, help="days per block (EPZ 2021-22, EPZ 2023, MAF)")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    K.ram_gate(3.0)
    blocks = {"EPZ 2021-22 (choice)": site_rows("EPZ", SITES["EPZ"][0], (2021, 2022), a.n, a.seed),
              "EPZ 2023": site_rows("EPZ", SITES["EPZ"][0], (2023, 2023), a.n, a.seed),
              "MAF 2021-23": site_rows("MAF", SITES["MAF"][0], SITES["MAF"][1], a.n, a.seed)}
    lines = [f"S3 radar thinned: seed {a.seed}, inflation 1.5, 00Z balloon vs radar 23 UTC; u and v averaged; points = CRPS skill vs free (%)"]
    sums = {}
    for name, df in blocks.items():
        if df.empty:
            lines.append(f"{name}: no usable days")
            continue
        s = sums[name] = summary(df)
        lines.append(f"{name}: {df.day.nunique()} days")
        for band, _, _ in BANDS:
            for m in ["free"] + list(SETTINGS):
                c, cv, sk = s[(band, m)]
                lines.append(f"  {band:8s} {m:18s} CRPS {c:5.2f} ({sk:+5.1f} %)  cov90 {cv:.2f}")
    ch = choose(sums["EPZ 2021-22 (choice)"]) if "EPZ 2021-22 (choice)" in sums else None
    if ch is None:
        lines.append("KILL: no setting reaches coverage 0.85-0.95 at 2.5-5 km on the EPZ choice hours -> S3 closed for good.")
        K.report("b4_radar_thinned", lines)
        return
    lines.append(f"Chosen on EPZ 2021-22: {ch}")
    ok_all = True
    for name in ("EPZ 2023", "MAF 2021-23"):
        if name not in sums:
            ok_all = False
            continue
        s, df = sums[name], blocks[name]
        cov = s[("2.5-5 km", ch)][1]
        pts = s[("5-12 km", ch)][2] - s[("5-12 km", "shipped 4 lv s3.0")][2]
        hi = df[df.band == "5-12 km"].pivot_table(index="day", columns="method", values="crps")
        dm, dlo, dhi = K.block_boot((hi[ch] - hi["shipped 4 lv s3.0"]).to_numpy(), list(hi.index), draws=1000)
        ok = 0.85 <= cov <= 0.95 and pts >= 2.0
        ok_all &= ok
        lines.append(f"  {name}: cov90 2.5-5 km {cov:.2f}, 5-12 km {pts:+.1f} points vs shipped (CRPS {dm:+.3f} [{dlo:+.3f}, {dhi:+.3f}])  {'ok' if ok else 'fail'}")
    lines.append("Rule (pre-set): coverage 0.85-0.95 at 2.5-5 km AND >= 2 points better at 5-12 km than shipped four levels, at EPZ 2023 and MAF; both seeds.")
    lines.append("Seed verdict: " + ("PASS (needs the other seed)" if ok_all else "FAIL -> S3 closed; the shipped four levels stay"))
    K.report("b4_radar_thinned", lines)


def _selfcheck():
    ur = np.full(len(H), np.nan)
    vr = ur.copy()
    ur[H == 1500.0], vr[H == 1500.0] = 4.0, -2.0
    assert obs_at(THIN, ur, vr) == {("wind_u", 1500.0): 4.0, ("wind_v", 1500.0): -2.0} and obs_at(SHIPPED[:1], ur, vr) == {}
    s = {("2.5-5 km", m): (1.0, 0.80, 0.0) for m in SETTINGS}
    s.update({("5-12 km", m): (1.0, 0.9, 0.0) for m in SETTINGS})
    assert choose(s) is None
    s[("2.5-5 km", "thin5 s4.5")] = (1.0, 0.88, 0.0)
    assert choose(s) == "thin5 s4.5"


_selfcheck()
if __name__ == "__main__":
    main()
