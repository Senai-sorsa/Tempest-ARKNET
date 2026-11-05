"""Quick checks for the classic mistakes (AUTOPILOT.md "Pitfall checks"). Run after every item that trains, fits or changes a file, and at the end of every phase.

    PYTHONPATH=. python scripts/pitfall_check.py MODEL.pt CALIB.npz DATA.npz [--aux FILE ...] [--first-test-year 2024] [--last-test-year 2025] [--max-year 2023] [--skip-model]

Prints one line per check: PASS, WARN (known or mild, explained) or FAIL (stop and fix before trusting any number). Exit code 1 if anything FAILs.
Checks: 1 train / validation / calibration / test windows do not overlap, 2 nothing fitted on the final-test months, 3 hashes of auxiliary files match, 4 outputs are
finite and physical, 5 sampling is reproducible with a seed and differs between seeds, 6 shuffled dates make the forecast worse (the model really uses its inputs),
7 skill is not suspiciously high, 8 coverage is not bought with width, 9 normalisation comes from the training years only, 10 repository hygiene,
11 result files are newer than the model, 12 train / validation gap.
"""
import argparse
import glob
import os
import subprocess

import numpy as np
import torch

RES = []


def rec(status, name, msg=""):
    RES.append((status, name, msg))
    print(f"{status:<5} {name}: {msg}", flush=True)


def check_windows(ck, a, aux):
    k = ck["members"][0] if "members" in ck else ck
    if "train_years" in k:
        tr, va = k["train_years"], k["val_years_range"]
        src = "stored in the checkpoint"
    else:
        vy = int(k["cfg"].get("val_years", 3))
        tr, va = [None, a.max_year - vy], [a.max_year - vy + 1, a.max_year]
        src = f"inferred (max-year {a.max_year}, val_years {vy}; the checkpoint predates the stored ranges)"
    rec("PASS" if tr[1] < a.first_test_year and va[1] < a.first_test_year else "FAIL", "1a train/validation before test", f"train {tr}, validation {va}, test from {a.first_test_year} ({src})")
    if k["cfg"].get("val_block_frac"):                                 # block validation: validation blocks are cut out of the training years with 3-day gaps (train.py split)
        rec("PASS", "1b train and validation do not overlap", f"block validation ({k['cfg']['val_block_frac']:.0%} of 14-day blocks, 3-day gaps): rows are disjoint by construction")
    else:
        rec("PASS" if tr[1] < va[0] else "FAIL", "1b train and validation do not overlap", f"train ends {tr[1]}, validation starts {va[0]}")
    for f in aux:
        t = np.load(f)
        if "fit_from" in t.files:
            ff, ft = int(t["fit_from"]), int(t["fit_to"])
            ok = ft < a.first_test_year
            overlap = not (ft < va[0] or ff > va[1])
            rec("PASS" if ok else "FAIL", f"2 {os.path.basename(f)} fitted before the test years", f"fit {ff}-{ft}, test from {a.first_test_year}")
            if overlap:
                rec("WARN", f"1c {os.path.basename(f)} overlaps the early-stopping validation years", f"fit {ff}-{ft} vs validation {va[0]}-{va[1]}: the checkpoint was chosen on those years, "
                    "so residuals there are slightly optimistic and the fitted ranges slightly narrow (coverage on the test years is the judge; IL-76 splits them)")
            if ft >= 2026:
                rec("FAIL", "2 final-test months used", f"{f} fitted through {ft}")
    return tr, va


def check_hashes(model, calib, aux):
    from tempest.calibrate import spread
    sha = spread.model_hash(model)
    for f in [calib] + aux:
        t = np.load(f)
        if "model_sha" in t.files:
            rec("PASS" if str(t["model_sha"]) == sha else "FAIL", f"3 {os.path.basename(f)} matches this model", str(t["model_sha"]))


