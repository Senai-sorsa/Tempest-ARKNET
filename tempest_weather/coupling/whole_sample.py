"""Whole-sample coupling (the default, and the most faithful): the requested variables are columns of ONE set of whole atmospheres, so every draw is a row
of that table. Nothing is modelled about the joint structure, so shear, temperature-density, thermals-with-wind and every skewed or bounded relation
stay as they really occurred together. Stratified draws (a Latin-hypercube dimension) sort the rows by a chosen key and pick equally spaced ranks.
"""
import numpy as np


class WholeSample:
    METHOD = "whole_sample"

    def __init__(self, columns, table, key=None):
        self.columns, self.table = list(columns), np.asarray(table, float)
        self.key = np.asarray(key, float) if key is not None else None

    def draw(self, k, rng=None, stratified=False):
        """-> (indices, rows): k row indices into the table and the rows themselves (k, n_variables). Rows are reused only when k exceeds the table."""
        rng = rng or np.random.default_rng()
        n = len(self.table)
        if stratified and self.key is not None:
            order = np.argsort(self.key)
            x = (np.arange(k) + rng.random(k)) / k
            rng.shuffle(x)
            idx = order[np.minimum((x * n).astype(int), n - 1)]
        else:
            idx = rng.choice(n, k, replace=k > n)
        return idx, self.table[idx]

    def spec(self):
        return dict(method=self.METHOD, columns=self.columns, n=len(self.table), note="draw row indices into `table`; every row is one whole atmosphere",
                    table=self.table)
