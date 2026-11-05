import zipfile

import numpy as np

from tempest.calibrate.station import apply, correct, fit, read_igra, to_grid
from tempest.profiles.diff import to_diff
from tempest.profiles.to_heights import HEIGHTS


def test_correction_matches_balloon_mean_and_spread():
    rng = np.random.default_rng(0)
    era = rng.normal(0, 1, (6000, 4, len(HEIGHTS))).astype(np.float32)
    obs = (2 + 0.5 * era + rng.normal(0, 1, era.shape)).astype(np.float32)  # balloon = biased, damped + own detail
    g = rng.integers(0, 2, 6000)
    t = fit(era[:4000], obs[:4000], g[:4000], 2)
    out = apply(t, era[4000:], g[4000:], rng)
    raw = out[:, :3]  # first 3 variables (the 4th, RH, is clipped to 0-100)
    assert abs(raw.mean() - 2) < 0.05 and abs(raw.std() / obs[4000:, :3].std() - 1) < 0.05
    assert np.allclose(t["b"][:, :3], 0.5, atol=0.1) and (t["n"] > 0).all()


def test_correct_runs_on_difference_view():
    rng = np.random.default_rng(1)
    era = rng.normal(280, 5, (500, 4, len(HEIGHTS))).astype(np.float32)
    t = fit(era, era + 1, np.zeros(500, int), 16)
    t |= dict(lat=np.array([31.87, 31.95]), lon=np.array([-106.7, -102.19]))
    out = correct(t, to_diff(era[:10]), np.full(10, 31.9), np.full(10, -106.5), np.full(10, 1), np.full(10, 17.0), rng)
    assert np.allclose(np.cumsum(out, -1)[:, :3], era[:10, :3] + 1, atol=1e-3)  # group 0: Santa Teresa, DJF, 00Z (~17 h solar)


def test_to_grid_interpolates_and_leaves_wide_gaps_missing():
    h = np.array([0.0, 40, 1000, 5000, 5500])
    y = to_grid(h, h * 2)
    assert np.allclose(y[HEIGHTS <= 1000], 2 * HEIGHTS[HEIGHTS <= 1000])
    assert np.isnan(y[(HEIGHTS > 1000) & (HEIGHTS < 5000)]).all() and y[HEIGHTS == 5000] == 10000


def test_read_igra_parses_fixed_width(tmp_path):
    def row(p, gph, t, rh, u, v):
        f = [p, gph, gph, t] + [-99999] * 7 + [rh, rh, -99999, u, -99999, v, -99999, -99999]
        return "".join(f"{x:7d} " for x in f).rstrip()
    lines = ["#USM00072364 2020 01 01 00 2306    3 header rest"]
    lines += [row(87488, 1254, 2837, 260, -2, -36), row(85000, 1492, 2809, 294, -29, -26),
              row(70000, 3062, 2721, 402, 31, 48)]
    lines += ["#USM00072364 2020 01 01 18 9999    1 skipped", row(87000, 1254, 2837, 260, 0, 0)]
    with zipfile.ZipFile(tmp_path / "s.zip", "w") as z:
        z.writestr("s.txt", "\n".join(lines) + "\n")
    t, prof, sfc = read_igra(tmp_path / "s.zip", 2020, 2020)
    assert len(t) == 1 and str(t[0]) == "2020-01-01 00:00:00"
    assert np.allclose(sfc[0], [283.7, 87488, 26.0])
    assert np.isclose(prof[0, 2, 0], 283.7 - 2.8 * 10 / 238, atol=0.05)  # T near the ground, K
    assert np.isnan(prof[0, :, HEIGHTS > 1900]).all()


def test_spread_calibration_fixes_too_narrow_ranges():
    from tempest.calibrate import spread
    from tempest.scoring.score import coverage90
    rng = np.random.default_rng(3)
    d = 179  # full output width, so clip_ranges hits the RH columns (values here stay inside 0-100)
    mu = rng.normal(50, 5, (8000, 1, d))
    truth = (mu[:, 0] + rng.standard_t(5, (8000, d)) * 3).astype(np.float32)  # heavy-tailed real spread
    samples = (mu + rng.normal(0, 1.5, (8000, 199, d))).astype(np.float32)  # model: too narrow, too light-tailed
    t = spread.fit(samples[:4000], truth[:4000])  # keep=20 of 199 members, as in main
    raw, cal = (coverage90(x, truth[4000:], 0.99).mean() for x in (samples[4000:], spread.apply(t, samples[4000:])))
    assert raw < 0.8 and abs(cal - 0.99) < 0.005


