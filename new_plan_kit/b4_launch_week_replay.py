"""New_Plan 10.2 O3: launch-week factor. Replay an anemometer set up k = 3, 7, 14 days before the test day: each of those days gives
r_j = mean measured 10 m speed / mean tool speed (prior pool mean) at 09, 13, 17 local; the site factor starts at 1.0 and moves by a decaying
average, f <- f + (1/30)(r_j - f), oldest day first (alpha 1/30 per day, as tempest_weather/bias.py). The test hour (one random 08-20 local hour
of the test day) is then scored with Launch(site_cal={"method": "ratio", "ratio": f}) against no factor.
Change from the plan row (recorded in New_Plan section 9): the plan starts from the S2 regional shape, but S2 was dropped (premise wrong, 2 of 9),
so the start is "no factor" (1.0), which is what the pad has today without S2. "Shape alone" in the rule below therefore means "no factor".
Sites TCS and MAF, test days 2023-25 (history days may reach back into late 2022), never 2026.
PASS (pre-set): at k = 7, CRPS better than no factor with a day-block interval that excludes 0 at both sites, and coverage not lower (to 2 dp);
      both seeds. k = 3 and 14 reported too. Else closed.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b4_launch_week_replay.py --seed 0     # then --seed 1
    KIT_SMOKE=1 PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b4_launch_week_replay.py --n 2
Result: docs/results/logs/kit_b4_launch_week_replay.log
"""
import argparse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

import kit_common as K
from b1_observe_loso import score, speed10

SITES = {"TCS": "America/Denver", "MAF": "America/Chicago"}
KS = (3, 7, 14)
ALPHA = 1.0 / 30.0
HIST_LOCAL = (9, 13, 17)
# AV10 (--start il207b, opt-in): IL-207b per-cell factors, mean of its two hour seeds (fit 2021-22; TCS = sitecal.TCS_SPEED_FACTOR)
IL207B = {"TCS": {"08-11/cool": 0.985, "08-11/warm": 1.015, "12-15/cool": 1.135, "12-15/warm": 1.135, "16-20/cool": 1.06, "16-20/warm": 1.29},
          "MAF": {"08-11/cool": 1.13, "08-11/warm": 1.13, "12-15/cool": 0.89, "12-15/warm": 1.005, "16-20/cool": 0.86, "16-20/warm": 1.125}}


