"""The region (box, grid, stations) in one place: configs/region.toml. Everything that used to hard-code 31-34 N, 108-101 W, 13 x 29 grid points, the 34 -> 31 ordering or the two
balloon stations should ask this module (review item: adjustable for any location). The default file is the pilot box, so nothing changes until the file does.

    from tempest import region
    r = region.load()                       # Region dataclass (path argument or the environment variable TEMPEST_REGION select another file)
    r.n_lat, r.n_lon, r.n_points            # 13, 29, 377
    r.point_index(lat, lon)                 # index of the nearest grid point in the profile stores (rows from the north-west corner, longitude fastest)
    r.contains(lat, lon)                    # inside the trained area?
    r.era5_lon360                           # (252.0, 259.0), for stores that use 0-360
"""
import os
import tomllib
from dataclasses import dataclass, field

import numpy as np

DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "region.toml")


@dataclass
class Region:
    name: str
    lat_north: float
    lat_south: float
    lon_west: float
    lon_east: float
    step: float
    stations: dict = field(default_factory=dict)      # id -> (lat, lon, launch height m)
    asos: dict = field(default_factory=dict)          # id -> (lat, lon), order = station flag value

    @property
    def n_lat(self):
        return int(round((self.lat_north - self.lat_south) / self.step)) + 1

    @property
    def n_lon(self):
        return int(round((self.lon_east - self.lon_west) / self.step)) + 1

    @property
    def n_points(self):
        return self.n_lat * self.n_lon

    @property
    def era5_lon360(self):
        return (self.lon_west % 360.0, self.lon_east % 360.0)

    def contains(self, lat, lon):
        return self.lat_south <= lat <= self.lat_north and self.lon_west <= lon <= self.lon_east

    def point_index(self, lat, lon):
        """Index of the nearest grid point; the stores run from the north-west corner, longitude fastest."""
        i = np.round((self.lat_north - np.asarray(lat, float)) / self.step).astype(int)
        j = np.round((np.asarray(lon, float) - self.lon_west) / self.step).astype(int)
        return np.clip(i, 0, self.n_lat - 1) * self.n_lon + np.clip(j, 0, self.n_lon - 1)

    def grid(self):
        """-> (lat (n_points,), lon (n_points,)) in store order."""
        la = self.lat_north - self.step * np.arange(self.n_lat)
        lo = self.lon_west + self.step * np.arange(self.n_lon)
        return np.repeat(la, self.n_lon), np.tile(lo, self.n_lat)


def load(path=None):
    path = path or os.environ.get("TEMPEST_REGION") or DEFAULT
    with open(path, "rb") as f:
        d = tomllib.load(f)
    return Region(name=d["name"], lat_north=d["lat_north"], lat_south=d["lat_south"], lon_west=d["lon_west"], lon_east=d["lon_east"], step=d["step"],
                  stations={k: tuple(v) for k, v in d.get("stations", {}).items()}, asos={k: tuple(v) for k, v in d.get("asos", {}).items()})
