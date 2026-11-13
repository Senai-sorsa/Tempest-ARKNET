"""C4: measure the radar wind error from the data, instead of the hand-set 3.0 m/s (tempest_weather_v2/radar.py VAD_SIGMA_MS). KILL RULE BELOW.
Idea (innovation statistics): for many hours, d = radar wind minus the mean of the tool's sample set, at the same place and heights.
If the tool's spread is honest, mean(d d') = B + R, with B = covariance of the tool's samples and R = covariance of the radar error. So
    R = mean(d d') - mean(B)       (u and v averaged; heights 500 ... 5000 m above the radar, every 500 m, nearest model height)
and from R:   sd = sqrt(mean diagonal of R)                 the radar error of one level, m/s
              L  = the height over which errors stay alike, from R(i, j) = sd2 exp(-|dz| / L)
              a  = growth with age, from the same radar volume against the tool 1, 2, 3 hours LATER:  sd(age) = sd (1 + a age)
Uses every cached radar file (data/raw/nexrad_nvw: EPZ, MAF, HDX, FTG; one volume per day-hour; never 2026; no download).
LIMITS, say them in any report: R also holds any part of the tool's error that its spread does not show (so sd is an UPPER estimate),
and the cached volumes are all near 23 and 11 UTC.
KILL: the diagonal of R is not positive at half or more of the heights (the tool's spread is already wider than the mismatch) -> keep 3.0 m/s, close C4.
THEN TEST (the script prints the exact commands): scripts/p3_vad_condition.py --sigma <value>. The engine treats each level's error as independent,
so with many levels that share an error the sd must be raised: sd_many = sd sqrt(sum of the error correlations / number of levels).
ADOPT RULE (for a later core change, not done here): the "radar+all" row must beat the "radar" (4 levels) row at 2.5-5 km AND coverage must be 0.85 or more.

    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b2_c4_innovation_fit.py              # about 1 h, 4 GB RAM, 3 threads
    KIT_SMOKE=1 PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b2_c4_innovation_fit.py --max-per-site 6 --n 256   # smoke test
Result: docs/results/logs/kit_b2_c4_innovation_fit.log
"""
import argparse

import numpy as np
import pandas as pd

import kit_common as K

LEV = np.array([int(np.argmin(np.abs(K.H - z))) for z in range(500, 5001, 500)])
DZ = np.abs(K.H[LEV][:, None] - K.H[LEV][None, :])
AGES = (0, 1, 2, 3)


def r_matrix(d, B):
    """d (cases, 2, L) innovations with NaN where the radar has no wind, B (cases, 2, L, L) -> R (L, L), u and v averaged, each pair from the cases that have both heights."""
    dd = d[..., :, None] * d[..., None, :]
    return np.nanmean(np.where(np.isnan(dd), np.nan, dd - B), axis=(0, 1))


def fit_L(R):
    """-> (sd, L m). sd from the diagonal; L by a search over 100 ... 10000 m on the off-diagonal pairs."""
    var = np.nanmean(np.diag(R))
    off = ~np.eye(len(R), dtype=bool) & ~np.isnan(R)
    Ls = np.geomspace(100, 10000, 200)
    return float(np.sqrt(var)), float(Ls[int(np.argmin([((R[off] / var - np.exp(-DZ[off] / L)) ** 2).sum() for L in Ls]))])


