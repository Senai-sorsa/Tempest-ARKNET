"""Audit 2026-11-14: confirm that the past-mode (mode P) network the tool SHIPS never saw the calibration (2021-23) or test (2024-25 and later) years.

    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/check_modep_years.py [--assets tempest_weather/assets] [--profiles data/pilot/profiles80.zarr] [--igra data/raw/igra]

1. Which checkpoint is shipped: the mode P weights inside <assets>/model.npz are compared with every models/modeP*.pt (exact match of all arrays).
2. Its training years: read from the checkpoint (train_years / val_years_range) when recorded. Older checkpoints (models/modeP.pt) do not record them, so they are
   RECOVERED: generator.train keeps the last `val_years` years of the rows it was given as early-stopping validation and stores each member's best validation loss.
   For every candidate last training year Y the script rebuilds those validation rows (balloon-ERA5 pairs of years Y - val_years + 1 .. Y, in the training order,
   the same random subset and the same validation noise seed) and recomputes the loss of the stored network. Only the true Y reproduces the stored loss (to float rounding);
   the training rows are then the pairs up to Y - val_years and nothing after Y was ever given to the network.
3. The other past-mode assets: range map (scripts/p4_modeP.py fits it on 2021-23), surface pool (years recorded in models/modeP_sfc_pool.npz), station map (fit_years).
Exit code 0 = no shipped past-mode part saw 2024 or later and the network saw nothing after 2020; 1 = a leak or an unresolved year; 2 = shipped weights not found.
Read-only: it writes nothing.
"""
import argparse
import glob
import json
import math
import os
import sys

import numpy as np
import torch

LAST_ALLOWED_NET = 2020        # protocol: train <= 2020 (validation inside it), calibrate 2021-23, test 2024-25
TEST_FROM = 2024


def shipped_match(assets):
    z = np.load(os.path.join(assets, "model.npz"), allow_pickle=False)
    meta = json.loads(str(z["modep_meta"]))
    found = []
    for path in sorted(glob.glob("models/modeP*.pt")):
        ck = torch.load(path, map_location="cpu", weights_only=True)
        mem = ck["members"] if "members" in ck else [ck]
        if len(mem) != meta["members"]:
            continue
        ok = True
        for k, m in enumerate(mem):
            for n, v in m["state"].items():
                key = f"modep_m{k}/{n}"
                if key not in z.files or z[key].shape != tuple(v.shape) or not np.array_equal(z[key], v.numpy().astype(np.float32)):
                    ok = False
                    break
            if not ok:
                break
        if ok:
            found.append((path, ck))
    return found


