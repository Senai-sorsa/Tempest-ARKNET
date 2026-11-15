#!/bin/bash
# AV19 launch (user go 2026-11-14): start scripts/gpu_av19_shape.sh only when >= 14 GB RAM is free and no Mode F evaluation runs (UR1 holds 15-17 GB at peak).
cd /c/Users/Senai/Tempest-ARKNET || exit 1
free_gb() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)' | tr -d '\r'; }
busy() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*il6_modeF.py*' }).Count" | tr -d '\r'; }
until [ "$(busy)" -eq 0 ] && [ "$(free_gb)" -ge 14 ]; do sleep 30; done
echo "$(date '+%F %T') [AV19] launch" >> data/l3.log
exec bash scripts/gpu_av19_shape.sh
