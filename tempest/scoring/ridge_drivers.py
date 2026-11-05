"""F-13: unknown drivers the way the tool serves them. The scorers' default "unknown" set copies the drivers (ONI, WWV, QBO, ...) of random training rows from
the same group (an analog draw); the tool instead draws them from the ridge index forecast (`tempest.ingest.index_forecast`) made `lead` months earlier.
`fill` writes that kind of draw into the driver columns of the repeated condition matrix, so the two scorers can report the skill of what is served.
Default off (`--driver-mode analog`)."""
import numpy as np
import pandas as pd

from tempest.generator.features import FEATURES, drivers
from tempest.ingest import index_forecast, indices


def row_months(cond, year):
    """Rows -> month-start timestamps of the target date, from the day-of-year features and the year."""
    c = lambda k: cond[:, FEATURES.index(k)]
    doy = np.round(np.arctan2(c("doy_sin"), c("doy_cos")) % (2 * np.pi) / (2 * np.pi) * 365.25).astype(int).clip(1, 366)
    t = pd.to_datetime(pd.Series(np.asarray(year).astype(int).astype(str))) + pd.to_timedelta(doy - 1, "D")
    return pd.DatetimeIndex(t).to_period("M").to_timestamp()


def fill(rep, cond, year, m, lead_months, rng, table=None):
    """rep: (N*m, F) repeated conditions to modify in place; cond (N, F), year (N,) the unrepeated rows. Returns rep."""
    table = indices.load() if table is None else table
    known = table.dropna(subset=indices.COLS)
    months = row_months(np.asarray(cond), year)
    names = drivers()
    cols = {k: FEATURES.index(k) for k in names}
    cache = {}
    for i, mo in enumerate(months):
        origin = mo - pd.DateOffset(months=lead_months)
        if origin > known.index[-1]:
            origin = known.index[-1]
        if mo not in cache:
            h = int((mo.year - origin.year) * 12 + mo.month - origin.month)
            d = index_forecast.draw(known, origin, max(h, 1), m, rng)                        # columns: oni, qbo30, qbo50, wwv
            lag = index_forecast.draw(known, origin, max(h - 3, 1), m, rng)[:, 0] if "oni_lag3" in cols else None
            cache[mo] = (d, lag)
        d, lag = cache[mo]
        sl = slice(i * m, (i + 1) * m)
        vals = dict(oni=d[:, 0], qbo30=d[:, 1], qbo50=d[:, 2], wwv=d[:, 3], oni_pos=np.maximum(d[:, 0], 0), oni_neg=np.minimum(d[:, 0], 0), oni_lag3=lag)
        for k, j in cols.items():
            rep[sl, j] = vals[k]
    return rep
