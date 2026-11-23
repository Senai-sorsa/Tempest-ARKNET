"""Paper figures for the Earth-GRAM comparison (static PNG, light background). REPORT ONLY.
Reads data/kit/breakdown_scores.npz and data/kit/gram_cases.csv; writes paper/figures/gram_*.png.
Colours: the dataviz reference palette, first three categorical slots (validated all-pairs) - tool blue, GRAM NCEP orange, GRAM RRA aqua;
the wind-scale figure uses one sequential orange ramp (magnitude of the scale factor).

    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore paper/gram_figures.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "new_plan_kit"))
import kit_common as K

FIG = os.path.join(K.REPO, "paper", "figures")
SRC = {"tool": ("Tool", "#2a78d6"), "gram_ncep": ("Earth-GRAM NCEP", "#eb6834"), "gram_rra": ("Earth-GRAM RRA", "#1baf7a")}
QL = {"u": "u (m/s)", "v": "v (m/s)", "T": "T (K)", "spd": "wind speed (m/s)"}
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "lines.linewidth": 2})


def save(fig, name):
    os.makedirs(FIG, exist_ok=True)
    fig.savefig(os.path.join(FIG, name), dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", os.path.join("paper", "figures", name))


def main():
    cases = pd.read_csv(os.path.join(K.OUT, "gram_cases.csv"))
    d = np.load(os.path.join(K.OUT, "breakdown_scores.npz"))
    assert list(d["case"]) == list(cases.case)
    t = pd.to_datetime(cases.time_utc)
    iso = t.dt.isocalendar()
    week = (iso.year.astype(str) + "-W" + iso.week.astype(str)).values
    hk = K.H / 1000

    # 1. 90 % coverage by height
    fig, ax = plt.subplots(1, 4, figsize=(9, 3.6), sharey=True)
    for a, q in zip(ax, QL):
        a.axvline(0.9, color=INK2, lw=1, ls="--")
        for s, (lab, c) in SRC.items():
            a.plot(np.nanmean(d[f"{s}__{q}__in90"], 0), hk, color=c, label=lab)
        a.set_xlim(0.55, 1.0)
        a.set_title(QL[q], fontsize=9)
        a.set_xlabel("share inside 90 % range")
    ax[0].set_ylabel("height above ground (km)")
    fig.legend(*ax[0].get_legend_handles_labels(), frameon=False, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.13), fontsize=8)
    fig.suptitle("Coverage of the central 90 % ensemble range (target 0.90, dashed), 800 balloon cases 2024-25", fontsize=10, x=0.01, y=1.04, ha="left")
    save(fig, "gram_coverage_by_height.png")

    # 2. paired CRPS difference vs tool by band, week-block 95 % interval
    fig, ax = plt.subplots(1, 4, figsize=(9, 2.8), sharey=True)
    y = np.arange(len(K.BANDS))[::-1]
    for a, q in zip(ax, QL):
        a.axvline(0, color=INK2, lw=1)
        for k, s in enumerate(("gram_ncep", "gram_rra")):
            lab, c = SRC[s]
            for j, (_, lo, hi) in enumerate(K.BANDS):
                ix = K.band_idx(lo, hi)
                bt, bs = np.nanmean(d[f"tool__{q}__crps"][:, ix], 1), np.nanmean(d[f"{s}__{q}__crps"][:, ix], 1)
                ok = np.isfinite(bt) & np.isfinite(bs)
                m, l, h = K.block_boot(bs[ok] - bt[ok], week[ok], draws=4000)
                b = bt[ok].mean()
                yy = y[j] + (0.12 if k == 0 else -0.12)
                a.plot([100 * l / b, 100 * h / b], [yy, yy], color=c, lw=2, solid_capstyle="round")
                a.plot(100 * m / b, yy, "o", color=c, ms=5, mec=SURF, mew=1.5, label=lab if j == 0 else None)
        a.set_title(QL[q], fontsize=9)
        a.set_xlabel("CRPS vs tool (%)")
    ax[0].set_yticks(y, [b[0] for b in K.BANDS])
    fig.legend(*ax[0].get_legend_handles_labels(), frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.2), fontsize=8)
    fig.suptitle("Paired CRPS difference to the tool (above 0 = tool better), 95 % interval from week blocks", fontsize=10, x=0.01, y=1.04, ha="left")
    save(fig, "gram_paired_crps.png")

    # 3. PIT histogram, wind speed 0-12 km
    fig, ax = plt.subplots(1, 3, figsize=(9, 2.6), sharey=True)
    ix = K.band_idx(0, 12000)
    for a, (s, (lab, c)) in zip(ax, SRC.items()):
        p = d[f"{s}__spd__pit"][:, ix].ravel()
        h = np.histogram(p[np.isfinite(p)], bins=10, range=(0, 1))[0]
        a.bar(np.arange(10) / 10 + 0.05, h / h.sum() / 0.1, width=0.1 - 0.012, color=c)
        a.axhline(1, color=INK2, lw=1, ls="--")
        a.set_title(lab, fontsize=9)
        a.set_xlabel("PIT")
        a.grid(axis="x", visible=False)
    ax[0].set_ylabel("density (flat = 1)")
    fig.suptitle("PIT histogram of wind speed, 0-12 km (a spike at the right = observed winds above every member)", fontsize=10, x=0.01, y=1.04, ha="left")
    save(fig, "gram_pit_windspeed.png")

    # 4. GRAM wind-scale sensitivity: wind-speed CRPS vs tool by band
    fig, a = plt.subplots(figsize=(4.6, 3))
    ramp = {"gram_ncep": ("s = 1.0 (as shipped)", "#f6b494"), "gram_ncep_ru1.2": ("s = 1.2", "#ef8a5c"),
            "gram_ncep_ru1.35": ("s = 1.35", "#d95926"), "gram_ncep_ru1.5": ("s = 1.5", "#9c3a12")}
    x = np.arange(len(K.BANDS))
    a.axhline(0, color=INK2, lw=1)
    for s, (lab, c) in ramp.items():
        v = []
        for _, lo, hi in K.BANDS:
            ixb = K.band_idx(lo, hi)
            bt, bs = np.nanmean(d[f"tool__spd__crps"][:, ixb], 1), np.nanmean(d[f"{s}__spd__crps"][:, ixb], 1)
            v.append(100 * (np.nanmean(bs) - np.nanmean(bt)) / np.nanmean(bt))
        a.plot(x, v, "-o", color=c, ms=5, mec=SURF, mew=1.5, label=lab)
    a.set_xticks(x, [b[0] for b in K.BANDS])
    a.set_ylabel("wind-speed CRPS vs tool (%)")
    a.legend(frameon=False, fontsize=8)
    a.set_title("Scaling GRAM's wind perturbations by s", fontsize=10, loc="left")
    save(fig, "gram_wind_scale.png")


if __name__ == "__main__":
    main()