def many_levels_factor(L, idx):
    """Factor on sd when len(idx) levels with error correlation exp(-dz / L) are fed to an engine that takes them as independent."""
    return float(np.sqrt(np.exp(-DZ[np.ix_(idx, idx)] / L).sum() / len(idx)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-per-site", type=int, default=150)
    ap.add_argument("--n", type=int, default=1024, help="size of the tool's sample set")
    a = ap.parse_args()
    from p3_vad_vs_balloon import parse
    from tempest_weather_v2.radar import RADARS
    K.ram_gate(6.0)
    rng = np.random.default_rng(0)
    d, B, days, used = {g: [] for g in AGES}, {g: [] for g in AGES}, [], {}
    for site in ("EPZ", "MAF", "HDX", "FTG"):
        lat, lon, elev = RADARS[site]
        times, fs = K.radar_files(site)
        keep = np.sort(rng.choice(len(fs), min(a.max_per_site, len(fs)), replace=False))
        for i in keep:
            t = times[i].round("h")
            if not K.day_ok(t + pd.Timedelta(hours=3)):
                continue
            uv = parse(fs[i], elev)
            if uv is None or np.isfinite(uv[0][LEV]).sum() < 3:
                continue
            obs = np.stack([uv[0][LEV], uv[1][LEV]])
            try:
                pools = [K.tool(lat, lon, t + pd.Timedelta(hours=g), seed=int(t.timestamp()) % 100000, n=a.n, elevation=elev) for g in AGES]
            except ValueError:          # an hour the tool cannot serve
                continue
            for g, atm in zip(AGES, pools):
                x = np.stack([np.asarray(atm["u"])[:, LEV], np.asarray(atm["v"])[:, LEV]])          # (2, n, L)
                d[g].append(obs - x.mean(1))
                B[g].append(np.stack([np.cov(x[j].T) for j in (0, 1)]))
            days.append(f"{site}{t.date()}")
            used[site] = used.get(site, 0) + 1
    assert len(days) >= 5, f"only {len(days)} usable radar hours"
    d, B, days = {g: np.array(v) for g, v in d.items()}, {g: np.array(v) for g, v in B.items()}, np.array(days)
    R = r_matrix(d[0], B[0])
    lines = [f"C4 radar error from innovations: {len(days)} radar hours ({', '.join(f'{k} {v}' for k, v in used.items())}), tool sample set {a.n}, heights 500-5000 m",
             "height m   radar minus tool: mean (bias) / rms    tool spread    R diagonal (m/s)2"]
    for k in range(len(LEV)):
        lines.append(f"{K.H[LEV[k]]:<11.0f}{np.nanmean(d[0][:, :, k]):+.2f} / {np.sqrt(np.nanmean(d[0][:, :, k] ** 2)):<27.2f}{np.sqrt(B[0][:, :, k, k].mean()):<15.2f}{R[k, k]:+.2f}")
    if (np.diag(R) <= 0).mean() >= 0.5 or np.nanmean(np.diag(R)) <= 0:
        lines.append("VERDICT: C4 KILLED. R is not positive: the tool's own spread already covers the radar mismatch. Keep 3.0 m/s.")
        return K.report("b2_c4_innovation_fit", lines)
    sd, L = fit_L(R)
    per = np.nanmean(d[0] ** 2 - np.diagonal(B[0], axis1=2, axis2=3), axis=(1, 2))               # one value per radar hour, for the interval
    ok = np.isfinite(per)
    _, lo, hi = K.block_boot(per[ok], days[ok], draws=1000)
    sds = [np.sqrt(max(np.nanmean(np.diag(r_matrix(d[g], B[g]))), 0.0)) for g in AGES]
    grow = float(np.sum([(sds[g] / sd - 1) * g for g in AGES[1:]]) / np.sum(np.square(AGES[1:])))
    four = np.array([int(np.argmin(np.abs(K.H[LEV] - z))) for z in (1000, 2000, 3000, 4000)])
    s4, s10 = sd * many_levels_factor(L, four), sd * many_levels_factor(L, np.arange(len(LEV)))
    lines += [f"radar error of one level: sd {sd:.2f} m/s, 95 % interval [{np.sqrt(max(lo, 0)):.2f}, {np.sqrt(max(hi, 0)):.2f}] (hand-set value today: 3.0)",
              f"height over which errors stay alike: L {L:.0f} m",
              "sd by age of the radar volume (0, 1, 2, 3 h): " + ", ".join(f"{s:.2f}" for s in sds) + f" -> growth a {grow:+.2f} per hour (sd(age) = sd (1 + a age))",
              f"sd to give an engine that takes levels as independent: 4 levels {s4:.2f} m/s, all 10 levels {s10:.2f} m/s",
              "VERDICT: C4 measured. Now run the test (CPU, about 10 min each; EPZ + Santa Teresa balloons, then MAF + Midland):",
              f"  PYTHONPATH=. .venv/Scripts/python -W ignore scripts/p3_vad_condition.py --sigma {s4:.2f}",
              f"  PYTHONPATH=. .venv/Scripts/python -W ignore scripts/p3_vad_condition.py --sigma {s10:.2f}",
              f"  PYTHONPATH=. .venv/Scripts/python -W ignore scripts/p3_vad_condition.py --sigma {s10:.2f} --radar MAF --balloon USM00072265",
              "  Compare with the same commands at --sigma 3.0. Adopt rule: row 'radar+all' beats row 'radar' at 2.5-5 km and coverage is 0.85 or more. Changing VAD_SIGMA_MS is a core change: report, do not edit."]
    K.report("b2_c4_innovation_fit", lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    n, L0, sd0 = 6000, 1500.0, 2.0
    Bm, Rm = 4.0 * np.exp(-DZ / 3000.0), sd0 ** 2 * np.exp(-DZ / L0)
    d = rng.multivariate_normal(np.zeros(len(LEV)), Bm + Rm, (n, 2))
    d[rng.random(d.shape) < 0.2] = np.nan                                         # gaps like clear air
    sd, L = fit_L(r_matrix(d, np.broadcast_to(Bm, (n, 2) + Bm.shape)))
    assert abs(sd - sd0) < 0.15 and 1000 < L < 2200, (sd, L)
    assert many_levels_factor(1e-6, np.arange(4)) == 1.0 and abs(many_levels_factor(1e12, np.arange(4)) - 2.0) < 1e-6


_selfcheck()
if __name__ == "__main__":
    main()
