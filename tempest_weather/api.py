"""The four calls. See README.md for examples.

    values(lat, lon, when, variables)                           ordered dict of best estimates (median of the atmospheres)
    distribution(lat, lon, when, variables, setting=0)           per variable: {"type", "params", "units", "note"}  (+ samples on request)
    couple(lat, lon, when, variables, method="whole_sample")    a coupling object: .draw(k) gives jointly consistent rows; .spec() describes it
    atmosphere(lat, lon, when, percentiles=(15, 50, 85))        single-value inputs for the simulator at points along the worst-to-best order

Settings of `distribution` / `couple`: 0 standard types, with model error | 1 standard types, without | 2 empirical, with model error | 3 empirical, without.
"With model error" = the full uncertainty set (generator members, drawn climate indices, range-calibration map); "without" = the predicted set (indices at their
expected values, no range map). Every answer includes mode, source and quality flags. Times: aware strings/datetimes are exact; a naive time is local solar time at the longitude.
"""
import hashlib
import json
import os

from datetime import datetime, timedelta, timezone

import numpy as np

from tempest_weather import _core, coupling, distributions, modes, outputs, ranking, registry
from tempest_weather.engine import Net
from tempest_weather.sources import era5_local
from tempest_weather.sources.indices import Indices

HERE = os.path.dirname(os.path.abspath(__file__))
BOX = dict(lat=(31.0, 34.0), lon=(-108.0, -101.0))
M_CAL = 199
_ASSETS = {}


def _assets(path=None):
    path = path or os.path.join(HERE, "assets")
    if path in _ASSETS:
        return _ASSETS[path]
    mf = os.path.join(path, "manifest.json")
    if not os.path.exists(mf):
        raise FileNotFoundError(f"model assets not found in {path}; copy the assets folder or run `python -m tempest.export_tool` in the main repo")
    manifest = json.load(open(mf, encoding="utf-8"))
    for name, want in manifest["files"].items():
        with open(os.path.join(path, name), "rb") as f:
            got = hashlib.file_digest(f, "sha256").hexdigest()
        if got != want:
            raise RuntimeError(f"asset {name} does not match its manifest hash (corrupted or from another release); re-copy the assets")
    z = np.load(os.path.join(path, "model.npz"), allow_pickle=False)
    net = Net.load(os.path.join(path, "model.npz"))
    a = dict(manifest=manifest, net=net, calib=dict(qz=z["calib/qz"], qu=z["calib/qu"], m=z["calib/m"]),
             head=Net.load(os.path.join(path, "model.npz"), prefix="head_") if manifest.get("head_included") else None,
             modep=Net.load(os.path.join(path, "model.npz"), prefix="modep_") if manifest.get("modep_included") else None,
             modep_calib=dict(qz=z["modep_calib/qz"], qu=z["modep_calib/qu"], m=z["modep_calib/m"]) if manifest.get("modep_included") else None,
             gust=dict(theta=z["gust/theta"], phi=z["gust/phi"]) if manifest.get("gust_included") else None,
             indices=Indices(np.load(os.path.join(path, "indices.npz"))), grid=dict(np.load(os.path.join(path, "grid.npz"))))
    _ASSETS[path] = a
    return a


def _time(when, lon):
    """-> (naive UTC datetime, solar hour). A datetime/ISO string with an offset is an exact instant; a naive one is local solar time at the longitude."""
    t = when if isinstance(when, datetime) else datetime.fromisoformat(str(when).strip().replace(" ", "T", 1) if " " in str(when).strip() and "T" not in str(when) else str(when).strip())
    if t.tzinfo is None:
        return t - timedelta(hours=lon / 15.0), t.hour + t.minute / 60
    u = t.astimezone(timezone.utc).replace(tzinfo=None)
    return u, (u.hour + u.minute / 60 + lon / 15.0) % 24


