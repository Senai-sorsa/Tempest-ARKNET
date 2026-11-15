"""New_Plan 17 UR10: G2-2's Student-t widening on the RADAR path, through Launch (p3_vad_condition.py bypasses Launch, so G2-2 never tested it).
Cases: El Paso radar (EPZ, cached NVW volumes in data/raw/nexrad_nvw, newest volume at most 65 min before the balloon) + Santa Teresa balloons
(USM00072364) at 00Z, 2023 (2022 too if 2023 has under 60 cases; stated in the log). Per case one Launch (climate mode, n 200, the pad = the balloon
station, seed from the time), then observe_radar(profile = the radar u, v on the model heights, the default levels 500-2000 m and sigma) with
t_update False (shipped) and True; same seed. Scored on the balloon at 2.5-5 km above the station (never observed): CRPS and 90 % coverage of
u and v, averaged. Surprise D^2 = sum over the observed levels of the squared standardised radar-minus-prior-mean, u and v (prior pool).
Rule (G2-2's rule, set before any run in New_Plan 17.2):
  PASS: on the 10 % most surprising cases |cov90 - 0.90| falls, AND on the other 90 % the CRPS change (t - shipped) has a 21-day block 95 %
        interval that contains 0 or lies below it.  KILL: the other 90 % worse beyond noise (interval above 0).  Otherwise FAIL (flag stays off).
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b33_ur10_radar_t.py        # about 30-60 min
Result: docs/results/logs/kit_b33_ur10_radar_t.log
"""
import numpy as np
import pandas as pd

import kit_common as K

NAME = "b33_ur10_radar_t"
LEVELS = (500.0, 1000.0, 1500.0, 2000.0)
SCORE = (2500, 5000)


def judge(top_cov0, top_cov1, rest_lo, rest_hi):
    if rest_lo > 0:
        return "KILL (the other 90 % worse beyond noise)"
    return "PASS" if abs(top_cov1 - 0.90) < abs(top_cov0 - 0.90) and rest_lo <= 0 else "FAIL (flag stays off)"


def main():
    from tempest_weather_v2 import Launch
    K.ram_gate(3.0)
    t, b = K.balloon(K.EPZ)
    lat, lon, elev = K.station_pos(K.EPZ)
    idx = K.radar_files("EPZ")
    k_sc = np.flatnonzero((K.H >= SCORE[0]) & (K.H < SCORE[1]))
    lv = [int(np.flatnonzero(K.H == h)[0]) for h in LEVELS]
    rows, years = [], [2023]
    for attempt in (0, 1):
        for i in np.flatnonzero((t.hour == 0) & np.isin(t.year, years)):
            if any(r["t"] == t[i] for r in rows):
                continue
            r = K.radar_uv("EPZ", t[i], elev, max_age_min=65, index=idx)
            if r is None or not np.isfinite(r[0][lv]).all():
                continue
            y_u, y_v = b["u"][i, k_sc], b["v"][i, k_sc]
            if not (np.isfinite(y_u).all() and np.isfinite(y_v).all()):
                continue
            ok = np.isfinite(r[0]) & np.isfinite(r[1])
            prof = dict(heights_asl_m=list(K.H[ok] + elev), u=list(r[0][ok]), v=list(r[1][ok]), site="EPZ", time=str(t[i]))
            try:
                L = Launch(lat, lon, t[i].strftime("%Y-%m-%d %H:%M"), tz="UTC", n=200, seed=int(t[i].timestamp()) % 100000, units="si", elevation=elev, mode="ai")
                prior = L._ensure_pool()["samples"]
                pu, pv = np.asarray(prior["u"], float)[:, lv], np.asarray(prior["v"], float)[:, lv]
                D2 = float((((r[0][lv] - pu.mean(0)) ** 2) / pu.var(0) + ((r[1][lv] - pv.mean(0)) ** 2) / pv.var(0)).sum())
                out = []
                for tu in (False, True):
                    s = L.observe_radar(site="EPZ", profile=prof, levels_m=LEVELS, t_update=tu)._ensure_pool()["samples"]
                    xu, xv = np.asarray(s["u"], float)[:, k_sc], np.asarray(s["v"], float)[:, k_sc]
                    crps = np.mean([K.crps1(xu[:, j], y_u[j]) for j in range(len(k_sc))] + [K.crps1(xv[:, j], y_v[j]) for j in range(len(k_sc))])
                    cov = np.mean([np.percentile(x[:, j], 5) <= y[j] <= np.percentile(x[:, j], 95) for x, y in ((xu, y_u), (xv, y_v)) for j in range(len(k_sc))])
                    out += [crps, cov]
                rows.append(dict(t=t[i], D2=D2, c0=out[0], k0=out[1], c1=out[2], k1=out[3]))
            except Exception as e:   # noqa: BLE001 (a case the tool cannot serve is counted and skipped)
                print(t[i], "skipped:", repr(e)[:80], flush=True)
        if len(rows) >= 60 or attempt == 1:
            break
        years = [2022, 2023]
    R = pd.DataFrame(rows)
    top = R.D2 >= R.D2.quantile(0.90)
    blk = ((R.t.dt.normalize() - pd.Timestamp("2022-01-01")).dt.days // 21).astype(str).to_numpy()
    dm, lo, hi = K.block_boot((R.c1 - R.c0)[~top].to_numpy(), blk[~top.to_numpy()], draws=1000)
    lines = [f"UR10 radar t-update: EPZ radar + Santa Teresa 00Z balloons, years {years}, {len(R)} cases; scored at {SCORE[0]}-{SCORE[1]} m above the station (u and v)"]
    for lab, sel in (("all", np.ones(len(R), bool)), ("top 10 % surprise", top.to_numpy()), ("other 90 %", ~top.to_numpy())):
        s = R[sel]
        lines.append(f"  {lab:<18} n {len(s):4d}: CRPS shipped {s.c0.mean():.3f} t {s.c1.mean():.3f}; cov90 shipped {s.k0.mean():.2f} t {s.k1.mean():.2f}")
    lines.append(f"  other 90 %: CRPS change t - shipped {dm:+.4f} [{lo:+.4f}, {hi:+.4f}] (21-day blocks); D^2 threshold {R.D2.quantile(0.9):.1f}")
    lines.append("Rule (G2-2's, pre-set): PASS = top-10 % coverage error falls and the other 90 % CRPS interval contains 0 or lies below; KILL = the other 90 % worse beyond noise.")
    lines.append("Verdict: " + judge(R.k0[top].mean(), R.k1[top].mean(), lo, hi))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(0.70, 0.85, -0.01, 0.01) == "PASS"
    assert judge(0.70, 0.60, -0.01, 0.01).startswith("FAIL")
    assert judge(0.70, 0.85, 0.001, 0.02).startswith("KILL")


_selfcheck()
if __name__ == "__main__":
    main()
