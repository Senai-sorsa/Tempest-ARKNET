"""Train the generator.

    python -m tempest.generator.train --data data/train/pilot.npz --out models/generator_pilot.pt [--max-year 2014]

The .npz holds `cond` (N, F) from features.features, `target` (N, D) = station-corrected profiles in
difference space (profiles.diff.to_diff per variable, flattened) followed by the surface fields, and `year`
(N,). Optional `cond_names`, `target_names`. Building it from the profile store is phase 6A work.
Validation = the last `val_years` years kept; `--max-year` drops later years for a walk-forward fold.
With `val_block_frac` > 0 it is instead that share of 14-day blocks drawn from every year (rows within 3 days
of a validation block are left out of training, weather remembers a few days), so training keeps the recent years.
Loss (training and validation) is scored on rebuilt profiles (differences summed back up, standardised), so
errors that pile up with height count: per-value almost-fair CRPS (as ECMWF AIFS-CRPS) + es_weight x energy score
/ sqrt(D), the second term keeping heights jointly consistent.
`members` (config) trains that many seeds side by side (one loop, each its own batches, noise and early stop) and
saves them in one file; Sampler splits samples evenly across them. On a GPU the normalised training rows live on the
GPU (float16, ~2 bytes x 192 columns per row) and the forward pass runs in bfloat16; validation stays float32.
`linear_features` (year and the ENSO/QBO indices) enter as straight-line effects, see model.Generator.
"""
import argparse
import copy
import math
import struct
import time
import tomllib
import zipfile

import numpy as np
import torch

from tempest.generator.model import Generator, afcrps, energy_score, make_generator
from tempest.generator.sample import standard_pressure
from tempest.profiles.to_heights import HEIGHTS, PROFILE

DEFAULTS = dict(noise_dim=32, width=512, depth=4, m=4, crps_alpha=0.95, es_weight=0.1, step_weight=0.0, batch=4096, lr=1e-3, weight_decay=1e-4,
                arch="mlp",              # "tokens": attention along the 44 heights (IL-8); "mlp" is the adopted generator
                steps=20000, eval_every=500, patience=10, val_years=3, val_block_frac=0.0, val_rows=50000, seed=0,
                linear_features=["year", "oni", "wwv", "qbo30", "qbo50"],
                # Phase 2 keys, all off by default (see docs/plans/PHASED_PLAN.md):
                step_strides=None,          # e.g. [1, 2, 4, 8, 16]: CRPS on sums of that many height steps; weights share step_weight
                ema_decay=0.0,              # e.g. 0.999: evaluate and save an exponential moving average of the weights
                superadiabatic_weight=0.0,  # e.g. 0.01: penalty on lapse rates above 9.8 K/km above 2 km
                shear_tail_weight=0.0,      # e.g. 0.3: tail-weighted CRPS of the vector wind shear (strong-shear layers)
                product_pairs=None,         # IL-97: e.g. [["oni", "qbo30"], ["oni", "qbo50"]]: products of two linear features as extra straight-line effects
                interactions=False,         # F-14: slope network sees the driver columns too (driver x driver effects); mlp arch only
                m_final=0, final_steps=0,   # F-15: draw m_final samples per row (instead of m) for the last final_steps steps: less noisy pairwise-spread gradients where the shape is finished
                low_weight=1.0,             # C4b: weight of the per-value CRPS at heights <= low_top_m (1.0 = off; 3.0 = three times as much as above)
                wind_vec_weight=0.0,        # C4b: weight of an extra energy score on the (u, v) vector plus CRPS of the wind speed, both at heights <= low_top_m (0 = off)
                low_top_m=300.0,
                rh_loss_weight=0.0,         # F-19: extra CRPS on relative humidity in per cent (rebuilt from T and the dpd coordinate); only for dpd-target datasets
                train_rows=0,               # F-29: use a random subset of this many training rows (0 = all); lets the float32-storage comparison fit in GPU memory
                store_dtype="float16",      # F-29: "float32" keeps the GPU training rows at full precision (reference mode)
                fill_mask=False,            # review 2026-11-07: heights that build_dataset --fill-top filled (above fill_top_idx) count 0 in the loss; needs a dataset built with --fill-top after 2026-11-07
                shear_tail_q=0.9,           # shear above this quantile of the training rows (per layer) counts in that term
                ignore_inputs=[],           # L3: input columns the network must not see (e.g. ["lat", "lon"]); they stay in the data for scoring
                geo_sh=0, geo_siren=0,      # L3: spherical harmonics of degree geo_sh replace raw lat/lon inside the network (siren > 0: through a sine network)
                context_inputs=[],          # L3: input names routed to the context FiLM instead of the input layer (model.Generator context_cols)
                context_film_sep=False,     # L3: the context gets its own FiLM per block instead of being added to the noise embedding (model ctx_sep)
                geo_siren_w0=1.0,           # L3: SIREN first-layer frequency (1 = the scored L3-4 siren)
                terrain_head_inputs=[],     # L3: input names for the altitude-decayed terrain head
                noise_t_dims=0, noise_t_nu=4.0,   # Gemini idea 1: this many noise numbers are Student-t (model noise_t)
                noise_t_head=0, noise_t_clip=8.0,                   # Gemini idea 1b: the first K t numbers also scale a zero-init output head (past the layer norms)
                jump_k=0, jump_top=3000.0)        # Gemini idea 3: K learned tanh jumps below jump_top metres (model jump)
