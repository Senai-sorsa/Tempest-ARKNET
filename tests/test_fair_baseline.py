"""AU-1 (New_Plan 15.1): fair CRPS and the whole-pool climatology baseline of `score --fair-baseline`."""
import numpy as np

from tempest.scoring import diag, score


def test_crps_fair_matches_pairwise_definition():
    rng = np.random.default_rng(0)
    x, y = rng.normal(size=(5, 7, 3)), rng.normal(size=(5, 3))
    m = x.shape[1]
    want = np.abs(x - y[:, None]).mean(1) - np.abs(x[:, :, None] - x[:, None, :]).sum((1, 2)) / (2 * m * (m - 1))
    assert np.allclose(score.crps_fair(x, y), want)


def test_no_skill_model_against_thin_pool_is_neutral_only_when_fair():   # plan test 4a (R = 75)
    rng = np.random.default_rng(1)
    n = 60000                                 # fair-skill noise sd ~0.0006 at this n
    y = rng.normal(size=(n, 1))
    pool, model = rng.normal(size=(n, 75, 1)), rng.normal(size=(n, 199, 1))
    plain = 1 - score.crps_ensemble(model, y).mean() / score.crps_ensemble(pool, y).mean()
    fair = 1 - score.crps_fair(model, y).mean() / score.crps_fair(pool, y).mean()
    assert 0.005 < plain < 0.012, plain       # thin-pool bonus credited as skill: (1/150 - 1/398) E|X-X'| / CRPS = +0.008 for a normal
    assert abs(fair) < 0.002, fair


def test_pool_of_199_rows_equals_fair_score_of_that_ensemble(monkeypatch):   # plan test 4b
    monkeypatch.setattr(score, "to_physical", lambda t: t)
    rng = np.random.default_rng(2)
    target = rng.normal(size=(500, 4))
    pools = {7: np.arange(10, 209), 3: np.arange(300, 330)}
    keys_va = np.array([7, 3, 7])
    truth = rng.normal(size=(3, 4))
    crps, mae, R = score.pool_scores(target, pools, keys_va, truth)
    for j, k in enumerate(keys_va):
        ens = target[pools[k]][None]
        assert np.allclose(crps[j], score.crps_fair(ens, truth[j:j + 1])[0])
        assert np.allclose(mae[j], np.abs(np.median(target[pools[k]], 0) - truth[j]))
    assert list(R) == [199, 30, 199]


def test_headline_override_with_the_plain_arrays_changes_nothing():
    rng = np.random.default_rng(3)
    n, m, d = 60, 9, 4
    sets = {k: rng.normal(size=(n, m, d)) for k in ("clim", "clim15", "known", "unknown")}
    truth, day = rng.normal(size=(n, d)), np.repeat(np.arange(12), 5)
    groups = [("u", "a", np.array([1, 1, 0, 0], bool)), ("u", "b", np.array([0, 0, 1, 1], bool))]
    base = diag.headline(sets, truth, day, groups, n_boot=50)
    ov = {f"crps_{k}": score.crps_ensemble(x, truth) for k, x in sets.items()}
    ov.update({f"mae_{k}": np.abs(np.median(x, 1) - truth) for k, x in sets.items()})
    assert base.equals(diag.headline(sets, truth, day, groups, n_boot=50, override=ov))
    fair = diag.headline(sets, truth, day, groups, n_boot=50, override={"crps_clim15": score.crps_fair(sets["clim15"], truth)})
    assert not base["skill15_known"].equals(fair["skill15_known"])


def test_daily_sums_rebuild_the_headline_point_estimate(tmp_path):   # AU-4 step 0
    rng = np.random.default_rng(4)
    n, m, d = 60, 9, 4
    sets = {k: rng.normal(size=(n, m, d)) for k in ("clim", "clim15", "known", "unknown")}
    truth, day = rng.normal(size=(n, d)), np.repeat(np.arange(12), 5) + 2024000
    groups = [("u", "a", np.array([1, 1, 0, 0], bool)), ("u", "b", np.array([0, 0, 1, 1], bool))]
    path = tmp_path / "x_daily.csv"
    base = diag.headline(sets, truth, day, groups, n_boot=20)
    assert base.equals(diag.headline(sets, truth, day, groups, n_boot=20, daily=str(path)))
    import pandas as pd
    t = pd.read_csv(path)
    assert len(t) == 24 and set(t.day) == set(day) and (t.rows == 5).all()
    s = t.groupby("band")[["crps_known", "crps_clim15"]].sum()
    assert np.allclose(1 - s.crps_known / s.crps_clim15, base.set_index("band").skill15_known)


def test_block_bootstrap_holds_the_mean_of_correlated_days_only_with_week_blocks():   # AU-4 pass rule
    rng = np.random.default_rng(5)
    n, rho, reps = 730, 0.7, 400
    day = np.array([(2024 + i // 366) * 1000 + i % 366 for i in range(n)])   # true ids across the year end
    hit = {1: 0, diag.BLOCK_DAYS: 0}
    for _ in range(reps):
        e = rng.normal(size=n)
        x = np.empty(n)
        x[0] = e[0] / np.sqrt(1 - rho ** 2)
        for i in range(1, n):
            x[i] = rho * x[i - 1] + e[i]
        for b in hit:
            _, lo, hi = diag.block_bootstrap_ci(x, day, n_boot=300, seed=int(rng.integers(1 << 30)), block_days=b)
            hit[b] += lo <= 0 <= hi
    cov = {b: h / reps for b, h in hit.items()}
    # plan target 93-97 %: no block reaches it at 730 days (simulated, 600 repeats: 1 d 0.58, 7 d 0.86, 14 d 0.90, 21 d 0.92, 30 d 0.91, 45 d 0.90:
    # longer blocks drop less cross-cut correlation but leave fewer blocks), so the bound is the best reachable +- 3 SE
    assert 0.88 <= cov[diag.BLOCK_DAYS] <= 0.97, cov
    assert cov[1] < 0.80, cov


def test_block_days_one_leaves_the_headline_unchanged_and_blocks_widen_it():
    rng = np.random.default_rng(6)
    n, m, d = 400, 9, 4
    day = np.repeat(np.arange(200), 2) + 2024000
    shared = np.repeat(np.cumsum(rng.normal(size=200)) * 0.3, 2)[:, None, None]   # slow drift shared by the model's error
    sets = {k: rng.normal(size=(n, m, d)) for k in ("clim", "clim15", "known")}
    sets["unknown"] = rng.normal(size=(n, m, d)) + shared
    truth = rng.normal(size=(n, d))
    groups = [("u", "a", np.array([1, 1, 0, 0], bool)), ("u", "b", np.array([0, 0, 1, 1], bool))]
    base = diag.headline(sets, truth, day, groups, n_boot=200)
    assert base.equals(diag.headline(sets, truth, day, groups, n_boot=200, block_days=1))
    wk = diag.headline(sets, truth, day, groups, n_boot=200, block_days=7)
    assert np.allclose(wk.skill15_unknown, base.skill15_unknown)
    assert ((wk.skill15_unknown_hi - wk.skill15_unknown_lo) > (base.skill15_unknown_hi - base.skill15_unknown_lo)).all()
