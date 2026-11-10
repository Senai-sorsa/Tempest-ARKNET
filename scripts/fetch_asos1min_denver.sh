#!/bin/bash
# IL-181 (b): IEM one-minute ASOS (sknt, drct, gust_sknt) for Denver International (DEN) and Centennial (APA), 2016-2025, one file per station-year into data/raw/asos1min_denver
# (its own folder; probe 2020-06-01..08 OK for both, BJC has no one-minute data). Resumable: a year whose file exists and is non-trivial is skipped. Polite: one request at a time, 5 s apart.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
OUT=data/raw/asos1min_denver
for st in DEN APA; do for y in $(seq 2016 2025); do
  f=$OUT/${st}_${y}.csv
  [ -s $f ] && [ $(stat -c %s $f) -gt 100000 ] && continue
  curl -s -m 1800 -A "tempest-arknet-research" -o $f.part "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?station=${st}&vars=sknt&vars=drct&vars=gust_sknt&sts=${y}-01-01T00:00Z&ets=$((y+1))-01-01T00:00Z&sample=1min&what=download&tz=UTC" && mv $f.part $f
  echo "$(date '+%F %T') $st $y $(stat -c %s $f 2>/dev/null) bytes" >> data/fetch_asos1min_denver.log
  sleep 5
done; done
echo "$(date '+%F %T') [ASOS1D] done" >> data/l3.log
