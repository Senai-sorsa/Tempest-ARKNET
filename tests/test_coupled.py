"""Coupled files: whole-sample rows preserved, physical consistency, placeholders, sha256, correlation sanity."""
import hashlib
import json
import tomllib

import numpy as np

from tempest.output import coupled
from tempest.profiles import thermo
from tempest.profiles.to_heights import HEIGHTS


def _phys(n=200, seed=0):
    rng = np.random.default_rng(seed)
    nh = len(HEIGHTS)
    base_T = np.linspace(300, 215, nh)
    shift = rng.normal(0, 3, (n, 1))
    T = base_T + shift + rng.normal(0, 0.5, (n, nh))
    u = rng.normal(5, 5, (n, 1)) + np.linspace(0, 20, nh) + rng.normal(0, 1, (n, nh))
    v = rng.normal(0, 3, (n, nh))
    RH = np.clip(rng.normal(40, 20, (n, nh)), 0, 100)
    sfc = np.stack([T[:, 0] + 1, 87000 + rng.normal(0, 300, n), RH[:, 0]], 1)
    return np.concatenate([u, v, T, RH, sfc], 1)


def test_rows_preserved_and_consistent():
    ph = _phys()
    nh = len(HEIGHTS)
    a, meta = coupled.build(ph, 1400.0, np.zeros((len(ph), 5)))
    assert np.allclose(a["u"], ph[:, :nh], atol=1e-3) and np.allclose(a["T"], ph[:, 2 * nh:3 * nh], atol=1e-3)
    k = 17  # one row alone gives the same derived values as the batch: nothing leaks between rows
    one = thermo.column(HEIGHTS, ph[k, 2 * nh:3 * nh], ph[k, 3 * nh:4 * nh], ph[k, 4 * nh + 1], t_sfc=ph[k, 4 * nh], rh_sfc=ph[k, 4 * nh + 2], z_sfc=1400.0)
    assert np.allclose(a["rho"][k], one["rho"], rtol=1e-5) and np.allclose(a["a"][k], one["a"], rtol=1e-5)
    assert np.allclose(a["height_asl"], 1400 + HEIGHTS)
    assert np.isnan(a["w"]).all() and np.isnan(a["gust_mu"]).all() and meta["coupling"] == "whole-sample"
    assert (np.diff(a["p"], axis=1) < 0).all()


def test_files_and_sha(tmp_path):
    ph = _phys()
    a, meta = coupled.build(ph, 1400.0, np.zeros((len(ph), 5)), query=dict(lat=33.0))
    paths = coupled.write(str(tmp_path), a, meta)
    z = np.load(paths["samples"])
    assert json.loads(str(z["metadata"]))["coupling"] == "whole-sample" and z["u"].shape == (len(ph), len(HEIGHTS))
    t = tomllib.loads(open(paths["toml"], encoding="utf-8").read())
    assert t["coupling"]["samples_sha256"] == hashlib.sha256(open(paths["samples"], "rb").read()).hexdigest()
    c = np.load(paths["coupling"])
    d = c["corr_full"]
    assert np.allclose(np.diag(d), 1) and np.allclose(d, d.T, atol=1e-9) and np.abs(d).max() <= 1 + 1e-9
    assert c["eof_modes"].shape[1] == d.shape[0] and abs(c["eof_variance"].sum()) <= 1.0 + 1e-6


def test_temperature_density_are_anticorrelated_in_the_data():
    ph = _phys(400)
    a, meta = coupled.build(ph, 1400.0, np.zeros((len(ph), 5)))
    c = coupled.coupling(a)
    vs = list(c["variables"])
    assert c["corr_vars_at_height"][10, vs.index("T"), vs.index("rho")] < -0.5  # warm column is thinner at a given height
