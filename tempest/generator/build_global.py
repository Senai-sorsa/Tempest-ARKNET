"""G3 / G4 training file from the global store (data/raw/era5_global), in the build_dataset layout.

    python -m tempest.generator.build_global --out data/train/g3_na.npz --box 15 75 -170 -50 --nside 32 \
        --hold-igra 0.3 --rows 4000000 --features base --rh-target dpd --statics --ztrop models/global/tropo_clim.npz \
        --group point [--last-year 2025]
    python -m tempest.generator.build_global --out data/train/g4_global.npz --rows 12000000 --rh-target dpd --statics \
        --ztrop models/global/tropo_clim.npz --group koppen --koppen models/global/koppen.npz

Rows: every (store point, day) of the chosen points (one UTC hour per day, cycling, so all local hours occur), kept at
random so the total is about --rows. Targets are plain ERA5 (the global balloon correction is a separate G4 step).
Columns: the active base / p2 features, plus with --statics oro_m sdor slor anor lsm coast_km tpi_m, plus with --ztrop
the climatological tropopause height ztrop_clim. elev_site = elev_grid = oro_m (grid point rows).
Sidecar (always): row_point (store index), row_time, row_group (--group: point / koppen / continent / igra_held),
held_igra (store indices left out with --hold-igra, for the unseen-station gate).
Eval file of the held (or seen) IGRA sites of a training file: --points-from data/train/g3_na.npz --which held --first-year 2024.
"""
import argparse
import os

import numpy as np
import pandas as pd

from tempest.generator import features as feat
from tempest.generator.build_dataset import SURFACE, target_names
from tempest.generator.features import FEATURES, features
from tempest.generator.sample import dpd_from_rh
from tempest.geo import global_store as gs
from tempest.geo import points as gp
from tempest.ingest import indices
from tempest.profiles.diff import from_diff, to_diff
from tempest.profiles.to_heights import HEIGHTS, PROFILE, fill_top, top_valid

STATICS = ["oro_m", "sdor", "slor", "anor", "lsm", "coast_km", "tpi_m"]


def targets(prof, rh2m, t2m, sp, rh_target="dpd"):
    """Profiles {u, v, T, RH} (n, 44), surface (n,) -> (n, 179) targets and (n, 4) top index (build_dataset layout,
    top heights above the store's 50 hPa top filled from the highest valid height, as build_dataset --fill-top)."""
    tops = np.stack([top_valid(prof[v]) for v in PROFILE], 1)
    diffs = np.stack([to_diff(fill_top(prof[v])) for v in PROFILE], 1)
    sfc = [t2m[:, None], sp[:, None], rh2m[:, None]]
    if rh_target == "dpd":
        lev = from_diff(diffs)
        i_t, i_rh = PROFILE.index("T"), PROFILE.index("RH")
        lev[:, i_rh] = dpd_from_rh(lev[:, i_t].astype(np.float64), lev[:, i_rh].astype(np.float64))
        diffs = to_diff(lev)
        sfc[2] = dpd_from_rh(t2m[:, None].astype(np.float64), rh2m[:, None].astype(np.float64))
    return np.concatenate([diffs.reshape(len(t2m), -1)] + sfc, 1).astype(np.float32), tops.astype(np.int8)


