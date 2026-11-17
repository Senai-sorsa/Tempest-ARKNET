#!/bin/bash
# T1 step 0: NCEI 1-s BUFR archive members are <WBAN id>_<yyyymmddhh>; EPZ Santa Teresa 03020, MAF Midland 23023. One month streamed, only these kept.
cd "$(dirname "$0")/.." ; L=data/l3.log
u=https://www.ncei.noaa.gov/data/us-radiosonde-bufr/archive/us-radiosonde_BBUFR_d202406_c20240715.tar.gz
mkdir -p data/t1_bufr
echo "$(date '+%F %T') [T1s0] start extract" >> $L
curl -sL --retry 3 "$u" | tar -xz -C data/t1_bufr --wildcards '03020_*' '23023_*' > data/t1_step0.log 2>&1
echo "$(date '+%F %T') [T1s0] done $(find data/t1_bufr -type f | wc -l) files" >> $L
