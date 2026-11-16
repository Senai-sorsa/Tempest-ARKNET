"""New_Plan 12.6 DP v4: tower replay of the drone profiler. TTU SWiFT 200 m tower (data/raw/a2e/ttu_swift_200m, 10-min rows).
Case = a tower hour t0 (minute 00) that also has rows 30 and 60 min later. The tool (Launch, climate mode, n 200, seed from t0, pad = the tower) is run for the launch time t0 + lead (lead 30 and 60 min):
  arm A (shipped, 10 m report only): observe(wind_10m, wind_from_deg) from the tower 10 m at t0.
  arm B (drone profile): arm A + observe_radar(profile = tower u, v at t0 interpolated to the model heights 10 / 50 / 100 / 150 / 200 m, sigma 0.5 m/s, levels those five).
Score: CRPS of the 50-150 m layer-mean wind (mean of u at the model heights 50, 100, 150; same for v; the mean of the u and v CRPS) against the tower layer mean at t0 + lead (tower interpolated the same way). Also reported: persistence (tower layer mean at t0) as a point forecast (absolute error).
Gain = (CRPS A - CRPS B) / CRPS A, pooled over cases (ratio of means); interval by a 1000-draw bootstrap over campaign blocks (hours > 12 h apart start a block).
Rule (New_Plan 12.6, set before any run): at lead 30 min, PASS = gain >= 40 %; KILL = gain < 15 %; else MISS. Lead 60 reported. Limits: the tool's launch time is the target time while the observation is not aged (no age weighting);
the tower is 3-4 campaigns, not independent; the replay never tests the cross-pattern self-calibration or a real drone, which wait for the user (ASK_LATER).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b67_dp_tower_replay.py
Result: docs/results/logs/kit_b67_dp_tower_replay.log
"""
import numpy as np
import pandas as pd

import kit_common as K

NAME = "b67_dp_tower_replay"
LAT, LON = 33.607, -102.047
FT = (33, 55, 155, 245, 382, 519, 656)
MH = np.array([10.0, 50.0, 100.0, 150.0, 200.0])
LAYER = [1, 2, 3]
SIGMA = 0.5


def judge(gain):
    return "PASS" if gain >= 0.40 else ("KILL" if gain < 0.15 else "MISS")


def uv(speed, dirn):
    r = np.deg2rad(dirn)
    return -speed * np.sin(r), -speed * np.cos(r)


def profile(row, cols):
    """tower row -> u, v on MH (linear in height, NaN if a needed tower height is missing)."""
    z, u, v = [], [], []
    for h, (sc, dc) in cols.items():
        s, d = row[sc], row[dc]
        if np.isfinite(s) and np.isfinite(d):
            a, b = uv(s, d)
            z.append(h); u.append(a); v.append(b)
    if len(z) < 4 or min(z) > 10.5 or max(z) < 199:
        return None
    return np.interp(MH, z, u), np.interp(MH, z, v)


def blocks(t, gap_h=12):
    t = pd.DatetimeIndex(t)
    return np.concatenate([[0], np.cumsum(np.diff(t.values) > np.timedelta64(gap_h, "h"))])


