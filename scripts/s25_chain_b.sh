#!/bin/bash
# loop: wait for the GF1 chain (s25_chain_a.sh) to finish, then run GF4 (it failed earlier on --m 99 vs calib m 199, fixed).
cd /c/Users/Senai/Tempest-ARKNET || exit 1
while powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'gpu_s25_gf1|s25_chain_a' }).Count" | grep -qv "^0"; do sleep 120; done
bash scripts/cpu_s25_gf4.sh