def decay(ratios, start=1.0, alpha=ALPHA):
    """Decaying average over daily ratios, oldest first (None = a day without data, skipped)."""
    f = start
    for r in ratios:
        if r is not None:
            f += alpha * (r - f)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150, help="test days per site")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--start", choices=("none", "il207b"), default="none", help="il207b (AV10): start from the IL-207b cell factor; base arm = that factor alone")
    ap.add_argument("--report", default="b4_launch_week_replay")
    a = ap.parse_args()
    from b3_il207b_site_shift import cell_of
    base = "no factor" if a.start == "none" else "IL-207b alone"
    from tempest_weather_v2 import obs as O
    from tempest_weather_v2.launch import Launch
    K.ram_gate(4.0)
    rng = np.random.default_rng(a.seed)
    arms = ("no factor",) + ((base,) if a.start != "none" else ()) + tuple(f"k={k}" for k in KS)
    lines = [f"O3 launch-week factor: start {'1.0 (no S2 shape)' if a.start == 'none' else 'IL-207b cell factor'}, alpha 1/30 per day, history at 09/13/17 local; one 08-20 local test hour per day, 2023-25, {a.n} days per site, seed {a.seed}"]
    verdict = True
    for st, tz in SITES.items():
        z = ZoneInfo(tz)
        lat, lon, elev = O.STATIONS[st]
        obs = K.asos_speed(st, range(2022, 2026))
        memo = {}

        def ratio(day):
            """Measured / tool mean speed on one local day (None if no hour has a measurement)."""
            if day in memo:
                return memo[day]
            m, t = [], []
            for hl in HIST_LOCAL:
                h = datetime(day.year, day.month, day.day, hl, tzinfo=z).astimezone(timezone.utc)
                if h in obs:
                    L = Launch(lat, lon, h.strftime("%Y-%m-%d %H:%M"), tz="UTC", n=200, seed=int(h.timestamp()) % 100000, units="si", elevation=elev, mode="ai")
                    m.append(obs[h][0])
                    t.append(float(speed10(L).mean()))
            memo[day] = float(np.mean(m) / np.mean(t)) if t and np.mean(t) > 0.1 else None
            return memo[day]

        cand = sorted({h.astimezone(z).date() for h in obs if 2023 <= h.astimezone(z).year <= 2025 and 8 <= h.astimezone(z).hour <= 20})
        res, days, skipped, facs = {k: [] for k in arms}, [], [], {k: [] for k in KS}
        for d in [cand[i] for i in np.sort(rng.choice(len(cand), min(a.n, len(cand)), replace=False))]:
            hs = [h for h in (datetime(d.year, d.month, d.day, hl, tzinfo=z).astimezone(timezone.utc) for hl in range(8, 21)) if h in obs]
            if not hs:
                continue
            h = hs[rng.integers(len(hs))]
            assert K.day_ok(h)
            when, seed = h.strftime("%Y-%m-%d %H:%M"), int(h.timestamp()) % 100000
            try:
                rs = [ratio(d - timedelta(days=j)) for j in range(max(KS), 0, -1)]      # oldest first
                y, out = obs[h][0], {}
                out["no factor"] = score(speed10(Launch(lat, lon, when, tz="UTC", n=200, seed=seed, units="si", elevation=elev, mode="ai")), y)
                f0 = 1.0 if a.start == "none" else IL207B[st][cell_of(h, z)]
                if a.start != "none":
                    out[base] = score(speed10(Launch(lat, lon, when, tz="UTC", n=200, seed=seed, units="si", elevation=elev, mode="ai",
                                                     site_cal={"method": "ratio", "ratio": f0})), y)
                for k in KS:
                    f = decay(rs[-k:], start=f0)
                    facs[k].append(f)
                    out[f"k={k}"] = score(speed10(Launch(lat, lon, when, tz="UTC", n=200, seed=seed, units="si", elevation=elev, mode="ai",
                                                         site_cal={"method": "ratio", "ratio": f})), y)
            except Exception as e:   # noqa: BLE001  (a day the tool cannot serve is skipped, and counted)
                skipped.append(repr(e)[:80])
                continue
            for k in arms:
                res[k].append(out[k])
            days.append(d.isoformat())
        n = len(days)
        lines.append(f"{st}: {n} test days, {len(skipped)} skipped" + (f" (first: {skipped[0]})" if skipped else "")
                     + "; mean factor " + ", ".join(f"k={k} {np.mean(facs[k]):.3f} (range {np.min(facs[k]):.3f}-{np.max(facs[k]):.3f})" for k in KS if facs[k]))
        if n < 2:
            verdict = False
            continue
        arr = {k: np.array(v) for k, v in res.items()}
        for nm in arms[:len(arms) - len(KS)]:
            lines.append(f"  {nm:<9}  CRPS {arr[nm][:, 0].mean():.3f}  coverage {arr[nm][:, 1].mean():.2f}")
        for k in KS:
            name = f"k={k}"
            dm, dlo, dhi = K.block_boot(arr[name][:, 0] - arr[base][:, 0], days, draws=1000)
            cov, cov0 = arr[name][:, 1].mean(), arr[base][:, 1].mean()
            row = f"  {name:<9}  CRPS {arr[name][:, 0].mean():.3f}  coverage {cov:.2f}  minus {base} {dm:+.4f} [{dlo:+.4f}, {dhi:+.4f}]"
            if k == 7:
                ok = dhi < 0 and round(cov, 2) >= round(cov0, 2)
                verdict &= bool(ok)
                row += "  ok" if ok else "  fail"
            lines.append(row)
    lines.append(f"Rule (pre-set): k = 7 CRPS better than {base} (interval excludes 0) and coverage not lower, both sites, both seeds.")
    lines.append("Seed verdict: " + ("PASS (needs the other seed)" if verdict else "FAIL -> O3 closed"))
    K.report(a.report, lines)


def _selfcheck():
    assert decay([]) == 1.0 and decay([None, None]) == 1.0
    assert abs(decay([2.0]) - (1.0 + 1.0 / 30.0)) < 1e-12
    assert decay([1.5] * 14) > decay([1.5] * 7) > decay([1.5] * 3) > 1.0


_selfcheck()
if __name__ == "__main__":
    main()
