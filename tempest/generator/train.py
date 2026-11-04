"""Train the generator.

    python -m tempest.generator.train --data data/train/pilot.npz --out models/generator_pilot.pt [--max-year 2014]

The .npz holds `cond` (N, F) from features.features, `target` (N, D) = station-corrected profiles in
difference space (profiles.diff.to_diff per variable, flattened) followed by the surface fields, and `year`
(N,). Optional `cond_names`, `target_names`. Building it from the profile store is phase 6A work.
Validation = the last `val_years` years kept; `--max-year` drops later years for a walk-forward fold.
"""
import argparse
import math
import time
import tomllib

import numpy as np
import torch

from tempest.generator.model import Generator, energy_score

DEFAULTS = dict(noise_dim=32, width=512, depth=5, m=4, batch=4096, lr=1e-3, weight_decay=1e-4,
                steps=20000, eval_every=500, patience=10, val_years=3, val_rows=50000, seed=0)


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
    ref = np.sort(rng.choice(tr_idx, min(len(tr_idx), 1_000_000), replace=False))  # stats from 1M rows: avoids copying the full set
    cm, cs = cond[ref].mean(0), safe(cond[ref].std(0))
    tm, ts = target[ref].mean(0), safe(target[ref].std(0))
    norm = {k: torch.tensor(v, dtype=torch.float32) for k, v in dict(cm=cm, cs=cs, tm=tm, ts=ts).items()}

    def batch(idx):
        c = torch.from_numpy(((cond[idx] - cm) / cs).astype(np.float32)).to(device)
        t = torch.from_numpy(((target[idx] - tm) / ts).astype(np.float32)).to(device)
        return c, t

    model = Generator(cond.shape[1], target.shape[1], cfg["noise_dim"], cfg["width"], cfg["depth"]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: 0.5 * (1 + math.cos(math.pi * s / cfg["steps"])))
    vc, vt = batch(va_idx)

    best, best_state, bad, t0 = float("inf"), None, 0, time.time()
    for step in range(1, cfg["steps"] + 1):
        model.train()
        c, t = batch(tr_idx[rng.integers(0, len(tr_idx), cfg["batch"])])
        loss = energy_score(model(c, cfg["m"]), t)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        sched.step()
        if step % cfg["eval_every"] == 0 or step == cfg["steps"]:
            model.eval()
            with torch.no_grad():
                v = float(sum(energy_score(model(vc[i:i + 8192], cfg["m"]), vt[i:i + 8192]) * len(vc[i:i + 8192])
                              for i in range(0, len(vc), 8192)) / len(vc))
            log(f"step {step:6d}  train ES {loss.item():.4f}  val ES {v:.4f}  {time.time() - t0:.0f}s")
            if v < best:
                best, bad = v, 0
                best_state = {k: x.detach().cpu().clone() for k, x in model.state_dict().items()}
            else:
                bad += 1
                if bad >= cfg["patience"]:
                    log("early stop")
                    break

    ckpt = dict(state=best_state, cfg=cfg, norm=norm, n_cond=cond.shape[1], n_out=target.shape[1],
                val_es=best, **(meta or {}))
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
    d = np.load(a.data, mmap_mode="r")
    keep = slice(None) if a.max_year is None else np.flatnonzero(d["year"] <= a.max_year)
    cond, target, year = (np.asarray(d[k][keep]) for k in ("cond", "target", "year"))
    meta = {k: [str(x) for x in d[k]] for k in ("cond_names", "target_names") if k in d}
    train(cond, target, year, cfg, a.out, meta=meta)


if __name__ == "__main__":
    main()
