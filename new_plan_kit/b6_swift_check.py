"""SWiFT check (To-do queue; sanity check only, no adoption on it alone): the tool vs the TTU SWiFT 200 m tower.

Tower: data/raw/a2e/ttu_swift_200m/processed/swift_10min.csv (from scripts/a2e_swift_ingest.py), 4 days of 2013-14.
Each tower hour hh:00 UTC: the 10-min window starting hh:00 against the tool's atmosphere_set at the same time,
three arms: 'climate' (the default call without an ERA5 store: climate generator, flagged 'fallback-mode'),
'past' (mode past on the local ERA5 day + night stores, full model error) and 'ERA5' (past, predicted=True: the
ERA5 value itself; its coverage and PIT are degenerate, read its bias only). Heights 10, 47, 75, 116, 158, 200 m; 200-10 m speed difference; gust10 against
the hour's largest 3 s gust at 10 m. Tower position: Reese Technology Center near Lubbock, taken as
33.607 N, 102.047 W (from memory, a few km uncertain; well inside one 0.25 deg grid cell).

Measures: PIT (rank of the tower value among the members), 90 % band coverage, mean bias of the median.
4 days only, so hours are strongly tied: read as a sanity check (is the tool far off?), not a score.
Reading set before the run: a height is "off" if its 90 % coverage is under 0.70 or its PIT mean is outside 0.3-0.7.

    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b6_swift_check.py [n_members]
"""
import sys

import numpy as np
import pandas as pd

from tempest_weather import api, registry

N = int(sys.argv[1]) if len(sys.argv) > 1 else 512
LAT, LON = 33.607, -102.047
HFT = [(33, 10), (155, 47), (245, 75), (382, 116), (519, 158), (656, 200)]
d = pd.read_csv("data/raw/a2e/ttu_swift_200m/processed/swift_10min.csv", parse_dates=["time_utc"])
d["hour"] = d["time_utc"].dt.floor("h")
gmax = d.groupby("hour")["gust3s_33ft"].max()
top = d[d["time_utc"].dt.minute == 0].set_index("hour")

STORE = "data/pilot/profiles.zarr;data/pilot/profiles80_night.zarr"
ARMS = [("climate", {}), ("past", dict(mode="past", era5_store=STORE)), ("ERA5", dict(mode="past", era5_store=STORE, predicted=True))]
rows = []  # arm, name, tower value, member values
skipped = {}
used, modes = 0, {}
for (h, r), (arm, kw) in ((x, a) for x in top.iterrows() for a in ARMS):
    try:
        atm, info = api.atmosphere_set(LAT, LON, h.strftime("%Y-%m-%dT%H:%MZ"), n=N, seed=int(h.timestamp()) % 100000, **kw)
    except (ValueError, LookupError) as e:  # outside the solar window / hour not in the store
        skipped[arm + ": " + str(e)[:40]] = skipped.get(arm + ": " + str(e)[:40], 0) + 1
        continue
    names = ["wind_speed@%d" % m for _, m in HFT] + ["gust10"]
    ev = registry.evaluate(atm, names, np.random.default_rng(1))
    for ft, m in HFT:
        rows.append((arm, "speed %d m" % m, r["speed_%dft" % ft], ev["wind_speed@%d" % m]))
    rows.append((arm, "speed 200 - 10 m", r["speed_656ft"] - r["speed_33ft"], ev["wind_speed@200"] - ev["wind_speed@10"]))
    rows.append((arm, "gust 10 m (hour max 3 s)", gmax.get(h, np.nan), ev["gust10"]))
    modes[arm] = modes.get(arm, set()) | {info["mode"]}
    used += arm == "climate"

print("tower hours %d, used %d, modes %s, skipped %s, members %d" % (len(top), used, modes, skipped, N))
print("%-8s %-26s %5s %8s %8s %8s %9s %8s %8s" % ("arm", "quantity", "n", "tower", "tool med", "bias", "cover 90", "PIT mean", "PIT<.05"))
off = []
for arm, name in dict.fromkeys(x[:2] for x in rows):
    obs = np.array([x[2] for x in rows if x[:2] == (arm, name)], dtype=float)
    mem = np.array([x[3] for x in rows if x[:2] == (arm, name)], dtype=float)
    ok = np.isfinite(obs)
    obs, mem = obs[ok], mem[ok]
    pit = (mem < obs[:, None]).mean(axis=1)
    lo, hi = np.percentile(mem, 5, axis=1), np.percentile(mem, 95, axis=1)
    cov = float(np.mean((obs >= lo) & (obs <= hi)))
    med = np.median(mem, axis=1)
    print("%-8s %-26s %5d %8.2f %8.2f %+8.2f %9.2f %8.2f %8.2f" % (arm, name, ok.sum(), obs.mean(), med.mean(), (med - obs).mean(), cov, pit.mean(), (pit < 0.05).mean()))
    if arm != "ERA5" and (cov < 0.70 or not 0.3 <= pit.mean() <= 0.7):
        off.append(arm + " " + name)
print("Reading (set before the run: off if coverage < 0.70 or PIT mean outside 0.3-0.7):", "off at " + ", ".join(off) if off else "no quantity off")
