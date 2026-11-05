"""Schaake shuffle: marginals unchanged, dependence taken from the template."""
import numpy as np

from tempest.calibrate import shuffle


def test_marginals_kept_and_dependence_copied():
    rng = np.random.default_rng(0)
    n, m, d = 40, 500, 6
    x = rng.normal(0, 1, (n, m, d))                              # independent columns
    z = rng.normal(0, 1, (n, m, 1))
    template = z + 0.3 * rng.normal(0, 1, (n, m, d))             # strongly dependent columns
    y = shuffle.apply(x, template)
    assert np.allclose(np.sort(y, 1), np.sort(x, 1))
    c = lambda a: np.mean([np.corrcoef(a[i, :, 0], a[i, :, 1])[0, 1] for i in range(n)])
    assert abs(c(x)) < 0.1 and c(y) > 0.8 and abs(c(y) - c(template)) < 0.1
