#!/bin/bash
# Resume loop 3 after a runner restart: wait for an orphaned training run, keep its output if it finished, then start the runner.
cd /c/Users/Senai/Tempest-ARKNET || exit 1
tr() { powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'generator.train' }).Count" | tr -d '\r'; }
while [ "$(tr)" != "0" ]; do sleep 60; done
for f in models/l3_*.pt.part; do
  [ -f "$f" ] || continue
  V=$(basename $f .pt.part); V=${V#l3_}
  grep -q "^trained in" data/l3_train_$V.log && mv $f ${f%.part} || rm -f $f
done
exec bash scripts/ap_l3.sh "$@"
