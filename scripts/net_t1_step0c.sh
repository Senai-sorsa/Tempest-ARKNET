#!/bin/bash
# T1 step 0 (C-BUFR variant): the B-BUFR files carry embedded tables eccodes cannot decode; try the CBUFR archive, same month, EPZ 03020 / MAF 23023.
cd "$(dirname "$0")/.." ; L=data/l3.log
u=https://www.ncei.noaa.gov/data/us-radiosonde-bufr/archive/us-radiosonde_CBUFR_d202406_c20240715.tar.gz
mkdir -p data/t1_cbufr
echo "$(date '+%F %T') [T1s0c] start extract" >> $L
curl -sL --retry 3 "$u" | tar -xz -C data/t1_cbufr --wildcards '03020_*' '23023_*' > data/t1_step0c.log 2>&1
echo "$(date '+%F %T') [T1s0c] done $(find data/t1_cbufr -type f | wc -l) files" >> $L
