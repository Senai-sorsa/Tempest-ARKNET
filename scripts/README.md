# scripts

Run by hand. Naming: `phase*.sh` / `p35_chain.sh` / `whead_chain.sh` queue GPU jobs one at a time (they wait for a free GPU and skip finished stages; never edit a running one).

| Script | Purpose |
|---|---|
| `compare_headline.py` | two headline CSVs -> per-cell table and the phase pass rule |
| `physics.py` | wind-shear and lapse-rate percentiles, samples vs truth |
| `coupling_check.py` | correlations between variables / heights, samples vs real cases |
| `gust_check.py`, `soak_check.py`, `whead.py`, `index_bakeoff.py` | Phase 3 item checks |
| `p4_probe.py`, `p4_modeP.py`, `p4_modeP_baseline.py` | Phase 4 API probe and past-date mode |
| `ridge_check.py` | offline choice of the balloon-correction smoothing (rejected) |
| `phase2.sh`, `phase2_variant*.sh` | build + train + calibrate + score one variant (`VAR=name`, config `configs/generator_<name>.toml`) |
| `cap_cpu.sh` | source before launching a job: pins the shell to 12 CPUs |
| `run_logger.cmd` | one pass of the forecast logger (for a scheduler) |