def _gust_params(g, ws, doy, hour):
    a, h = 2 * np.pi * doy / 365.25, 2 * np.pi * hour / 24.0
    X = np.stack([np.ones_like(ws), ws, ws ** 2 / 10.0, np.full_like(ws, np.sin(a)), np.full_like(ws, np.cos(a)), np.full_like(ws, np.sin(h)),
                  np.full_like(ws, np.cos(h)), np.zeros_like(ws)], 1)
    return X @ g["theta"], np.exp(np.clip(X @ g["phi"], -5, 5))


STATIONS = [(31.8728, -106.6981), (31.9475, -102.1894)]  # Santa Teresa, Midland: the station index the past-date network was trained with


def _past_phys(A, store, lat, lon, t_utc, n, rng):
    """Past dates: ERA5 profile for that hour + learned balloon-minus-ERA5 residual draws, range-calibrated. -> ((n, 179) physical, ERA5 dict)."""
    e = era5_local.profile(store, lat, lon, t_utc)
    st = int(np.argmin([(lat - a) ** 2 + (lon - b) ** 2 for a, b in STATIONS]))
    a = 2 * np.pi * t_utc.timetuple().tm_yday / 365.25
    hour12 = 1.0 if 6 <= t_utc.hour < 18 else 0.0
    era = np.concatenate([e["u"], e["v"], e["T"], e["RH"]]).astype(np.float32)
    cond = np.concatenate([[st, np.sin(a), np.cos(a), hour12], era]).astype(np.float32)
    groups = int(np.ceil(n / M_CAL))
    res = A["modep"].sample(np.tile(cond, (groups * M_CAL, 1)), rng).reshape(groups, M_CAL, -1)
    x = era[None, None, :] + res
    i = 3 * _core.NH
    x[..., i:i + _core.NH] = np.clip(x[..., i:i + _core.NH], 0, 100)
    x = _core.calibrate(A["modep_calib"], x, clip=False).reshape(groups * M_CAL, -1)[:n]
    nh = _core.NH
    t2m = e["t2m"] + (x[:, 2 * nh] - e["T"][0])
    rh2m = np.clip(e["rh2m"] + (x[:, 3 * nh] - e["RH"][0]), 0, 100)
    return np.concatenate([x, t2m[:, None], np.full((n, 1), e["sp"]), rh2m[:, None]], 1).astype(np.float32), e


