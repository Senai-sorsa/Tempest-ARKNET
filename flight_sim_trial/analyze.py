"""Summarise the trial: S0 plain standard atmosphere, S1 scaled standard + uniform wind, S2 Tempest samples. Also sanity-check the sampled atmospheres.

    cd flight_sim_trial/src ; .venv/Scripts/python -I ../analyze.py afternoon [morning]
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src", "src"))
from flight_sim.environment import atmosphere as fs_atm   # noqa: E402

R = os.path.join(HERE, "results")
tags = sys.argv[1:] or ["afternoon"]
lines = []
P = lambda s="": (print(s), lines.append(s))

for tag in tags:
    df = pd.read_csv(os.path.join(R, f"flights_{tag}.csv"))
    meta = json.load(open(os.path.join(R, f"meta_{tag}.json")))
    at = np.load(os.path.join(R, f"atmosphere_{tag}.npz"))
    s0, s1, s2 = df.iloc[0], df.iloc[1], df[df.scenario.str.startswith("S2")]
    P(f"\n=== {tag}: {meta['when']}  (n = {len(s2)} sampled atmospheres) ===")
    P(f"S1 inputs from the sample medians: T {meta['s1']['T'] - 273.15:.1f} C, p {meta['s1']['p'] / 1000:.2f} kPa, RH {meta['s1']['rh']:.0f} %, wind {meta['s1']['wind']:.1f} m/s from {meta['s1']['from_deg']:.0f} deg")
    cols = ["apogee_agl_m", "max_speed", "max_q_pa", "flight_time_s", "drift_m", "north_m", "east_m", "rho_pad", "T_pad", "max_wind"]
    t = pd.DataFrame({"S0 plain ISA": s0[cols], "S1 scaled+wind": s1[cols], "S2 mean": s2[cols].mean(), "S2 sd": s2[cols].std(),
                      "S2 p5": s2[cols].quantile(0.05), "S2 p50": s2[cols].quantile(0.5), "S2 p95": s2[cols].quantile(0.95)})
    P(t.round(2).to_string())
    pr = lambda col, v: 100.0 * (s2[col] < v).mean()
    P(f"\nwhere the conventional runs fall inside the Tempest distribution (percentile): apogee S0 {pr('apogee_agl_m', s0.apogee_agl_m):.0f}, S1 {pr('apogee_agl_m', s1.apogee_agl_m):.0f};"
      f" flight time S0 {pr('flight_time_s', s0.flight_time_s):.0f}, S1 {pr('flight_time_s', s1.flight_time_s):.0f};  drift S0 {pr('drift_m', s0.drift_m):.0f}, S1 {pr('drift_m', s1.drift_m):.0f}")
    P(f"apogee difference S0 -> S2 median: {s2.apogee_agl_m.median() - s0.apogee_agl_m:+.0f} m ({100 * (s2.apogee_agl_m.median() / s0.apogee_agl_m - 1):+.1f} %);  S1 -> S2 median: {s2.apogee_agl_m.median() - s1.apogee_agl_m:+.0f} m")
    P(f"apogee spread across the sampled atmospheres: sd {s2.apogee_agl_m.std():.0f} m, p5-p95 {s2.apogee_agl_m.quantile(.05):.0f}-{s2.apogee_agl_m.quantile(.95):.0f} m;   drift p5-p95 {s2.drift_m.quantile(.05):.0f}-{s2.drift_m.quantile(.95):.0f} m (S0 has {s0.drift_m:.0f} m with no wind)")
    P(f"correlation of S2 apogee with pad air density {np.corrcoef(s2.apogee_agl_m, s2.rho_pad)[0, 1]:+.2f}, with surface T {np.corrcoef(s2.apogee_agl_m, s2['T_pad'])[0, 1]:+.2f};  drift with max wind {np.corrcoef(s2.drift_m, s2.max_wind)[0, 1]:+.2f}")

    # sanity of the sampled atmospheres against the standard day at the pad
    z, pad = np.asarray(at["height_asl"], float), float(at["pad_m"])
    T, p, u, v, rh = (np.asarray(at[k], float) for k in ("T", "p", "u", "v", "RH"))
    std = [fs_atm._standard_conditions(h) for h in z]
    sT, sp_ = np.array([c.temperature for c in std]), np.array([c.pressure for c in std])
    P("\nprofile sanity (sample median vs the standard day at the same altitude):")
    P("  height AGL  T_med-T_isa (K)   p_med/p_isa   |wind| p50/p95 (m/s)   T p5-p95 (C)")
    for j in (0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 43):
        sp = np.hypot(u[:, j], v[:, j])
        P(f"  {z[j] - pad:8.0f}    {np.median(T[:, j]) - sT[j]:+8.1f}        {np.median(p[:, j]) / sp_[j]:8.3f}      {np.median(sp):5.1f} / {np.percentile(sp, 95):5.1f}       {np.percentile(T[:, j], 5) - 273.15:6.1f} {np.percentile(T[:, j], 95) - 273.15:6.1f}")
    t2m, sfc = np.asarray(at["t2m"], float), np.asarray(at["sp"], float)
    P(f"  surface: T2m p5/p50/p95 {np.percentile(t2m, 5) - 273.15:.1f}/{np.median(t2m) - 273.15:.1f}/{np.percentile(t2m, 95) - 273.15:.1f} C; sp p5/p50/p95 {np.percentile(sfc, 5) / 1000:.2f}/{np.median(sfc) / 1000:.2f}/{np.percentile(sfc, 95) / 1000:.2f} kPa; RH2m median {np.median(at['rh2m']):.0f} %")
    lapse = -(T[:, 1:] - T[:, :-1]) / np.diff(z)[None, :] * 1000.0
    P(f"  lowest-layer lapse rate (10-50 m): p50 {np.median(lapse[:, 0]):.1f} K/km, p95 {np.percentile(lapse[:, 0], 95):.1f} K/km (dry adiabatic 9.8); share of samples with lapse > 9.8 in any of the first 3 layers: {100 * (lapse[:, :3] > 9.8).any(1).mean():.0f} %")
    P(f"  site T2m vs the 10 m level temperature: median {np.median(t2m - T[:, 0]):+.2f} K (a jump of more than ~2 K is suspicious)")

    # figure
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 3, figsize=(14, 4))
        ax[0].hist(s2.apogee_agl_m, 25, color="#2a78d6", alpha=0.8)
        ax[0].axvline(s0.apogee_agl_m, color="k", ls="--", label="S0 plain standard")
        ax[0].axvline(s1.apogee_agl_m, color="#eb6834", ls="--", label="S1 scaled + wind")
        ax[0].set_xlabel("apogee AGL (m)"); ax[0].legend(); ax[0].set_title(f"{tag}: apogee")
        ax[1].scatter(s2.east_m, s2.north_m, s=8, color="#2a78d6", label="Tempest samples")
        ax[1].plot([s0.east_m], [s0.north_m], "k*", ms=12, label="S0"); ax[1].plot([s1.east_m], [s1.north_m], "o", color="#eb6834", label="S1")
        ax[1].set_xlabel("east (m)"); ax[1].set_ylabel("north (m)"); ax[1].set_aspect("equal"); ax[1].legend(); ax[1].set_title("landing point relative to pad")
        zz = (z - pad) / 1000.0
        for q, c in ((5, "#9ec5f4"), (50, "#2a78d6"), (95, "#9ec5f4")):
            ax[2].plot(np.percentile(T, q, 0) - 273.15, zz, color=c)
        ax[2].plot(sT - 273.15, zz, "k--", label="standard day"); ax[2].set_xlabel("T (C)"); ax[2].set_ylabel("height AGL (km)"); ax[2].set_title("temperature p5/p50/p95"); ax[2].legend()
        fig.tight_layout(); fig.savefig(os.path.join(R, f"trial_{tag}.png"), dpi=110)
    except Exception as e:   # noqa: BLE001
        P(f"(figure skipped: {e})")

open(os.path.join(R, "summary.txt"), "w", encoding="utf-8").write("\n".join(lines))
