"""Reality check for the trial: do real late-June soundings at Santa Teresa NM (IGRA USM00072364, 00 UTC) fall inside the Tempest distribution for the same place and hour?
Read-only on the repo's data; run with the project's python:   .venv/Scripts/python -W ignore flight_sim_trial/check_vs_balloons.py
"""
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest_weather import _core, api   # noqa: E402

MISSING = -32768
d = np.load(os.path.join(REPO, "data", "igra_heights", "USM00072364.npz"), allow_pickle=True)
elev, lat, lon = float(d["elev"][0]), float(d["lat"][0]), float(d["lon"][0])
t = d["time"]
mon_day = np.array([int(str(x)[5:7]) * 100 + int(str(x)[8:10]) for x in t])
hour = np.array([int(str(x)[11:13]) for x in t])
year = np.array([int(str(x)[:4]) for x in t])
sel = (mon_day >= 615) & (mon_day <= 630) & (hour == 0) & (year >= 2011) & (year <= 2025)
dec = lambda k: np.where(d[k][sel][:, :44] == MISSING, np.nan, d[k][sel][:, :44] / 10.0)
obs = dict(T=dec("T"), RH=dec("RH"), u=dec("u"), v=dec("v"))
print(f"{sel.sum()} soundings (Jun 15-30, 00 UTC, 2011-2025) at {lat:.2f},{lon:.2f}, station elevation {elev:.0f} m")

atm, info = api.atmosphere_set(lat, lon, "2025-06-25T00:00:00+00:00", n=1000, mode="ai", seed=3, elevation=elev)
print("tool:", info["source"], "| pad", round(info["elevation_m"]), "m |", info.get("quality"))
H = np.asarray(_core.HEIGHTS)
spd_o, spd_s = np.hypot(obs["u"], obs["v"]), np.hypot(atm["u"], atm["v"])
bands = ((0, 1000), (1000, 3000), (3000, 6000), (6000, 12000), (12000, 18001))
print("\nshare of real soundings inside the tool's range (ideal: 90 % in p5-p95, 98 % in p1-p99); median bias = obs median - tool median")
print(f"{'var':>6} {'band (m AGL)':>14} {'in p5-p95':>10} {'in p1-p99':>10} {'bias':>8} {'obs sd':>8} {'tool sd':>8}")
for name, o, s in (("T (K)", obs["T"], atm["T"]), ("RH (%)", obs["RH"], atm["RH"]), ("u (m/s)", obs["u"], atm["u"]), ("v (m/s)", obs["v"], atm["v"]), ("speed", spd_o, spd_s)):
    for lo, hi in bands:
        m = (H >= lo) & (H < hi)
        ins90, ins98, n, bias, so, ss = 0, 0, 0, [], [], []
        for j in np.flatnonzero(m):
            x = o[:, j]
            x = x[np.isfinite(x)]
            if len(x) < 20:
                continue
            q = np.percentile(s[:, j], [1, 5, 50, 95, 99])
            ins90 += ((x >= q[1]) & (x <= q[3])).sum()
            ins98 += ((x >= q[0]) & (x <= q[4])).sum()
            n += len(x)
            bias.append(np.median(x) - q[2])
            so.append(x.std())
            ss.append(s[:, j].std())
        if n:
            print(f"{name:>6} {lo:>6}-{hi:<7} {100 * ins90 / n:9.0f}% {100 * ins98 / n:9.0f}% {np.mean(bias):+8.2f} {np.mean(so):8.2f} {np.mean(ss):8.2f}")
# near-surface lapse rate: real balloons vs the tool
lap_o = -(obs["T"][:, 1:4] - obs["T"][:, :3]) / np.diff(H[:4])[None, :] * 1000.0
lap_s = -(atm["T"][:, 1:4] - atm["T"][:, :3]) / np.diff(H[:4])[None, :] * 1000.0
print(f"\nlowest-layer lapse rate (10-50 m / 50-100 / 100-150 m), K/km: balloons p50 {np.nanmedian(lap_o[:, 0]):.1f} / {np.nanmedian(lap_o[:, 1]):.1f} / {np.nanmedian(lap_o[:, 2]):.1f}"
      f"   tool p50 {np.median(lap_s[:, 0]):.1f} / {np.median(lap_s[:, 1]):.1f} / {np.median(lap_s[:, 2]):.1f}")
print(f"surface: tool T2m p5/p50/p95 {np.percentile(atm['t2m'], 5) - 273.15:.1f}/{np.median(atm['t2m']) - 273.15:.1f}/{np.percentile(atm['t2m'], 95) - 273.15:.1f} C;"
      f" balloon lowest-level T p5/p50/p95 {np.nanpercentile(obs['T'][:, 0], 5) - 273.15:.1f}/{np.nanmedian(obs['T'][:, 0]) - 273.15:.1f}/{np.nanpercentile(obs['T'][:, 0], 95) - 273.15:.1f} C")
