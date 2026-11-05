"""E12: station map with RH from the 2022-23 fit and T/u/v from 1991-2020 (pools: RH rows cycled to the old n)."""
import numpy as np
from tempest.profiles.to_heights import PROFILE
import sys
A = sys.argv[1:] or ["models/station_map_2020.npz", "models/station_map_2223.npz", "models/station_map_mix.npz"]
old, new = dict(np.load(A[0])), dict(np.load(A[1]))
assert (old["stations"] == new["stations"]).all()
r = PROFILE.index("RH"); out = {k: v.copy() for k, v in old.items()}
used = 0
for g in range(old["n"].shape[0]):
    if (new["n"][g] == 0).any():
        continue  # no 2022-23 leftovers for this group: keep the old RH
    used += 1
    out["a"][g, r], out["b"][g, r] = new["a"][g, r], new["b"][g, r]
    for j in range(3):
        idx = np.arange(old["n"][g, j]) % new["n"][g, j]  # shortcut: RH leftover paired at random with T/u/v leftover
        out["pool"][g, j, :len(idx), r] = new["pool"][g, j, idx, r]
np.savez(A[2], **out)
print("groups with 2022-23 RH:", used, "of", old["n"].shape[0], "| new n min/median", new["n"].min(), np.median(new["n"]))
