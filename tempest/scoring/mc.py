"""Monte Carlo checks of GLOBAL_PLAN §9 on one scored set (score.py --mc writes <stem>_mc.csv).

Every member is judged as a whole column, the way a Monte Carlo user consumes it:
  phys     (§9.1) per-member violation rates (superadiabatic layer above 200 m, shear beyond ERA5's 99.99th percentile,
           surface-to-10 m jump beyond ERA5's 99.9th percentile) next to the same rate in the ERA5 truth rows
  es       (§9.2) energy score of the whole standardised column, skill vs recent climatology, per season x day/night
  derived  (§9.2) CRPS skill and 90/99 % coverage of bulk shear 0-6 km, max wind and its height, the strongest
           inversion step below 3 km, and the cold-point (tropopause proxy) height and T
  blend    (§9.3) skill per band when a share w of the members is swapped for climatology members
  filled   (§9.7) T skill/coverage at heights the fill-top step filled (isothermal copies) vs real heights
  terrain  (§9.8) 99 % coverage per variable x band x ground-elevation class
shortcut: no hypsometric check (the profile has fixed AGL heights and no pressure per level); add it when the
targets carry pressure. Regimes come from inputs (season, day/night), never from the truth, so coverage stays fair.
"""
import numpy as np
import pandas as pd

from tempest.scoring import diag
from tempest.profiles.to_heights import HEIGHTS, PROFILE

N = len(HEIGHTS)
IU, IV, IT = (PROFILE.index(k) * N for k in ("u", "v", "T"))
DZ = np.diff(HEIGHTS) / 1000.0


def _crps(x, y):  # same exact formula as score.crps_ensemble (not imported: score imports this module)
    x = np.sort(x, axis=1)
    m = x.shape[1]
    i = np.arange(1, m + 1)[None, :, None]
    return 2 / m ** 2 * ((x - y[:, None]) * (m * (y[:, None] < x) - i + 0.5)).sum(1)


def _cov(x, y, p):
    m = x.shape[1]
    k = max(1, int(round((1 - p) / 2 * (m + 1))))
    s = np.partition(x, [k - 1, m - k], axis=1)
    return (y >= s[:, k - 1]) & (y <= s[:, m - k])


def derived(p):
    """(..., 179) physical -> (..., 6): bulk shear 0-6 km, max wind, its height, inversion step < 3 km, cold-point height, cold-point T."""
    u, v, T = p[..., IU:IU + N], p[..., IV:IV + N], p[..., IT:IT + N]
    k6 = int(np.argmin(np.abs(HEIGHTS - 6000)))
    spd = np.hypot(u, v)
    up = HEIGHTS > 8000
    cold = np.argmin(T[..., up], -1)
    return np.stack([np.hypot(u[..., k6] - u[..., 0], v[..., k6] - v[..., 0]), spd.max(-1), HEIGHTS[spd.argmax(-1)],
                     np.diff(T, axis=-1)[..., HEIGHTS[1:] <= 3000].max(-1), HEIGHTS[up][cold],
                     np.take_along_axis(T[..., up], cold[..., None], -1)[..., 0]], -1)


DERIVED = ["bulk_shear_0_6km", "max_wind", "max_wind_height", "inversion_step_lt3km", "coldpoint_height", "coldpoint_T"]


def violations(p, thr):
    """(..., 179) -> dict of boolean (...) per check; thr from the truth rows (shear 99.99 %, sfc jump 99.9 %)."""
    T, u, v = p[..., IT:IT + N], p[..., IU:IU + N], p[..., IV:IV + N]
    lapse = -np.diff(T, axis=-1) / DZ
    sup = ((lapse - 9.8) * DZ)[..., HEIGHTS[1:] > 200]           # K of excess over dry-adiabatic per layer
    shear = np.hypot(np.diff(u, axis=-1), np.diff(v, axis=-1)) / DZ
    sfc = np.abs(p[..., 4 * N] - T[..., 0])                        # t2m vs T at 10 m
    return dict(superadiabatic_gt1K=sup.max(-1) > 1.0, shear_gt_era5_9999=(shear > thr["shear"]).any(-1),
                sfc_jump_gt_era5_999=sfc > thr["sfc"])


