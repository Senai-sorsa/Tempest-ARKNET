# New_Plan section 25: code status (for the loop session)

Code only. Nothing here was trained, judged, or run on real data, except the GX3 step 0 disk check (read-only).
Commits on main, not pushed: b54abbb (shared pieces), f75ad65 (GF2, GF4, GF1, GX2, GT2, GX3 step 0), 5c3c8ed (GF3), d0054bd (MF2 to H5).

## How every item runs

- **Arm runner:** `scripts/s25_arm.sh NAME SEED DELTA.toml [key=value ...]`. It runs one arm for one seed and follows the 25.1 rules:
  - It trains on 1991-2023 with 2021-23 held out for validation (`--max-year 2023`, val_years 3).
  - It then runs range calibration (2021-23), the shear map and the lapse map, refit in that order.
  - Scoring covers the verdict years 2024-25 only: (a) raw + range calibration, (b) the full stack. It also runs the shape diagnostics and the s25 shape metrics (`--blocks 7`) for (a) and (b), plus the Denver fill-top report.
  - Each step is skipped if its output already exists, so a killed runner can simply be restarted.
  - Environment: `STEPS`, `STAGE=train`, `INIT`, `NOSHUF=1`, `PRE=1`, `DRY=1`. A DRY run prints commands only and writes no log lines.
  - It waits until no other training or scoring python process is running, at least 6 GB of RAM is free, and (before training) the GPU is below 85 C. It sources `scripts/cap_cpu.sh`.
- **Paired baseline:** `configs/s25/base.toml` (the shipped c4w settings), seeds 0 and 100, same data. Every runner starts with it and reuses it if it already exists.
- **Seed noise:** |base s0 − base s100|.
- **Delta configs:** `configs/s25/*.toml`. Generated full configs go to `configs/s25/gen/` (never committed).
- **Outputs:** models in `models/s25/`; run log `docs/results/logs/s25.log`; step logs `docs/results/logs/s25_<arm>_s<seed>_*.log`; verdicts `docs/results/logs/kit_s25_<item>.log`.
- **Judges:** `new_plan_kit/s25_judges.py <item>`. Each judge's docstring holds its PRE-SET pass/kill rule; line numbers below. Picks and gates go to `docs/results/logs/s25_<item>_pick.txt`.
- **Launch:** `nohup bash scripts/<runner> > /dev/null 2>&1 &`. Run one GPU runner at a time; every runner shares the base arm.
- **Flags:** every new option is a cfg key or a new file, OFF by default.
  - New cfg keys in `tempest/generator/train.py`: `es_beta`, `vario_weight`, `svec_weight`, `twes_*`, `sig_weight`, `sig_stride`, `distill_teacher`, `distill_m`, `distill_data_weight`, `model_kw_extra`, the `s25` table, and `arch` values flow, rml, har, moe, eof, prior, analog, refine.
  - New model code lives in `tempest/generator/s25_models.py` and `s25_losses.py`.
  - New numpy samplers in `tempest_weather/engine.py` (`inner_member`, `flow_sample`, `rml_sample`, `tau_embed`) are additions only.

## Identity and suite

- **train.py and model.py:**
  - `tests/test_s25.py::test_s25_keys_at_defaults_are_byte_identical_to_golden`: with every s25 key at its default, the result is byte-identical to the existing golden in `tests/test_flags_off.py`.
  - `test_make_generator_mlp_unchanged`: the shipped mlp is unchanged.
  - `test_cfg_default_keys_match_train_defaults`.
- **engine.py:** additions only; no existing line changed. `test_engine_numpy_flow_and_rml_match_torch` covers the new functions. The existing engine and tool tests are in the suite.
- **scoring:** `tempest/scoring/` was not touched. The new metrics live in `scripts/s25_shape.py`.
- **Suite before:** 461 passed.
- **Suite after:** see the end of `docs/agent/pytest_after.txt` and the line below.

- **Suite after (2026-11-18, tests/ + tempest_weather_v2/tests):** 518 passed, 0 failed, in 30 min. That is the 461 from before plus the 57 new tests in tests/test_s25.py.

## Items

Smoke check for every training arm: `tests/test_s25.py::test_every_arm_delta_trains[<arm>]` trains each delta config with the tiny trainer and checks that the checkpoint samples through `Sampler`. Every arm passed.

