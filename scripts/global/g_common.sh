#!/bin/bash
# Shared pieces for the G-stage launchers (docs/global/README.md). Source it, do not run it.
#   step NAME CMD...   runs CMD once: skipped when results/$G/NAME.done exists, so a relaunch resumes;
#                      a failed step leaves no done-file and stops the script (exit 1).
#   DRY=1              print the commands instead of running them (checks the wiring without a GPU).
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=${PY:-python}
export PYTHONPATH=.${PYTHONPATH:+:$PYTHONPATH}
OUT=results/$G
mkdir -p "$OUT"

# G6 is the one-time final global test: never from these scripts.
if [ "${TEMPEST_FINAL_GLOBAL:-}" = 1 ]; then
  echo "TEMPEST_FINAL_GLOBAL=1 is set: that unlocks the G6 window. Unset it; G1-G5 never use it." >&2; exit 2
fi
for d in data/raw/*2026* data/train/final_2026h2* data/raw/igra; do
  [ -e "$d" ] && [ -z "${ALLOW_LOCAL:-}" ] && { echo "locked 2026 data present ($d): this is not a G bundle (docs/global/BUNDLE.md); set ALLOW_LOCAL=1 only on the dev laptop" >&2; exit 2; }
done

log() { echo "$(date '+%F %T') [$G] $*" | tee -a "$OUT/run.log"; }

step() {
  local name=$1; shift
  [ -f "$OUT/$name.done" ] && { log "skip $name (done)"; return 0; }
  if [ -n "${DRY:-}" ]; then echo "DRY $name: $*"; return 0; fi
  log "start $name"
  if "$@" >> "$OUT/$name.log" 2>&1; then date '+%F %T' > "$OUT/$name.done"; log "done $name"
  else log "FAILED $name (see $OUT/$name.log)"; exit 1; fi
}

seeded() {  # seeded CFG SEED -> path of a copy of CFG with its seed line set (the seed lives in the config)
  local c=$OUT/$(basename "${1%.toml}")_s$2.toml
  sed "s/^seed = .*/seed = $2/" "$1" > "$c"
  grep -q "^seed = $2$" "$c" || { echo "no 'seed =' line in $1" >&2; exit 1; }
  echo "$c"
}

not_built() {  # stage needs code that does not exist yet: say what, write NOT_BUILT, exit 3
  { echo "$G cannot run yet. Missing (docs/plans/GLOBAL_PLAN.md $G):"; printf '  - %s\n' "$@"; } | tee "$OUT/NOT_BUILT.txt" >&2
  exit 3
}
