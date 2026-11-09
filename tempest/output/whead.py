"""Vertical-wind head (PHASED_PLAN 3.2): the resolved vertical wind w (m/s, up positive) on the 44 heights, drawn
CONDITIONALLY on a whole sampled atmosphere.

Design note (deviation from the written plan): the plan added w as a 5th output of the main generator (223 outputs, a
full retrain that touches every score). Instead this is a small second Engression network whose inputs are the
generator's own input features AND the sampled physical profile (u, v, T, RH at 44 heights, t2m, sp, rh2m). Because w is
drawn given the sample, a calm cold column and a stormy warm one get matching vertical motion, the coupling the Monte
Carlo needs, and the generator that passed its tests is not touched. Train with scripts/whead.py.
"""
import numpy as np

from tempest.generator.sample import Sampler


def head_inputs(cond, phys):
    """cond (N, F) generator features, phys (N, 179) physical sample -> (N, F + 179) float32 head inputs."""
    return np.concatenate([np.asarray(cond, np.float32), np.asarray(phys, np.float32)], axis=1)


def sample_w(head: Sampler, cond, phys):
    """-> (N, 44) w samples, one per row (each row is one sampled atmosphere)."""
    return head(head_inputs(cond, phys))
