"""New_Plan 19 WD4 (step 0): u / v anisotropy and direction of the tool's climate-mode 10 m wind against six ASOS stations. Measurement only, CPU, no training.
Stations TCS MAF ELP ABQ ALM FST, 00-ish UTC hours 15 / 18 / 21 (STARTS of b14), every month, station years 2016-2020 (the RA gap fit years); tool members:
api.atmosphere_sequence(.., mode="ai", n=1024, offset 0), the same call as b40. Speeds under 2 m/s dropped on BOTH sides (station direction undefined when calm).
Per station: pooled sd(u), sd(v) (within month x hour cell, variance averaged), ratio q = sd v / sd u for the tool and the station;
direction: mean resultant length (concentration) of the tool and of the station, and the median |circular-mean difference| over cells (degrees).
Rule (set 2026-11-15 in New_Plan 19 WD4): measurement. A v-only spread follow-up is proposed only if q_tool / q_station > 1.15 at 4 of 6 stations.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b50_wd4_direction.py
Result: docs/results/logs/kit_b50_wd4_direction.log
"""
import numpy as np

import kit_common as K

NAME = "b50_wd4_direction"
SITES = {"TCS": (33.2369, -107.2672), "MAF": (31.9425, -102.2019), "ELP": (31.8067, -106.3778),
         "ABQ": (35.0402, -106.6092), "ALM": (32.8399, -105.9906), "FST": (30.9157, -102.9163)}
HOURS, YEARS, MINS = (15, 18, 21), range(2016, 2021), 2.0


def uv(speed, deg):
    """meteorological direction (from, degrees) -> u, v."""
    r = np.deg2rad(deg)
    return -speed * np.sin(r), -speed * np.cos(r)


def circ(u, v):
    """-> (mean resultant length of the unit vectors, mean direction angle in radians) of wind vectors (u, v)."""
    s = np.hypot(u, v)
    a, b = (u / s).mean(), (v / s).mean()
    return float(np.hypot(a, b)), float(np.arctan2(a, b))


def cell_stats(tu, tv, su, sv):
    """-> (var u tool, var v tool, var u stn, var v stn, R tool, R stn, |dir diff| deg) for one month x hour cell after the calm filter, or None."""
    tm, sm = np.hypot(tu, tv) >= MINS, np.hypot(su, sv) >= MINS
    if tm.sum() < 50 or sm.sum() < 30:
        return None
    tu, tv, su, sv = tu[tm], tv[tm], su[sm], sv[sm]
    rt, at = circ(tu, tv)
    rs, as_ = circ(su, sv)
    d = abs((np.rad2deg(at - as_) + 180) % 360 - 180)
    return tu.var(), tv.var(), su.var(), sv.var(), rt, rs, d


def judge(q):
    """q = {site: (q tool, q station)} -> verdict string."""
    n = sum(t / s > 1.15 for t, s in q.values())
    return (f"v-only follow-up proposed ({n} of {len(q)} stations above 1.15)" if n >= 4 else f"no follow-up ({n} of {len(q)} stations above 1.15)")


def main():
    K.ram_gate(4.0)
    from tempest_weather import api
    lines = ["WD4 step 0: 10 m wind anisotropy and direction, tool (climate mode) vs ASOS 2016-2020, speeds >= 2 m/s on both sides"]
    q = {}
    for st, (la, lo) in SITES.items():
        obs = K.asos_speed(st, YEARS)
        rows = []
        for m in range(1, 13):
            for h in HOURS:
                sel = [(s, d) for t, (s, d) in obs.items() if t.month == m and t.hour == h]
                if len(sel) < 30:
                    continue
                s, d = np.array(sel).T
                try:
                    atms, _ = api.atmosphere_sequence(la, lo, f"2013-{m:02d}-15T{h:02d}:00:00+00:00", offsets=(0,), n=1024, seed=0, mode="ai")
                except ValueError:
                    continue
                tu, tv = atms[0]["u"][:, 0].astype(float), atms[0]["v"][:, 0].astype(float)
                r = cell_stats(tu, tv, *uv(s, d))
                if r:
                    rows.append(r)
        if not rows:
            lines.append(f"  {st}: no usable cells")
            continue
        a = np.array(rows)
        qt, qs = np.sqrt(a[:, 1].mean() / a[:, 0].mean()), np.sqrt(a[:, 3].mean() / a[:, 2].mean())
        q[st] = (qt, qs)
        lines.append(f"  {st}: {len(a)} cells; sd u tool {np.sqrt(a[:, 0].mean()):.2f} stn {np.sqrt(a[:, 2].mean()):.2f}; sd v tool {np.sqrt(a[:, 1].mean()):.2f} stn {np.sqrt(a[:, 3].mean()):.2f}; "
                     f"q = sd v / sd u: tool {qt:.2f} stn {qs:.2f} (ratio {qt / qs:.2f}); direction concentration R tool {a[:, 4].mean():.2f} stn {a[:, 5].mean():.2f}; "
                     f"median |mean-direction difference| {np.median(a[:, 6]):.0f} deg")
    lines.append("Rule (set 2026-11-15, New_Plan 19 WD4): measurement; v-only spread follow-up only if q tool / q station > 1.15 at 4 of 6 stations.")
    lines.append("Result: " + judge(q))
    K.report(NAME, lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    u, v = rng.normal(0, 2, 4000), rng.normal(0, 4, 4000)
    r = cell_stats(u, v, u, v)
    assert abs(r[3] / r[2] - 4) < 0.5 and r[6] < 1e-6
    su, sv = uv(np.array([5.0]), np.array([270.0]))   # from the west -> u positive
    assert su[0] > 4.9 and abs(sv[0]) < 1e-9
    assert judge({str(i): (1.3, 1.0) for i in range(6)}).startswith("v-only") and judge({str(i): (1.0, 1.0) for i in range(6)}).startswith("no")


_selfcheck()
if __name__ == "__main__":
    main()
