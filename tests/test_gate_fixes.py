"""IL-109 / IL-111 gate fixes: optional tolerance and Gaussian-baseline margin; defaults must not change old verdicts."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from compare_headline import compare  # noqa: E402
from tempest.scoring import diag  # noqa: E402


def _sets(with_gauss=True, seed=0):
    r = np.random.default_rng(seed)
    N, m, D = 200, 12, 4
    truth = r.normal(size=(N, D))
    mk = lambda s: r.normal(size=(N, m, D)) * s
    sets = dict(clim=mk(2), clim15=mk(2), known=mk(1), unknown=mk(1))
    if with_gauss:
        sets["gauss"] = mk(1.5)
    grp = [("t", "a", np.arange(D) < 2), ("t", "b", np.arange(D) >= 2)]
    return diag.headline(sets, truth, np.arange(N) // 4, grp, n_boot=20)


def test_headline_gauss_columns_are_additive():
    with_g, without = _sets(True), _sets(False)
    assert "margin_gauss_unknown" in with_g and "skill15_gauss" in with_g
    assert not any("gauss" in c for c in without.columns)
    assert set(without.columns) <= set(with_g.columns)


def test_compare_defaults_unchanged_and_tol_and_gauss_rule():
    t = _sets(True)
    worse = t.copy()
    for c in ("skill15_unknown", "skill15_unknown_lo", "skill15_unknown_hi"):
        worse[c] = worse[c] - 0.0005
    _, s0 = compare(t, worse)
    assert not s0["pass_a"]                      # default: strict
    _, s1 = compare(t, worse, tol=0.001)
    assert s1["pass_a"]                          # tolerance applies only when asked
    _, s2 = compare(t, t, require_gauss=True)
    assert s2["pass_d"] == (t["margin_gauss_unknown"].mean() > 0 and not (t["margin_gauss_unknown_hi"] < 0).any())
    _, s3 = compare(t.drop(columns=[c for c in t.columns if "gauss" in c]), t.drop(columns=[c for c in t.columns if "gauss" in c]), require_gauss=True)
    assert not s3["passed"]                      # asked for the rule but no data: fail safe
