"""New_Plan 19 WD5: the SWiFT tower check (b6_swift_check) re-scored by CAMPAIGN BLOCK, not by hour. Measurement only, CPU, minutes.
Same hours, arms (climate / past / ERA5 value), members and seeds as b6. The 131 hours are a few days: hours inside a campaign are tied, so every statement is
made per block (hours more than 12 h apart start a new block) and a conclusion "survives" only if its sign holds in EVERY block.
Output per arm x height: bias of the median by block, real / arm speed ratio by block; then: ratio real / ERA5-value rising with height in every block?;
past-arm and climate-arm bias negative in every block?; climate arm is NOT a fair arm (weather and climate confounded): its numbers are read for spread only.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b51_wd5_swift_blocks.py [n_members]
Result: docs/results/logs/kit_b51_wd5_swift_blocks.log
"""
import sys

import numpy as np
import pandas as pd

import kit_common as K

NAME = "b51_wd5_swift_blocks"
HFT = [(33, 10), (155, 47), (245, 75), (382, 116), (519, 158), (656, 200)]
LAT, LON = 33.607, -102.047
STORE = "data/pilot/profiles.zarr;data/pilot/profiles80_night.zarr"
ARMS = [("climate", {}), ("past", dict(mode="past", era5_store=STORE)), ("ERA5", dict(mode="past", era5_store=STORE, predicted=True))]


def blocks(times, gap_h=12):
    """sorted DatetimeIndex -> block id per entry (new block when the gap to the previous hour exceeds gap_h)."""
    t = pd.DatetimeIndex(times)
    return np.concatenate([[0], np.cumsum(np.diff(t.values) > np.timedelta64(gap_h, "h"))]) if len(t) else np.array([], int)


def all_blocks(pred):
    """pred: list of booleans, one per block -> True when it holds in every block (and there is at least one)."""
    return bool(len(pred)) and all(pred)


def main():
    from tempest_weather import api, registry
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 512
    d = pd.read_csv("data/raw/a2e/ttu_swift_200m/processed/swift_10min.csv", parse_dates=["time_utc"])
    d["hour"] = d["time_utc"].dt.floor("h")
    top = d[d["time_utc"].dt.minute == 0].set_index("hour").sort_index()
    blk = dict(zip(top.index, blocks(top.index)))
    rec = []  # arm, height m, block, tower speed, tool median
    for (h, r), (arm, kw) in ((x, a) for x in top.iterrows() for a in ARMS):
        try:
            atm, _ = api.atmosphere_set(LAT, LON, h.strftime("%Y-%m-%dT%H:%MZ"), n=N, seed=int(h.timestamp()) % 100000, **kw)
        except (ValueError, LookupError):
            continue
        ev = registry.evaluate(atm, ["wind_speed@%d" % m for _, m in HFT], np.random.default_rng(1))
        for ft, m in HFT:
            rec.append((arm, m, blk[h], r["speed_%dft" % ft], float(np.median(ev["wind_speed@%d" % m]))))
    df = pd.DataFrame(rec, columns=["arm", "m", "blk", "tower", "med"])
    nb = df.blk.nunique()
    lines = [f"WD5 SWiFT by campaign block: {len(top)} tower hours in {nb} blocks (gap > 12 h), {N} members; sizes " + ", ".join(f"{b}:{n}" for b, n in top.groupby(list(blk.values())).size().items())]
    ratio = {}
    for arm, _ in ARMS:
        for m in [x[1] for x in HFT]:
            g = df[(df.arm == arm) & (df.m == m)].groupby("blk")
            bias, rat = (g.med.mean() - g.tower.mean()), g.tower.mean() / g.med.mean()
            ratio[(arm, m)] = rat
            lines.append(f"  {arm:8s} {m:3d} m: bias by block " + " ".join(f"{v:+.2f}" for v in bias) + " | real / arm speed " + " ".join(f"{v:.2f}" for v in rat))
    heights = [x[1] for x in HFT]
    rise = all_blocks([ratio[("ERA5", heights[-1])][b] > ratio[("ERA5", heights[0])][b] for b in ratio[("ERA5", 10)].index])
    neg_past = all_blocks([bool((df[(df.arm == "past") & (df.m == m)].groupby("blk").apply(lambda g: g.med.mean() - g.tower.mean()) < 0).all()) for m in heights])
    lines.append(f"Survives in EVERY block: real / ERA5 ratio higher at 200 m than at 10 m: {rise}; past-arm bias negative at all six heights: {neg_past}.")
    lines.append("Climate arm: not a fair arm (three episodes); read for spread only. Measurement, no adoption.")
    K.report(NAME, lines)


def _selfcheck():
    t = pd.DatetimeIndex(["2013-01-01 00:00", "2013-01-01 05:00", "2013-01-03 00:00", "2013-01-03 01:00"])
    assert list(blocks(t)) == [0, 0, 1, 1] and all_blocks([True, True]) and not all_blocks([True, False]) and not all_blocks([])


_selfcheck()
if __name__ == "__main__":
    main()