def energy(x, y, sd, m=50):
    """Energy score of whole standardised columns, (N,) per row; first m members (pairs cost m^2)."""
    xs, ys = x[:, :m] / sd, y / sd
    fit = np.linalg.norm(xs - ys[:, None], axis=-1).mean(1)
    spread = np.stack([np.linalg.norm(xs[:, i, None] - xs[:, i + 1:], axis=-1).sum(1) for i in range(m - 1)], 1).sum(1)
    return fit - spread / (m * (m - 1) / 2) / 2


def write(stem, x, clim15, truth, cond, names, band_masks, w_list=(0.25, 0.5)):
    """x, clim15 (N, m, 179) physical samples; truth (N, 179); cond (N, F) raw inputs; names = feature names."""
    rows = []
    add = lambda check, group, metric, model, ref: rows.append(dict(check=check, group=group, metric=metric, model=float(model), ref=float(ref)))
    T, u, v = truth[:, IT:IT + N], truth[:, IU:IU + N], truth[:, IV:IV + N]
    thr = dict(shear=np.quantile(np.hypot(np.diff(u, axis=-1), np.diff(v, axis=-1)) / DZ, 0.9999, axis=0),
               sfc=np.quantile(np.abs(truth[:, 4 * N] - T[:, 0]), 0.999))
    for name, q in (("shear_9999", 0.9999), ("sfc_jump_999", 0.999)):    # IL-110: what stands behind each tail threshold
        sup = diag.tail_support(len(truth), q)
        add("tail", "all", f"{name}_expected_exceedances_per_column", sup["expected_per_column"], 10.0)   # ref = the minimum we want (10)
    vm, vt = violations(x, thr), violations(truth, thr)
    for k in vm:  # ref = ERA5's own rate (the shear/sfc ones are ~1e-4/1e-3 by construction)
        add("phys", "all", k, vm[k].mean(), vt[k].mean())

    c = {k: cond[:, names.index(k)] for k in ("doy_sin", "doy_cos", "hour_sin", "hour_cos")}
    mon = (np.arctan2(c["doy_sin"], c["doy_cos"]) % (2 * np.pi) / (2 * np.pi) * 12).astype(int) % 12
    season = np.array(["DJF", "MAM", "JJA", "SON"])[((mon + 1) % 12) // 3]
    hour = np.arctan2(c["hour_sin"], c["hour_cos"]) % (2 * np.pi) / (2 * np.pi) * 24
    regime = np.char.add(season, np.where((hour >= 9) & (hour < 18), "_day", "_night"))
    sd = np.where(truth.std(0) > 1e-6, truth.std(0), 1.0)
    es_x, es_c = energy(x, truth, sd), energy(clim15, truth, sd)
    for g in ["all"] + sorted(set(regime)):
        s = slice(None) if g == "all" else regime == g
        add("es", g, "es_skill_vs_clim15", 1 - es_x[s].mean() / es_c[s].mean(), 0.0)

    dx, dc, dt = derived(x), derived(clim15), derived(truth)
    cx, cc = _crps(dx, dt).mean(0), _crps(dc, dt).mean(0)
    for j, k in enumerate(DERIVED):
        add("derived", k, "crps_skill_vs_clim15", 1 - cx[j] / cc[j], 0.0)
        for p in (0.9, 0.99):
            add("derived", k, f"cov{int(p * 100)}", _cov(dx[..., j], dt[:, j], p).mean(), _cov(dc[..., j], dt[:, j], p).mean())

    cr_c = _crps(clim15, truth).mean(0)
    for w in (0.0,) + tuple(w_list):
        k = int(round(w * x.shape[1]))
        mix = np.concatenate([clim15[:, :k], x[:, k:]], 1)
        cr = _crps(mix, truth).mean(0)
        for var, band, sel in band_masks:
            add("blend", f"{var} {band}", f"skill_w{w:g}", 1 - cr[sel].mean() / cr_c[sel].mean(), 0.0)

    # filled heights (fill-top build: above the 50 hPa top, ~20.5 km MSL, copies of the highest valid height). Found by
    # MSL height, not by exact copies: build_dataset's station correction runs after fill_top, so the copies are not equal.
    # shortcut: fixed 50 hPa height (it moves ~+-0.4 km with season); the 19.5-20.5 km MSL band is left out as ambiguous.
    msl = cond[:, names.index("elev_grid")][:, None] + HEIGHTS[None]
    filled, real = msl > 20500, (HEIGHTS >= 12000)[None] & (msl < 19500)
    if filled.sum() >= 200:
        cT = _crps(x[..., IT:IT + N], T)
        cTc = _crps(clim15[..., IT:IT + N], T)
        cv = _cov(x[..., IT:IT + N], T, 0.99)
        for g, msk in (("filled", filled), ("real_12_18km", real)):
            add("filled", g, "T_crps_skill_vs_clim15", 1 - cT[msk].mean() / cTc[msk].mean(), msk.mean())
            add("filled", g, "T_cov99", cv[msk].mean(), 0.99)

    elev = cond[:, names.index("elev_grid")]
    cls = np.digitize(elev, [1500, 2500])
    cov = _cov(x, truth, 0.99)
    for ci, lab in enumerate(["ground_lt1500m", "ground_1500_2500m", "ground_gt2500m"]):
        r = cls == ci
        if r.sum() < 200:
            continue
        for var, band, sel in band_masks:
            add("terrain", f"{lab} {var} {band}", "cov99", cov[r][:, sel].mean(), 0.99)

    out = pd.DataFrame(rows)
    out.to_csv(stem + "_mc.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_rows", 400, "display.float_format", "{:.4f}".format):
        print("\nMONTE CARLO CHECKS (GLOBAL_PLAN §9):")
        print(out[out.check.isin(["phys", "es", "derived", "filled"])].to_string(index=False))
    print(f"wrote {stem}_mc.csv")
    return out


# self-check: a perfect ensemble (members drawn like the truth) scores ~0 skill and ~nominal coverage; a fill-top run is found
if __name__ == "__main__":
    rng = np.random.default_rng(0)
    base = np.zeros(4 * N + 3)
    base[IT:IT + N] = 300 - 6.5 * HEIGHTS / 1000
    base[4 * N] = base[IT]
    draw = lambda *s: base + rng.normal(0, 1, (*s, 4 * N + 3)).cumsum(-1) * 0.1
    tr, xs, cl = draw(400), draw(400, 99), draw(400, 99)
    names = ["doy_sin", "doy_cos", "hour_sin", "hour_cos", "elev_grid"]
    cond = np.c_[rng.normal(size=(400, 4)), np.r_[np.full(200, 1000.0), np.full(200, 3000.0)]]  # half over high ground: top height filled
    masks = [("T", "0-18 km", np.r_[np.zeros(IT, bool), np.ones(N, bool), np.zeros(N + 3, bool)])]
    import tempfile, os
    o = write(os.path.join(tempfile.mkdtemp(), "t"), xs, cl, tr, cond, names, masks)
    assert abs(o.query("check == 'es' and group == 'all'").model.item()) < 0.05
    assert abs(o.query("check == 'derived' and group == 'max_wind' and metric == 'cov90'").model.item() - 0.9) < 0.05
    f = o.query("check == 'filled' and metric == 'T_cov99'").set_index("group")
    assert abs(f.loc["filled", "model"] - 0.99) < 0.05 and abs(f.loc["real_12_18km", "model"] - 0.99) < 0.05  # perfect ensemble: nominal in both
    assert 0 < o.query("check == 'filled' and group == 'filled'").ref.iloc[0] < 0.05  # 200 rows x 1 height of 400 x 44
    print("mc self-check ok")
