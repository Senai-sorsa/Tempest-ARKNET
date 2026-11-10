"""F-V2 step 2 (2026-11-10): does the SHIPPED forecast mode work at the hours and leads the tool refuses today? The tool's own mode F parts (bundled assets: network, range map,
error-profile templates of the nearest tested lead, 50:50 ridge mixture; tempest_weather/api.py forecast path) are applied to the 00Z + 12Z refetch rows of the TEST year 2022
(data/modeF_v2/2022.npz, built by scripts/il6_build_v2.py), and scored with the CRPS against the ERA5 truth, next to an HOUR-AWARE climatology (199 rows of 2016-2020 of the same valid
UTC hour, day of year within 20 days, ground height within 250 m) and the raw HRES profile. Per valid solar hour (about 05 / 11 / 17 h) x lead bin. u, v, T, RH at 44 heights.
CPU only.  PYTHONPATH=. python -W ignore scripts/fv2_eval.py [--rows 4000] [--assets tempest_weather/assets] [--rows-dir data/modeF_v2] [--out docs/results/logs/fv2_eval.log]"""
import argparse

import numpy as np

from tempest.forecast import modeF as F
from tempest.scoring.score import crps_ensemble
from tempest_weather import _core, api

LEADS = (1, 3, 5, 7)
BINS = [(0.2, 1.5, "0.25-1.5 d"), (1.5, 3.5, "1.5-3.5 d"), (3.5, 5.5, "3.5-5.5 d"), (5.5, 7.5, "5.5-7.5 d"), (7.5, 10.1, "7.5-10 d")]


def tool_samples(A, d, rng, m=199):
    """The api forecast path for each row (network, range map, shuffle by the nearest lead's templates, 50:50 ridge mixture) -> (n, m, 176)."""
    nh = _core.NH
    c = F.cond_matrix(d, int(A["modef_coarse"]))
    base = d["hres"].reshape(len(c), -1).astype(np.float64)
    out = np.empty((len(c), m, F.D), np.float32)
    for k in range(len(c)):
        res = A["modef"].sample(np.tile(c[k], (m, 1)), rng).reshape(1, m, -1)
        x = base[k][None, None, :] + res
        x[..., 3 * nh:4 * nh] = np.clip(x[..., 3 * nh:4 * nh], 0, 100)
        x = _core.calibrate(A["modef_calib"], x, clip=False)
        L = min(LEADS, key=lambda q: abs(q - float(d["lead_days"][k])))
        tpl = A["modef_tpl"][L]
        ranks = np.argsort(np.argsort(tpl[rng.integers(0, len(tpl), (1, m))], axis=1), axis=1)
        x = np.take_along_axis(np.sort(x, axis=1), ranks, axis=1)[0]
        x[:, 3 * nh:4 * nh] = np.clip(x[:, 3 * nh:4 * nh], 0, 100)
        if A.get("modef_ridge") is not None:
            r = A["modef_ridge"][L]
            b_in = np.where(np.isfinite(base[k]), base[k], r["mu"])
            pred = np.concatenate([(b_in - r["mu"]) / r["sd"], [1.0]]) @ r["W"]
            lin = pred[None, :] + r["res"][rng.integers(0, len(r["res"]), m)].astype(np.float64)
            lin[:, 3 * nh:4 * nh] = np.clip(lin[:, 3 * nh:4 * nh], 0, 100)
            use = rng.random(m) < 0.5
            x[use] = lin[use]
        out[k] = x
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=4000)
    ap.add_argument("--assets", default=None)
    ap.add_argument("--rows-dir", default="data/modeF_v2")
    ap.add_argument("--test-year", type=int, default=2022)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="docs/results/logs/fv2_eval.log")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    A = api._assets(a.assets)
    te = dict(np.load(f"{a.rows_dir}/{a.test_year}.npz"))
    i = np.sort(rng.choice(len(te["obs"]), min(a.rows, len(te["obs"])), replace=False))
    te = {k: v[i] for k, v in te.items()}
    tr = [dict(np.load(f"{a.rows_dir}/{y}.npz")) for y in range(2016, 2021)]
    tr = {k: np.concatenate([t[k] for t in tr]) for k in ("obs", "doy", "z_sfc", "valid_utc_hour")}
    truth = te["obs"].reshape(len(i), -1)
    x_tool = tool_samples(A, te, rng)
    tro = tr["obs"].reshape(len(tr["obs"]), -1)
    clim = np.empty_like(x_tool)
    for k in range(len(i)):
        dd = np.abs(((tr["doy"] - te["doy"][k] + 183) % 366) - 183)
        ok = np.flatnonzero((dd <= 20) & (np.abs(tr["z_sfc"] - te["z_sfc"][k]) < 250) & (tr["valid_utc_hour"] == te["valid_utc_hour"][k]))
        clim[k] = tro[rng.choice(ok if len(ok) > 30 else np.arange(len(tro)), 199)]
    raw = np.repeat(te["hres"].reshape(len(i), 1, -1), 2, 1)
    c_tool, c_clim, c_raw = (crps_ensemble(x, truth) for x in (x_tool, clim, raw))
    sh = np.round(F.solar_hour(te)).astype(int)
    lines = [f"F-V2 step 2: shipped forecast mode (assets {a.assets or 'default'}) on {len(i):,} rows of {a.test_year}, CRPS skill vs an hour-aware climatology (raw HRES in brackets); "
             f"mean over u, v, T, RH at 44 heights. The tool serves today: solar 14-20 h, leads 0.75-7.5 d."]
    hdr = "solar h | " + " | ".join(f"{b[2]:>18s}" for b in BINS)
    lines.append(hdr)
    for h in sorted(np.unique(sh)):
        cells = []
        for lo, hi, _ in BINS:
            k = (sh == h) & (te["lead_days"] >= lo) & (te["lead_days"] < hi)
            if k.sum() < 30:
                cells.append(f"{'n<30':>18s}")
                continue
            s_t = 1 - c_tool[k].mean() / c_clim[k].mean()
            s_r = 1 - c_raw[k].mean() / c_clim[k].mean()
            cells.append(f"{s_t:+.3f} ({s_r:+.3f}) n{int(k.sum()):4d}")
        lines.append(f"{h:7d} | " + " | ".join(cells))
    for v, name in enumerate(("u", "v", "T", "RH")):
        sl = slice(v * F.NH, (v + 1) * F.NH)
        per = []
        for h in sorted(np.unique(sh)):
            k = sh == h
            per.append(f"{h:02d} h {1 - c_tool[k][:, sl].mean() / c_clim[k][:, sl].mean():+.3f}")
        lines.append(f"  {name:2s} by solar hour, all leads: " + ", ".join(per))
    print("\n".join(lines), flush=True)
    with open(a.out, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n")


if __name__ == "__main__":
    main()
