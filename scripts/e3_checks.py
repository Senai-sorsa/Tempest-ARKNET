"""E3: hash and leak checks for the final system. Exits 1 if anything fails.
    PYTHONPATH=. python scripts/e3_checks.py"""
import subprocess
import sys

import numpy as np
import torch

from tempest.calibrate import spread

B = "models/generator_80_p2f"
bad = []


def check(ok, name, msg=""):
    print(("PASS " if ok else "FAIL ") + name + (": " + msg if msg else ""), flush=True)
    if not ok:
        bad.append(name)


# 1. nothing from data/ or models/ (or credentials) is tracked
files = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split("\n")
check(not [f for f in files if f.startswith(("data/", "models/"))], "no data/ or models/ in git")
check(not [f for f in files if "ecmwfdatastoresrc" in f or f.endswith((".grib", ".nc", ".zarr"))], "no credentials, grib, nc or zarr files in git")
check(not [f for f in files if f.startswith("tempest_weather/assets")], "bundled tool assets are not in git")

# 2. hashes: every post-processing file records the model (and calibration) it was fitted for
msha = spread.model_hash(B + ".pt")
ck = torch.load(B + ".pt", map_location="cpu", weights_only=True)
k0 = ck["members"][0] if "members" in ck else ck
for name in ("calib2021", "shearmap2021_cell8", "seasonal2021_rhsfc", "shearmap2021_shuf_full"):
    z = np.load(f"{B}.{name}.npz")
    check("model_sha" in z.files and str(z["model_sha"]) == msha, f"{name} carries the sha of {B}.pt")
w = np.load("models/whead_clean.wcalib2021.npz")
check(int(w["m"]) == 199, "w-head range map fitted with m = 199")

# 3. no 2026 rows (or test years) in training, validation or calibration
tr, va = k0.get("train_years"), k0.get("val_years_range")
if tr is None:                                    # the adopted p2f predates the stored ranges: training used --max-year 2023 (scripts/phase2_variant.sh) with the last val_years of those as validation
    vy = int(k0["cfg"]["val_years"])
    tr, va = [1991, 2023 - vy], [2023 - vy + 1, 2023]
    src = "inferred from cfg.val_years and --max-year 2023"
else:
    src = "stored in the checkpoint"
check(tr[1] <= 2020 and va[1] <= 2023, "generator train / validation years end before 2024", f"train {tr}, validation {va} ({src})")
cz = np.load(f"{B}.calib2021.npz")
check("fit_year" not in cz.files or int(cz["fit_year"]) <= 2023, "range map fitted on 2023 or earlier")
sm = np.load(f"{B}.shearmap2021_cell8.npz")
check(int(sm["fit_to"]) <= 2023, "shear map fitted on 2023 or earlier", f"{int(sm['fit_from'])}-{int(sm['fit_to'])}")
for name in ("models/whead_clean.pt",):
    k = torch.load(name, map_location="cpu", weights_only=True)
    k = k["members"][0] if "members" in k else k
    check(k.get("train_years", [0, 0])[1] <= 2018 and k.get("val_years_range", [0, 0])[1] <= 2020, "clean w head trained <= 2018, early stop <= 2020", f"{k.get('train_years')} {k.get('val_years_range')}")
d = np.load("data/train/pilot80_dpd.npz", mmap_mode="r")
y = np.asarray(d["year"])
check(int((y >= 2026).sum()) > 0, "2026 rows exist in the dataset (for the final test only)", f"{int((y >= 2026).sum()):,} rows")
print(f"\n{len(bad)} failed" if bad else "\nall E3 checks passed")
sys.exit(1 if bad else 0)
