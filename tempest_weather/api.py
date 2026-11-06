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

from tempest_weather import _core, bias as _bias, coupling, distributions, forecast, modes, outputs, ranking, registry
from tempest_weather.engine import Net
from tempest_weather.sources import era5_local, openmeteo
from tempest_weather.sources.indices import Indices

HERE = os.path.dirname(os.path.abspath(__file__))
BOX = dict(lat=(31.0, 34.0), lon=(-108.0, -101.0))      # default only; the assets carry their own grid and the check in atmosphere_set uses it
M_CAL = 199
_ASSETS = {}


def _load_post(z, manifest):
    """Optional shape post-processing assets (IL-91 / F-16): Schaake-shuffle templates (month x 2-hour bin), shear-space map, seasonal widths. None when not exported."""
    if not manifest.get("post_included"):
        return None
    post = {}
    if "post/tpl" in z.files:
        post["tpl"] = z["post/tpl"]
    if "post/rank" in z.files:
        post["rank"], post["cell"] = z["post/rank"], int(z["post/cell"])
    if "post/smap_grid" in z.files:
        post["smap"] = dict(grid=z["post/smap_grid"], gain=z["post/smap_gain"])
    if "post/seasonal" in z.files:
        post["seasonal"] = z["post/seasonal"]
    return post


