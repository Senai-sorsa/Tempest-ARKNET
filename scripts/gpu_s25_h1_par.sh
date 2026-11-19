#!/bin/bash
# H1 driver on the PAR gate (see s25_arm_par.sh): noise s100 now, then wait for the old-gate h1_prior s100 instance, then the full loop (skips done steps) and the judge.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
JUDGE() { env "PYTHONPATH=.;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/s25_judges.py "$1"; }
bash scripts/s25_arm_par.sh h1_noise 100 configs/s25/h1_noise.toml || exit 2
while [ "$(powershell -NoProfile -c "@(Get-CimInstance Win32_Process | ? { \$_.CommandLine -match 's25_arm.sh h1_prior 100' }).Count" | tr -dc '0-9')" != "0" ]; do sleep 60; done
for s in 0 100; do for a in h1_prior h1_noise; do bash scripts/s25_arm_par.sh $a $s configs/s25/$a.toml || exit 2; done; done
JUDGE h1
