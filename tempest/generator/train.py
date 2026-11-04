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

DEFAULTS = dict(noise_dim=32, width=512, depth=4, m=4, crps_alpha=0.95, es_weight=0.1, step_weight=0.0, batch=4096, lr=1e-3, weight_decay=1e-4,
                steps=20000, eval_every=500, patience=10, val_years=3, val_block_frac=0.0, val_rows=50000, seed=0,
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


def split(year, cond, names, cfg):
    """-> (train, validation) row masks. Tail years by default; with val_block_frac, 14-day blocks from every year
    (the same blocks for every member and seed) with a 3-day gap dropped on each side."""
    if not cfg.get("val_block_frac"):
        val = year > year.max() - cfg["val_years"]
        return ~val, val
    doy = np.arctan2(cond[:, names.index("doy_sin")], cond[:, names.index("doy_cos")]) % (2 * np.pi) / (2 * np.pi) * 365.25
    day = year.astype(np.int64) * 366 + doy.astype(np.int64)
    vb = np.random.default_rng(12345).random(int(day.max()) // 14 + 2) < cfg["val_block_frac"]
    val = vb[day // 14]
    return ~(val | vb[(day - 3) // 14] | vb[(day + 3) // 14]), val


def train(cond, target, year, cfg=None, out=None, device=None, log=print, meta=None, members=1):
    """-> one checkpoint, or dict(members=[...]) when members > 1 (member k uses seed + k)."""
    cfg = {**DEFAULTS, **(cfg or {})}
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    rng = np.random.default_rng(cfg["seed"])
    torch.set_float32_matmul_precision("high")

    year = np.asarray(year)
    tr, val = split(year, cond, list((meta or {}).get("cond_names", [])), cfg)
    tr_idx, va_idx = np.flatnonzero(tr), np.flatnonzero(val)
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
        loss = afcrps(s, y, cfg["crps_alpha"]) + cfg["es_weight"] * energy_score(s, y) / math.sqrt(y.shape[-1])
        if cfg["step_weight"] and n_prof:  # CRPS on the height-to-height steps too: level CRPS alone leaves shear too smooth
            loss = loss + cfg["step_weight"] * afcrps(samples[..., :n_prof], t[..., :n_prof], cfg["crps_alpha"])
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
    dt = torch.float16 if gpu else torch.float32
    Xc = torch.empty(len(tr_idx), cond.shape[1], dtype=dt, device=device)
    Xt = torch.empty(len(tr_idx), target.shape[1], dtype=dt, device=device)
    for i in range(0, len(tr_idx), 1_000_000):
        j = tr_idx[i:i + 1_000_000]
        Xc[i:i + len(j)] = torch.from_numpy(((cond[j] - cm) / cs).astype(np.float32)).to(device)
        Xt[i:i + len(j)] = torch.from_numpy(((targets(j) - tm) / ts).astype(np.float32)).to(device)
    vc = torch.from_numpy(((cond[va_idx] - cm) / cs).astype(np.float32)).to(device)
    vt = torch.from_numpy(((targets(va_idx) - tm) / ts).astype(np.float32)).to(device)

    mem = []
    for k in range(members):
        torch.manual_seed(cfg["seed"] + k)
        model = Generator(cond.shape[1], target.shape[1], cfg["noise_dim"], cfg["width"], cfg["depth"],
                          linear_cols=linear_cols).to(device)
        opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"], fused=gpu or None)
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: 0.5 * (1 + math.cos(math.pi * s / cfg["steps"])))
        g = torch.Generator(device).manual_seed(cfg["seed"] + k)  # this member's batch rows
        mem.append(dict(model=model, opt=opt, sched=sched, g=g, seed=cfg["seed"] + k, best=float("inf"),
                        best_state=None, bad=0, history=[], done=False))

    t0 = time.time()
    for step in range(1, cfg["steps"] + 1):
        for k, M in enumerate(mem):
            if M["done"]:
                continue
            model = M["model"]
            model.train()
            idx = torch.randint(0, len(tr_idx), (cfg["batch"],), device=device, generator=M["g"])
            c, t = Xc[idx].float(), Xt[idx].float()
            with torch.autocast("cuda", torch.bfloat16, enabled=gpu):
                s = model(c, cfg["m"])
            loss = score(s.float(), t)
            M["opt"].zero_grad(set_to_none=True)
            loss.backward()
            gnorm = torch.nn.utils.clip_grad_norm_(model.parameters(), float("inf"))  # measure only, no clipping
            M["opt"].step()
            M["sched"].step()
            if step % cfg["eval_every"] == 0 or step == cfg["steps"]:
                model.eval()
                # same validation noise at every check: fresh noise made early stopping chase sampling luck;
                # forking restores the training RNG afterwards, so the training run itself is unchanged
                with torch.no_grad(), torch.random.fork_rng(devices=[torch.device(device)] if gpu else []):
                    torch.manual_seed(M["seed"] + 12345)
                    v = float(sum(score(model(vc[i:i + 8192], cfg["m"]), vt[i:i + 8192])
                                  * len(vc[i:i + 8192])
                                  for i in range(0, len(vc), 8192)) / len(vc))
                    d = diagnose(model, vc[:4096], vt[:4096])
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

    ckpts = [dict(state=M["best_state"], cfg={**cfg, "seed": M["seed"]}, norm=norm, n_cond=cond.shape[1],
                  n_out=target.shape[1], linear_cols=linear_cols, sp_offset=sp_offset, val_loss=M["best"],
                  history=M["history"], **(meta or {})) for M in mem]
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
    a = ap.parse_args()
    with open(a.config, "rb") as f:
        cfg = tomllib.load(f)
    d = load_npz(a.data)
    keep = np.flatnonzero((d["year"] <= (a.max_year or 9999)) & (d["year"] >= (a.min_year or 0)))
    if len(keep) and keep[-1] - keep[0] + 1 == len(keep):  # contiguous years: a memory-mapped slice, no 6 GB RAM copy
        keep = slice(keep[0], keep[-1] + 1)
    cond, target, year = (d[k][keep] for k in ("cond", "target", "year"))
    meta = {k: [str(x) for x in d[k]] for k in ("cond_names", "target_names") if k in d}
    t0 = time.time()
    train(cond, target, np.asarray(year), cfg, out=a.out, meta=meta, members=int(cfg.pop("members", 1)))
    print(f"trained in {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
