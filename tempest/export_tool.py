"""Export trained models into tempest_weather/assets/ for the standalone tool (numpy only).

    python -m tempest.export_tool --model models/generator_80_p2f.pt --calib models/generator_80_p2f.calib2021.npz
                                  --head models/whead.pt --gust models/gust_model.npz --out tempest_weather/assets

Writes model.npz (generator weights, calibration, w-head weights, gust parameters), indices.npz (snapshot of the ONI / WWV / QBO / GMST tables) and
grid.npz (the 377 grid points and their elevations), manifest.json (sha256 of every file and of the source checkpoints, training and calibration years, area, creation time). The tool refuses assets whose
hashes disagree with the manifest. Assets are kept out of git.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone

import numpy as np
import torch

from tempest.ingest import indices


def sha(path):
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def pack(ckpt, prefix, arrays):
    members = ckpt["members"] if "members" in ckpt else [ckpt]
    m0 = members[0]
    c = m0["cfg"]
    # the numpy engine (tempest_weather/engine.py) runs only the plain MLP + linear slope; anything else would export silently wrong
    extra = [k for k, bad in (("model_kw", bool(m0.get("model_kw"))), ("arch", c.get("arch", "mlp") not in (None, "mlp")),
                              ("interactions", bool(c.get("interactions"))), ("product_pairs", bool(m0.get("product_pairs")))) if bad]
    if extra:
        raise SystemExit(f"{prefix or 'model'}: checkpoint uses {extra}, which the numpy engine does not implement; port them to tempest_weather/engine.py first")
    meta = dict(members=len(members), n_cond=m0["n_cond"], n_out=m0["n_out"], linear_cols=list(m0["linear_cols"]), noise_dim=c["noise_dim"], width=c["width"],
                depth=c["depth"], sp_offset=m0.get("sp_offset"), cond_names=list(m0.get("cond_names", [])), rh_target=m0.get("rh_target", "rh"))
    arrays[prefix + "meta"] = np.array(json.dumps(meta))
    for k, m in enumerate(members):
        for n, v in m["state"].items():
            arrays[f"{prefix}m{k}/{n}"] = v.numpy().astype(np.float32)
        for n, v in m["norm"].items():
            arrays[f"{prefix}norm{k}/{n}"] = v.numpy().astype(np.float32)
    return meta


def _has_post2022(path):
    """True if the mode P network in `path` was trained with the post-2022 indicator as its last input (F-11 part 2)."""
    if not path:
        return False
    k = torch.load(path, map_location="cpu", weights_only=True)
    k = k["members"][0] if "members" in k else k
    names = k.get("cond_names") or []
    return bool(names) and names[-1] == "post2022"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--calib", required=True)
    ap.add_argument("--head")
    ap.add_argument("--post-templates", help="IL-91/F-16: dataset npz; stores Schaake-shuffle dependence templates (month x 2-hour bin, 199 real training-year profiles each) in the assets")
    ap.add_argument("--post-cell", type=int, default=0, help="with --post-templates: one template set per block of N x N grid points (8 = 2 degrees; stored as uint8 ranks) instead of one for the whole box")
    ap.add_argument("--post-smap", help="IL-91/F-16: shear-space map npz (tempest.calibrate.shear_map output) to apply after the shuffle")
    ap.add_argument("--post-lmap", help="L21b / IL-162: lapse-rate quantile map npz (tempest.calibrate.lapse_map output, fitted on THIS model's stack) applied after the shear map; opt-in")
    ap.add_argument("--post-pit", help="PIT recalibration table npz (scripts/il86_fit.py output); loop 2 H1, opt-in, off by default")
    ap.add_argument("--post-pit-damp", type=float, default=0.5, help="strength of --post-pit (0.5 = the tested half-way map)")
    ap.add_argument("--post-seasonal", help="seasonal width factors npz (tempest.calibrate.seasonal output); not verified inside the stack, off unless asked")
    ap.add_argument("--modep-sta", help="F-11: station-correction map (models/station_map_mix.npz); with --modep, the columns where hybrid_use_network is False are served by the station correction instead of the network")
    ap.add_argument("--modep-sfc", help="F-12: surface residual pool for past dates (scripts/modeP_surface.py output); default off")
    ap.add_argument("--coherence", help="group C1: lag-correlation table (scripts/c1_fit_lagcorr.py output) for hourly coherence of sequences")
    ap.add_argument("--coherence-regimes", help="group C3: per-regime lag tables (scripts/c3_regime.py output); sequences then use the table of each trajectory's shear regime")
    ap.add_argument("--coherence-dist", help="group C2: distance-correlation table (scripts/c2_fit_distcorr.py output) for downrange coherence")
    ap.add_argument("--wcalib", help="F-27: range map for the w head (scripts/whead_calib.py output); default off")
    ap.add_argument("--gust")
    ap.add_argument("--modep", help="past-date residual network (models/modeP.pt); its range map is read from the same name with .calib.npz")
    ap.add_argument("--modef", help="forecast-conditioned network (models/modeF_v2.pt); range map from the same name with .calib.npz")
    ap.add_argument("--modef-bl", default="models/modeF_bl.npz", help="boundary-layer tables fitted with the forecast converter")
    ap.add_argument("--modef-rows", default="data/modeF", help="training rows (per-year npz) from which the error-profile templates of the Schaake shuffle are taken")
    ap.add_argument("--modef-ridge", action="store_true", help="IL-80: also store the per-lead ridge regression (and a pool of its residuals) so forecast mode can mix the network 50:50 with the ridge")
    ap.add_argument("--modef-coarse", type=int, default=4, help="every k-th height of the forecast profile is a network input")
    ap.add_argument("--indices", default="data/raw/indices")
    ap.add_argument("--profiles", default="data/pilot/profiles80.zarr", help="for the grid points and their elevations")
    ap.add_argument("--solar-hours", default="6-21", help="solar-hour window the model was trained on (manifest solar_hours; the tool refuses hours outside it). 0-24 = all hours (l3_h_all24)")
    ap.add_argument("--out", default="tempest_weather/assets")
    a = ap.parse_args()
    solar_hours = [float(x) for x in a.solar_hours.split("-")]
    assert len(solar_hours) == 2 and 0 <= solar_hours[0] < solar_hours[1] <= 24, "--solar-hours is LO-HI within 0-24"
    os.makedirs(a.out, exist_ok=True)
    arrays = {}
    meta = pack(torch.load(a.model, map_location="cpu", weights_only=True), "", arrays)
    cal = np.load(a.calib)
    for k in ("qz", "qu", "m", "fit_year"):
        if k in cal.files:
            arrays[f"calib/{k}"] = cal[k]
    if a.head:
        pack(torch.load(a.head, map_location="cpu", weights_only=True), "head_", arrays)
    post = bool(a.post_templates or a.post_smap or a.post_seasonal or a.post_pit or a.post_lmap)
    if a.post_templates:
        from tempest.calibrate.shuffle import cell_keys
        from tempest.generator.sample import to_physical
        from tempest.generator.train import load_npz
        from tempest.scoring.score import group_keys
        dd = load_npz(a.post_templates)
        k_all, yr = group_keys(np.asarray(dd["cond"])), np.asarray(dd["year"])
        from tempest.calibrate.shuffle import grid_n_lon
        n_lon = grid_n_lon(dd["cond"])
        assert n_lon > 0 or not a.post_cell, "--post-cell needs a full regular grid in --post-templates"
        keys = cell_keys(k_all, a.post_cell, n_lon=n_lon) if a.post_cell else k_all % 144
        ukeys = np.unique(keys[yr < 2021])
        rng_t = np.random.default_rng(0)
        first_test = 2021                                                          # templates from training years only (<= 2020)
        tr = np.flatnonzero(yr < first_test)
        if a.post_cell:
            cells = np.unique(ukeys // 144)
            ncol = -(-n_lon // a.post_cell)
            lat_i, lon_i = cells // 100, cells % 100
            cid = lat_i * ncol + lon_i
            tpl = np.zeros((int(cid.max()) + 1, 144, 199, 179), np.uint8)
            for c, k0 in zip(cid, cells):
                for b in range(144):
                    r = tr[keys[tr] == k0 * 144 + b]
                    if len(r):
                        pick = np.sort(rng_t.choice(r, 199, replace=len(r) < 199))
                        x_ = to_physical(np.asarray(dd["target"][pick]))
                        tpl[c, b] = np.argsort(np.argsort(x_, axis=0), axis=0).astype(np.uint8)
            arrays["post/rank"] = tpl
            arrays["post/cell"] = np.array(a.post_cell)
        else:
            tpl = np.zeros((144, 199, 179), np.float16)
            for k in range(144):
                r = tr[keys[tr] == k]
                if len(r):
                    pick = np.sort(rng_t.choice(r, 199, replace=len(r) < 199))
                    tpl[k] = to_physical(np.asarray(dd["target"][pick])).astype(np.float16)
            arrays["post/tpl"] = tpl
    if a.post_smap:
        sm = np.load(a.post_smap)
        arrays["post/smap_grid"], arrays["post/smap_gain"] = sm["grid"], sm["gain"]
        assert "edges" not in sm.files, "7-group maps need an edges asset (not exported yet)"
    if a.post_lmap:
        lm = np.load(a.post_lmap)
        arrays["post/lmap_xk"], arrays["post/lmap_yk"] = lm["xk"], lm["yk"]
    if a.post_pit:
        pt = np.load(a.post_pit)
        arrays["post/pit_ginv"], arrays["post/pit_groups"], arrays["post/pit_damp"] = pt["ginv"], pt["groups"], np.array(a.post_pit_damp)
    if a.post_seasonal:
        arrays["post/seasonal"] = np.load(a.post_seasonal)["scale"]
    if a.modep_sta:
        use = np.load(a.modep.rsplit(".", 1)[0] + ".hybrid_use_network.npy")
        cols = np.flatnonzero(~use)
        sm = np.load(a.modep_sta, allow_pickle=True)
        nh_ = 44
        v_, h_ = cols // nh_, cols % nh_
        assert (v_ == 3).all(), "export of the station-correction columns is written for the RH block only (the hybrid choice picked other variables)"
        arrays["modep_sta/cols"] = cols.astype(np.int32)
        arrays["modep_sta/a"], arrays["modep_sta/b"] = sm["a"][:, 3][:, h_], sm["b"][:, 3][:, h_]
        arrays["modep_sta/pool"] = sm["pool"][:, :, :, 3][..., h_].astype(np.float16)
        arrays["modep_sta/n"], arrays["modep_sta/cuts"] = sm["n"], sm["cuts"]
    if a.modep_sfc:
        sp_ = np.load(a.modep_sfc)
        arrays["modep_sfc/res"], arrays["modep_sfc/key"] = sp_["res"], sp_["key"]
    if a.coherence:
        ch = np.load(a.coherence)
        arrays["coherence/rho"] = ch["rho"]
        if "kappa" in ch.files:
            arrays["coherence/kappa"] = ch["kappa"]
    if a.coherence_regimes:
        cr = np.load(a.coherence_regimes)
        arrays["coherence/rho_regime"], arrays["coherence/shear_edges"] = cr["lag"], cr["shear_edges"]
    if a.coherence_dist:
        cd = np.load(a.coherence_dist)
        arrays["coherence_dist/rho"], arrays["coherence_dist/km"] = cd["rho"], cd["km"]
    if a.wcalib:
        wc = np.load(a.wcalib)
        for k in ("qz", "qu", "m"):
            arrays[f"wcalib/{k}"] = wc[k]
    if a.gust:
        g = np.load(a.gust)
        arrays["gust/theta"], arrays["gust/phi"] = g["wind_theta"], g["wind_phi"]
    if a.modep:
        pack(torch.load(a.modep, map_location="cpu", weights_only=True), "modep_", arrays)
        mc = np.load(a.modep.rsplit(".", 1)[0] + ".calib.npz")
        for k in mc.files:
            arrays[f"modep_calib/{k}"] = mc[k]
    if a.modef:
        pack(torch.load(a.modef, map_location="cpu", weights_only=True), "modef_", arrays)
        mc = np.load(a.modef.rsplit(".", 1)[0] + ".calib.npz")
        for k in mc.files:
            arrays[f"modef_calib/{k}"] = mc[k]
        bl = np.load(a.modef_bl)
        for k in bl.files:
            arrays[f"modef_bl/{k}"] = bl[k]
        arrays["modef/coarse"] = np.array(a.modef_coarse)
        rows = [np.load(os.path.join(a.modef_rows, f"{y}.npz")) for y in range(2016, 2021)]       # training years only
        lead = np.concatenate([r["lead_days"] for r in rows])
        err = np.concatenate([(r["obs"] - r["hres"]).reshape(len(r["obs"]), -1) for r in rows])
        rng = np.random.default_rng(0)
        for L in (1, 3, 5, 7):
            idx = rng.choice(np.flatnonzero(lead == L), 1500, replace=False)
            arrays[f"modef_tpl/L{L}"] = err[idx].astype(np.float16)                                  # real forecast-error profiles: the dependence template of the shuffle
        if a.modef_ridge:
            h_all = np.concatenate([r["hres"].reshape(len(r["obs"]), -1) for r in rows]).astype(np.float64)
            o_all = np.concatenate([r["obs"].reshape(len(r["obs"]), -1) for r in rows]).astype(np.float64)
            for L in (1, 3, 5, 7):
                k = lead == L
                mu, sd = h_all[k].mean(0), h_all[k].std(0) + 1e-6
                Z = np.concatenate([(h_all[k] - mu) / sd, np.ones((k.sum(), 1))], 1)
                W = np.linalg.solve(Z.T @ Z + 200.0 * np.eye(Z.shape[1]), Z.T @ o_all[k])                 # same ridge as scripts/il6_modeF.py (lambda 200)
                res = o_all[k] - Z @ W
                pick = rng.choice(len(res), min(3000, len(res)), replace=False)
                arrays[f"modef_ridge/L{L}/mu"], arrays[f"modef_ridge/L{L}/sd"], arrays[f"modef_ridge/L{L}/W"] = mu.astype(np.float32), sd.astype(np.float32), W.astype(np.float32)
                arrays[f"modef_ridge/L{L}/res"] = res[pick].astype(np.float16)
    np.savez(os.path.join(a.out, "model.npz"), **arrays)
    tab = indices.load(a.indices).dropna(subset=["oni", "qbo30", "qbo50", "wwv"])
    gm = indices.gmst_table(a.indices)
    months = np.array([t.year * 100 + t.month for t in tab.index])
    gm_months = np.array([t.year * 100 + t.month for t in gm.index])
    np.savez(os.path.join(a.out, "indices.npz"), months=months, oni=tab["oni"].to_numpy(), wwv=tab["wwv"].to_numpy(), qbo30=tab["qbo30"].to_numpy(),
             qbo50=tab["qbo50"].to_numpy(), gmst_months=gm_months, gmst=gm.to_numpy())
    import xarray as xr
    ds = xr.open_zarr(a.profiles)
    np.savez(os.path.join(a.out, "grid.npz"), lat=ds.lat.values.astype(np.float32), lon=ds.lon.values.astype(np.float32), elev=ds.z_sfc.values.astype(np.float32))
    files = ["model.npz", "indices.npz", "grid.npz"]
    manifest = dict(created=datetime.now(timezone.utc).isoformat(timespec="seconds"), area=dict(lat=[float(ds.lat.min()), float(ds.lat.max())], lon=[float(ds.lon.min()), float(ds.lon.max())]),
                    trained_years="1991-2023 (validation 2021-23)", calibration_fit="2021-2023, m = 199", model_source=os.path.basename(a.model),
                    source_sha256=sha(a.model), calib_sha256=sha(a.calib), head_included=bool(a.head), wcalib_included=bool(a.wcalib), post_included=post, modep_sfc_included=bool(a.modep_sfc), modep_sta_included=bool(a.modep_sta), coherence_included=bool(a.coherence), coherence_dist_included=bool(a.coherence_dist), modep_post2022=_has_post2022(a.modep), modef_ridge_included=bool(a.modef and a.modef_ridge), modep_included=bool(a.modep), modef_included=bool(a.modef), gust_included=bool(a.gust), features=meta["cond_names"],
                    humidity_target=meta["rh_target"], solar_hours=solar_hours, files={f: sha(os.path.join(a.out, f)) for f in files})
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    print(json.dumps(manifest, indent=1)[:1200])


if __name__ == "__main__":
    main()
