#!/bin/bash
# Full test suite in the GPU gap after a tag's 'done' line (rule: no pytest beside a GPU score). Usage: bash scripts/gpu_gap_tests.sh TAG   (e.g. IL169)
# Log: data/l3.log [TESTS]; output docs/results/logs/tests_after_<TAG>.log
cd /c/Users/Senai/Tempest-ARKNET || exit 1
. scripts/cap_cpu.sh
TAG=${1:?tag}
log() { echo "$(date '+%F %T') [TESTS] $*" >> data/l3.log; }
until grep -q "\[$TAG\] done" data/l3.log; do sleep 60; done
log "start after $TAG"
OUT=docs/results/logs/tests_after_$TAG.log
.venv/Scripts/python -m pytest tempest_weather_v2/tests tests -q -p no:cacheprovider --ignore=tests/test_flight_sim_readers.py > $OUT 2>&1
log "done after $TAG: $(tail -1 $OUT)"
