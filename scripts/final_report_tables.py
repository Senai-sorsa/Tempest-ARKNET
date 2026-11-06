"""E5 helper: tables for docs/results/FINAL_REPORT.md from the final-test outputs (docs/final_test) and the development-year backups.
    PYTHONPATH=. python scripts/final_report_tables.py > docs/final_test/tables.md"""
import numpy as np
import pandas as pd

from tempest.scoring.score import band_masks, physical_names

FT, DV, MD = "docs/final_test/final_headlines", "docs/final_test/dev_backup", "models"
FIN, E12 = "generator_80_p2f", "generator_80_b0smix"
files = {
    ("ERA5", "final"): (f"{FT}/{FIN}_cal2021_smap_shufc8_headline.csv", f"{MD}/{FIN}_cal2021_smap_shufc8.score.csv"),
    ("ERA5", "e12"): (f"{FT}/{E12}_cal2021_headline.csv", f"{MD}/{E12}_cal2021.score.csv"),
    ("balloons", "final"): (f"{FT}/{FIN}_sonde_cal2021_smap_headline.csv", f"{MD}/{FIN}_sonde_cal2021_smap.score.csv"),
    ("balloons", "e12"): (f"{FT}/{E12}_sonde_cal2021_headline.csv", f"{MD}/{E12}_sonde_cal2021.score.csv"),
}
dev = {"ERA5": f"{DV}/{FIN}_cal2021_smap_shufc8_headline.csv", "balloons": f"{DV}/{FIN}_sonde_cal2021_smap_headline.csv"}
masks = band_masks()


def gauss_skill(score_csv):
    s = pd.read_csv(score_csv).set_index("column").reindex(physical_names())
    out = {}
    for v, b, sel in masks:
        out[(v, b)] = (1 - s.crps_unknown[sel].mean() / s.crps_gauss[sel].mean(), 1 - s.crps_unknown[sel].mean() / s.crps_clim[sel].mean(), s.cov99_gauss[sel].mean())
    return out


for truth in ("ERA5", "balloons"):
    h, e = pd.read_csv(files[truth, "final"][0]).set_index(["var", "band"]), pd.read_csv(files[truth, "e12"][0]).set_index(["var", "band"])
    d = pd.read_csv(dev[truth]).set_index(["var", "band"])
    g, ge = gauss_skill(files[truth, "final"][1]), gauss_skill(files[truth, "e12"][1])
    rows = []
    for k in h.index:
        better = h.loc[k, "skill15_unknown_lo"] > e.loc[k, "skill15_unknown_hi"]
        worse = h.loc[k, "skill15_unknown_hi"] < e.loc[k, "skill15_unknown_lo"]
        rows.append(dict(cell=f"{k[0]} {k[1]}", skill15=f"{h.loc[k, 'skill15_unknown']:+.4f} [{h.loc[k, 'skill15_unknown_lo']:+.4f}, {h.loc[k, 'skill15_unknown_hi']:+.4f}]",
                         e12=f"{e.loc[k, 'skill15_unknown']:+.4f}", vs_e12="better" if better else "WORSE" if worse else "tie",
                         vs_gauss=f"{g[k][0] * 100:+.1f} %", cov99=f"{h.loc[k, 'cov99_unknown']:.4f}", cov99_gauss=f"{g[k][2]:.4f}", dev_skill15=f"{d.loc[k, 'skill15_unknown']:+.4f}", dev_cov99=f"{d.loc[k, 'cov99_unknown']:.4f}"))
    t = pd.DataFrame(rows)
    ms = h.skill15_unknown.mean()
    print(f"\n### {truth}, 2026 January-June, final system vs E12 and vs the Gaussian baseline (drivers unknown)\n")
    print(f"mean skill15: final {ms:+.4f} (E12 {e.skill15_unknown.mean():+.4f}, development years {d.skill15_unknown.mean():+.4f}); mean |cov99 - 0.99|: final {(h.cov99_unknown - 0.99).abs().mean():.4f} (E12 {(e.cov99_unknown - 0.99).abs().mean():.4f}, development {(d.cov99_unknown - 0.99).abs().mean():.4f}); mean CRPS skill vs the Gaussian baseline: final {np.mean([v[0] for v in g.values()]) * 100:+.1f} %, E12 {np.mean([v[0] for v in ge.values()]) * 100:+.1f} %; cells better than the Gaussian: {sum(v[0] > 0 for v in g.values())} of {len(g)}\n")
    print("| " + " | ".join(t.columns) + " |")
    print("|" + "---|" * len(t.columns))
    for r in t.itertuples(index=False):
        print("| " + " | ".join(str(x) for x in r) + " |")
