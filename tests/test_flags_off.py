"""Flags-off guard: a tiny fixed-seed training run must give exactly the numbers recorded before the Phase 2 changes.

`tests/golden_train.json` was written by the code of commit aa2e009 (before any Phase 2 edit) with
`python tests/test_flags_off.py --write`. If a later change moves these numbers while every new flag is off, that
change broke the old behaviour.
"""
import hashlib
import json
import os
import sys

import numpy as np
import torch

from tempest.generator.features import FEATURES
from tempest.generator.build_dataset import target_names
from tempest.generator.train import train

GOLDEN = os.path.join(os.path.dirname(__file__), "golden_train.json")


def run(extra_cfg=None, steep=False):
    rng = np.random.default_rng(7)
    n = 6000
    cond = rng.normal(size=(n, len(FEATURES))).astype(np.float32)
    cond[:, FEATURES.index("year")] = np.repeat(np.arange(2000, 2012), n // 12)
    d = 4 * 44 + 3
    base = rng.normal(size=(n, d)).astype(np.float32) * 0.3
    base[:, :176] += cond[:, :1] * 0.5                      # something to learn
    base[:, 2 * 44] += 280                                   # T surface ~ 280 K so physical() is sane
    if steep:  # temperature falling 12 K/km above 2 km (all layers super-adiabatic), so the hinge has something to push on
        from tempest.profiles.to_heights import HEIGHTS
        base[:, 2 * 44 + 1:3 * 44] = (-12.0 * np.diff(HEIGHTS) / 1000.0)[None, :]
    year = cond[:, FEATURES.index("year")].astype(np.int16)
    cfg = dict(width=32, depth=2, noise_dim=4, batch=256, steps=40, eval_every=20, val_years=2, lr=2e-3, step_weight=0.5,
               val_rows=1000, **(extra_cfg or {}))
    torch.manual_seed(0)
    ck = train(cond, base, year, cfg, device="cpu", log=lambda *_: None, members=2,
               meta=dict(cond_names=list(FEATURES), target_names=target_names()))
    out = {}
    for k, m in enumerate(ck["members"]):
        h = hashlib.sha256()
        for name in sorted(m["state"]):
            h.update(m["state"][name].numpy().tobytes())
        out[f"member{k}"] = dict(val=[x[2] for x in m["history"]], train=[x[1] for x in m["history"]], sha=h.hexdigest()[:16])
    return out


def test_flags_off_matches_golden():
    got = run()
    want = json.load(open(GOLDEN, encoding="utf-8"))
    assert got == want


if __name__ == "__main__":
    if "--write" in sys.argv:
        with open(GOLDEN, "w", encoding="utf-8") as f:
            json.dump(run(), f, indent=1)
        print("wrote", GOLDEN)


def test_phase2_loss_flags_run_and_change_results():
    base = run()
    for extra in (dict(step_strides=[1, 2, 4, 8, 16]), dict(ema_decay=0.9)):
        got = run(extra)
        v = got["member0"]["val"] + got["member0"]["train"]
        assert np.isfinite(v).all(), extra
        assert got != base, extra
    steep0, steep1 = run(steep=True), run(dict(superadiabatic_weight=1.0), steep=True)
    assert np.isfinite(steep1["member0"]["val"]).all() and steep1 != steep0  # the hinge acts when layers are too steep
    assert run(dict(superadiabatic_weight=0.01)) == base                       # and does nothing when none are


def test_shear_tail_flag_runs_changes_results_and_off_is_golden():
    got = run(dict(shear_tail_weight=0.3))
    assert np.isfinite(got["member0"]["val"]).all() and got != run()
    assert run(dict(shear_tail_weight=0.0)) == json.load(open(GOLDEN, encoding="utf-8"))
