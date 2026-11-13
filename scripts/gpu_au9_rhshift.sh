#!/bin/bash
# AU-9 (New_Plan 15.3): the shipped l3_c4wl seed 0 balloon (sonde) run, same flags as the AU-6 plain run (whose score.csv equals the shipped one),
# now with the full dew-point-kept humidity site shift (to_site, RH_SHIFT_BLEND = False). Pass: RH 0-1 km and 1-5 km skill15 not worse than
# models/l3_c4wl_s0_sonde_cal2021_smap_headline.csv by more than the seed noise (0.003). Model copied to models/au9_l3_c4wl_s0.pt. Log: data/l3.log [AU9].
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
PY=.venv/Scripts/python
DA=data/train/pilot80_l21_day_dpd.npz C=models/l3_c4w PR=data/pilot/profiles80.zarr
CAL=$C.calib2021.npz SM=$C.shearmap2021_cell8.npz M=models/au9_l3_c4wl_s0.pt
log() { echo "$(date '+%F %T') [AU9] $*" >> data/l3.log; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train|calibrate|scoring|il6_modeF|pytest' }).Count" | tr -d '\r'; }
ram_gb() { powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)" | tr -d '\r'; }
wait_free() { while [ "$(busy)" != "0" ] || [ "$(ram_gb)" -lt 6 ]; do sleep 60; done; }
for f in $DA $CAL $SM models/l3_c4wl_s0.pt; do [ -f $f ] || { log "FAILED missing $f"; exit 1; }; done
cp models/l3_c4wl_s0.pt $M
log start
if [ ! -f models/au9_l3_c4wl_s0_sonde_cal2021_smap_headline.csv ]; then
  wait_free
  $PY -W ignore -u -m tempest.scoring.sonde --model $M --data $DA --profiles $PR --m 199 --first-test-year 2024 --last-test-year 2025 --calib $CAL --shear-map $SM \
    > data/au9_sonde.log 2>&1 && log "sonde scored" || { log "FAILED sonde"; exit 2; }
fi
$PY - >> data/l3.log <<'PY'
import pandas as pd
a = pd.read_csv("models/l3_c4wl_s0_sonde_cal2021_smap_headline.csv").set_index(["var", "band"])
b = pd.read_csv("models/au9_l3_c4wl_s0_sonde_cal2021_smap_headline.csv").set_index(["var", "band"])
for k in [c for c in a.index if c[0] in ("RH", "rh2m")]:
    d = b.loc[k, "skill15_known"] - a.loc[k, "skill15_known"]
    print(f"[AU9] {k[0]} {k[1]}: skill15_known {a.loc[k,'skill15_known']:+.4f} -> {b.loc[k,'skill15_known']:+.4f} ({d:+.4f}); cov99 {a.loc[k,'cov99_known']:.3f} -> {b.loc[k,'cov99_known']:.3f}")
PY
log done
