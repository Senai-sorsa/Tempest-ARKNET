"""New_Plan 28.11 item 12: O3 / AV10 (b38, k = 7 MISS taken in by the 2026-11-20 ruling) re-scored through the TOOL PATH: Launch.launch_week(readings) with the pad
readings at 09 / 13 / 17 local of the 7 days before, against the same launch with the default site_cal ("auto" = IL-207b at TCS, nothing elsewhere) and with no factor.
Same sites, years (2023-25), test-day draw and test hour as b4 / b38. Port check (no rule): TCS should repeat b38 k = 7 (-0.0227) within noise; MAF starts from 1.0 in the
tool (IL-207b is TCS-only there), so MAF is compared to no factor, not to b38's MAF start.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b90_o3_tool_path.py --seed 0
Result: docs/results/logs/kit_b90_o3_tool_path.log
"""
import argparse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

import kit_common as K
from b1_observe_loso import score, speed10
from b4_launch_week_replay import HIST_LOCAL, SITES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    from tempest_weather_v2 import obs as O
    from tempest_weather_v2.launch import Launch
    K.ram_gate(4.0)
    rng = np.random.default_rng(a.seed)
    arms = ("no factor", "auto", "launch_week")
    lines = [f"O3 through the tool path (Launch.launch_week, k = 7, alpha 1/30), 2023-25, {a.n} days per site, seed {a.seed}"]
    for st, tz in SITES.items():
        z = ZoneInfo(tz)
        lat, lon, elev = O.STATIONS[st]
        obs = K.asos_speed(st, range(2022, 2026))
        cand = sorted({h.astimezone(z).date() for h in obs if 2023 <= h.astimezone(z).year <= 2025 and 8 <= h.astimezone(z).hour <= 20})
        res, days, facs, skipped = {k: [] for k in arms}, [], [], 0
        for d in [cand[i] for i in np.sort(rng.choice(len(cand), min(a.n, len(cand)), replace=False))]:
            hs = [h for h in (datetime(d.year, d.month, d.day, hl, tzinfo=z).astimezone(timezone.utc) for hl in range(8, 21)) if h in obs]
            if not hs:
                continue
            h = hs[rng.integers(len(hs))]
            assert K.day_ok(h)
            when, seed = h.strftime("%Y-%m-%d %H:%M"), int(h.timestamp()) % 100000
            rd = {}
            for j in range(1, 8):
                dj = d - timedelta(days=j)
                for hl in HIST_LOCAL:
                    t = datetime(dj.year, dj.month, dj.day, hl, tzinfo=z).astimezone(timezone.utc)
                    if t in obs:
                        rd[t] = obs[t][0]
            try:
                kw = dict(tz="UTC", n=200, seed=seed, units="si", elevation=elev, mode="ai")
                L = Launch(lat, lon, when, **kw)
                Lw = L.launch_week(rd)
                y = obs[h][0]
                out = {"no factor": score(speed10(Launch(lat, lon, when, site_cal=None, **kw)), y), "auto": score(speed10(L), y), "launch_week": score(speed10(Lw), y)}
            except Exception:   # noqa: BLE001  (a day the tool cannot serve is skipped, and counted)
                skipped += 1
                continue
            facs.append(Lw._site_cal["ratio"])
            for k in arms:
                res[k].append(out[k])
            days.append(d.isoformat())
        arr = {k: np.array(v) for k, v in res.items()}
        lines.append(f"{st}: {len(days)} test days, {skipped} skipped; launch_week factor mean {np.mean(facs):.3f} (range {np.min(facs):.3f}-{np.max(facs):.3f})")
        for k in arms:
            lines.append(f"  {k:<11}  CRPS {arr[k][:, 0].mean():.3f}  coverage {arr[k][:, 1].mean():.2f}")
        for b in ("no factor", "auto"):
            dm, dlo, dhi = K.block_boot(arr["launch_week"][:, 0] - arr[b][:, 0], days, draws=1000)
            lines.append(f"  launch_week minus {b}: {dm:+.4f} [{dlo:+.4f}, {dhi:+.4f}]")
    lines.append("Port check: TCS launch_week minus auto should repeat b38 k = 7 minus IL-207b alone (-0.0227 [-0.0482, +0.0003]) within noise; MAF b38 -0.0269 was vs the MAF IL-207b start.")
    K.report(f"b90_o3_tool_path_s{a.seed}", lines)


if __name__ == "__main__":
    main()
