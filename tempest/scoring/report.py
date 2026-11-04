"""Charts for looking over a trained model later; score.main calls `report` and saves PNGs into <model>_report/.

training_curves   loss per checkpoint check, each seed member (train thin, held-out thick)
skill_by_height   CRPS skill vs climatology per variable and height (> 0 beats climatology)
crps_by_height    CRPS in physical units per variable and height (lower is better)
coverage          share of truths inside the 90 % range (0.90 is right; lower = too confident)
rank_histograms   where the truth falls among the model's samples (flat = honest spread; U = too narrow)
variogram_skill   profile-shape skill (shear, differences between heights) per variable
surface_skill     CRPS skill of the near-surface fields
example_profiles  a few held-out cases: truth vs the model's 5-95 % range and median
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # files only, no window
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Colors follow the method, never the chart: same color for the same method everywhere.
COLOR = {"clim": "#52514e", "gauss": "#eb6834", "known": "#2a78d6", "unknown": "#1baf7a"}
LABEL = {"clim": "climatology", "gauss": "Gaussian (Earth-GRAM style)", "known": "model, drivers known",
         "unknown": "model, drivers unknown"}
UNIT = {"u": "m/s", "v": "m/s", "T": "K", "RH": "%"}
plt.rcParams.update({"figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "axes.edgecolor": "#c3c2b7",
                     "axes.labelcolor": "#52514e", "xtick.color": "#52514e", "ytick.color": "#52514e",
                     "text.color": "#0b0b0b", "axes.grid": True, "grid.color": "#e8e7e3", "grid.linewidth": 0.8,
                     "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2,
                     "font.size": 10, "savefig.dpi": 130, "savefig.bbox": "tight"})


def _by_height(path, res, profile, heights, col, methods, xlabel, title, ref=None):
    fig, axs = plt.subplots(1, len(profile), figsize=(3.4 * len(profile), 5), sharey=True)
    n = len(heights)
    for i, (ax, v) in enumerate(zip(axs, profile)):
        for k in methods:
            ax.plot(res[col.format(k)].to_numpy()[i * n:(i + 1) * n], heights / 1000, color=COLOR[k],
                    marker="o", markersize=3, label=LABEL[k])
        if ref is not None:
            ax.axvline(ref, color="#0b0b0b", linewidth=1, linestyle="--")
        ax.set_title(v + (f" ({UNIT[v]})" if "crps_" in col else ""))
        ax.set_xlabel(xlabel)
    axs[0].set_ylabel("height above ground (km)")
    axs[0].legend(loc="best", fontsize=8, frameon=False)
    fig.suptitle(title)
    fig.savefig(path)
    plt.close(fig)


def report(out_dir, res, vs, ranks, examples, histories, profile, heights, surface, truth_label="truth (ERA5)"):
    """res: per-column score table; vs: variogram table; ranks: (N, D) rank of truth among m samples (0..m);
    examples: (truth (k, D), samples (k, m, D)); histories: list of [(step, train, val)] per member or None."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    n, D = len(heights), ranks.shape[1]

    if any(histories):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for j, h in enumerate(histories):
            if h:
                s, tr, va = np.array(h).T
                c = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"][j % 8]
                ax.plot(s, tr, color=c, linewidth=1, alpha=0.5)
                ax.plot(s, va, color=c, label=f"member {j + 1} held-out (best {va.min():.4f})")
        ax.set_xlabel("training step")
        ax.set_ylabel("loss (lower is better)")
        ax.set_title("Training curves: thick = held-out years, thin = training batch")
        ax.legend(frameon=False, fontsize=8)
        fig.savefig(out / "training_curves.png")
        plt.close(fig)

    _by_height(out / "skill_by_height.png", res, profile, heights, "skill_{}", ("gauss", "known", "unknown"),
               "skill vs climatology", "CRPS skill by height (right of the dashed line beats climatology)", ref=0)
    _by_height(out / "crps_by_height.png", res, profile, heights, "crps_{}", ("clim", "gauss", "known", "unknown"),
               "CRPS (lower is better)", "Average error of the forecast spread, physical units")
    _by_height(out / "coverage.png", res, profile, heights, "cov90_{}", ("clim", "gauss", "known", "unknown"),
               "share inside 90 % range", "90 % range coverage (dashed = ideal 0.90)", ref=0.9)

    groups = [(v, slice(i * n, (i + 1) * n)) for i, v in enumerate(profile)] + [("surface", slice(len(profile) * n, D))]
    m = int(ranks.max())
    fig, axs = plt.subplots(1, len(groups), figsize=(3.2 * len(groups), 3.6), sharey=True)
    for ax, (v, sl) in zip(axs, groups):
        f = np.bincount(ranks[:, sl].ravel(), minlength=m + 1) / ranks[:, sl].size
        ax.bar(np.arange(m + 1), f, width=0.85, color=COLOR["known"])
        ax.axhline(1 / (m + 1), color="#0b0b0b", linewidth=1, linestyle="--")
        ax.set_title(v)
        ax.set_xlabel("rank of truth among samples")
    axs[0].set_ylabel("share of cases")
    fig.suptitle("Rank histograms, drivers known (flat at the dashed line = honest spread; U shape = too narrow)")
    fig.savefig(out / "rank_histograms.png")
    plt.close(fig)

    def bars(path, names, series, title, xlabel):
        fig, ax = plt.subplots(figsize=(7, 0.6 * len(names) * len(series) / 2 + 1.5))
        y, w = np.arange(len(names)), 0.8 / len(series)
        for j, (k, vals) in enumerate(series.items()):
            ax.barh(y + (j - (len(series) - 1) / 2) * w, vals, height=w * 0.9, color=COLOR[k], label=LABEL[k])
        ax.axvline(0, color="#0b0b0b", linewidth=1)
        ax.set_yticks(y, names)
        ax.invert_yaxis()
        ax.set_xlabel(xlabel)
        ax.set_title(title)
        ax.legend(frameon=False, fontsize=8)
        fig.savefig(path)
        plt.close(fig)

    bars(out / "variogram_skill.png", list(vs["var"]), {k: vs[f"vs_skill_{k}"] for k in ("gauss", "known", "unknown")},
         "Profile-shape skill vs climatology (variogram score; > 0 beats climatology)", "skill")
    sres = res.set_index("column").loc[surface]
    bars(out / "surface_skill.png", surface, {k: sres[f"skill_{k}"] for k in ("gauss", "known", "unknown")},
         "Near-surface CRPS skill vs climatology", "skill")

    truth, samp = examples
    fig, axs = plt.subplots(len(truth), len(profile), figsize=(3.2 * len(profile), 3.6 * len(truth)), sharey=True,
                            squeeze=False)
    for r in range(len(truth)):
        for i, v in enumerate(profile):
            ax, sl = axs[r, i], slice(i * n, (i + 1) * n)
            lo, med, hi = np.quantile(samp[r][:, sl], [0.05, 0.5, 0.95], axis=0)
            ax.fill_betweenx(heights / 1000, lo, hi, color=COLOR["known"], alpha=0.25, linewidth=0,
                             label="model 5-95 %")
            ax.plot(med, heights / 1000, color=COLOR["known"], linewidth=1.5, label="model median")
            ax.plot(truth[r][sl], heights / 1000, color="#0b0b0b", linewidth=1.5, label=truth_label)
            ax.set_title(f"case {r + 1}: {v} ({UNIT[v]})")
        axs[r, 0].set_ylabel("height (km)")
    axs[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle("Example held-out profiles")
    fig.savefig(out / "example_profiles.png")
    plt.close(fig)

    res.to_csv(out / "scores_per_column.csv", index=False)
    vs.to_csv(out / "variogram.csv", index=False)
    return sorted(p.name for p in out.iterdir())