N_PROF = len(HEIGHTS) * len(PROFILE)  # leading target columns that are profile differences (real data only)


def load_npz(path):
    """Dataset file -> dict of arrays (see _load). Also activates what the dataset says about itself: its input
    columns (features.FEATURES) and its humidity target (sample.RH_TARGET); old files without those keys reset both
    to the original behaviour."""
    out = _load(path)
    from tempest.generator import features, sample
    features.set_active(out["cond_names"] if "cond_names" in out else features.BASE_FEATURES)
    sample.set_rh_target(str(out["rh_target"]) if "rh_target" in out else "rh")
    return out


def _load(path):
    """Uncompressed .npz (np.savez) -> dict of read-only memory maps. np.load ignores mmap_mode for .npz and
    would read all 6 GB into RAM; here rows are read from disk when indexed. Compressed files fall back to np.load.
    An overlay file (loop 3) holds `base_npz` = the path of a full dataset plus the arrays it replaces (e.g. a wider
    `cond` and its `cond_names`); the result is the base dataset with those arrays swapped in."""
    out = _load_one(path)
    if "base_npz" in out:
        base = _load_one(str(np.asarray(out.pop("base_npz"))))
        if len(base["year"]) != len(out.get("cond", base["cond"])):
            raise ValueError(f"overlay {path} does not match its base dataset (row counts differ)")
        base.update(out)
        out = base
    return out


def _load_one(path):
    out = {}
    with zipfile.ZipFile(path) as z, open(path, "rb") as f:
        for i in z.infolist():
            if i.compress_type != zipfile.ZIP_STORED:
                return dict(np.load(path))
            f.seek(i.header_offset)
            n, m = struct.unpack("<HH", f.read(30)[26:30])  # local header: file name and extra field lengths
            f.seek(i.header_offset + 30 + n + m)
            v = np.lib.format.read_magic(f)
            shape, fortran, dtype = (np.lib.format.read_array_header_1_0 if v == (1, 0) else np.lib.format.read_array_header_2_0)(f)
            out[i.filename.removesuffix(".npy")] = np.memmap(path, dtype, "r", offset=f.tell(), shape=shape,
                                                             order="F" if fortran else "C")
    return out


