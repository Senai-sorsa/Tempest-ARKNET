#!/bin/bash
# After ap_g9.sh: rescore p2f and siren at Denver with the fixed §9.7 filled check (mc.py now finds filled heights by
# MSL height; the first version looked for exact copies, which the station correction removes, so it found none).
# ap_g9.sh skips runs whose _mc.csv exists, so moving the two old CSVs aside and relaunching rescores only those two.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
while powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | ? { \$_.CommandLine -match 'ap_g9\.sh' }).Count" | tr -d '\r' | grep -qv '^0$'; do sleep 300; done
for V in p2f siren; do f=models/g9_${V}_den_cal2021_mc.csv; [ -f $f ] && mv $f ${f%.csv}_nofill.csv; done
echo "$(date '+%F %T') [G9] refill: rescoring p2f/siren Denver with the MSL filled check" >> data/l3.log
bash scripts/ap_g9.sh