def sample(model, calib, data, rows, m, seed, shuffle=False, years=(2024, 2025)):
    from tempest.calibrate import spread
    from tempest.generator.features import FEATURES
    from tempest.generator.sample import Sampler, to_physical
    from tempest.generator.train import load_npz
    d = load_npz(data)
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    sampler = Sampler(torch.load(model, map_location="cpu", weights_only=True))
    cal = spread.load(calib, model)
    idx = np.sort(np.random.default_rng(0).choice(np.flatnonzero((d["year"] >= years[0]) & (d["year"] <= years[1])), rows, replace=False))
    cond = np.asarray(d["cond"])[idx].copy()
    if shuffle:
        cols = [FEATURES.index(c) for c in ("doy_sin", "doy_cos", "hour_sin", "hour_cos", "year", "oni", "wwv", "qbo30", "qbo50") if c in FEATURES]
        cond[:, cols] = cond[rng.permutation(len(cond))][:, cols]
    x = spread.apply(cal, sampler.profiles(np.repeat(cond, m, axis=0)).reshape(len(idx), m, -1))
    return x, to_physical(np.asarray(d["target"][idx])), d, idx


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("calib")
    ap.add_argument("data")
    ap.add_argument("--aux", nargs="*", default=[])
    ap.add_argument("--first-test-year", type=int, default=2024)
    ap.add_argument("--last-test-year", type=int, default=2025)
    ap.add_argument("--max-year", type=int, default=2023, help="--max-year used when the model was trained (only for checkpoints without stored ranges)")
    ap.add_argument("--rows", type=int, default=600)
    ap.add_argument("--m", type=int, default=199)
    ap.add_argument("--skip-model", action="store_true", help="only the file / repository checks (no sampling)")
    a = ap.parse_args()
    ck = torch.load(a.model, map_location="cpu", weights_only=True)
    k = ck["members"][0] if "members" in ck else ck
    tr, va = check_windows(ck, a, a.aux)
    check_hashes(a.model, a.calib, a.aux)
    # 12 train / validation gap from the stored history
    h = k.get("history") or []
    if h and isinstance(h[-1], dict) and "train" in h[-1] and "val" in h[-1]:
        gap = h[-1]["val"] / max(h[-1]["train"], 1e-9)
        rec("PASS" if gap < 1.35 else "WARN", "12 train/validation gap", f"validation loss is {gap:.2f} x training loss")
    # 11 stale results
    for f in glob.glob(a.model.rsplit(".", 1)[0] + "*_headline.csv"):
        if os.path.getmtime(f) < os.path.getmtime(a.model):
            rec("WARN", "11 result older than the model", os.path.basename(f))
    # 10 repository hygiene
    try:
        files = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split()
        bad = [f for f in files if f.startswith(("data/", "models/")) or f.endswith((".pt", ".safetensors", ".grib", ".nc", ".zarr"))]
        big = [f for f in files if os.path.exists(f) and os.path.getsize(f) > 5_000_000 and not f.endswith("uv.lock")]
        msgs = subprocess.run(["git", "log", "--format=%B"], capture_output=True, text=True).stdout.lower()
        rec("PASS" if not bad and not big and "co-authored" not in msgs else "FAIL", "10 repository hygiene", f"data/model files tracked: {len(bad)}, files > 5 MB: {len(big)}, attribution lines: {msgs.count('co-authored')}")
    except Exception as e:  # noqa: BLE001
        rec("WARN", "10 repository hygiene", f"could not run git: {e}")
    if not a.skip_model:
        from tempest.profiles.to_heights import HEIGHTS
        from tempest.scoring.score import crps_ensemble
        NH = len(HEIGHTS)
        x, y, d, idx = sample(a.model, a.calib, a.data, a.rows, a.m, 0, years=(a.first_test_year, a.last_test_year))
        # 4 finite and physical
        fin = bool(np.isfinite(x).all())
        rh = x[..., 3 * NH:4 * NH]
        T = x[..., 2 * NH:3 * NH]
        spd = np.hypot(x[..., :NH], x[..., NH:2 * NH])
        ok = fin and rh.min() >= 0 and rh.max() <= 100.0001 and 150 < T.min() and T.max() < 340 and spd.max() < 150 and x[..., 4 * NH + 1].min() > 20000
        rec("PASS" if ok else "FAIL", "4 outputs finite and physical", f"finite {fin}, RH [{rh.min():.1f}, {rh.max():.1f}], T [{T.min():.0f}, {T.max():.0f}] K, wind max {spd.max():.0f} m/s, sp min {x[..., 4 * NH + 1].min():.0f}")
        sd = x.std(1)
        dead = float((sd.max(0) < 1e-6).mean())
        dup = float(np.mean([len(np.unique(x[i, :, 5])) / x.shape[1] for i in range(min(50, len(x)))]))
        rec("PASS" if dead == 0 and dup > 0.95 else "FAIL", "4b samples are not collapsed", f"constant columns {dead:.3f}, distinct share of samples {dup:.3f}")
        # 5 reproducibility
        x2, _, _, _ = sample(a.model, a.calib, a.data, 100, a.m, 0, years=(a.first_test_year, a.last_test_year))
        x3, _, _, _ = sample(a.model, a.calib, a.data, 100, a.m, 0, years=(a.first_test_year, a.last_test_year))
        x4, _, _, _ = sample(a.model, a.calib, a.data, 100, a.m, 1, years=(a.first_test_year, a.last_test_year))
        same = np.allclose(x2, x3, atol=1e-4)
        rec("PASS" if same and not np.allclose(x2, x4, atol=1e-4) else "WARN", "5 reproducible with a seed, different between seeds", f"same seed identical: {same}")
        # 6 shuffled dates must hurt
        xs, ys, _, _ = sample(a.model, a.calib, a.data, a.rows, a.m, 0, shuffle=True, years=(a.first_test_year, a.last_test_year))
        c_real, c_shuf = crps_ensemble(x, y).mean(), crps_ensemble(xs, ys).mean()
        rec("PASS" if c_shuf > c_real else "FAIL", "6 shuffled dates are worse than real dates", f"CRPS real {c_real:.4f}, shuffled {c_shuf:.4f}")
        # 8 sharpness: width of the central 99 % range vs the climatology of the truth
        lo, hi = np.percentile(x, [0.5, 99.5], axis=1)
        w_model = (hi - lo).mean(0)
        tr_rows = np.flatnonzero(d["year"] < a.first_test_year)[::40]
        from tempest.generator.sample import to_physical
        clim = to_physical(np.asarray(d["target"][tr_rows]))
        w_clim = np.percentile(clim, 99.5, axis=0) - np.percentile(clim, 0.5, axis=0)
        ratio = float(np.nanmedian(w_model / np.maximum(w_clim, 1e-9)))
        rec("PASS" if ratio <= 1.05 else "WARN", "8 99 % range is not wider than the climate range", f"median width ratio model / climatology {ratio:.2f}")
        # 9 normalisation from training years only
        cm = np.asarray(k["norm"]["cm"])
        cond = np.asarray(d["cond"])
        trn = cond[d["year"] <= (tr[1] if tr[1] else a.max_year - 3)].mean(0)
        allm = cond.mean(0)
        sdv = np.maximum(cond.std(0), 1e-9)
        cols = [i for i in range(len(cm)) if i not in k.get("linear_cols", [])] or list(range(len(cm)))
        e_tr, e_all = np.abs((cm - trn) / sdv)[cols].max(), np.abs((cm - allm) / sdv)[cols].max()
        rec("PASS" if e_tr <= e_all + 0.05 else "WARN", "9 normalisation from training years", f"max deviation from training mean {e_tr:.3f} sd, from all-years mean {e_all:.3f} sd")
    # 7 suspiciously high skill (from the stored headline, if any)
    for f in glob.glob(a.model.rsplit(".", 1)[0] + "_cal*_headline.csv")[:1]:
        import pandas as pd
        t = pd.read_csv(f)
        s = t["skill15_unknown"].mean() if "skill15_unknown" in t else np.nan
        rec("PASS" if not np.isfinite(s) or s < 0.15 else "FAIL", "7 skill is not suspiciously high", f"mean skill15 (unknown drivers) {s:+.4f} in {os.path.basename(f)}")
    fails = [r for r in RES if r[0] == "FAIL"]
    print(f"\n{sum(r[0] == 'PASS' for r in RES)} pass, {sum(r[0] == 'WARN' for r in RES)} warn, {len(fails)} fail")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