def member_val_loss(m, cond, target, years, last_year, device="cpu"):
    """Recompute generator.train's validation loss of one stored member for a training set whose last year is last_year."""
    from tempest.generator.model import afcrps, energy_score, make_generator
    cfg = m["cfg"]
    keep = np.flatnonzero(years <= last_year)
    yr = years[keep]
    val = np.flatnonzero(yr > yr.max() - cfg["val_years"])
    base_seed = int(cfg["seed"]) - int(m.get("_k", 0))
    rng = np.random.default_rng(base_seed)                         # train(): the first draw of rng is the validation subset
    va = keep[rng.choice(val, min(len(val), cfg["val_rows"]), replace=False)]
    nm = {k: v.double().numpy() for k, v in m["norm"].items()}
    vc = torch.from_numpy(((cond[va] - nm["cm"]) / nm["cs"]).astype(np.float32))
    vt = torch.from_numpy(((target[va].astype(np.float64) - nm["tm"]) / nm["ts"]).astype(np.float32))
    net = make_generator(cfg.get("arch", "mlp"), m["n_cond"], m["n_out"], cfg["noise_dim"], cfg["width"], cfg["depth"], linear_cols=m.get("linear_cols"), **m.get("model_kw", {}))
    net.load_state_dict(m["state"])
    net.eval()
    with torch.no_grad(), torch.random.fork_rng():
        torch.manual_seed(int(cfg["seed"]) + 12345)
        vb, tot = 8192, 0.0
        for i in range(0, len(vc), vb):
            s, y = net(vc[i:i + vb], cfg["m"]), vt[i:i + vb]
            tot += float(afcrps(s, y, cfg["crps_alpha"]) + cfg["es_weight"] * energy_score(s, y) / math.sqrt(y.shape[-1])) * len(y)
    return tot / len(vc), int(yr.max() - cfg["val_years"] + 1), int(len(va))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assets", default="tempest_weather/assets")
    ap.add_argument("--profiles", default="data/pilot/profiles80.zarr")
    ap.add_argument("--igra", default="data/raw/igra")
    ap.add_argument("--candidates", type=int, nargs="+", default=list(range(2017, 2026)), help="candidate last years of the rows the network was given")
    a = ap.parse_args()
    mf = json.load(open(os.path.join(a.assets, "manifest.json"), encoding="utf-8"))
    if not mf.get("modep_included"):
        print(f"{a.assets}: no past-mode network shipped; nothing to check")
        return 0
    found = shipped_match(a.assets)
    if not found:
        print(f"FAIL: the mode P weights in {a.assets}/model.npz match no models/modeP*.pt; cannot check its years")
        return 2
    path, ck = found[0]
    print(f"shipped mode P network = {path} (all {len(ck['members'] if 'members' in ck else [ck])} members' arrays identical)" + (f"; also identical: {[p for p, _ in found[1:]]}" if len(found) > 1 else ""))
    mem = ck["members"] if "members" in ck else [ck]
    for k, m in enumerate(mem):
        m["_k"] = k
    bad = []
    ty = mem[0].get("train_years")
    if ty is not None:
        vy = mem[0].get("val_years_range")
        last = max(ty[1], vy[1] if vy else ty[1])
        print(f"recorded: train {ty}, validation {vy}")
        if last > LAST_ALLOWED_NET:
            bad.append(f"network rows reach {last} (> {LAST_ALLOWED_NET})")
    else:
        print("training years NOT recorded in the checkpoint: recovering them from the stored validation losses (takes a few minutes)")
        from tempest.forecast import modeP as P
        d = P.load_pairs(a.profiles, a.igra, tendency="tend" in os.path.basename(path))
        post = bool(mem[0].get("cond_names")) and mem[0]["cond_names"][-1] == "post2022"
        cond, target, years = P.cond_matrix(d, post), P.residual(d), d["time"].year.to_numpy()
        print(f"{len(years):,} balloon-ERA5 pairs {years.min()}-{years.max()}")
        rows = []
        for Y in a.candidates:
            res = [member_val_loss(m, cond, target, years, Y) for m in mem]
            rel = max(abs(r[0] - float(m["val_loss"])) / float(m["val_loss"]) for r, m in zip(res, mem))
            rows.append((rel, Y))
            print(f"  last year {Y} (validation {res[0][1]}-{Y}, {res[0][2]:,} rows): recomputed {', '.join(f'{r[0]:.6f}' for r in res)} vs stored {', '.join(f'{float(m['val_loss']):.6f}' for m in mem)}  rel. diff {rel:.2e}")
        rows.sort()
        best_rel, best_Y = rows[0]
        second = rows[1][0] if len(rows) > 1 else float("inf")
        if best_rel < 1e-4 and second > 100 * max(best_rel, 1e-7):
            print(f"RECOVERED: the network was given pairs up to {best_Y} (validation {best_Y - mem[0]['cfg']['val_years'] + 1}-{best_Y}, training before)")
            if best_Y > LAST_ALLOWED_NET:
                bad.append(f"network rows reach {best_Y} (> {LAST_ALLOWED_NET})")
        else:
            bad.append(f"training years not resolved (best candidate {best_Y}, rel. diff {best_rel:.1e}, next {second:.1e}); the IGRA / ERA5 inputs may have changed since training")
    # the other shipped past-mode parts
    cal = np.load(path.rsplit(".", 1)[0] + ".calib.npz")
    print(f"range map {os.path.basename(path.rsplit('.', 1)[0])}.calib.npz: keys {cal.files} (scripts/p4_modeP.py fits it on 2021-23 00Z soundings; years not stored in the file)")
    if mf.get("modep_sfc_included") and os.path.exists("models/modeP_sfc_pool.npz"):
        sp = np.load("models/modeP_sfc_pool.npz", allow_pickle=False)
        z = np.load(os.path.join(a.assets, "model.npz"), allow_pickle=False)
        same = np.array_equal(z["modep_sfc/res"], sp["res"])
        print(f"surface pool: years {str(sp['years'])}, identical to the shipped one: {same}")
        if str(sp["years"]) != "<=2020" or not same:
            bad.append("surface pool years not <= 2020 or not the shipped pool")
    if mf.get("modep_sta_included"):
        sm = np.load("models/station_map_mix.npz", allow_pickle=True)
        fy = [int(x) for x in sm["fit_years"]]
        z = np.load(os.path.join(a.assets, "model.npz"), allow_pickle=False)
        cols = z["modep_sta/cols"]
        same = np.allclose(z["modep_sta/a"], sm["a"][:, 3][:, cols % 44]) and np.allclose(z["modep_sta/b"], sm["b"][:, 3][:, cols % 44])
        print(f"station map (RH columns {len(cols)}): models/station_map_mix.npz fit years {fy}, identical to the shipped tables: {same}")
        if fy[1] >= TEST_FROM or not same:
            bad.append(f"station map fitted up to {fy[1]} or not the shipped one")
    if bad:
        print("RESULT: FAIL -", "; ".join(bad))
        return 1
    print(f"RESULT: PASS - no shipped past-mode part saw {TEST_FROM} or later; the network saw nothing after {LAST_ALLOWED_NET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