def atmosphere_set(lat, lon, when, n=1024, predicted=False, seed=0, elevation=None, mode=None, assets=None, now=None, era5_store=None):
    """-> (atm dict of arrays with the sample first, info dict). The shared engine behind all four calls."""
    if not (BOX["lat"][0] <= lat <= BOX["lat"][1] and BOX["lon"][0] <= lon <= BOX["lon"][1]):
        raise ValueError(f"({lat}, {lon}) is outside the trained area {BOX}; modes beyond the pilot box need the CONUS stage")
    A = _assets(assets)
    rng = np.random.default_rng(seed)
    t_utc, sh = _time(when, lon)
    if not 6.0 <= sh <= 21.0:
        raise ValueError(f"solar time {sh:.1f} h is outside the trained 06-21 h window")
    store_path = era5_store or era5_local.default_path()
    avail = {"past"} if (store_path and A["modep"] is not None) else set()
    used, quality = modes.choose(modes.lead_days(t_utc, now), mode, avail)
    g = A["grid"]
    p = int(np.argmin((g["lat"] - lat) ** 2 + (g["lon"] - lon) ** 2))
    elev_grid = float(g["elev"][p])
    elev = elev_grid if elevation is None else float(elevation)       # the site; the model is run at the grid elevation, then moved to the site
    if used == "past" and predicted:
        quality = quality + ["past-without-model-error-is-the-ERA5-value"]
    groups = 1 if predicted else int(np.ceil(n / M_CAL))
    total = n if predicted else groups * M_CAL
    drv, drv_note = A["indices"].draws(t_utc, total, rng, expected=predicted)
    names = A["net"].names
    cond = _core.feature_matrix(names, g["lat"][p], g["lon"][p], elev_grid, elev_grid, t_utc.timetuple().tm_yday, sh, t_utc.year, drv[:, 0], drv[:, 3], drv[:, 1], drv[:, 2],
                                gmst=A["indices"].gmst_at(t_utc) if "gmst" in names else None)
    if used == "past":
        store = era5_local.open_store(store_path)
        if predicted:                                    # no model error: the ERA5 value itself, every sample identical
            _, e = _past_phys(A, store, lat, lon, t_utc, M_CAL, rng)
            phys = np.tile(np.concatenate([e["u"], e["v"], e["T"], e["RH"], [e["t2m"], e["sp"], e["rh2m"]]]).astype(np.float32), (n, 1))
        else:
            phys, _ = _past_phys(A, store, lat, lon, t_utc, n, rng)
        cond = cond[:n] if len(cond) >= n else np.tile(cond[:1], (n, 1))
    else:
        phys = A["net"].profiles(cond, rng)
        if not predicted:
            phys = _core.calibrate(A["calib"], phys.reshape(groups, M_CAL, -1)).reshape(total, -1)[:n]
            cond = cond[:n]
    nh = _core.NH
    if elev != elev_grid:                                             # surface temperature and pressure to the site elevation (standard lapse rate, hypsometric)
        dz = elev - elev_grid
        t_ = phys[:, 4 * nh]
        phys[:, 4 * nh + 1] *= np.exp(-_core.G0 * dz / (_core.RD * (t_ - 0.0065 * dz / 2)))
        phys[:, 4 * nh] = t_ - 0.0065 * dz
    atm = dict(u=phys[:, :nh], v=phys[:, nh:2 * nh], T=phys[:, 2 * nh:3 * nh], RH=phys[:, 3 * nh:4 * nh], t2m=phys[:, 4 * nh], sp=phys[:, 4 * nh + 1], rh2m=phys[:, 4 * nh + 2])
    th = _core.thermo_column(_core.HEIGHTS, atm["T"], atm["RH"], atm["sp"], t_sfc=atm["t2m"], rh_sfc=atm["rh2m"], z_sfc=elev)
    atm.update(p=th["p"], rho=th["rho"], a=th["a"])
    atm["w"] = A["head"].sample(np.concatenate([cond, phys.astype(np.float32)], 1), rng) if A["head"] is not None else None
    atm["gust_mu"] = atm["gust_beta"] = None
    if A["gust"] is not None:
        atm["gust_mu"], atm["gust_beta"] = _gust_params(A["gust"], np.hypot(atm["u"][:, 0], atm["v"][:, 0]), t_utc.timetuple().tm_yday, sh)
    src = ("ERA5 + learned balloon correction" if not predicted else "ERA5 value") if used == "past" else (
        "tempest generator (calibrated)" if not predicted else "tempest generator (predicted set, no range map)")
    info = dict(mode=used, source=src, quality=quality,
                valid_utc=str(t_utc), solar_hour=sh, grid_point=p, elevation_m=elev, grid_elevation_m=elev_grid, indices=drv_note, kind="predicted" if predicted else "uncertainty",
                model=A["manifest"]["model_source"], n=n)
    if "fallback-mode" in quality:
        info["note"] = "the corrected-prediction source for this lead is not available; the climate generator answered"
    return atm, info


def _need(variables):
    if isinstance(variables, str):
        variables = [variables]
    return list(variables)


def values(lat, lon, when, variables, mode=None, n=1024, seed=0, **kw):
    """Best estimate of each requested variable (median across the atmospheres; wind direction from the vector median). Returns an ordered dict."""
    names = _need(variables)
    atm, info = atmosphere_set(lat, lon, when, n, False, seed, mode=mode, **kw)
    ev = registry.evaluate(atm, [v for v in names if not v.startswith("wind_dir@")], np.random.default_rng(seed + 1))
    out = {}
    for v in names:
        if not v.startswith("wind_dir@"):
            out[v] = float(np.median(ev[v]))
        else:
            z = v.split("@")[1]
            e = registry.evaluate(atm, [f"u@{z}", f"v@{z}"])
            out[v] = float(np.degrees(np.arctan2(-np.median(e[f"u@{z}"]), -np.median(e[f"v@{z}"]))) % 360.0)
    return dict(values=out, units={v: registry.units_of(v) for v in names}, **{k: info[k] for k in ("mode", "source", "quality", "valid_utc")})


