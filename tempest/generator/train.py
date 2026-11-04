"""Train the generator.

    python -m tempest.generator.train --data data/train/pilot.npz --out models/generator_pilot.pt [--max-year 2014]

The .npz holds `cond` (N, F) from features.features, `target` (N, D) = station-corrected profiles in
difference space (profiles.diff.to_diff per variable, flattened) followed by the surface fields, and `year`
(N,). Optional `cond_names`, `target_names`. Building it from the profile store is phase 6A work.
Validation = the last `val_years` years kept; `--max-year` drops later years for a walk-forward fold.
Loss (training and validation) is scored on rebuilt profiles (differences summed back up, standardised), so
errors that pile up with height count: per-value almost-fair CRPS (as ECMWF AIFS-CRPS) + es_weight x energy score
/ sqrt(D), the second term keeping heights jointly consistent.
`members` (config) trains that many seeds and saves them in one file; Sampler splits samples evenly across them.
`linear_features` (year and the ENSO/QBO indices) enter as straight-line effects, see model.Generator.
"""
import argparse
import math
import struct
import time
import tomllib
import zipfile

import numpy as np
import torch

from tempest.generator.model import Generator, afcrps, energy_score
from tempest.generator.sample import standard_pressure
from tempest.profiles.to_heights import HEIGHTS, PROFILE

DEFAULTS = dict(noise_dim=32, width=512, depth=4, m=4, es_weight=0.1, step_weight=0.0, batch=4096, lr=1e-3, weight_decay=1e-4,
                steps=20000, eval_every=500, patience=10, val_years=3, val_rows=50000, seed=0,
                linear_features=["year", "oni", "wwv", "qbo30", "qbo50"])
N_PROF = len(HEIGHTS) * len(PROFILE)  # leading target columns that are profile differences (real data only)


def load_npz(path):
    """Uncompressed .npz (np.savez) -> dict of read-only memory maps. np.load ignores mmap_mode for .npz and
    would read all 6 GB into RAM; here rows are read from disk when indexed. Compressed files fall back to np.load."""
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


def train(cond, target, year, cfg=None, out=None, device=None, log=print, meta=None):
    cfg = {**DEFAULTS, **(cfg or {})}
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(cfg["seed"])
    rng = np.random.default_rng(cfg["seed"])
    torch.set_float32_matmul_precision("high")

    year = np.asarray(year)
    val = year > year.max() - cfg["val_years"]
    tr_idx, va_idx = np.flatnonzero(~val), np.flatnonzero(val)
    if len(tr_idx) == 0 or len(va_idx) == 0:
        raise ValueError("need both training and validation years; check val_years and the year array")
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
    tref = targets(ref)
    tm, ts = tref.mean(0), safe(tref.std(0))
    norm = {k: torch.tensor(v, dtype=torch.float32) for k, v in dict(cm=cm, cs=cs, tm=tm, ts=ts).items()}
    linear_cols = [names.index(k) for k in cfg["linear_features"] if k in names]
    n_prof = N_PROF if len((meta or {}).get("target_names", [])) == N_PROF + 3 else 0

    def physical(r):  # raw targets -> profiles rebuilt from the differences; works on numpy and torch
        if not n_prof:
            return r
        p = r[..., :n_prof].reshape(*r.shape[:-1], len(PROFILE), len(HEIGHTS)).cumsum(-1)
        rest = r[..., n_prof:]
        return (np.concatenate if isinstance(r, np.ndarray) else torch.cat)([p.reshape(*r.shape[:-1], n_prof), rest], -1)

    ph = physical(tref)
    pm, ps = (torch.tensor(a, dtype=torch.float32, device=device) for a in (ph.mean(0), safe(ph.std(0))))
    del ph, tref
    tm_d, ts_d = norm["tm"].to(device), norm["ts"].to(device)
    phys_std = lambda x: (physical(x * ts_d + tm_d) - pm) / ps  # normalised diffs -> standardised profiles

    def score(samples, t):
        s, y = phys_std(samples), phys_std(t)
        loss = afcrps(s, y) + cfg["es_weight"] * energy_score(s, y) / math.sqrt(y.shape[-1])
        if cfg["step_weight"] and n_prof:  # CRPS on the height-to-height steps too: level CRPS alone leaves shear too smooth
            loss = loss + cfg["step_weight"] * afcrps(samples[..., :n_prof], t[..., :n_prof])
        return loss

    def batch(idx):
        c = torch.from_numpy(((cond[idx] - cm) / cs).astype(np.float32)).to(device)
        t = torch.from_numpy(((targets(idx) - tm) / ts).astype(np.float32)).to(device)
        return c, t

    model = Generator(cond.shape[1], target.shape[1], cfg["noise_dim"], cfg["width"], cfg["depth"],
                      linear_cols=linear_cols).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: 0.5 * (1 + math.cos(math.pi * s / cfg["steps"])))
    vc, vt = batch(va_idx)

    best, best_state, bad, t0, history = float("inf"), None, 0, time.time(), []
    for step in range(1, cfg["steps"] + 1):
        model.train()
        c, t = batch(tr_idx[rng.integers(0, len(tr_idx), cfg["batch"])])
        loss = score(model(c, cfg["m"]), t)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        sched.step()
        if step % cfg["eval_every"] == 0 or step == cfg["steps"]:
            model.eval()
            with torch.no_grad():
                v = float(sum(score(model(vc[i:i + 8192], cfg["m"]), vt[i:i + 8192])
                              * len(vc[i:i + 8192])
                              for i in range(0, len(vc), 8192)) / len(vc))
            log(f"step {step:6d}  train {loss.item():.4f}  val {v:.4f}  {time.time() - t0:.0f}s")
            history.append((step, loss.item(), v))
            if v < best:
                best, bad = v, 0
                best_state = {k: x.detach().cpu().clone() for k, x in model.state_dict().items()}
            else:
                bad += 1
                if bad >= cfg["patience"]:
                    log("early stop")
                    break

    ckpt = dict(state=best_state, cfg=cfg, norm=norm, n_cond=cond.shape[1], n_out=target.shape[1],
                linear_cols=linear_cols, sp_offset=sp_offset, val_loss=best, history=history, **(meta or {}))
    if out:
        torch.save(ckpt, out)
    return ckpt


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="configs/generator.toml")
    ap.add_argument("--max-year", type=int)
    a = ap.parse_args()
    with open(a.config, "rb") as f:
        cfg = tomllib.load(f)
    d = load_npz(a.data)
    keep = slice(None) if a.max_year is None else np.flatnonzero(d["year"] <= a.max_year)
    cond, target, year = (np.asarray(d[k][keep]) for k in ("cond", "target", "year"))
    meta = {k: [str(x) for x in d[k]] for k in ("cond_names", "target_names") if k in d}
    members, seed = int(cfg.pop("members", 1)), int(cfg.get("seed", DEFAULTS["seed"]))
    ckpts = []
    for k in range(members):
        print(f"member {k + 1}/{members}", flush=True)
        ckpts.append(train(cond, target, year, {**cfg, "seed": seed + k}, meta=meta))
        torch.save(ckpts[0] if members == 1 else dict(members=ckpts), a.out)  # saved after each: a crash keeps the finished ones


if __name__ == "__main__":
    main()