def choose_points(pts, box=None, nside=0, hold_igra=0.0, seed=0):
    idx = gp.select(pts, box)
    if nside:
        idx = gp.thin(pts, idx, nside)
    held = gp.igra_holdout(pts, idx, hold_igra, seed) if hold_igra else np.array([], int)
    return np.setdiff1d(idx, held), held


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--store", default=gs.STORE)
    ap.add_argument("--indices", default="data/raw/indices")
    ap.add_argument("--box", type=float, nargs=4, metavar=("LAT0", "LAT1", "LON0", "LON1"))
    ap.add_argument("--nside", type=int, default=0, help="thin to one non-IGRA point per equal-area cell of this HEALPix nside (0 = all)")
    ap.add_argument("--hold-igra", type=float, default=0.0, help="share of IGRA sites left out entirely (G3 unseen-station gate)")
    ap.add_argument("--rows", type=int, default=4_000_000)
    ap.add_argument("--first-year", type=int, default=1991)
    ap.add_argument("--last-year", type=int, default=2025)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--features", choices=["base", "p2"], default="base")
    ap.add_argument("--rh-target", choices=["rh", "dpd"], default="dpd")
    ap.add_argument("--statics", action="store_true")
    ap.add_argument("--ztrop", help="tropopause climatology from tempest.geo.tropo_clim fit")
    ap.add_argument("--group", choices=["none", "point", "koppen", "continent"], default="point")
    ap.add_argument("--koppen", help="Koppen table from tempest.geo.koppen (needed for --group koppen)")
    ap.add_argument("--points-from", help="eval file on the stations of another build_global file (replaces --box / --nside / --hold-igra)")
    ap.add_argument("--which", choices=["held", "seen"], default="held", help="with --points-from: its held_igra sites, or the IGRA sites it trained on")
    a = ap.parse_args(argv)
    if a.last_year > 2025:
        raise SystemExit("G stages never read 2026 (docs/global/README.md holdout rules)")
    if a.group == "koppen" and not a.koppen:
        ap.error("--group koppen needs --koppen")
    feat.set_active(feat.P2_FEATURES if a.features == "p2" else feat.BASE_FEATURES)
    names = list(FEATURES) + (STATICS if a.statics else []) + (["ztrop_clim"] if a.ztrop else [])
    feat.set_active(names)

    pts = gs.points(a.store)
    if a.points_from:                                                              # G3 unseen-station gate: held vs seen IGRA sites
        src = np.load(a.points_from)
        idx = np.sort(src["held_igra"]) if a.which == "held" else np.unique(src["row_point"])
        idx, held = (idx if a.which == "held" else idx[gp.is_igra(pts["igra"][idx])]).astype(int), np.array([], int)
        if not len(idx):
            raise SystemExit(f"--points-from {a.points_from}: no {a.which} IGRA sites")
    else:
        idx, held = choose_points(pts, tuple(a.box) if a.box else None, a.nside, a.hold_igra, a.seed)
    lat, lon = pts["lat"][idx], pts["lon"][idx]
    from tempest.geo.statics import statics
    st = statics(lat, lon)
    grp = {"none": np.zeros(len(idx), np.int16), "point": np.arange(len(idx), dtype=np.int32)}.get(a.group)
    if a.group == "koppen":
        from tempest.geo import koppen
        grp = koppen.lookup(dict(np.load(a.koppen)), lat, lon).astype(np.int16)
    elif a.group == "continent":
        from tempest.scoring.spatial import continent
        grp = continent(lat, lon, st["lsm"] > 0.5).astype(np.int16)
    tab = dict(np.load(a.ztrop)) if a.ztrop else None
    tbl = indices.load(a.indices)
    gm = indices.gmst_table(a.indices) if a.features == "p2" else None

    months = gs.months(a.first_year, a.last_year, a.store)
    if not len(months) or not len(idx):
        raise SystemExit(f"no rows: {len(months)} store months in {a.first_year}-{a.last_year}, {len(idx)} points (check --store / years / --box)")
    frac = min(1.0, a.rows / (len(idx) * 30.44 * len(months)))
    rng = np.random.default_rng(a.seed)
    print(f"{len(idx):,} points ({len(held)} IGRA sites held out), {len(months)} months, keep share {frac:.4f}", flush=True)
    parts = []
    for name in months:
        m = gs.month(name, a.store)
        t, p = np.nonzero(rng.random((len(m["valid_time"]), len(idx))) < frac)
        if not len(t):
            continue
        pr, rh2m = gs.profiles(m, pts, idx, oro_m=st["oro_m"])
        tgt, tops = targets({k: v[t, p] for k, v in pr.items()}, rh2m[t, p], m["t2m"][t, idx[p]], m["sp"][t, idx[p]], a.rh_target)
        tt = pd.DatetimeIndex(m["valid_time"][t])
        sh = (tt.hour.to_numpy() + lon[p] / 15.0) % 24
        oni, qbo30, qbo50, wwv = indices.at(tbl, tt).T
        extra = {k: st[k][p] for k in STATICS} if a.statics else {}
        if tab is not None:
            from tempest.geo.tropo_clim import lookup
            extra["ztrop_clim"] = lookup(tab, lat[p], lon[p], tt.month.to_numpy())
        cond = features(lat[p], lon[p], st["oro_m"][p], st["oro_m"][p], tt.dayofyear.to_numpy(), sh, tt.year.to_numpy(),
                        oni, wwv, qbo30, qbo50, **indices.feature_extras(FEATURES, tbl, gm, tt), **extra)
        parts.append(dict(cond=cond, target=tgt, year=tt.year.to_numpy().astype(np.int16), fill_top_idx=tops,
                          row_point=idx[p].astype(np.int32), row_time=tt.to_numpy().astype("datetime64[h]"), row_group=grp[p]))
        print(f"{name}: {sum(len(q['year']) for q in parts):,} rows", flush=True)
    if not parts:
        raise SystemExit(f"no rows: no store month in {a.first_year}-{a.last_year} gave a sample (check the store, the years and --rows)")
    out = {k: np.concatenate([q[k] for q in parts]) for k in parts[0]}
    ok = np.isfinite(out["target"]).all(1) & np.isfinite(out["cond"]).all(1)
    print(f"dropping {(~ok).sum():,} rows with missing values", flush=True)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "wb") as fh:
        np.savez(fh, **{k: v[ok] for k, v in out.items()}, cond_names=np.array(names), target_names=np.array(target_names()),
                 rh_target=np.array(a.rh_target), held_igra=held.astype(np.int32), group_kind=np.array(a.group),
                 correction=np.array("none (plain ERA5, global store)"))
    print(f"wrote {a.out}: {ok.sum():,} rows, {len(names)} inputs, {out['target'].shape[1]} targets", flush=True)


if __name__ == "__main__":
    main()