def _set_for(lat, lon, when, setting, n, seed, mode, kw):
    if setting not in (0, 1, 2, 3):
        raise ValueError("setting must be 0, 1, 2 or 3")
    return atmosphere_set(lat, lon, when, n, predicted=setting in (1, 3), seed=seed, mode=mode, **kw)


def distribution(lat, lon, when, variables, setting=0, n=1024, seed=0, mode=None, samples=False, **kw):
    """One description per variable: {"type", "params", "units", "note"[, "samples"]}. Standard types for settings 0/1, empirical tables for 2/3."""
    names = _need(variables)
    atm, info = _set_for(lat, lon, when, setting, n, seed, mode, kw)
    ev = registry.evaluate(atm, names, np.random.default_rng(seed + 1))
    out = {}
    for v in names:
        spec = distributions.describe(ev[v], setting in (0, 1), units=registry.units_of(v))
        if samples:
            spec["samples"] = ev[v]
        out[v] = spec
    return dict(variables=out, setting=setting, **{k: info[k] for k in ("mode", "source", "quality", "valid_utc", "kind", "indices")})


def couple(lat, lon, when, variables, method="whole_sample", setting=0, n=1024, seed=0, mode=None, **kw):
    """A coupling object over the requested variables (draw(k) -> (indices, rows), spec()). `whole_sample` rows are real atmospheres from one set."""
    names = _need(variables)
    if method == "gaussian_copula" and any(v.startswith("wind_dir@") for v in names):
        raise ValueError("wind_dir is a circular angle (1 and 359 degrees are neighbours) and cannot enter a Gaussian copula; ask for u@z and v@z (and derive the direction) "
                         "or use method='whole_sample'")
    atm, info = _set_for(lat, lon, when, setting, n, seed, mode, kw)
    ev = registry.evaluate(atm, names, np.random.default_rng(seed + 1))
    table = np.stack([ev[v] for v in names], 1)
    marg = [distributions.describe(table[:, j], setting in (0, 1), units=registry.units_of(v)) for j, v in enumerate(names)] if method == "gaussian_copula" else None
    key = registry.evaluate(atm, ["mean_wind@10-3000"])["mean_wind@10-3000"]
    c = coupling.make(method, names, table, marg, key=key)
    c.info = {k: info[k] for k in ("mode", "source", "quality", "valid_utc", "kind")}
    return c


def atmosphere(lat, lon, when, percentiles=(15, 50, 85), extras=(), n=1024, seed=0, mode=None, score_fn=None, **kw):
    """Single-value simulator inputs at each percentile of the worst-to-best order of the day's atmospheres (0 = worst, 100 = best). -> list of dicts
    (see outputs.inputs_from_values) each with meta: percentile, flight_score, sample index, mode, source, quality."""
    atm, info = atmosphere_set(lat, lon, when, n, False, seed, mode=mode, **kw)
    score = (score_fn or ranking.flight_score)(atm)
    ev = registry.evaluate(atm, ["wind_speed@100", "u@100", "v@100", *extras], np.random.default_rng(seed + 1), score_fn=score_fn)
    out = []
    for pc in percentiles:
        i = ranking.pick(score, pc)
        g = _core.HEIGHTS
        d = outputs.inputs_from_values(lat, lon, info["elevation_m"], atm["t2m"][i], atm["sp"][i], np.clip(atm["rh2m"][i], 0, 100) / 100.0, ev["u@100"][i], ev["v@100"][i],
                                       extras={k: ev[k][i] for k in extras},
                                       meta=dict(percentile=pc, flight_score=float(score[i]), sample=i, **{k: info[k] for k in ("mode", "source", "quality", "valid_utc", "indices")}))
        out.append(d)
    return out
