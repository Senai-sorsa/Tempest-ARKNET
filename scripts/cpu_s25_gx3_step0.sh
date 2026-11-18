#!/usr/bin/env bash
# New_Plan 25 GX3 step 0 (minutes, read-only, fetches nothing): do the g2 ERA5 profiles exist on disk as HEIGHT stores?
# Pre-set rule: YES only if every configs/region_g2_*.toml region has a height store (data/pilot/*<region>*.zarr or
# data/train/*<region>*.npz). Raw pressure-level zarr in data/raw/era5_g2_<site> alone does NOT count
# (it still needs tempest.profiles.to_heights). NO -> GX3 goes to "Needs the user" (global track stays off; no G0).
#   nohup bash scripts/cpu_s25_gx3_step0.sh &
cd "$(dirname "$0")/.." || exit 1
LOG=docs/results/logs/kit_s25_gx3_step0.log
ok=1
{
  echo "== GX3 step 0 $(date -u +%FT%TZ)"
  for cfg in configs/region_g2_*.toml; do
    site=$(basename "$cfg" .toml); site=${site#region_g2_}
    raw=data/raw/era5_g2_$site
    rawst=missing; [ -f "$raw/DONE" ] && rawst=done
    store=""
    for p in data/pilot/*"$site"*.zarr data/pilot/*g2_"$site"*.zarr data/train/*"$site"*.npz; do
      [ -e "$p" ] || continue
      store="$store $p"
    done
    [ -n "$store" ] || ok=0
    echo "$site raw=$rawst height_store=${store:- none}"
  done
  if [ $ok = 1 ]; then echo "GX3 step 0: YES (all g2 height stores present)"
  else echo "GX3 step 0: NO (height stores missing; raw ERA5 status above) -> GX3 needs the user"; fi
} | tee -a "$LOG"