def test_diag_columns_reads_calibrated_and_biased_ensembles():
    from tempest.scoring import diag
    rng = np.random.default_rng(0)
    y = rng.normal(size=(20000, 2))
    x = rng.normal(size=(20000, 199, 2))
    x[..., 1] += 1.0  # second column biased high
    c = diag.columns(x, y)
    assert abs(c.ss_ratio[0] - 1) < 0.05 and abs(c.miss_lo[0] - 0.005) < 0.003 and abs(c.bias[0]) < 0.03
    assert c.bias[1] > 0.9 and c.miss_lo[1] > 0.03 and c.miss_hi[1] < 0.003


def test_leftovers_follow_moisture_and_old_maps_still_apply():
    rng = np.random.default_rng(2)
    level = rng.uniform(10, 90, (3000, 1, 1)).astype(np.float32)  # how moist each sounding is
    era = level + rng.normal(0, 2, (3000, 4, len(HEIGHTS))).astype(np.float32)
    obs = era + rng.normal(0, 1, era.shape).astype(np.float32) * (level > 60) * 10  # scatter only when moist
    t = fit(era, obs, np.zeros(3000, int), 1)
    moist, dry = level[:, 0, 0] > 70, level[:, 0, 0] < 30
    sd = lambda sel: (apply(t, era[sel], np.zeros(sel.sum(), int), rng) - era[sel])[:, 0].std()
    assert sd(moist) > 3 * sd(dry)
    old = dict(a=t["a"], b=t["b"], pool=t["pool"][:, 1], n=t["n"][:, 1])
    assert apply(old, era[:5], np.zeros(5, int), rng).shape == (5, 4, len(HEIGHTS))


def test_apply_refuses_a_map_fitted_with_another_member_count():
    import pytest

    from tempest.calibrate import spread
    t = dict(qz=np.tile(spread.LEVELS[:, None], (1, 2)), qu=np.tile(spread.LEVELS[:, None], (1, 2)), m=np.array(199))
    with pytest.raises(ValueError):
        spread.apply(t, np.random.default_rng(0).normal(size=(3, 50, 2)).astype(np.float32))


def test_headline_bootstrap():
    from tempest.scoring import diag
    rng = np.random.default_rng(0)
    n, m, d = 400, 49, 3
    truth = rng.normal(size=(n, d))
    good = truth[:, None, :] + rng.normal(scale=0.3, size=(n, m, d))  # sharp and centred: should beat climatology
    clim = rng.normal(size=(n, m, d))
    groups = [("T", "a", np.array([1, 1, 0], bool)), ("T", "b", np.array([0, 0, 1], bool))]
    tab = diag.headline(dict(clim=clim, clim15=clim, known=good, unknown=clim), truth, np.arange(n) // 4, groups, n_boot=200)
    assert len(tab) == 2 and (tab.skill_known > 0.3).all() and (tab.skill_unknown.abs() < 1e-12).all()
    assert (tab.skill_known_lo <= tab.skill_known).all() and (tab.skill_known <= tab.skill_known_hi).all()
    assert (tab.mae_known < tab.mae_clim).all() and tab.cov99_unknown.between(0.9, 1).all()


def test_calib_provenance(tmp_path):
    import pytest
    from tempest.calibrate import spread
    m1, m2, c = tmp_path / "a.pt", tmp_path / "b.pt", tmp_path / "a.calib.npz"
    m1.write_bytes(b"model one"); m2.write_bytes(b"model two")
    np.savez(c, m=5, model_sha=spread.model_hash(m1))
    assert int(spread.load(c, m1)["m"]) == 5
    with pytest.raises(SystemExit):
        spread.load(c, m2)
    np.savez(c, m=5)  # old files without a hash still load
    assert int(spread.load(c, m2)["m"]) == 5
