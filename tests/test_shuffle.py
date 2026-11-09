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


def test_blended_rank_shuffle_keeps_marginals_and_interpolates():       # IL-161
    import numpy as np
    from tempest.calibrate import shuffle as S
    rng = np.random.default_rng(0)
    x = rng.normal(size=(5, 200, 6))
    tpl = rng.normal(size=(5, 200, 6))
    full = S.apply(x, tpl)
    assert np.array_equal(S.apply(x, tpl, 1.0), full)
    for w in (0.0, 0.5, 0.75):
        y = S.apply(x, tpl, w)
        assert np.allclose(np.sort(y, axis=1), np.sort(x, axis=1))                # marginals unchanged
    assert np.allclose(S.apply(x, tpl, 0.0), x)                                    # w = 0 keeps the network's own order
    def agree(a, b):                                                              # mean rank correlation between two orderings
        ra, rb = np.argsort(np.argsort(a, 1), 1), np.argsort(np.argsort(b, 1), 1)
        return float(np.mean([np.corrcoef(ra[i, :, c], rb[i, :, c])[0, 1] for i in range(5) for c in range(6)]))
    assert agree(S.apply(x, tpl, 0.5), tpl) < agree(S.apply(x, tpl, 0.75), tpl) < agree(full, tpl) + 1e-9
    assert agree(S.apply(x, tpl, 0.5), x) > agree(S.apply(x, tpl, 0.75), x) > agree(full, x)
