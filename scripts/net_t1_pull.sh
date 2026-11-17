#!/bin/bash
# 23.T1 full pull 2024-01..2025-12, EPZ + MAF, parsed to 50 m, raw dropped per month
cd "$(dirname "$0")/.." ; L=data/l3.log
echo "$(date '+%F %T') [T1] start 2024-01..2025-12" >> $L
nice -n 10 .venv/Scripts/python -W ignore scripts/t1_pull.py 2024-01 2025-12 > data/t1_pull.log 2>&1
echo "$(date '+%F %T') [T1] done $(ls data/t1 | wc -l) files" >> $L
