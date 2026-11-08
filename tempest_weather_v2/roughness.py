"""Directional surface roughness z0 (spec R1): from a land-cover map, not a network API.

* `build_sector_map(landcover, cell_m, table)`: for every cell, every 30-degree wind sector and season, the inverse-distance-weighted GEOMETRIC mean of z0 over a 1 km fetch upwind of the cell
  (the EPA AERSURFACE method). `landcover` holds NLCD class codes on a regular grid; `table` maps class -> z0 (m) per season.
* `RoughnessMap`: the result as log-coded uint8 (z0 = 1e-4 * 10**(code / 64), 1e-4 .. 10 m) on a grid, saved as .npz. `z0(lat, lon, wind_from_deg, month)` picks the cell, the sector of that
  sample's own 10 m wind direction, and the season.
* No map covers the point -> the caller falls back to the default z0 = 0.03 m and flags 'z0-default-0.03' (the old fixed value).
The bundled `data/z0_table.csv` holds APPROXIMATE typical values by NLCD class (Davenport-Wieringa style roughness classes). It is a stand-in: replace it with the published AERSURFACE tables
before relying on the numbers (the file says so). The NLCD map itself is not shipped here; build it with `build_sector_map` and save it with `RoughnessMap.save`.
"""
import csv
import os

import numpy as np

__all__ = ["RoughnessMap", "build_sector_map", "load_table", "season_of", "Z0_DEFAULT"]

Z0_DEFAULT = 0.03
SECTORS, SEASONS = 12, 4
TABLE_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "z0_table.csv")


def season_of(month):
    """0 = DJF, 1 = MAM, 2 = JJA, 3 = SON."""
    return ((int(month) % 12) // 3)


def load_table(path=TABLE_CSV):
    """-> {class code: (z0 DJF, MAM, JJA, SON)} from a CSV with columns class,name,winter,spring,summer,fall (lines starting with # are comments)."""
    out = {}
    with open(path, encoding="utf-8", newline="") as f:
        rows = csv.reader(line for line in f if line.strip() and not line.lstrip().startswith("#"))
        header = next(rows)
        for r in rows:
            out[int(r[0])] = tuple(float(x) for x in r[2:6])
    if not out or len(header) < 6:
        raise ValueError(f"{path} is not a z0 table (class,name,winter,spring,summer,fall)")
    return out


def _encode(z0):
    return np.clip(np.round(64.0 * np.log10(np.maximum(z0, 1e-4) / 1e-4)), 0, 255).astype(np.uint8)


def _decode(code):
    return 1e-4 * 10.0 ** (np.asarray(code, np.float64) / 64.0)


def build_sector_map(landcover, cell_m, table, fetch_m=1000.0):
    """landcover (ny, nx) class codes (row 0 = north) -> uint8 codes (SEASONS, SECTORS, ny, nx). Sector s is centred on the direction the wind blows FROM, 30 s degrees from north."""
    lc = np.asarray(landcover)
    ny, nx = lc.shape
    classes = np.unique(lc)
    missing = [int(c) for c in classes if int(c) not in table]
    if missing:
        raise KeyError(f"land-cover classes {missing} are not in the z0 table")
    r = int(fetch_m // cell_m)
    out = np.empty((SEASONS, SECTORS, ny, nx), np.uint8)
    for season in range(SEASONS):
        z0 = np.zeros((ny, nx))
        for c in classes:
            z0[lc == c] = table[int(c)][season]
        logz = np.log(z0)
        num = np.zeros((SECTORS, ny, nx))
        den = np.zeros((SECTORS, ny, nx))
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                d = np.hypot(dy, dx) * cell_m
                if d == 0 or d > fetch_m:
                    continue
                # the upwind cell sits at (row + dy, col + dx); north is up, so its bearing from the centre cell is atan2(east, north) = atan2(dx, -dy)
                bearing = np.degrees(np.arctan2(dx, -dy)) % 360.0
                s = int(((bearing + 15.0) % 360.0) // 30.0)
                src_y = slice(max(0, dy), ny + min(0, dy))
                src_x = slice(max(0, dx), nx + min(0, dx))
                dst_y = slice(max(0, -dy), ny - max(0, dy))
                dst_x = slice(max(0, -dx), nx - max(0, dx))
                w = 1.0 / d
                num[s, dst_y, dst_x] += w * logz[src_y, src_x]
                den[s, dst_y, dst_x] += w
        own = logz[None]
        res = np.where(den > 0, num / np.maximum(den, 1e-12), own)       # no upwind cell inside the grid (edge): the cell's own value
        out[season] = _encode(np.exp(res))
    return out


class RoughnessMap:
    def __init__(self, codes, lat0, lon0, dlat, dlon):
        """codes (SEASONS, SECTORS, ny, nx) uint8; cell (0, 0) is the north-west corner centre at (lat0, lon0); dlat > 0 southwards, dlon > 0 eastwards (degrees per cell)."""
        self.codes = np.asarray(codes, np.uint8)
        if self.codes.ndim != 4 or self.codes.shape[:2] != (SEASONS, SECTORS):
            raise ValueError("codes must have shape (4 seasons, 12 sectors, ny, nx)")
        self.lat0, self.lon0, self.dlat, self.dlon = float(lat0), float(lon0), float(dlat), float(dlon)

    @property
    def shape(self):
        return self.codes.shape[2:]

    def covers(self, lat, lon):
        ny, nx = self.shape
        i, j = (self.lat0 - lat) / self.dlat, (lon - self.lon0) / self.dlon
        return (-0.5 <= i < ny - 0.5) & (-0.5 <= j < nx - 0.5)

    def z0(self, lat, lon, wind_from_deg, month):
        """z0 (m) for the point, the wind direction(s) it comes FROM and the month; arrays broadcast over the wind direction. NaN where the point is outside the map."""
        ny, nx = self.shape
        i = int(round((self.lat0 - lat) / self.dlat))
        j = int(round((lon - self.lon0) / self.dlon))
        if not (0 <= i < ny and 0 <= j < nx):
            return np.full(np.shape(wind_from_deg), np.nan)
        sec = (((np.asarray(wind_from_deg, float) + 15.0) % 360.0) // 30.0).astype(int)
        return _decode(self.codes[season_of(month), sec, i, j])

    def save(self, path):
        with open(path, "wb") as f:
            np.savez_compressed(f, codes=self.codes, grid=np.array([self.lat0, self.lon0, self.dlat, self.dlon]))
        return path

    @classmethod
    def load(cls, path):
        with np.load(path) as z:
            g = z["grid"]
            return cls(z["codes"], *g)


def load_default():
    """The map shipped in data/z0_sectors.npz or placed in the user cache (<cache>/z0_sectors.npz); None when there is none."""
    from tempest_weather_v2 import _files
    for p in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "z0_sectors.npz"), os.path.join(_files.cache_dir(), "z0_sectors.npz")):
        if os.path.exists(p):
            return RoughnessMap.load(p)
    return None