def main():
    from tempest_weather_v2 import Launch
    K.ram_gate(3.0)
    d = pd.read_csv("data/raw/a2e/ttu_swift_200m/processed/swift_10min.csv", parse_dates=["time_utc"]).set_index("time_utc").sort_index()
    cols = {round(f * 0.3048): (f"speed_{f}ft", f"dir_{f}ft") for f in FT if f"speed_{f}ft" in d.columns and f"dir_{f}ft" in d.columns}
    hrs = [t for t in d.index if t.minute == 0]
    rows = []
    for t0 in hrs:
        p0 = profile(d.loc[t0], cols)
        if p0 is None:
            continue
        r = {"t": t0}
        ok = False
        for lead in (30, 60):
            t1 = t0 + pd.Timedelta(minutes=lead)
            if t1 not in d.index:
                continue
            p1 = profile(d.loc[t1], cols)
            if p1 is None:
                continue
            try:
                L = Launch(LAT, LON, t1.strftime("%Y-%m-%d %H:%M"), tz="UTC", n=200, seed=int(t0.timestamp()) % 100000, units="si", mode="ai")
                elev = float(L.elevation_info()[0])
                s10 = float(np.hypot(p0[0][0], p0[1][0]))
                fr = float((np.rad2deg(np.arctan2(-p0[0][0], -p0[1][0])) + 360) % 360)
                A = L.observe(wind_10m=s10, wind_from_deg=fr)
                prof = dict(heights_asl_m=list(MH + elev), u=list(p0[0]), v=list(p0[1]), site="tower", time=str(t0))
                B = A.observe_radar(site="tower", profile=prof, levels_m=tuple(MH), sigma_ms=SIGMA)
                out = []
                for X in (A, B):
                    s = X._ensure_pool()["samples"]
                    out.append([np.asarray(s[q], float)[:, LAYER].mean(1) for q in ("u", "v")])
            except Exception as e:   # noqa: BLE001 (a case the tool cannot serve is counted and skipped)
                print(t0, lead, "skipped:", repr(e)[:80], flush=True)
                continue
            y = [p1[0][LAYER].mean(), p1[1][LAYER].mean()]
            r[f"A{lead}"] = float(np.mean([K.crps1(out[0][i], y[i]) for i in (0, 1)]))
            r[f"B{lead}"] = float(np.mean([K.crps1(out[1][i], y[i]) for i in (0, 1)]))
            r[f"P{lead}"] = float(np.mean([abs(p0[i][LAYER].mean() - y[i]) for i in (0, 1)]))
            ok = True
        if ok:
            rows.append(r)
    R = pd.DataFrame(rows)
    R["blk"] = blocks(R.t)
    rng = np.random.default_rng(0)
    ub = R.blk.unique()
    lines = [f"DP tower replay: SWiFT 200 m tower, {len(R)} hours in {len(ub)} campaign blocks, 200 members; 50-150 m layer-mean wind (u, v CRPS mean), tower sigma {SIGMA} m/s"]
    gains = {}
    for lead in (30, 60):
        g = R.dropna(subset=[f"A{lead}", f"B{lead}"])
        if not len(g):
            continue
        gain = 1 - g[f"B{lead}"].mean() / g[f"A{lead}"].mean()
        bs = []
        for _ in range(1000):
            pick = rng.choice(ub, len(ub))
            s = pd.concat([g[g.blk == b] for b in pick])
            bs.append(1 - s[f"B{lead}"].mean() / s[f"A{lead}"].mean())
        gains[lead] = gain
        per = [1 - x[f"B{lead}"].mean() / x[f"A{lead}"].mean() for _, x in g.groupby("blk")]
        lines.append(f"  lead {lead} min: n {len(g)}; CRPS A (10 m only) {g[f'A{lead}'].mean():.3f}, B (profile) {g[f'B{lead}'].mean():.3f}, persistence abs error {g[f'P{lead}'].mean():.3f}; gain {100 * gain:.1f} % [{100 * np.percentile(bs, 2.5):.1f}, {100 * np.percentile(bs, 97.5):.1f}]; by block " + " ".join(f"{100 * x:.0f}" for x in per))
    lines.append("Rule (pre-set): at lead 30 min PASS = gain >= 40 %; KILL = gain < 15 %; else MISS.")
    lines.append("Verdict: " + (judge(gains[30]) if 30 in gains else "no usable cases"))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(0.5) == "PASS" and judge(0.1) == "KILL" and judge(0.2) == "MISS"
    u, v = uv(5.0, 270.0)
    assert abs(u - 5) < 1e-9 and abs(v) < 1e-9
    assert list(blocks(pd.DatetimeIndex(["2013-01-01 00:00", "2013-01-03", "2013-01-03 01:00"]))) == [0, 1, 1]


_selfcheck()
if __name__ == "__main__":
    main()