def split(year, cond, names, cfg):
    """-> (train, validation) row masks. Tail years by default; with val_block_frac, 14-day blocks from every year
    (the same blocks for every member and seed) with a 3-day gap dropped on each side."""
    if not cfg.get("val_block_frac"):
        val = year > year.max() - cfg["val_years"]
        return ~val, val
    doy = np.arctan2(cond[:, names.index("doy_sin")], cond[:, names.index("doy_cos")]) % (2 * np.pi) / (2 * np.pi) * 365.25
    day = (np.asarray(year, np.int64) - 1970).astype("datetime64[Y]").astype("datetime64[D]").astype(np.int64) + np.minimum(doy.astype(np.int64), 364)   # true day number (leap years included), review 1.4
    vb = np.random.default_rng(12345).random(int(day.max()) // 14 + 2) < cfg["val_block_frac"]
    val = vb[day // 14]
    tr = ~(val | vb[(day - 3) // 14] | vb[(day + 3) // 14])
    yrs, cnt_v, cnt_t = np.unique(year), [(val & (year == y)).sum() for y in np.unique(year)], [(tr & (year == y)).sum() for y in np.unique(year)]
    if val.sum() < 0.02 * len(year) or min(cnt_t) == 0:                                          # review 1.5: minimum support on both sides
        raise ValueError(f"block validation split has too little support: {int(val.sum())} validation rows, training rows per year min {min(cnt_t)}")
    print(f"block validation: {int(val.sum()):,} validation rows ({100 * val.mean():.1f} %), years without validation rows: {[int(y) for y, c in zip(yrs, cnt_v) if c == 0]}", flush=True)
    return tr, val


def train(cond, target, year, cfg=None, out=None, device=None, log=print, meta=None, members=1, fill_top_idx=None):
    """-> one checkpoint, or dict(members=[...]) when members > 1 (member k uses seed + k).
    fill_top_idx (N, 4) int8: with cfg fill_mask, the highest real height per row and variable (dataset array of the same name)."""
    cfg = {**DEFAULTS, **(cfg or {})}
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    rng = np.random.default_rng(cfg["seed"])
    torch.set_float32_matmul_precision("high")

    year = np.asarray(year)
    tr, val = split(year, cond, list((meta or {}).get("cond_names", [])), cfg)
    tr_idx, va_idx = np.flatnonzero(tr), np.flatnonzero(val)
    if len(tr_idx) == 0 or len(va_idx) == 0:
        raise ValueError("need both training and validation years; check val_years and the year array")
    if cfg["train_rows"] and len(tr_idx) > cfg["train_rows"]:
        tr_idx = np.sort(np.random.default_rng(777).choice(tr_idx, cfg["train_rows"], replace=False))
    va_idx = rng.choice(va_idx, min(len(va_idx), cfg["val_rows"]), replace=False)

    # Normalisation from training rows only, so validation stays unseen.
    # A constant column gets scale 1, not ~0: otherwise any new value at query time explodes to +-1e6.
    safe = lambda s: np.where(s > 1e-6, s, 1.0)
    names, tnames = list((meta or {}).get("cond_names", [])), list((meta or {}).get("target_names", []))
    # sp is learned as the departure from standard pressure at the grid elevation (Sampler adds it back)
    sp_offset = [tnames.index("sp"), names.index("elev_grid")] if "sp" in tnames and "elev_grid" in names else None

    def targets(idx):  # rows of target (a copy), with the sp offset removed
        t = np.array(target[idx], np.float64)
        if sp_offset:
            t[:, sp_offset[0]] -= standard_pressure(cond[idx, sp_offset[1]])
        return t

    ref = np.sort(rng.choice(tr_idx, min(len(tr_idx), 1_000_000), replace=False))  # stats from 1M rows: avoids copying the full set
    cm, cs = cond[ref].mean(0), safe(cond[ref].std(0))
    for k in cfg["ignore_inputs"]:  # L3: a huge scale makes the normalised column 0 everywhere (training and Sampler alike)
        cs[names.index(k)] = 1e30
    tref = targets(ref)
    tm, ts = tref.mean(0), safe(tref.std(0))
    norm = {k: torch.tensor(v, dtype=torch.float32) for k, v in dict(cm=cm, cs=cs, tm=tm, ts=ts).items()}
    linear_cols = [names.index(k) for k in cfg["linear_features"] if k in names]
    lin_names = [names[i] for i in linear_cols]
    pp = [[lin_names.index(a_), lin_names.index(b_)] for a_, b_ in (cfg["product_pairs"] or [])]
    n_prof = N_PROF if len((meta or {}).get("target_names", [])) == N_PROF + 3 else 0
    model_kw = {}                                     # L3 options; empty = the adopted network
    if cfg["geo_sh"]:
        assert not {"lat", "lon"} & set(cfg["ignore_inputs"]), "geo_sh drops lat/lon itself and needs their real scale; do not also ignore them"
        gc = [names.index("lat"), names.index("lon")]
        model_kw["geo"] = dict(cols=gc, mu=[float(cm[i]) for i in gc], sd=[float(cs[i]) for i in gc], L=int(cfg["geo_sh"]), siren=int(cfg["geo_siren"]),
                               **({"w0": float(cfg["geo_siren_w0"])} if cfg["geo_siren_w0"] != 1.0 else {}))
    if cfg["context_inputs"]:
        model_kw["context_cols"] = [names.index(k) for k in cfg["context_inputs"]]
        if cfg["context_film_sep"]:
            model_kw["ctx_sep"] = True
    if cfg["terrain_head_inputs"]:
        hts = np.concatenate([np.tile(np.asarray(HEIGHTS, float), len(PROFILE)), np.zeros(target.shape[1] - N_PROF)]) if n_prof else np.zeros(target.shape[1])
        model_kw["terrain_head"] = dict(cols=[names.index(k) for k in cfg["terrain_head_inputs"]], height=hts.tolist())

    if cfg["noise_t_dims"]:
        model_kw["noise_t"] = dict(dims=int(cfg["noise_t_dims"]), nu=float(cfg["noise_t_nu"]), clip=float(cfg["noise_t_clip"]), **({"head": int(cfg["noise_t_head"])} if cfg["noise_t_head"] else {}))
    if cfg["jump_k"] and n_prof:
        model_kw["jump"] = dict(K=int(cfg["jump_k"]), top=float(cfg["jump_top"]), height=[float(x) for x in HEIGHTS], n_var=len(PROFILE),
                                inv_ts=(1.0 / np.asarray(norm["ts"][:N_PROF], float)).tolist())   # model adds raw-unit jumps in normalised-target space

    def physical(r):  # raw targets -> profiles rebuilt from the differences; works on numpy and torch
        if not n_prof:
            return r
        p = r[..., :n_prof].reshape(*r.shape[:-1], len(PROFILE), len(HEIGHTS)).cumsum(-1)
        rest = r[..., n_prof:]
        return (np.concatenate if isinstance(r, np.ndarray) else torch.cat)([p.reshape(*r.shape[:-1], n_prof), rest], -1)

    ph = physical(tref)
    pm, ps = (torch.tensor(a, dtype=torch.float32, device=device) for a in (ph.mean(0), safe(ph.std(0))))
    stride_scale = {}  # spread of each window-sum column in the training rows (for cfg step_strides)
    if cfg["step_strides"] and n_prof:
        dref = tref[:, :n_prof].reshape(len(tref), len(PROFILE), len(HEIGHTS))[..., 1:]
        cum = np.pad(np.cumsum(dref, -1), [(0, 0), (0, 0), (1, 0)])
        for st in cfg["step_strides"]:
            stride_scale[st] = torch.tensor(safe((cum[..., st:] - cum[..., :-st]).std(0)), dtype=torch.float32, device=device)
    shear_thr = shear_scale = None  # for cfg shear_tail_weight: per-layer threshold and scale of the excess shear
    if cfg["shear_tail_weight"] and n_prof:
        dref = tref[:, :n_prof].reshape(len(tref), len(PROFILE), len(HEIGHTS))[..., 1:]
        shear_ref = np.hypot(dref[:, PROFILE.index("u")], dref[:, PROFILE.index("v")]) / (np.diff(HEIGHTS) / 1000.0)
        thr = np.quantile(shear_ref, cfg["shear_tail_q"], axis=0)
        shear_thr = torch.tensor(thr, dtype=torch.float32, device=device)
        shear_scale = torch.tensor(safe(np.maximum(shear_ref - thr, 0).std(0)), dtype=torch.float32, device=device)
    del ph, tref
    tm_d, ts_d = norm["tm"].to(device), norm["ts"].to(device)
    phys_std = lambda x: (physical(x * ts_d + tm_d) - pm) / ps  # normalised diffs -> standardised profiles

    n_h, n_v = len(HEIGHTS), len(PROFILE)
    strides = list(cfg["step_strides"] or []) if n_prof else []
    if strides:  # window sums of s consecutive steps (changes over s heights), scaled by their spread in the training rows
        def windows(d, st):  # (..., V, 43) -> (..., V, 43 - st + 1)
            c = (np.cumsum if isinstance(d, np.ndarray) else torch.cumsum)(d, -1)
            c = np.pad(c, [(0, 0)] * (c.ndim - 1) + [(1, 0)]) if isinstance(c, np.ndarray) else torch.nn.functional.pad(c, (1, 0))
            return c[..., st:] - c[..., :-st]
    t_idx = PROFILE.index("T")
    dz_km = torch.tensor(np.diff(HEIGHTS) / 1000.0, dtype=torch.float32, device=device)
    above2 = torch.tensor(HEIGHTS[1:] > 2000, device=device)

    def stride_loss(samples, t):
        d_s = (samples[..., :n_prof] * ts_d[:n_prof] + tm_d[:n_prof]).reshape(*samples.shape[:-1], n_v, n_h)[..., 1:]
        d_t = (t[..., :n_prof] * ts_d[:n_prof] + tm_d[:n_prof]).reshape(*t.shape[:-1], n_v, n_h)[..., 1:]
        tot = 0.0
        for st in strides:
            ws, wt = windows(d_s, st) / stride_scale[st], windows(d_t, st) / stride_scale[st]
            tot = tot + afcrps(ws.flatten(-2), wt.flatten(-2), cfg["crps_alpha"])
        return tot / len(strides)

    def superadiabatic(samples):  # mean squared excess of the lapse rate over dry-adiabatic above 2 km, in K/km
        d = (samples[..., :n_prof] * ts_d[:n_prof] + tm_d[:n_prof]).reshape(*samples.shape[:-1], n_v, n_h)
        dT = d[..., t_idx, 1:]                       # temperature change per layer (K)
        lapse = -dT / dz_km
        return torch.relu(lapse[..., above2] - 9.8).pow(2).mean()

    def shear_tail_loss(samples, t):  # threshold-weighted CRPS of |vector shear| (m/s per km): only the excess over the threshold counts
        def f(x):
            d = (x[..., :n_prof] * ts_d[:n_prof] + tm_d[:n_prof]).reshape(*x.shape[:-1], n_v, n_h)[..., 1:]
            sh = torch.hypot(d[..., PROFILE.index("u"), :], d[..., PROFILE.index("v"), :]) / dz_km
            return torch.relu(sh - shear_thr) / shear_scale
        return afcrps(f(samples), f(t), cfg["crps_alpha"])

    rh_w = cfg["rh_loss_weight"] if (n_prof and (meta or {}).get("rh_target") == "dpd") else 0.0
    iT_, iR_ = PROFILE.index("T") * len(HEIGHTS), PROFILE.index("RH") * len(HEIGHTS)

    def rh_pct(x):  # normalised differences (..., D) -> relative humidity in per cent from T and the learned coordinate ln(T - Td + 1)
        p = physical(x * ts_d + tm_d)
        T = torch.clamp(p[..., iT_:iT_ + len(HEIGHTS)], 150.0, 350.0)             # early in training the samples can be far off; the formula has a pole at 32 K and overflows
        lnd = p[..., iR_:iR_ + len(HEIGHTS)]
        td = torch.minimum(T - torch.clamp(torch.expm1(torch.clamp(lnd, max=5.0)), min=0.0), T)
        f = lambda q: 17.502 * (q - 273.16) / (q - 32.19)
        return 100.0 * torch.exp(torch.clamp(f(td) - f(T), max=0.0))            # ratio of saturation vapour pressures as one exponential, never above 100 %

    low_h = np.flatnonzero(np.asarray(HEIGHTS) <= cfg["low_top_m"])
    low_cols = torch.tensor(np.concatenate([i * n_h + low_h for i in range(n_v)]) if n_prof else [], dtype=torch.long, device=device)
    iu_, iv_ = PROFILE.index("u") * n_h if n_prof else 0, PROFILE.index("v") * n_h if n_prof else 0
    low_idx = torch.tensor(low_h, dtype=torch.long, device=device)

    def low_wind_loss(samples, t, s_std, y_std):   # C4b: vector energy score on (u, v) + CRPS of speed, near the ground, in units of about 3 m/s
        ps_, pt_ = physical(samples * ts_d + tm_d), physical(t * ts_d + tm_d)
        us, vs = ps_[..., iu_ + low_idx], ps_[..., iv_ + low_idx]                  # (B, m, K)
        ut, vt = pt_[..., iu_ + low_idx], pt_[..., iv_ + low_idx]
        es = energy_score(torch.stack([us, vs], -1).flatten(-2) / 3.0, torch.stack([ut, vt], -1).flatten(-2) / 3.0) / math.sqrt(2 * len(low_h))
        sp = afcrps(torch.hypot(us, vs) / 3.0, torch.hypot(ut, vt) / 3.0, cfg["crps_alpha"])
        return es + sp

    def score(samples, t, top=None):
        if top is not None:   # fill_mask: filled heights take the target's value, so every term below sees no error and no gradient there
            mk = (torch.arange(n_h, device=top.device) > top[..., None].long()).flatten(-2)
            mk = torch.cat([mk, mk.new_zeros(len(mk), t.shape[-1] - n_prof)], 1)                                    # surface columns are never filled
            samples = torch.where(mk[:, None], t[:, None], samples)
        s, y = phys_std(samples), phys_std(t)
        if top is not None:
            s = torch.where(mk[:, None], y[:, None], s)
        loss = afcrps(s, y, cfg["crps_alpha"]) + cfg["es_weight"] * energy_score(s, y) / math.sqrt(y.shape[-1])
        if cfg["low_weight"] != 1.0 and n_prof:
            loss = loss + (cfg["low_weight"] - 1.0) * afcrps(s[..., low_cols], y[..., low_cols], cfg["crps_alpha"])
        if cfg["wind_vec_weight"] and n_prof:
            loss = loss + cfg["wind_vec_weight"] * low_wind_loss(samples, t, s, y)
        if cfg["step_weight"] and n_prof:  # CRPS on the height-to-height steps too: level CRPS alone leaves shear too smooth
            if strides:
                loss = loss + cfg["step_weight"] * stride_loss(samples, t)
            else:
                loss = loss + cfg["step_weight"] * afcrps(samples[..., :n_prof], t[..., :n_prof], cfg["crps_alpha"])
        if rh_w:
            r_s, r_y = rh_pct(samples), rh_pct(t)
            if top is not None:
                r_s = torch.where(mk[:, None, iR_:iR_ + n_h], r_y[:, None], r_s)
            loss = loss + rh_w * afcrps(r_s / 25.0, r_y / 25.0, cfg["crps_alpha"])
        if cfg["superadiabatic_weight"] and n_prof:
            loss = loss + cfg["superadiabatic_weight"] * superadiabatic(samples)
        if cfg["shear_tail_weight"] and n_prof:
            loss = loss + cfg["shear_tail_weight"] * shear_tail_loss(samples, t)
        return loss

    groups = ([(v, slice(i * len(HEIGHTS), (i + 1) * len(HEIGHTS))) for i, v in enumerate(PROFILE)]
              + [("sfc", slice(n_prof, None))]) if n_prof else [("all", slice(None))]

    def diagnose(model, c, t):  # per-variable CRPS and spread/skill on one validation chunk: shows where the loss comes from
        s, y = phys_std(model(c, cfg["m"])), phys_std(t)
        m = s.shape[1]
        sd = (s.var(1, unbiased=True).mean(0) * (m + 1) / m).sqrt()
        rmse = ((s.mean(1) - y) ** 2).mean(0).sqrt()
        bias = (s.mean(1) - y).mean(0)
        return "  ".join(f"{g}: crps {afcrps(s[..., sl], y[..., sl]).item():.4f} ss {(sd[sl].mean() / rmse[sl].mean()).item():.2f}"
                         f" bias {bias[sl].mean().item():+.3f}" for g, sl in groups)

    gpu = str(device).startswith("cuda")
    # shortcut: every training row is normalised and copied to the device once (CPU runs keep a float32 copy in
    # RAM; fine for tests, a GPU-less full run would need ~2x the data in RAM)
    dt = torch.float16 if (gpu and cfg.get("store_dtype", "float16") != "float32") else torch.float32       # F-29: store_dtype = "float32" keeps the training rows at full precision (reference mode)
    Xc = torch.empty(len(tr_idx), cond.shape[1], dtype=dt, device=device)
    Xt = torch.empty(len(tr_idx), target.shape[1], dtype=dt, device=device)
    for i in range(0, len(tr_idx), 1_000_000):
        j = tr_idx[i:i + 1_000_000]
        Xc[i:i + len(j)] = torch.from_numpy(((cond[j] - cm) / cs).astype(np.float32)).to(device)
        Xt[i:i + len(j)] = torch.from_numpy(((targets(j) - tm) / ts).astype(np.float32)).to(device)
    vc = torch.from_numpy(((cond[va_idx] - cm) / cs).astype(np.float32)).to(device)
    vt = torch.from_numpy(((targets(va_idx) - tm) / ts).astype(np.float32)).to(device)
    Xf = vf = None
    if cfg["fill_mask"]:
        if fill_top_idx is None or not n_prof:
            raise ValueError("fill_mask needs a profile dataset built with build_dataset --fill-top (array fill_top_idx); rebuild it")
        Xf = torch.from_numpy(np.asarray(fill_top_idx[tr_idx], np.int8)).to(device)
        vf = torch.from_numpy(np.asarray(fill_top_idx[va_idx], np.int8)).to(device)
        log(f"fill_mask: {float((Xf < n_h - 1).any(1).float().mean()):.1%} of training rows have filled heights")

    mem = []
    for k in range(members):
        torch.manual_seed(cfg["seed"] + k)
        model = make_generator(cfg["arch"], cond.shape[1], target.shape[1], cfg["noise_dim"], cfg["width"], cfg["depth"],
                               linear_cols=linear_cols, **({"interactions": True} if cfg["interactions"] else {}),
                               **({"product_pairs": pp} if pp else {}), **model_kw).to(device)
        opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"], fused=gpu or None)
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: 0.5 * (1 + math.cos(math.pi * s / cfg["steps"])))
        g = torch.Generator(device).manual_seed(cfg["seed"] + k)  # this member's batch rows
        mem.append(dict(model=model, opt=opt, sched=sched, g=g, seed=cfg["seed"] + k, best=float("inf"),
                        best_state=None, bad=0, history=[], done=False,
                        ema=copy.deepcopy(model).eval() if cfg["ema_decay"] else None))

    t0 = time.time()
    for step in range(1, cfg["steps"] + 1):
        for k, M in enumerate(mem):
            if M["done"]:
                continue
            model = M["model"]
            model.train()
            idx = torch.randint(0, len(tr_idx), (cfg["batch"],), device=device, generator=M["g"])
            c, t = Xc[idx].float(), Xt[idx].float()
            with torch.autocast("cuda" if gpu else "cpu", torch.bfloat16, enabled=gpu):
                s = model(c, cfg["m_final"] if (cfg["m_final"] and step > cfg["steps"] - cfg["final_steps"]) else cfg["m"])
            loss = score(s.float(), t, None if Xf is None else Xf[idx])
            M["opt"].zero_grad(set_to_none=True)
            loss.backward()
            gnorm = torch.nn.utils.clip_grad_norm_(model.parameters(), float("inf"))  # measure only, no clipping
            M["opt"].step()
            M["sched"].step()
            if M["ema"] is not None:  # weights averaged over the last ~1/(1-decay) steps; evaluated and saved instead of the raw ones
                with torch.no_grad():
                    torch._foreach_lerp_(list(M["ema"].parameters()), list(model.parameters()), 1 - cfg["ema_decay"])
            if step % cfg["eval_every"] == 0 or step == cfg["steps"]:
                if M["ema"] is not None:
                    model = M["ema"]
                model.eval()
                # same validation noise at every check: fresh noise made early stopping chase sampling luck;
                # forking restores the training RNG afterwards, so the training run itself is unchanged
                with torch.no_grad(), torch.random.fork_rng(devices=[torch.device(device)] if gpu else []):
                    torch.manual_seed(M["seed"] + 12345)
                    vb = 8192 if cfg["arch"] == "mlp" else 1024   # the token model holds 44 tokens per sample: smaller chunks
                    v = float(sum(score(model(vc[i:i + vb], cfg["m"]), vt[i:i + vb], None if vf is None else vf[i:i + vb])
                                  * len(vc[i:i + vb])
                                  for i in range(0, len(vc), vb)) / len(vc))
                    d = diagnose(model, vc[:vb // 2 if vb < 8192 else 4096], vt[:vb // 2 if vb < 8192 else 4096])
                tag = f"member {k + 1}  " if members > 1 else ""
                log(f"{tag}step {step:6d}  train {loss.item():.4f}  val {v:.4f}  lr {M['sched'].get_last_lr()[0]:.2e}  "
                    f"grad {gnorm.item():.3f}  {time.time() - t0:.0f}s")
                log(f"    val by var (standardised; ss = spread/skill, 1 ideal): {d}")
                M["history"].append((step, loss.item(), v))
                if v < M["best"]:
                    M["best"], M["bad"] = v, 0
                    M["best_state"] = {n: x.detach().cpu().clone() for n, x in model.state_dict().items()}
                else:
                    M["bad"] += 1
                    if M["bad"] >= cfg["patience"]:
                        log(f"{tag}early stop")
                        M["done"] = True
        if all(M["done"] for M in mem):
            break

    for M in mem:                                                                               # F-30: a run whose validation never produced a finite loss has no checkpoint to save
        if M["best_state"] is None:
            raise RuntimeError(f"member seed {M['seed']}: no finite validation loss was ever recorded (NaN or inf); nothing to save. Check the data, learning rate and loss terms.")
        bad_norm = [k for k, v in norm.items() if not bool(torch.isfinite(torch.as_tensor(v)).all())]
        if bad_norm:
            raise RuntimeError(f"normalisation arrays {bad_norm} contain non-finite values; training data has NaN or inf columns")
    ckpts = [dict(state=M["best_state"], cfg={**cfg, "seed": M["seed"]}, norm=norm, n_cond=cond.shape[1],
                  n_out=target.shape[1], linear_cols=linear_cols, product_pairs=pp, sp_offset=sp_offset, val_loss=M["best"],
                  **({"model_kw": model_kw} if model_kw else {}),
                  history=M["history"], train_years=[int(year[tr_idx].min()), int(year[tr_idx].max())], val_years_range=[int(year[va_idx].min()), int(year[va_idx].max())],
                  **(meta or {})) for M in mem]
    ckpt = ckpts[0] if members == 1 else dict(members=ckpts)
    if out:
        torch.save(ckpt, out)
    return ckpt


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="configs/generator.toml")
    ap.add_argument("--max-year", type=int)
    ap.add_argument("--min-year", type=int, help="drop earlier years (same file, shorter history)")
    ap.add_argument("--point-stride", type=int, default=1,
                    help="data-needs test: keep grid points on a (0.25 x N)-degree lattice only (N=2: 1/4 of the points)")
    ap.add_argument("--hour-cycle", type=int, default=1,
                    help="data-needs test: keep 1 of every N hours, shifted by one hour each day (all hours still seen; "
                         "N=16 on the 06-21 h pilot = one hour per day, the global plan's diurnal-cycled store)")
    a = ap.parse_args()
    with open(a.config, "rb") as f:
        cfg = tomllib.load(f)
    d = load_npz(a.data)
    m = (d["year"] <= (a.max_year or 9999)) & (d["year"] >= (a.min_year or 0))
    if a.point_stride > 1 or a.hour_cycle > 1:
        n = [str(x) for x in d["cond_names"]]
        c = lambda k: np.asarray(d["cond"][:, n.index(k)], dtype=np.float64)
        on = lambda x: np.round(x / 0.25).astype(int) % a.point_stride == 0
        hour = np.round(np.mod(np.arctan2(c("hour_sin"), c("hour_cos")) / (2 * np.pi) * 24, 24)).astype(int) % 24
        doy = np.mod(np.arctan2(c("doy_sin"), c("doy_cos")) / (2 * np.pi) * 365.25, 365.25)
        day = np.asarray(d["year"]).astype(int) * 366 + np.floor(doy + 1e-6).astype(int)
        m &= on(c("lat")) & on(c("lon")) & ((hour + day) % a.hour_cycle == 0)
        print(f"thinning: point stride {a.point_stride}, hour cycle {a.hour_cycle} -> {m.sum()} of {len(m)} rows", flush=True)
    keep = np.flatnonzero(m)
    if len(keep) and keep[-1] - keep[0] + 1 == len(keep):  # contiguous years: a memory-mapped slice, no 6 GB RAM copy
        keep = slice(keep[0], keep[-1] + 1)
    cond, target, year = (d[k][keep] for k in ("cond", "target", "year"))
    meta = {k: [str(x) for x in d[k]] for k in ("cond_names", "target_names") if k in d}
    if "rh_target" in d:
        meta["rh_target"] = str(d["rh_target"])
    t0 = time.time()
    train(cond, target, np.asarray(year), cfg, out=a.out, meta=meta, members=int(cfg.pop("members", 1)),
          fill_top_idx=d["fill_top_idx"][keep] if cfg.get("fill_mask") and "fill_top_idx" in d else None)
    print(f"trained in {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