| Item | Status | Runner (launch) | Code / flags | Smoke | Rule |
|---|---|---|---|---|---|
| GF2 | done | `scripts/gpu_s25_gf2.sh` | 9 cells: `s25_arm.sh` with `STAGE=train STEPS=3000 lr=… weight_decay=…`; follow-up `gf2_big` (batch 16384, 2× lr, 12000 steps) runs only if PASS | arm test (base); DRY ok | `s25_judges.py:168` (gf2), gf2_follow |
| GF4 | done | `scripts/cpu_s25_gf4.sh` (CPU, needs `base_s0`) | `scripts/s25_gf4_condcal.py` (monotone stretch, 4 params per var × band; drivers: spread, stability, 500 hPa wind; fit 2021-23, score 2024-25; PIT TV; 2021 vs 2022 sign-swap check); `s25_shape.py --dump` | `--selfcheck` ok (gradient check, monotone) | `:199` |
| GF1 | done | `scripts/gpu_s25_gf1.sh` | 11 arms `configs/s25/gf1_*.toml` + gx2 (`es_beta`, `vario_weight`, `svec_weight`, `twes_*`); 3000-step screen vs base3k, then the 2 picks at 6000 steps on s0 and s100 | arm tests; DRY ok | `:216` screen, `:241` full (writes `s25_gf1_moved_pick.txt`) |
| GX2 | done | `scripts/gpu_s25_gx2.sh` | `configs/s25/gx2.toml` (twES on u, v 0-18 km, q90, weight 0.1) | arm test; DRY ok | `:273` |
| GT2 | done | `scripts/gpu_s25_gt2.sh` | `configs/s25/gt2_il8b.toml` (tokens, d 96, 3000 steps); `scripts/s25_pool.py` (IL-23 pool = base members + il8b members); `PRE=1` pipeline | `test_gt2_pool_mlp_plus_tokens_samples_through_sampler`; DRY ok | `:296` |
| GX3 step 0 | done: **NO** | `scripts/cpu_s25_gx3_step0.sh` (ran; read-only) | checks data/raw/era5_g2_<site>/DONE and the height stores | result in `docs/results/logs/kit_s25_gx3_step0.log`: all 6 g2 sites have raw ERA5 (DONE), none has a height store | rule in the script header; **GX3 needs the user** |
| GF3 | done | `scripts/gpu_s25_gf3.sh` | `configs/s25/gf3_f1.toml` (arch flow, 8 Euler steps), `gf3_f2.toml` (`INIT=` F1, +1000 steps afCRPS on 4-step samples), F3 = `NOSHUF=1` F1; `scripts/s25_sampler_cost.py` (numpy Euler at 4, 8, 16 steps: forward passes, ms per 1000, × base, RMS gap to 32 steps, numpy-vs-torch check) → `s25_sampler_cost.log` | arm tests; sampler `--selfcheck` ok (numpy vs torch 7e-7); DRY ok | `:322` |
| MF2 | done | `scripts/gpu_s25_mf2.sh` | `mf2_k3.toml`, `mf2_k5.toml` (arch rml, K=3 and 5); numpy `rml_sample` | arm tests; DRY ok | `:339` |
| GX1 | done | `scripts/gpu_s25_gx1.sh` | `gx1.toml` (`sig_weight` 0.05), `gx1_s2.toml` (+`sig_stride` 2). Gate: exits unless `s25_gf1_moved_pick.txt` = YES | arm tests; DRY ok (gate closed now) | `:346` |
| GT1 | done | `scripts/gpu_s25_gt1.sh` | `gt1.toml` (arch har, 7 blocks); error per block from `s25_shape.py --blocks 7` (`block_crps`) | arm test; `test_har_blocks_cover_every_column_once`; DRY ok | `:355` |
| MF1 | done | `scripts/gpu_s25_mf1.sh` | `mf1.toml` + `distill_teacher="models/s25/<gf3 pick>_s<seed>.pt"` (energy distance, m 8; `load_teacher` refuses a different normalisation). Gate: exits if `s25_gf3_pick.txt` is empty | `test_distill_smoke`; DRY ok (gate closed now) | `:397` |
| H1 | done | `scripts/gpu_s25_h1.sh` | `h1_prior.toml` (arch prior, gram mode, output = prior + residual), `h1_noise.toml` (N(0,1) control) | arm tests; DRY ok | `:417` |
| H3 | done | `scripts/gpu_s25_h3.sh` | `h3_moe.toml` (arch moe, E 3, balance 0.01); `scripts/s25_gate_month.py` writes `models/s25/h3_moe_s<seed>_gate.csv` (month, w0..w2, top_share, collapse; row "all" carries the flag) | `test_moe_gate_logged`; gate script `--selfcheck` ok (forced expert → collapse flagged); DRY ok | `:365` |
| H4 | done | `scripts/gpu_s25_h4.sh` | `h4_eof.toml` (arch eof, 95 % variance, AR(1)) | arm test; DRY ok | `:287` |
| H2 | done | `scripts/gpu_s25_h2.sh` | `h2_analog.toml` (arch analog, k 8, own year excluded, `max_mb` 200), plus the `NOSHUF=1` stack | arm test; DRY ok | `:381` |
| H5 | done | `scripts/gpu_s25_h5.sh` | `h5_t02.toml` / `h5_t04.toml` (arch flow, `tau_min` 0.8 / 0.6, 3 steps), trained as `h5_t0Xf` (`STAGE=train`); `scripts/s25_compose_refine.py` joins base member k with flow member k into arch refine `h5_t0X` (refuses different norms, inputs or member counts, and never overwrites); then `PRE=1` | compose `--selfcheck` ok (composed output = draft + refine by hand, loads in Sampler, norm refusal); DRY ok | `:433` |

The selfchecks also run in pytest: `tests/test_s25.py::test_s25_script_selfchecks[...]`.

## Decisions taken (the plan left them open)

- **GF4:** scored against ERA5 2024-25, not balloons (no balloon set exists for that window here).
- **Weights:** GX2 `twes_weight` 0.1; GX1 `sig_weight` 0.05; GT1 uses 7 blocks (plan: 6-8).
- **GF1:** the 11th arm is the GX2 twES arm. A GX2 run already made as a GF1 pick is reused.
- **GF2 follow-up:** reported only (`gf2_follow`); no ship decision.
- **H5:**
  - The draft is the paired base.
  - Each base member is paired with the flow member of the same index, giving one refine model per member and an ensemble of the same size.
  - t0 0.2 / 0.4 means `tau_min` 0.8 / 0.6, with 3 Euler steps (plan: 2-3).
- **MF1:** the teacher is the first GF3 pick of the same seed.
- **GT2:** pool = base members + il8b members.
- **GF3 cost:** measured on the first member, best of 2 runs, 2000 rows from 2024. Timings are machine-dependent; the forward-pass counts are exact.

## Not done / needs the user

- **GX3:** step 0 = NO. Building the g2 height stores needs a `tempest.profiles.to_heights` run on the raw g2 zarr (6 × ~5 GB). That is the user's call; GX3 was not coded further.
- Nothing was trained or judged; the loop session runs the runners.
- `docs/results/logs/s25.log` holds no lines. It is created on the first real run.
