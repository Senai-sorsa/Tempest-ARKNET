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
    meta = dict(members=len(members), n_cond=m0["n_cond"], n_out=m0["n_out"], linear_cols=list(m0["linear_cols"]), noise_dim=c["noise_dim"], width=c["width"],
                depth=c["depth"], sp_offset=m0.get("sp_offset"), cond_names=list(m0.get("cond_names", [])), rh_target=m0.get("rh_target", "rh"))
    arrays[prefix + "meta"] = np.array(json.dumps(meta))
    for k, m in enumerate(members):
        for n, v in m["state"].items():
            arrays[f"{prefix}m{k}/{n}"] = v.numpy().astype(np.float32)
        for n, v in m["norm"].items():
            arrays[f"{prefix}norm{k}/{n}"] = v.numpy().astype(np.float32)
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--calib", required=True)
    ap.add_argument("--head")
    ap.add_argument("--gust")
    ap.add_argument("--modep", help="past-date residual network (models/modeP.pt); its range map is read from the same name with .calib.npz")
    ap.add_argument("--indices", default="data/raw/indices")
    ap.add_argument("--profiles", default="data/pilot/profiles80.zarr", help="for the grid points and their elevations")
    ap.add_argument("--out", default="tempest_weather/assets")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    arrays = {}
    meta = pack(torch.load(a.model, map_location="cpu", weights_only=True), "", arrays)
    cal = np.load(a.calib)
    for k in ("qz", "qu", "m", "fit_year"):
        if k in cal.files:
            arrays[f"calib/{k}"] = cal[k]
    if a.head:
        pack(torch.load(a.head, map_location="cpu", weights_only=True), "head_", arrays)
    if a.gust:
        g = np.load(a.gust)
        arrays["gust/theta"], arrays["gust/phi"] = g["wind_theta"], g["wind_phi"]
    if a.modep:
        pack(torch.load(a.modep, map_location="cpu", weights_only=True), "modep_", arrays)
        mc = np.load(a.modep.rsplit(".", 1)[0] + ".calib.npz")
        for k in mc.files:
            arrays[f"modep_calib/{k}"] = mc[k]
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
    manifest = dict(created=datetime.now(timezone.utc).isoformat(timespec="seconds"), area=dict(lat=[31.0, 34.0], lon=[-108.0, -101.0]),
                    trained_years="1991-2023 (validation 2021-23)", calibration_fit="2021-2023, m = 199", model_source=os.path.basename(a.model),
                    source_sha256=sha(a.model), calib_sha256=sha(a.calib), head_included=bool(a.head), modep_included=bool(a.modep), gust_included=bool(a.gust), features=meta["cond_names"],
                    humidity_target=meta["rh_target"], files={f: sha(os.path.join(a.out, f)) for f in files})
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    print(json.dumps(manifest, indent=1)[:1200])


if __name__ == "__main__":
    main()