def _post_process(A, x, doy, sh, pts=None, grid=None):
    """x (groups, M_CAL, D) range-calibrated samples -> seasonal widths, then the shuffle with the template of the query's month x 2-hour bin, then the shear map (the order the scorer uses)."""
    post = A.get("post")
    if not post:
        return x
    month, hb = int(doy / 365.25 * 12) % 12, int(sh / 2) % 12
    if "seasonal" in post:
        x = _core.seasonal_apply(post["seasonal"], x, np.full(len(x), month + 1))
    if "rank" in post and pts is not None:                           # templates per block of grid points (IL-95): each range-map block comes from one point, so it gets its block's ranks
        ncol = -(-29 // post["cell"])
        lat_i = np.rint((grid["lat"][pts] - grid["lat"].min()) / 0.25).astype(int) // post["cell"]
        lon_i = np.rint((grid["lon"][pts] - grid["lon"].min()) / 0.25).astype(int) // post["cell"]
        r = post["rank"][lat_i * ncol + lon_i, month * 12 + hb]               # (groups, 199, 179)
        ok = r.max(axis=(1, 2)) > 0
        if ok.any():
            x = x.copy()
            x[ok] = _core.shuffle_apply_ranks(x[ok], r[ok])
    if "tpl" in post:
        tpl = post["tpl"][month * 12 + hb].astype(np.float32)
        if np.any(tpl):                                                  # an empty bin (no training rows) leaves the order as it is
            x = _core.shuffle_apply(x, np.broadcast_to(tpl, x.shape))
    if "smap" in post:
        x = _core.shear_apply(post["smap"], x)
    return x


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
             modef=Net.load(os.path.join(path, "model.npz"), prefix="modef_") if manifest.get("modef_included") else None,
             modef_calib=dict(qz=z["modef_calib/qz"], qu=z["modef_calib/qu"], m=z["modef_calib/m"]) if manifest.get("modef_included") else None,
             modef_bl=dict(ratio=z["modef_bl/ratio"], dpd_a=float(z["modef_bl/dpd_a"]), dpd_b=float(z["modef_bl/dpd_b"])) if manifest.get("modef_included") else None,
             modef_tpl={L: z[f"modef_tpl/L{L}"].astype(np.float32) for L in (1, 3, 5, 7)} if manifest.get("modef_included") else None,
             modef_coarse=int(z["modef/coarse"]) if manifest.get("modef_included") else 4,
             wcalib=dict(qz=z["wcalib/qz"], qu=z["wcalib/qu"], m=z["wcalib/m"]) if manifest.get("wcalib_included") else None,
             post=_load_post(z, manifest),
             sta=dict(cols=z["modep_sta/cols"], a=z["modep_sta/a"], b=z["modep_sta/b"], pool=z["modep_sta/pool"], n=z["modep_sta/n"], cuts=z["modep_sta/cuts"]) if manifest.get("modep_sta_included") else None,
             sfc_pool=dict(res=z["modep_sfc/res"], key=z["modep_sfc/key"]) if manifest.get("modep_sfc_included") else None,
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


_GUST_SITES = {"MAF": (31.9425, -102.2019), "TCS": (33.2369, -107.2672)}


def _gust_station(lat, lon):
    """1 for the Truth or Consequences side (Spaceport America), 0 for Midland: the flag the gust model was fitted with."""
    d = {k: (lat - a) ** 2 + (lon - b) ** 2 for k, (a, b) in _GUST_SITES.items()}
    return 1.0 if d["TCS"] < d["MAF"] else 0.0


def _gust_params(g, ws, doy, hour, station=0.0):
    """hour = UTC hour of the query (the model was fitted with the UTC hour of the reports)."""
    a, h = 2 * np.pi * doy / 365.25, 2 * np.pi * hour / 24.0
    X = np.stack([np.ones_like(ws), ws, ws ** 2 / 10.0, np.full_like(ws, np.sin(a)), np.full_like(ws, np.cos(a)), np.full_like(ws, np.sin(h)),
                  np.full_like(ws, np.cos(h)), np.full_like(ws, station)], 1)
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
    if A["manifest"].get("modep_post2022"):                        # F-11 part 2: the network was trained with the post-2022 indicator (1 from 2022 on = the current humidity sensors)
        cond = np.concatenate([cond, [1.0 if t_utc.year >= 2022 else 0.0]]).astype(np.float32)
    groups = int(np.ceil(n / M_CAL))
    res = A["modep"].sample(np.tile(cond, (groups * M_CAL, 1)), rng).reshape(groups, M_CAL, -1)
    x = era[None, None, :] + res
    i = 3 * _core.NH
    x[..., i:i + _core.NH] = np.clip(x[..., i:i + _core.NH], 0, 100)
    x = _core.calibrate(A["modep_calib"], x, clip=False).reshape(groups * M_CAL, -1)[:n]
    nh = _core.NH
    sta = A.get("sta")
    if sta is not None:                                            # F-11: where the station correction beat the network on 2021-23 (RH 12-18 km), serve it: a + b ERA5 + a leftover profile of the same group and moisture class
        gid = (st * 4 + (t_utc.month % 12) // 3) * 2 + int(hour12)
        wet = float(e["RH"][(_core.HEIGHTS >= 5000) & (_core.HEIGHTS <= 13000)].mean())
        j = int(wet > sta["cuts"][gid, 0]) + int(wet > sta["cuts"][gid, 1])
        nj = int(sta["n"][gid, j])
        cols = sta["cols"]
        sc = sta["a"][gid] + sta["b"][gid] * era[cols]
        left = sta["pool"][gid, j, (rng.random(n) * nj).astype(np.int64)].astype(np.float64) if nj > 0 else 0.0
        x[:, cols] = np.clip(sc[None, :] + left, 0, 100)
    pool = A.get("sfc_pool")
    if pool is not None:                                           # F-12: surface values = ERA5 + a whole (t2m, sp, rh2m) residual row of the same station x season x launch hour (joint, empirical)
        key = (st * 4 + (t_utc.month % 12) // 3) * 2 + int(hour12)
        rows = pool["res"][pool["key"] == key]
        if len(rows):
            d = rows[rng.integers(0, len(rows), n)]
            sfc = np.stack([e["t2m"] + d[:, 0], e["sp"] + d[:, 1], np.clip(e["rh2m"] + d[:, 2], 0, 100)], 1)
            return np.concatenate([x, sfc], 1).astype(np.float32), e
    t2m = e["t2m"] + (x[:, 2 * nh] - e["T"][0])
    rh2m = np.clip(e["rh2m"] + (x[:, 3 * nh] - e["RH"][0]), 0, 100)
    return np.concatenate([x, t2m[:, None], np.full((n, 1), e["sp"]), rh2m[:, None]], 1).astype(np.float32), e


FORECAST_LEAD = (0.75, 7.5)       # days: the leads mode F was tested at are 1, 3, 5 and 7
FORECAST_SOLAR = (14.0, 20.0)     # hours of local solar time: the archived cases are all valid at 00 UTC, about 17 h solar in the box (AUTOPILOT F-8a)


def _forecast_phys(A, lat, lon, p, z_sfc, t_utc, lead, n, rng, fetch, predicted, bias_dir=None):
    """Forecast mode: Open-Meteo / IFS fields of that hour -> the 44-height profile -> learned forecast-error draws -> range map -> real error-profile dependence.
    -> ((n, 179) physical, the forecast profile dict, quality flags)."""
    doc = (fetch or openmeteo.fetch)(lat, lon, t_utc.strftime("%Y-%m-%d"))
    fields = forecast.fields_from_openmeteo(doc, int(t_utc.hour))
    flag = ["forecast-source:open-meteo-ecmwf_ifs025", f"forecast-lead-days:{lead:.2f}"]
    state = _bias.find(bias_dir or os.environ.get("TEMPEST_BIAS_DIR"), lat, lon)
    if state is not None:                                          # IL-98 item B: the live feed's recent surface bias at this site (EWMA, gated), subtracted before the profile is built
        dT, dW = _bias.apply_to_fields(fields, state, lead, t_utc.hour)
        if dT or dW:
            flag.append(f"surface-bias-corrected:dT={dT:+.2f}K,dWS={dW:+.2f}m/s(state-through-{state['updated']})")
    prof = forecast.forecast_profile(fields, z_sfc, A["modef_bl"])
    if min(abs(lead - x) for x in (1, 3, 5, 7)) > 0.6:
        flag.append("lead-between-the-tested-1-3-5-7-day-leads")
    nh = _core.NH
    base = forecast.flat(prof)
    if predicted:
        row = np.concatenate([base, [prof["t2m"], prof["sp"], prof["rh2m"]]]).astype(np.float32)
        return np.tile(row, (n, 1)), prof, flag
    groups = int(np.ceil(n / M_CAL))
    g = A["grid"]
    cond = forecast.condition(prof, float(g["lat"][p]), float(g["lon"][p]), z_sfc, t_utc.timetuple().tm_yday, lead, A["modef_coarse"])
    res = A["modef"].sample(np.tile(cond, (groups * M_CAL, 1)), rng).reshape(groups, M_CAL, -1)
    x = base[None, None, :] + res
    i = 3 * nh
    x[..., i:i + nh] = np.clip(x[..., i:i + nh], 0, 100)
    x = _core.calibrate(A["modef_calib"], x, clip=False)
    tpl = A["modef_tpl"][min((1, 3, 5, 7), key=lambda L: abs(L - lead))]          # real forecast-error profiles of the nearest tested lead
    ranks = np.argsort(np.argsort(tpl[rng.integers(0, len(tpl), (groups, M_CAL))], axis=1), axis=1)
    x = np.take_along_axis(np.sort(x, axis=1), ranks, axis=1).reshape(groups * M_CAL, -1)[:n]
    x[:, i:i + nh] = np.clip(x[:, i:i + nh], 0, 100)
    t2m = prof["t2m"] + (x[:, 2 * nh] - prof["T"][0])
    rh2m = np.clip(prof["rh2m"] + (x[:, 3 * nh] - prof["RH"][0]), 0, 100)
    return np.concatenate([x, t2m[:, None], np.full((n, 1), prof["sp"]), rh2m[:, None]], 1).astype(np.float32), prof, flag


def atmosphere_set(lat, lon, when, n=1024, predicted=False, seed=0, elevation=None, mode=None, assets=None, now=None, era5_store=None, fetch=None, bias_dir=None):
    """-> (atm dict of arrays with the sample first, info dict). The shared engine behind all four calls."""
    A = _assets(assets)
    box = dict(lat=(float(A["grid"]["lat"].min()), float(A["grid"]["lat"].max())), lon=(float(A["grid"]["lon"].min()), float(A["grid"]["lon"].max())))   # the assets define the trained area
    if not (box["lat"][0] <= lat <= box["lat"][1] and box["lon"][0] <= lon <= box["lon"][1]):
        raise ValueError(f"({lat}, {lon}) is outside the trained area {box}; other regions need their own assets (docs/REGION_PLAN.md)")
    rng = np.random.default_rng(seed)
    t_utc, sh = _time(when, lon)
    if not 6.0 <= sh <= 21.0:
        raise ValueError(f"solar time {sh:.1f} h is outside the trained 06-21 h window")
    store_path = era5_store or era5_local.default_path()
    avail = {"past"} if (store_path and A["modep"] is not None) else set()
    lead = modes.lead_days(t_utc, now)
    why_not = []
    if A["modef"] is not None:
        if not FORECAST_LEAD[0] <= lead <= FORECAST_LEAD[1]:
            why_not.append(f"forecast-mode-lead-outside-{FORECAST_LEAD[0]}-{FORECAST_LEAD[1]}-days")
        if not FORECAST_SOLAR[0] <= sh <= FORECAST_SOLAR[1]:
            why_not.append(f"forecast-mode-only-trained-for-solar-hours-{FORECAST_SOLAR[0]:g}-{FORECAST_SOLAR[1]:g}")
        if not why_not:
            avail.add("forecast")
    used, quality = modes.choose(lead, mode, avail)
    if used == "ai" and "fallback-mode" in quality and why_not and (mode in (None, "recent", "week", "forecast")):
        quality = quality + why_not
    g = A["grid"]
    p = int(np.argmin((g["lat"] - lat) ** 2 + (g["lon"] - lon) ** 2))      # nearest grid point (reported; the mode P and past paths use the exact position)
    pts, wts = _core.bilinear(g["lat"], g["lon"], lat, lon)             # the four points around the query and their bilinear weights (F-6)
    elev_grid = float(g["elev"][p])
    elev = float(np.dot(wts, g["elev"][pts])) if elevation is None else float(elevation)   # the site (bilinear grid elevation unless given); the model runs at each point's elevation, then moves to the site
    if used == "past" and predicted:
        quality = quality + ["past-without-model-error-is-the-ERA5-value"]
    if used == "ai":                                                  # the generator extrapolates a straight-line year trend past its training data (2025)
        yb = t_utc.year - 2025
        if yb > 5:
            quality = quality + [f"year-trend-extrapolated-{yb}-years-beyond-the-training-data" + ("-unreliable" if yb > 25 else "")]
    groups = 1 if predicted else int(np.ceil(n / M_CAL))
    total = n if predicted else groups * M_CAL
    drv, drv_note = A["indices"].draws(t_utc, total, rng, expected=predicted)
    names = A["net"].names
    # each block of M_CAL atmospheres (one range-map unit) comes from one of the four surrounding grid points, blocks allocated by the bilinear weights: smooth in space and every atmosphere stays whole
    if used == "past" or len(pts) == 1:
        row_pt = np.full(total, pts[int(np.argmax(wts))] if used != "past" else p)
    elif predicted:
        row_pt = rng.choice(pts, size=total, p=wts)
    else:
        row_pt = np.repeat(np.repeat(pts, _core.allocate(wts, groups, rng)), M_CAL)
    elev_row = g["elev"][row_pt].astype(float)
    cond = _core.feature_matrix(names, g["lat"][row_pt], g["lon"][row_pt], elev_row, elev_row, t_utc.timetuple().tm_yday, sh, t_utc.year, drv[:, 0], drv[:, 3], drv[:, 1], drv[:, 2],
                                gmst=A["indices"].gmst_at(t_utc) if "gmst" in names else None)
    if used == "past":
        store = era5_local.open_store(store_path)
        if predicted:                                    # no model error: the ERA5 value itself, every sample identical
            _, e = _past_phys(A, store, lat, lon, t_utc, M_CAL, rng)
            phys = np.tile(np.concatenate([e["u"], e["v"], e["T"], e["RH"], [e["t2m"], e["sp"], e["rh2m"]]]).astype(np.float32), (n, 1))
        else:
            phys, _ = _past_phys(A, store, lat, lon, t_utc, n, rng)
        cond = cond[:n] if len(cond) >= n else np.tile(cond[:1], (n, 1))
    elif used == "forecast":
        try:
            phys, fprof, fflags = _forecast_phys(A, lat, lon, p, elev_grid, t_utc, lead, n, rng, fetch, predicted, bias_dir)
            quality = quality + fflags
            cond = cond[:n] if len(cond) >= n else np.tile(cond[:1], (n, 1))
        except Exception as e:  # noqa: BLE001  (network, unexpected response: the climate generator answers, and says so)
            used, quality = "ai", ["fallback-mode", f"forecast-fetch-failed:{type(e).__name__}"]
            phys = None
    else:
        phys = None
    if phys is None:
        phys = A["net"].profiles(cond, rng)
        if not predicted:
            phys = _post_process(A, _core.calibrate(A["calib"], phys.reshape(groups, M_CAL, -1)), t_utc.timetuple().tm_yday, sh, row_pt[::M_CAL], g).reshape(total, -1)[:n]
            cond = cond[:n]
    nh = _core.NH
    w_site = None
    if A["head"] is not None:                                         # the vertical-wind head saw grid-elevation inputs: sample BEFORE the site shift
        if A.get("wcalib") is not None and used == "ai" and not predicted:     # F-27: w range map fitted on generated profiles; needs whole blocks of M_CAL atmospheres (padded by cycling the rows)
            pad = np.arange(total) % n
            w_all = A["head"].sample(np.concatenate([cond[pad], phys[pad].astype(np.float32)], 1), rng)
            w_site = _core.calibrate(A["wcalib"], w_all.reshape(groups, M_CAL, -1), clip=False).reshape(total, -1)[:n]
        else:
            w_site = A["head"].sample(np.concatenate([cond, phys.astype(np.float32)], 1), rng)
    dz_row = (elev - elev_row[:n]) if used != "past" else np.full(n, elev - elev_grid)
    if np.any(dz_row != 0):                                           # temperature, pressure and humidity to the site elevation (standard lapse rate fading with height, hypsometric)
        _core.site_shift(phys, dz_row)
    atm = dict(u=phys[:, :nh], v=phys[:, nh:2 * nh], T=phys[:, 2 * nh:3 * nh], RH=phys[:, 3 * nh:4 * nh], t2m=phys[:, 4 * nh], sp=phys[:, 4 * nh + 1], rh2m=phys[:, 4 * nh + 2])
    th = _core.thermo_column(_core.HEIGHTS, atm["T"], atm["RH"], atm["sp"], t_sfc=atm["t2m"], rh_sfc=atm["rh2m"], z_sfc=elev)
    atm.update(p=th["p"], rho=th["rho"], a=th["a"])
    atm["w"] = w_site
    atm["gust_mu"] = atm["gust_beta"] = None
    if A["gust"] is not None:
        atm["gust_mu"], atm["gust_beta"] = _gust_params(A["gust"], np.hypot(atm["u"][:, 0], atm["v"][:, 0]), t_utc.timetuple().tm_yday, t_utc.hour + t_utc.minute / 60.0, _gust_station(lat, lon))
    src = ("ERA5 + learned balloon correction" if not predicted else "ERA5 value") if used == "past" else ("IFS forecast (Open-Meteo) + learned forecast error" if used == "forecast" else
        "tempest generator (calibrated)" if not predicted else "tempest generator (predicted set, no range map)")
    info = dict(mode=used, source=src, quality=quality,
                valid_utc=str(t_utc), solar_hour=sh, grid_point=p, spatial_blend=dict(points=[int(x) for x in pts], weights=[round(float(x), 4) for x in wts]), elevation_m=elev, grid_elevation_m=elev_grid, indices=drv_note, kind="predicted" if predicted else "uncertainty",
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
