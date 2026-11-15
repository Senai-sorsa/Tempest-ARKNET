"""Shared helpers for the New_Plan section 17 scripts (UR1-UR15). Read-only: nothing here changes the repository or the tool.
Self-check:  PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/ur_common.py
"""
import io
import os
from contextlib import contextmanager, redirect_stdout

import numpy as np

import kit_common as K

M = os.path.join(K.REPO, "models")
MEM = os.path.join(K.REPO, "data", "kit", "ur_members")       # member files of section 17 re-scores (data/ is never committed)
METHOD = "network + PIT recal + range map + Schaake shuffle"
NEAR, BEYOND = (1, 3, 5, 7), 9
BLOCK = 21                                                    # AU-4 default day blocks


def var_of_col():
    """(176,) variable name of each Mode F column (4 variables x 44 heights, modeF.PROFILE order)."""
    from tempest.forecast.modeF import HEIGHTS, PROFILE
    return np.repeat(np.asarray(PROFILE), len(HEIGHTS))


def masks():
    """(176, 16) column weights of the 16 variable x band cells, each column of a cell weighted equally (as il6_modeF.py)."""
    from tempest.forecast import modeP as P
    m = np.stack([s for _, _, s in P.names()], 1).astype(float)
    return m / m.sum(0)


def load_members(path):
    """--save-members file -> dict(x (n, m, C) float32, truth (n, C), lead (n,), day (n,), lead_days (n,))."""
    z = np.load(path)
    return dict(x=z["med"][:, None, :] + z["dev"].astype(np.float32), truth=z["truth"], lead=z["lead"], day=z["day"], lead_days=z["lead_days"])


def score(x, truth, chunk=500):
    """-> (row CRPS mean over the 16 cells (n,), row cov99 mean over the 16 cells (n,)); the scorer's own functions, in chunks to save RAM."""
    from tempest.scoring.score import coverage90, crps_ensemble
    w = masks()
    c, v = np.empty(len(truth)), np.empty(len(truth))
    for i in range(0, len(truth), chunk):
        s = slice(i, i + chunk)
        c[s] = (crps_ensemble(x[s], truth[s]) @ w).mean(1)
        v[s] = (coverage90(x[s], truth[s], 0.99).astype(float) @ w).mean(1)
    return c, v


def by_lead(values, lead, leads=NEAR + (BEYOND,)):
    return np.array([np.nanmean(values[lead == L]) if (lead == L).any() else np.nan for L in leads])


def pooled_rows(stem, years=("", "_t2021")):
    """<stem><x>_rows.npz of several test years -> one dict (lead, day, crps). Missing files raise."""
    r = [np.load(os.path.join(M, stem + x + "_rows.npz")) for x in years]
    return {k: np.concatenate([v[k] for v in r]) for k in ("lead", "day", "crps")}


def have_rows(stem, years=("", "_t2021")):
    return all(os.path.exists(os.path.join(M, stem + x + "_rows.npz")) for x in years)


def paired(a, b, L, draws=1000):
    """rows dicts of two arms (same rows asserted) -> (percent change, mean diff, lo, hi) of a minus b at lead bin L, 21-day blocks."""
    assert (a["day"] == b["day"]).all() and (a["lead"] == b["lead"]).all(), "arms scored on different rows"
    k = b["lead"] == L
    dm, lo, hi = K.block_boot(a["crps"][k] - b["crps"][k], list(b["day"][k] // BLOCK), draws=draws)
    return 100 * (a["crps"][k].mean() / b["crps"][k].mean() - 1), dm, lo, hi


@contextmanager
def captured_report():
    """Inside the block, K.report prints nothing and writes nothing; the lines land in the yielded list (to wrap an older kit script)."""
    got, old = [], K.report
    K.report = lambda name, lines: got.extend(lines)
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            yield got
    finally:
        K.report = old


def _selfcheck():
    v = var_of_col()
    assert v.shape == (176,) and len(set(v.tolist())) == 4
    w = masks()
    assert w.shape == (176, 16) and np.allclose(w.sum(0), 1)
    rng = np.random.default_rng(0)
    y = rng.normal(size=(30, 176)).astype(np.float32)
    x = rng.normal(size=(30, 50, 176)).astype(np.float32)
    c, cv = score(x, y, chunk=7)
    assert c.shape == (30,) and 0.2 < c.mean() < 1.0 and 0.9 < cv.mean() <= 1.0
    with captured_report() as got:
        K.report("never_written", ["a", "b"])
        print("hidden")
    assert got == ["a", "b"] and K.report.__name__ == "report"
    print("ur_common selfcheck ok")


if __name__ == "__main__":
    _selfcheck()
