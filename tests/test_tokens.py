"""Height-token generator: same interface as Generator, output order and shape, noise makes samples differ, mlp stays the default."""
import torch

from tempest.generator import train
from tempest.generator.model import Generator, TokenGenerator, make_generator


def test_shapes_noise_and_linear_branch():
    torch.manual_seed(0)
    g = TokenGenerator(n_cond=12, n_out=44 * 4 + 3, noise_dim=8, width=64, depth=2, linear_cols=[0, 1], d=32, heads=4)
    x = torch.randn(5, 12)
    y = g(x, m=3)
    assert y.shape == (5, 3, 179) and g.n_out == 179
    assert (y[:, 0] - y[:, 1]).abs().mean() > 0                       # the noise matters
    y.sum().backward()
    assert all(p.grad is not None for p in g.parameters() if p.requires_grad)


def test_factory_and_default():
    assert isinstance(make_generator("mlp", 6, 20), Generator) and isinstance(make_generator("tokens", 6, 44 * 4, d=16, heads=2), TokenGenerator)
    assert train.DEFAULTS["arch"] == "mlp"
