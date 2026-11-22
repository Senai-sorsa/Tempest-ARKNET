# Useful results

What the experiments of the last 48 hours (2026-11-11 evening to 2026-11-13 20:45) left that is worth keeping, fixing or building on. Written 2026-11-13.

**What was read.** `New_Plan.md` sections 9, 10, 11.4-11.5, 12.2, 12.9-12.10, 13, 14 and 16 in full; `docs/notes/Almost ideas.md` in full; the 139 commit messages since 2026-11-10; the last day of `docs/logs/AUTOPILOT.md`; the head of `To-do-Concise.md`; the verdict logs `kit_b18` to `kit_b22`. Not read line by line: `docs/agent/handovers/HANDOVER_2026-11-11.md`, `docs/notes/Secondary ideas.md`, `docs/notes/Innovative idea review.md`, `docs/notes/Limitations to solve.md`, the older parts of AUTOPILOT.

**How to read it.** Every number is copied from a log or from `New_Plan.md` section 9. Nothing was run for this file. Where a sentence is my own reading and not a measured result, it says "my reading" or "untested". Outside papers were read as search summaries only, not in full. Nothing here changes a default; every adoption is still your call.

**Still running when this was written.** AV7 (two neighbour stations, 600 hours per target): seed 2 PASSED at both targets, seed 3 not finished.

---

## Update 2026-11-19 (passes since 11-14, and what to combine next)

Rows 16-25 below in 1A are new. Five combined experiments built from the remaining near misses are in New_Plan section 29 (X1-X5). The 26.2 combined copula + stretch (b84) MISSED on seed 0: it fixed 5-12 km shear p99 (0.96) but made low-Ri too common (12-18 km 0.244 vs balloons 0.154), so stretch variants are dropped.

## Update 2026-11-14 (trials run since this file was written)

**What was read.** The verdict logs `kit_b22` (AV7 seed 3), `kit_b23` (AV8), `kit_b24` (UR7), `kit_b38` to `kit_b44` (AV10, AV9, AV11, AV32, AV31, AV33, AV17), the commit messages from 2026-11-13 18:00 to 2026-11-14 08:30, and New_Plan section 17 (the UR rows). AV34 was still running and is not included. **One new measurement was made for this update**: the cov99 and CRPS of every pipeline step were read from the evaluation tables already on disk (`models/modeF_n5_*_eval.csv`, 20 files). Nothing was trained or re-scored. New rows below are marked **(11-14)**.

| Trial | Verdict | What it adds |
|---|---|---|
| AV7, two neighbours, seeds 2 / 3 | **PASS** | Moves row 11 from 1B to 1A. Merged coverage at TCS is 0.81, against 0.84-0.85 for each neighbour alone (part 2, row 20) |
| AV8, map first, update second, 200 h | MISS | One pair +0.002 inside noise; then AV31 |
| AV31, the same at 600 h | **PASS** | One more case of "more rows turn a miss into a pass". Gains are largest when there is no fresh report from the site itself (row 15) |
| AV10 / AV32 / AV33, launch-week tracker on top of IL-207b | MISS x3 | The gain **shrank** as the sample grew (150 to 300 days: -0.014 to -0.027 became -0.001 to -0.008), so this was not sample size. O3 is closed for good. The same replays strengthen IL-207b itself (row 6 note) |
| AV9, analog shift upward only | KILL | CRPS -0.018 / -0.027 with both halves below 0, strong-wind under-prediction cut by 15-27 %, but TCS coverage 0.89 -> 0.84 / 0.85. The centre is right and the spread is now too narrow (part 2, row 19) |
| AV11, x1.2 past-mode spread at airports | KILL | Better only at MAF; worse at LRU, PEQ and ELP. Past-mode coverage is 0.71-0.82 at every airport, and CRPS still gets worse when it is widened, so the fault is the centre, not the spread. 3 of 9 airports are outside the trained box |
| AV17, trust layer refit on l3_c4w | MISS | +0.0006 / +0.0006 / +0.0007 in three seeds, balloons +0.0012, no band worse. The whole gain sits in rh2m (+0.008 to +0.010) and v 0-1 km (+0.002 to +0.003). AV34 (a looser keep threshold) is running |
| UR7, SIGMA cov99 by lead | measurement | SIGMA 0.976-0.983 and NEST 0.978-0.984, flat across lead; binned 0.993 at 1 d falling to 0.930 beyond 7.5 d |

**The new measurement: the cov99 shortfall is made by the PIT step.** Each evaluation table scores the network at every stage of the pipeline. UR7 and the NEST / AV30 verdicts used the column `network + PIT recal + range map + Schaake shuffle`. The column without the PIT step (`network + range map + Schaake shuffle`) gives:

| Model (seed 0, NM/TX) | cov99 at 1 / 3 / 5 / 7 / beyond 7.5 d, with PIT | without PIT | CRPS, without PIT vs with |
|---|---|---|---|
| SIGMA | 0.977 / 0.978 / 0.981 / 0.980 / 0.983 | **0.987 / 0.988 / 0.990 / 0.990 / 0.993** | -0.04 to +0.04 % |
| NEST | 0.981 / 0.981 / 0.984 / 0.981 / 0.984 | **0.989 / 0.989 / 0.991 / 0.990 / 0.992** | -0.02 to +0.03 % |
| binned | 0.993 / 0.990 / 0.983 / 0.962 / 0.934 | 0.998 / 0.996 / 0.993 / 0.982 / 0.965 | -0.20 to +0.03 % |

The same holds in all 17 tables checked (SIGMA, NEST, NEST-t, N5 all-lead and binned; both boxes; both seeds). Without PIT, SIGMA and NEST sit within 0.005 of 0.99 at every lead in both boxes (lowest 0.9866, SIGMA at Denver 1 d), and CRPS changes by under 0.05 %. Per cell it is not perfect: at 1 d, SIGMA's T 1-5 km is 0.983 and v 12-18 km 0.983.

Two cautions. (1) This was found by looking, not by a rule set in advance, so it is a reason to run something, not a verdict. (2) My reading of the code, which needs one check: `scripts/il6_modeF.py:211` saves the range map fitted **without** PIT as `<stem>.calib.npz`, and `tempest/export_tool.py:208` loads that file. If the shipped forecast network was built this way, **the tool ships the no-PIT pipeline, while the verdicts scored the PIT one**. Then the note in part 0 ("the shipped-style binned model covers only 0.958-0.963 at 7 d") describes a step the tool does not use. The shipped path covers 0.979-0.982 at 7 d. That is still low, but less so. Both PIT and the range map are fitted on the same calibration rows (`cal`), and fitting two steps on the same rows can make the tails look right in-sample and come out narrow on new data. That is my guess at the cause, untested.

---

## 0. What the 48 hours say in general

These patterns decide the choices in parts 2 and 3.

**What kept working**

| Pattern | Evidence |
|---|---|
| A measured table beside the network beats a new network body | SIGMA's beta / s tables (PASS), the 6-number real-air gap (PASS), the per-site factor IL-207b (PASS), fixed widening AV6 (PASS), neighbour rho B (adopted) |
| More information in | ensemble features -1.9 to -3.1 %, an older run mixed in -0.8 to -2.4 %, the world start -0.7 to -2.5 %, radar on launch day +31 % |
| Learning the leftover around a climate centre | SIGMA (centre = climate + beta x forecast anomaly); earlier the climatology debias at Denver (-0.19 -> -0.03) |
| More test rows turn a near miss into a pass | AV28 MISS -> AV29 PASS on 2021 + 2022; O1 FAIL at 200 h -> AV7 seed 2 PASS at 600 h. Many "misses" were sample size, not the idea |
| Network size where there is signal | N6 best at 1-3 d; NEST beats SIGMA width 128 by 1.3-1.5 % at 1 d and ties at 7 d |

**What kept failing**

| Pattern | Evidence |
|---|---|
| One trunk fed two different input worlds | N4 KILL (zeros + "present" bit) |
| Hard routers between models | AV1 KILL on a 0.1 % tie; AV3 never ran |
| Re-ordering members | C2, G1-4, O5 (ECC), STRAND templates (they over-link: lift 3.51 vs real 2.35) |
| Trackers that follow recent errors | G1-5 (sat at its cap), G1-7 (not needed), O3 (moved only 0.9-1.2 in two weeks) |
| A uniform stretch to fix the far tails | RH 12-18 km: cov99 0.948 -> 0.991 but CRPS +5.9 % |
| Changing the noise shape to fix coverage | AV30: cov99 did not move at all |
| Run disagreement as a spread signal | C6 / AV4 / AV25: CRPS better every time, calibration worse on more dates |
| Guessing a site from descriptors | N2-C MISS, P7 neutral, S2 premise wrong |

**The one clause that killed the most.** The 99 % range (cov99) is the clause that stopped AV2, NEST and AV30, and it is the RH 12-18 km failure too. The NEST log shows why the clause is hard to read: the shipped-style binned model itself covers 0.991-0.993 at 1 d and only 0.958-0.963 at 7 d, while NEST is flat near 0.98. So "within 0.003 of binned" compares against a target that is itself off by up to 0.03 at 7 d. That is a finding about the shipped model, not only about NEST (see new idea 1). **Correction (11-14):** these numbers are the PIT column. The column the tool appears to export (no PIT) gives binned 0.979-0.982 at 7 d and NEST / SIGMA 0.987-0.993. See the update at the top and new idea 7.

---

## Part 1. Ideas to still consider adding

### 1A. Passed their pre-set rule, little downside

| # | Idea | Switch today | Measured | Downside / caveat | Best use |
|---|---|---|---|---|---|
| 1 | **SIGMA stage 2**: lead time as a noise level, tabled beta / s | `il6_modeF.py --sigma` (off) | vs binned: 1-7 d -1.7 to +0.0 %, beyond 7.5 d -3.9 to -4.8 %; beyond 7.5 d it beats the climate model by 0.55-0.70 CRPS, better at day 8, 9 and 10 in all 4 runs | not in the exported tool yet; its cov99 by lead is not in the log (check before export) | First choice for days 8-10, where the tool falls back to climate today. Also removes the four lead bins and the untuned ramp |
| 2 | **World start + 500 box steps** (N2 / AV29) | networks on disk, no tool path | pooled 2021 + 2022, 3 seeds: -0.7 to -2.5 %, wins 4/4/4 NM/TX and 3/3/4 Denver | third variation of N2 (forking paths); Denver 1 d interval touches 0 in two seeds | Every box. Strongest for a new or data-poor box: N2-B showed -1.9 to -5.1 % with one fit year, "worth about 3 box years" |
| 3 | **ENSF2 ensemble features** | `export --modef-ens`, `api ens_features=` (off) | -1.9 to -3.1 % NM/TX, -0.7 to -2.2 % Denver, three seeds | needs 24 ensemble inputs at launch; one test year | Use when the ensemble feed is there, the plain network when not. Keep them as two networks (N4) |
| 4 | **Real-air gap, 6 numbers** (RA stage 1a) | kit only | 90 % range against real balloons at 197 left-out stations: 0.83-0.90 -> 0.90-0.92 in all 6 bands | coverage pooled over leads; part of the gap is balloon noise | An opt-in "real air" output in every mode. Matters most at 10 m (0.83 without it) and at leads under 5 d; beyond a week it is 3 % of the error |
| 5 | **Cross-fitted members** (N1) | models trained, not exported | ERA5 skill15 +0.0020 / +0.0026, balloons +0.0030 / +0.0037 | members see 3 more years than the base, so part may be data | Climate mode. Run the one missing control first (part 2, row 13) |
| 6 | **Per-site wind factor** (IL-207b) | `tcs_speed_factor` (opt-in) | TCS CRPS -0.079 and -0.075, coverage 0.81 -> 0.85 / 0.86; Midland unchanged | TCS is a 30 km stand-in for the pad; seed 1's interval is the one the audit re-read wants confirmed | Only sites with their own record |
| 7 | **Student-t widening on a surprising report** (G2-2) | `observe(..., t_update=)` (off) | most surprising 10 %: cov90 0.85 -> 0.92; other 90 %: CRPS -0.0003 | radar path not tested; T / p / RH not widened | Turn on for ground reports. It acts only when the report is far from the pool |
| 8 | **Radar from 145 km** (O2) | no switch needed | Holloman keeps the El Paso gain: 2.5-5 km +27.6 % vs +29.1 %, 5-12 km +15.0 % vs +13.5 %, coverage 0.92 / 0.94 | 23 UTC hours only | The pad can use Holloman (about 80 km) with no distance term |
| 9 | **Fixed widening of raw ensemble wind** (AV6 a) | kit only | TCS x1.35: -0.022 [-0.040, -0.004]; MAF x1.55: -0.044 [-0.068, -0.020]; coverage error 0.24-0.27 -> 0.12 | the tool does not serve raw ensemble members | Only if a raw-ensemble path is ever served. Its real value is as evidence for new idea 3 |
| 13 **(11-14)** | **Two neighbour stations at once** (O1 / AV7), moved up from row 11 | kit only; ASK_LATER 31 | seeds 2 / 3 at 600 h: TCS -0.063 / -0.066 against the best single neighbour, ELP -0.042 / -0.043, every interval below 0; coverage TCS 0.81 / 0.81, ELP 0.84 / 0.86 | at TCS the merge is **narrower than either neighbour alone** (0.81 vs 0.84-0.85), one point above the floor | Any pad with two stations within reach. Keep the coverage fix in part 2, row 20 in mind before export |
| 14 **(11-14)** | **Site map first, launch-day update second** (S1 / AV31) | kit only; ASK_LATER 32 | 600 h, 2 seeds: map + B never worse than B at any of 8 pairs. With a neighbour's report: LRU -0.036 / -0.034 (intervals below 0), PEQ -0.022 / -0.003. With no report: TCS 1.540 -> 1.469 and 1.670 -> 1.606, MAF 1.535 -> 1.475 and 1.472 -> 1.441. Factors stable to 0.022 between seeds | with a fresh 1 h report from the site itself it adds little at TCS (-0.004 / -0.006, interval includes 0); MAF still -0.019 / -0.020 | Whenever the pad has no fresh report of its own: the map is the best thing we have for the hours before and between reports |
| 15 **(11-14)** | **SIGMA (and NEST) scored without the PIT step** | `il6_modeF.py`; the column is already in every `_eval.csv` | cov99 0.987-0.993 at every lead in both boxes and seeds, against 0.976-0.984 with PIT; CRPS within 0.05 % | found by looking, not by a pre-set rule (see the update above); a few cells still about 0.007 low at 1 d | If confirmed, SIGMA for days 8-10 needs no tail fix at all. This is the cheapest open item in the file |
| 16 **(11-19)** | **Trust layer, looser keep threshold** (AV34) | kit only; ASK_LATER 33 | ERA5 skill15 +0.0012, balloons +0.0019, no band worse | gain sits in rh2m and v 0-1 km only | Climate mode, on top of N1 |
| 17 **(11-19)** | **Shear map, 5-12 km at half gain + 12-18 km full** (AV35) | kit only; ASK_LATER 34 | shear p99 vs balloons 0.969 / 1.021 in those bands, CRPS +0.03 % | adds +0.014 vertical-correlation error at far pairs (22.V0); 0-1 km p99 untouched (0.71) | Every mode; the only fix so far for the shear-tail flaw above 5 km |
| 18 **(11-19)** | **Student-t output stack** (AV19) | kit only; ASK_LATER 38 | Denver +0.0189, NM/TX -0.0004 | helps the transfer box only | New or data-poor boxes, and the global stage |
| 19 **(11-19)** | **Cross-fitting is N1's gain** (UR8) | confirms row 5 | +0.0041 / +0.0047 against the same-data control | closes the "part may be data" caveat of row 5 | Row 5 is now clean |
| 20 **(11-19)** | **IL-207b confirmed** (UR9) | confirms row 6 | TCS CRPS -0.102 | still TCS as stand-in for the pad | Row 6 is now clean |
| 21 **(11-19)** | **Measured grid-to-point gap table** (UR3, new idea 3) | kit only | 1.54 m/s measured gap beats the fitted widening factors at TCS and MAF | two sites | Replaces row 9 style factors for ground wind |
| 22 **(11-19)** | **Gust items** (AV13, AV36) | kit only; ASK_LATER 35 / 36 | both passed their rules | see section 9 rows | Gust output |
| 23 **(11-19)** | **Nowcast** (NOW2) and **radar pairs** (E3) | kit only; ASK_LATER 37 / 42 | NOW2 +8 %; E3 -27.7 % / -10.3 % at 1 / 2 h | gains fade after 2 h | First 2 h of a launch window |
| 24 **(11-19)** | **DP tower** and **T3 nugget** | kit only; ASK_LATER 39 / 40 | both passed | T3 sign is the opposite at HDX: MAF only until explained | Site-specific |
| 25 **(11-19)** | **SIGMA holds on a third period** (UR15) | confirms row 1; ASK_LATER 43 | SIGMA gain repeats on 2023-24 | NEST cov99 at 1 d 0.917-0.936 in the same log (check if PIT column) | Row 1 is now clean for days 8-10 |

**Row 6 note (11-14).** The AV10 / AV32 / AV33 replays scored "IL-207b alone" against "no factor" on four fresh samples (2023-25, 08-20 local). TCS: 1.417 -> 1.427 (worse, 150 days, seed 0), 1.652 -> 1.572, 1.516 -> 1.458, 1.645 -> 1.580. MAF: 1.514 -> 1.463, 1.475 -> 1.464, 1.545 -> 1.499, 1.512 -> 1.505. Coverage was never lower. MAF was "unchanged" in the original IL-207b run but is better in all four replays here. The samples probably overlap (the 150-day runs share their days across AV10 and AV32, and the 300-day runs likely include them), so this is support, not a fresh pass. UR9 is still the confirming run.

### 1B. Missed the rule on sample size only (every point estimate in favour)

| # | Idea | Measured | What is missing |
|---|---|---|---|
| 10 | **Older run mixed in, network retrained** (CHORUS, AV24 / AV26) | better at every lead in all 4 runs on 2021 and on 2022 (-0.8 to -2.4 %), 14 of 16 pooled intervals below 0, cov99 within 0.003 | each run misses on one long lead; no clean third test year. A looser rule is your call (ASK_LATER 29). Yesterday's run is already kept by the tool's logger, so no new feed |
| 11 | **Two neighbour stations at once** (O1 / AV7) | seed 2 at 600 h: TCS -0.063 [-0.108, -0.020], El Paso -0.042 [-0.066, -0.019], coverage 0.81 / 0.84 | seed 3. TCS coverage 0.81 is one point above the floor |
| 12 | **NEST** (SIGMA at width 512, nested) | all 20 intervals below 0; 1 d -1.6 to -2.1 %, beyond 7.5 d -3.7 to -4.7 % | fails only the 1 % bar at NM/TX 3-5 d and the cov99 clause. Not ready as it is: see part 2, row 1. **(11-14)** Without the PIT step its cov99 is 0.989-0.992 at NM/TX and 0.988-0.990 at Denver, so the cov99 clause may not be a real fault (row 15). The 1 % bar is unchanged |
| 11 -> 13 **(11-14)** | Two neighbours now PASSED (AV7 seed 3); see row 13 | | |
| 16 **(11-14)** | **IL-10 trust layer refit on l3_c4w** (AV17) | ERA5 +0.0006 / +0.0006 / +0.0007 in 3 seeds, balloons +0.0012, coverage error flat, **no band worse anywhere**; T 12-18 km now 0.0000 (it lost -0.0043 in IL-10). Per band: rh2m +0.008 to +0.010, v 0-1 km +0.002 to +0.003 | the mean over 19 bands needs > 0.0009. Only 18 of 179 columns blend, so the mean is diluted by bands it never touches. AV34 (looser keep threshold) is running. A narrower kept version is part 2, row 24 |

### 1C. Small switches already in the code (off, tested, safe)

| Switch | What it does | When to use it |
|---|---|---|
| `Launch(past_wind_spread=1.2)` | wider past-mode ground wind | airport-like sites only (TCS / MAF -8 / -13 %); it hurt both open-basin sites. **(11-14)** AV11 KILL: at six servable airports it was better only at MAF (-0.029 [-0.050, -0.010]), worse at LRU (+0.024, interval above 0), PEQ and ELP, and neutral at TCS and ALM. Use it at MAF only, or not at all |
| `below_10m="loglaw"` | log-law wind below 10 m | rails under about 3 m |
| `sample_sobol_batch(z0_roughness_m="site")` | turbulence uses the site's own roughness (it never reached Dryden before) | rough sites; changes near-ground turbulence strength |
| `--wind-from 150` | removes a false shear step at 100-150 m (18 % of columns, p99 shear +21 %) | at the next store rebuild |
| station `--launch-tol 30` | drops 914 Santa Teresa soundings launched 60 m off | already the default for new fits; the shipped map still needs the refit |

**Reporting switches** (they change what we claim, not the tool): `--fair-baseline` (the honest ERA5 headline is about +1.7 to +1.8 %, not +2.8 %; ASK_LATER 27), `--gauss15` (the margin over a bell curve is 92 % shape, 8 % trend), `sonde --partial`, `--template-before-year 2021`. My reading: `--fair-baseline` should become the default before any number is quoted outside.

### 1D. Which piece where (the splits)

| Split | Use |
|---|---|
| **Lead 0-3 d** | most network capacity pays here (N6, NEST), plus ensemble features and the world start |
| **Lead 5-7 d** | small network; the older-run mix helps most here (7 d: -2.2 to -3.5 % even without retraining) |
| **Lead 8-10 d** | SIGMA, not the climate fallback |
| **10 m** | the real-air gap is largest relative to the error (coverage 0.83 without it); site factor; two neighbours; Student-t widening |
| **0-12 km wind** | the only bands where run disagreement ranks the error (0.30-0.38); nothing above 12 km |
| **2.5-12 km on launch day** | radar, also from a distant site |
| **12-18 km** | the weak band everywhere; treat on its own (new idea 6) |
| **Airport vs open basin** | wider past-mode spread at airports only |
| **Day vs night** | the TCS error has the same sign day and night (+0.52 / +1.08 m/s), so one factor per site is enough; gust-as-measurement helps only in daytime mixed air |
| **New or data-poor box** | world start first, then the box's own steps |
| **Own fresh report / neighbour report / no report** (11-14) | With a 1 h old report from the site itself, the update does nearly all the work (the TCS map adds -0.004 / -0.006, inside noise). With only a neighbour's report, the map adds -0.03 to -0.04 at LRU. With no report, the map alone adds -0.03 to -0.07. Two neighbours merged beat either one (AV7) |
| **Time of day x season at the site** (11-14) | AV31's map cells are stable between seeds (gap 0.022) but differ a lot. TCS runs 0.94-0.96 in cool mornings and late afternoons and 1.21-1.23 in warm late afternoons. MAF runs 1.14-1.16 in warm mornings and 0.84-0.85 in cool late afternoons. So the sign is the same day and night at TCS (S2), but the size is not: one number per site leaves this on the table (new idea 9) |
| **Centre vs spread** (11-14) | AV9, AV11 and AV7 all show it again: a step that moves the centre closer cuts CRPS and drops coverage; widening without moving the centre raises coverage and can make CRPS worse. Past-mode coverage is 0.71-0.82 at every airport, and that is a centre fault (new idea 8) |
| **rh2m and wind below 1 km** (11-14) | the only places the IL-10 trust layer still gains anything (AV17) |

---

## Part 2. Potential, but needs a new version

Each row: what failed, what the trend says, and the version I would build. "Drop" means a logged variation that I think is now the weaker path.

| # | Idea and state | Why it fell short | New version |
|---|---|---|---|
| 1 | **NEST / AV30** (MISS twice) | cov99 flat near 0.98; AV30 proved it is not the noise shape. The log's own guess: the s table / PIT step | Keep the network, fix the last step: tail calibration per lead day (new idea 1). Judge cov99 against 0.99, not against binned (rule change = your call). For the 1 % bar at NM/TX 5 d add the older-run mix, which gains exactly there |
| 2 | **N6 big model / AV1 / AV22** | worse at 7 d; hard split died on a tie | Drop AV22 (blend of two models). NEST is the same aim in one network and already beats binned at every lead. What NEST lacks against N6: the world start, all 44 heights, depth 4, 4 members. Add the world start first (new idea 2) |
| 3 | **N5 all-lead / AV2 / AV23** | short leads worse; cov99 0.978-0.983 beyond 7.5 d | Drop AV23. SIGMA already does N5's job without the short-lead loss, and its formula fades to climate by itself. Same tail fix as row 1 |
| 4 | **CHORUS mix** (rows 10 above) | 36 h older run only; older members add less at short leads | (a) 12 h older pairs if a refetch brings them; (b) put the mix inside SIGMA so the mixed profile also gets a smaller s. Outside work agrees with the shape of our gain: lagged runs help mostly at long range and plain averaging of old runs adds little, so keep the measured weights |
| 5 | **C6 / AV4 / AV25 run disagreement** (closed for calibration) | CRPS better on every test (-0.33 to -0.69 %, intervals below 0) but PIT worse on more dates | My reading: the signal says where the forecast is less right, not how wide the range should be. Use it on the centre: let it lower beta (pull toward climate) in SIGMA, in the 4 cells where it ranks the error. Also the run's own 6-hour change (ranks error at 0.25-0.39, needs no second run). Untested |
| 6 | **STRAND** (closed for climate mode) | templates over-link; the real floor was a per-hour bias | Two smaller things survive: (a) the climate-mode 10 m wind is windier than ERA5 (P under 5 m/s lower by 0.06-0.14), an open bias worth more than any re-ordering (new idea 5); (b) the shipped sequence under-links calm windows (lift 2.10 vs 2.35 at 5 m/s) and over-links at 8-10 m/s. Forecast-mode aged noise is still untested and holds only beyond day 4 |
| 7 | **S1 map first, update second** | one out-of-area neighbour at 0.78; factors unsteady with 40 h per cell | AV8 as logged (120 h per cell, out-of-area neighbours left out). CRPS was better at 12 of 12, so the order is right. Then stack with AV7 |
| 8 | **O3 launch-week factor** | the decaying average is too slow (factor moved 0.9-1.2 in two weeks) | Replace the tracker with a shrinkage average (new idea 4). SV step 0 already measured it: 5 / 10 / 30 readings explain 25 / 53 / 71 % of a station's offset |
| 9 | **G1-5 tracker / AV6** | it was a fixed widening, not tracking; part (b) blocked (no 2023-24 tool output) | Stop fitting a factor per site. The widening is the gap between a grid value and a point reading; measure it once (new idea 3) |
| 10 | **RH 12-18 km widening** | uniform stretch cost +5.9 % CRPS | First remove the drift AU-5 found (2021-23 balloons 8-11 % drier aloft than the 1991-2020 line); part of the "narrow range" may be a shifted centre. Only then tails only (new idea 1's method). My reading, untested |
| 11 | **Shear target, IL-103 aloft** (AV15, AV16) | each form passed one band | Low value for apogee (IL-201). Keep AV16 (12-18 km only) for loads work; build the measured-profile bank (E5) first, as the bar that says how much structure is missing |
| 12 | **O4 analog tail fix** | tail not halved, coverage 0.89 -> 0.83 | AV9 as logged (keep the spread). It is a referee only, so the risk is nil |
| 13 | **N1 cross-fit** (PASS, caveat) | gain may be the 3 extra years | One control: the base recipe trained on the same years without cross-fitting. If the gain stays, export |
| 14 | **A2 x1.2 at airports** (AV11) | site-type switch | Fold into new idea 4 (the site's own offset and spread) instead of an airport flag; a pad is not an airport |
| 15 | **Denver transfer** (AV19-AV21) | each fixed one thing and broke another | The trend favours AV21 (learn in anomaly space): it is what SIGMA does for forecast mode and what the debias did for Denver. Do it with the global work, not before |
| 16 | **IL-10 trust layer on NM/TX** (AV17) | lost on T 12-18 km only | AV17 as logged (that band switched off); cheap GPU scoring |
| 17 | **Gust as a measurement, regional gust law** (AV12, AV13) | too small / tie | Daytime gate and speed switch as logged; lowest priority |
| 18 **(11-14)** | **NEST and SIGMA cov99** (rows 1 and 3; UR7, UR1) | cov99 0.976-0.984 in the PIT column | **First a re-score, no new fit**: rerun the NEST (b20) and AV30 (b21) verdict scripts with their rules unchanged, but judged on the column the tool exports (no PIT). The CRPS rows hardly move, so this settles only the cov99 clause. Set the column choice in the verdict header before running it. It is a change of what is scored, so it is your call (as with UR1's rule). If it passes, UR1 shrinks to the few cells still off (T 1-5 km and v 12-18 km at 1 d, about 0.983) |
| 19 **(11-14)** | **AV9 analog shift** (KILL on coverage) | CRPS -0.018 / -0.027 and strong-wind under-prediction -15 / -27 %, both halves; TCS coverage 0.89 -> 0.84 / 0.85 | The shift is right; the spread was left as it was. (a) **Shift, then re-spread**: scale the analog spread so the fit-years cov90 after the shift equals the plain analog's, one number per site. (b) **Half shift** (w = 0.5), which keeps more of the old spread. (c) Shift only when ERA5 now is at or above 6 m/s, where the under-prediction lives. It is a referee, so the risk is nil. Rule: AV9's own |
| 20 **(11-14)** | **AV7 merge narrows at TCS** (coverage 0.81 vs 0.84-0.85 alone) | The merge uses the error correlation fitted on 2019-22 (r +0.39 / +0.43). Narrowing beyond what either source supports is the classic sign of over-trust | (a) **Centre-only merge**: the merged centre with the spread of the better single neighbour. (b) Fit r on the test-like hours only (08-20 local), since the 16,000 fit hours include night. Rule: AV7's CRPS clause kept, coverage at least 0.84 at TCS. Cheap: AV7's script and seeds |
| 21 **(11-14)** | **AV31 map vs report age** | with a 1 h old own report the map is nearly redundant at TCS; with no report it is worth 0.03-0.07 | Run the same replay with the report 3 h and 6 h old. The age at which the map's value comes back sets how long a pad report should be trusted on its own (new idea 10). One CPU run per age |
| 22 **(11-14)** | **O3 tracker on IL-207b** (AV10 / AV32 / AV33, closed) | the gain shrank from 150 to 300 days; day-to-day factors swing over about 0.75-1.40 around a steady 1.10-1.11 (TCS) / 1.00-1.03 (MAF) | **Drop the tracker line**, with no more alpha or window variations. The lesson to keep: the swing is weather, the steady part is the site. A short record should estimate the steady part once (UR4), not chase the swing. The one thing left that is not a tracker: k = 3 at MAF was below 0 in both 300-day seeds (-0.006 / -0.008), which is the size of a "yesterday's error" term. Only worth it inside UR4 as a second term, never alone |
| 23 **(11-14)** | **AV11 x1.2 at airports** (KILL) | past-mode coverage 0.71-0.82 everywhere, but widening worsens CRPS at 3 of 6 | Do not widen past mode further. The past-mode centre at airports is the fault: fold it into UR4 (the site offset) and UR3 (grid-to-point). **Also:** ONM, FST and ABQ (3 of 9 airports) are outside the trained box (lat 31-34), so UR4's 71-station replay must check which stations can be served before any rule counts them |
| 24 **(11-14)** | **AV17 / AV34 trust layer** | gain real but diluted over 19 bands | If AV34 also misses: **a trust layer on rh2m and v 0-1 km only**, judged on the bands it touches, with the other bands required to stay bit-identical. That is a rule change (mean over touched bands, not over all 19), so it is your call. My reading: rh2m +0.008 to +0.010 in all 3 seeds is worth having for launch-day humidity |
| 25 **(11-14)** | **Binned model beyond 7 d** | even without PIT it covers 0.979-0.982 at 7 d and 0.962-0.966 beyond 7.5 d, while SIGMA stays flat | My reading: the fixed lead bins lose the tail at long lead, not the last step. Another reason to move days 5-10 to SIGMA. Keep TAILCAL (UR1) for binned at 7 d only if binned stays the 5-7 d model |
| 26 **(11-14)** | **PIT recal on its own rows** | PIT and the range map are fitted on the same `cal` rows; PIT then costs 0.01 of cov99 out of sample in all 17 tables | Before PIT is dropped for good: fit PIT on half of `cal` and the range map on the other half, and see whether PIT then improves CRPS or the PIT shape without losing cov99 (the tables store no PIT score, so this needs one evaluation run). If not, remove PIT from the forecast verdict column. My reading, untested |

**One download that unblocks four verdicts.** HRES on disk ends 2022-12. A 2023-24 pull (a Colab pull like every HRES store) gives a clean third test year. It would settle CHORUS (ASK_LATER 29), AV6 part (b), any stacked forecast engine (new idea 2), and take the forking-paths doubt off N2. My reading: this is the highest-value single action in this file.

---

## Part 3. New ideas

Built from parts that worked. Each one is attacked in rounds and rebuilt; the last form is the one to test. Rules are proposals; set them in the verdict script before any run, as always.

### New idea 1. TAILCAL: fix the far tails per lead day, touch nothing else

**From:** the cov99 failures (AV2, NEST, AV30, RH), G2-2 (widening only where needed cost no CRPS), AV30 (noise shape is not the cause).

**First form.** After the range map, stretch only the part of each member set outside its own 5-95 % range, by one factor per lead day, so the 99 % range holds 99 %.

| Attack | Rebuild |
|---|---|
| The 1 % tail has few rows per cell, so the factors will be noise | One factor per variable x lead day, pooled over heights (my estimate, not counted: on the order of 1,000 misses per cell in the 2021 rows; count them in step 0); smooth across lead days |
| A stretch breaks the order of members across heights | It is a rising map per height, so ranks do not change and the Schaake shuffle is untouched |
| The uniform RH stretch cost +5.9 % CRPS | That moved the whole distribution. Here the middle 90 % is bit-identical; only 10 % of members move. Expect under 0.2 %; kill above 0.5 % |
| The factor must also shrink (binned over-covers nothing, but NEST covers more than binned at 7 d) | Allow factors below 1; separate lower and upper tail |
| Fitted on the year it is judged on | Fit on 2021 rows, judge on 2022; then swap as a check |
| "Within 0.003 of binned" cannot be passed when binned itself is 0.96 at 7 d | Proposed rule: cov99 within 0.005 of 0.99 at every lead, CRPS not worse by more than 0.2 %. This is a rule change, so it is your call |
| Outside methods adapt the padding online | Not needed: our miss is steady by lead, and trackers failed here three times. The outside result that matters is that tail-only padding leaves CRPS "virtually unchanged" |

**Final form.** A table (variable x lead day x lower / upper) of tail factors, applied after the range map. Test it first on the **shipped binned model**, where it is a fix for a measured fault (cov99 0.96 at 7 d), then on SIGMA, then on NEST. No training. About 1 h CPU on rows already on disk.

### New idea 2. One forecast engine, stacked in a fixed order

**From:** SIGMA (PASS), NEST (+1.3-1.5 % at 1 d over SIGMA), world start (PASS), older-run mix (near pass), ensemble features (confirmed), and N4's lesson.

**First form.** Train one network with everything on.

| Attack | Rebuild |
|---|---|
| The gains overlap; they will not add up | Fixed order, one stage at a time, each must add at least 0.5 % with an interval below 0 on pooled 2021 + 2022, or the stack stops there: (1) SIGMA, (2) + NEST, (3) + world start, (4) + older-run mix, (5) + ensemble |
| N4: optional inputs in one trunk lost 1-2.6 % | The ensemble never enters the trunk. Its mean is one more source in the closed-rule mix; its spread only scales s (held to 0.8-1.5). No feed = the plain table. The trunk always sees one profile of the same kind |
| The world network was fitted on the plain leftover, not SIGMA's target | Build beta / s tables on the world pairs (63.6 M on disk), train the world network on the scaled target, then swap in the box's tables for the 500 box steps. Side test: with a size-1 target the world model "as is" may now come within 1 % of the box model, the clause N2 failed |
| cov99 | TAILCAL is the last step of every stage |
| This is one more forecast-mode variation on the same test year | 3 seeds, 21-day blocks, both years pooled, the rule written once. Final word from the 2023-24 pull above |
| RAM: one forecast-mode job at a time | Stages run in sequence; NEST fits take about 5 minutes on the GPU |

**Final form.** `--sigma --nest` + world tables + mixed input + tail table, ensemble as a scale on s. Stage 1 is done, stage 2 exists; stage 3 is the next new run.

### New idea 3. One measured "grid to point" table instead of widening factors

**From:** RA stage 1a (PASS), AV6 (PASS), G1-5, the x1.2 switch, IL-207 (the TCS fault was bias, not spread), the tower check (past-mode coverage 0.51-0.60 at 47-200 m).

**First form.** Add the real-air gap spread to every member, everywhere.

| Attack | Rebuild |
|---|---|
| Part of the gap is balloon noise (about 0.5 m/s) | Subtract it in squares, using the radar as the third instrument (the C5 referee) |
| At 10 m the gap depends on the site: x1.2 helped airports and hurt basins | Two parts. The **centre** comes from the site (new idea 4). The **spread** is the table, and it shrinks as site readings arrive |
| IL-207 showed a bias, and spread cannot fix a bias | Same split: never widen to hide an offset |
| The tool already widens forecast wind (IL-101) | The table replaces it, it is not added on top. Test: does the 10 m gap (1.54 m/s) applied to the raw ensemble reach the coverage error 0.12 that the fitted factors 1.35 / 1.55 reached? If yes, no per-site fit is needed |
| It worsens scores against ERA5 | It is a separate output ("real air"), scored against balloons and stations only. Outside practice is the same: ECMWF adds this error before scoring against stations |
| Coverage was pooled over leads | Report by lead; the gap is the same size at every lead (1.81 / 1.82 / 1.84 m/s at 1.5 km), so it should hold |

**Final form.** One table (6 height bands, instrument noise removed) used the same way in climate, past and forecast mode, with the site's centre from idea 4. Needs no download for the 10 m test.

### New idea 4. FIRST-10: a pad's own offset from its first readings

**From:** SV step 0 (a station keeps its offset, 0.88; 10 readings explain 53 %), IL-207b (PASS), S1 (map first: CRPS better 12 of 12), S2 (same sign day and night), O3's failure, AV7.

**First form.** Average the first readings at the pad and use the ratio as the site factor.

| Attack | Rebuild |
|---|---|
| Five readings are noisy (25 % explained) | Shrink toward the regional value: factor = 1 + w x (measured - 1), w = n / (n + k). From the SV numbers k is about 9-15 (untested fit of mine: 5 / 10 / 30 readings give 25 / 53 / 71 %) |
| Readings an hour apart are not independent | Count days, not readings; fit k per day |
| A short record carries its season | The uncertainty left in the factor, (1 - w) x the between-station spread (1.01 m/s), goes into the pool as spread. The tool is honestly wider at an unknown pad and narrows as readings come in. Outside work: one month of site data gets close to a full year on average, but can be worse than no correction at poorly matched sites, which is what the shrinkage guards |
| O3 did this and failed | O3 used a slow decaying average from 1.0. This reaches half weight in about 10-15 days and starts from the regional prior |
| Two test sites cannot prove it | Replay at all 71 stations of the SV step 0, leave one out: pretend each is a new pad, feed it n days. Proposed rule: 10 m CRPS better than "no site term" with an interval below 0 at n = 10, no station worse by more than 0.03 |
| A better starting guess than "1.0" | The wind atlas factor (E1) as the prior centre, only if E1's own step 0 passes |
| Order with the launch-day report | Site centre first, then `observe`, then the second neighbour (S1 order) |

**Final form.** Prior (regional, later atlas) -> shrinkage update per day of readings -> leftover uncertainty as spread -> `observe`. No download; ASOS records are on disk.

### New idea 5. Calm-window fix: the per-hour wind first, the link second

**From:** STRAND stage 0 (independent hours give 0.41 for "under 5 m/s for 3 h", real 0.64), stage 1 and AV27 (the floor is the per-hour wind; the shipped sequence already carries most of the link), RA step 0 (real air is calm 17.3 % of the time, ERA5 11.0 %).

**First form.** Re-order members with real-day templates. That is what was killed.

| Attack | Rebuild |
|---|---|
| The largest error is not the link | Per-hour gap 0.12-0.19; link error of the shipped sequence 0.04-0.09. Fix the per-hour 10 m speed first |
| The cause of the windier 10 m wind is unknown | The code read ruled out the two intended widenings. One guess of mine, untested: calibrating the range of u and v separately widens each a little, and a wider u and v always raises the mean speed. Step 0: compare u, v and speed against ERA5 at the AV27 points before and after each calibration step |
| A speed fix can break the u / v ranges | Map the 10 m speed by quantile to the ERA5 speed of the same point, month and hour, keep the direction, then demand u and v cov90 within 0.003 of before |
| Then the link | Only if the 3-hour error is still above 0.02: two lag tables (calm and windy hours) in place of one, since the shipped sequence under-links at 5 m/s and over-links at 8-10 m/s |
| Truth is ERA5, and real air is calmer still | Second referee: ASOS 3-hour windows at TCS / MAF |

**Final form.** Step 0 (find where the speed drifts), a 10 m speed map, then the two-regime lag table if needed. The calm-window probability is the number a launch decision uses, so this is worth more than its size suggests.

### New idea 6. The 12-18 km package: one coordinate for the band that loses everywhere

**From:** T 12-18 km worse than climatology (-0.030 / -0.039); RH cov99 0.948; balloon drift aloft (AU-5); shear p99 24.6 vs 28.5; unstable layers 0.067 vs 0.149; the trust layer lost only there; SIREN at Denver -0.30 there; skill autocorrelation 19 days there (AU-4). E4 in the plan names the cause candidate: the tropopause moves through fixed heights.

**First form (E4).** Add fine balloon structure relative to the tropopause.

| Attack | Rebuild |
|---|---|
| Fine structure is the last thing to fix when the centre and range are off | Use the coordinate for the **calibration maps** first: range map, station line and shear map for 9-18 km indexed by distance from the member's own tropopause |
| Finding the tropopause on 44 heights is noisy | Lapse-rate rule on the member's T; fall back to the coldest point; skip the member (fixed-height map) when neither is clear |
| Is the change around 2020 really a height shift? | E4's step 0 answers both questions with balloons only: spread at fixed distance from the tropopause under 70 % of fixed-height spread at 3 or more levels, and the post-2020 change as a height shift. Kill at over 90 % |
| It will disturb the bands below | Bit-identical below 9 km by construction |
| RH aloft | Refit the station line on recent years first (AU-5 follow-up); the coordinate comes second |

**Final form.** Step 0 on balloons (no tool scoring), then the three maps in the new coordinate above 9 km, then the aloft-only shear map (AV16) and AV17 judged again on top.

**Note on idea 1 (11-14).** Its premise ("binned itself is 0.96 at 7 d") is the PIT column. On the column the tool exports, SIGMA and NEST already sit near 0.99, and binned is 0.98 at 7 d. TAILCAL is still worth building, but as the small last step of idea 7, not as the first item.

### New idea 7 (11-14). SHIPPED-COLUMN LEDGER: score what the tool runs, one step at a time

**From:** the PIT measurement in the update above (17 tables, the cov99 shortfall made by one step), NEST / AV30 / UR7, which all scored a column the export does not use (code reading), and the general pattern "a measured table beside the network beats a new network body".

**First form.** Switch every forecast verdict to the no-PIT column.

| Attack | Rebuild |
|---|---|
| Switching columns after seeing the numbers is a forking path | Write the column choice into the verdict scripts once, for **all future runs**, and re-score the past verdicts only as a report, not as new passes. The clean word comes from UR15 (2023-24), scored on the shipped column from the start |
| "Shipped" is a code reading, not checked | Step 0: load the shipped forecast pack, push 100 test rows through `tempest` and through the eval column, and demand identical members. Ten minutes on the CPU |
| One column hides where each step helps | A **ledger** per model: raw -> range map -> shuffle -> (PIT) -> (ridge blend), each with CRPS, cov90 and cov99 by lead. The eval already computes most of it; only cov90 is missing (UR7 noted it is not stored). Any new step must improve its own line of the ledger, or it is not added |
| The PIT step may help something the tables do not show | Part 2, row 26: fit PIT and the range map on separate halves of `cal`. Keep PIT only if its ledger line is better on new rows |
| The H2 mixes over-cover (0.992-0.996) | That is the same ledger telling us the mixes are wide. A mix chosen only on CRPS should still show its cov99, so that over-cover is caught as well as under-cover |

**Final form.** A fixed "as shipped" column plus a step ledger in `il6_modeF.py`'s report (new output only, defaults unchanged), the step 0 identity check, and past verdicts re-read as a report. No training. This comes before TAILCAL, UR2 stage 3 and any export of SIGMA.

### New idea 8 (11-14). MOVE-THEN-RESPREAD: every centre fix carries its own spread refit

**From:** AV9 (centre right, coverage -0.04 / -0.05), AV7 (merge narrows at TCS), AV11 (wider without a better centre is worse), C6 / AV4 / AV25 (CRPS better, calibration worse), IL-207 (the TCS fault was bias), AV31 (a mean map raises coverage as it fixes the centre: TCS 0.79 -> 0.82, 0.80 -> 0.83).

**First form.** After any step that moves the centre, rescale the spread so cov90 on the fit years is back at 0.90.

| Attack | Rebuild |
|---|---|
| Refitting spread on the same rows that set the shift overfits | Shift fitted on the fit years, spread scale fitted on a later held-out block of the fit years, judged on the test years |
| A global rescale undoes the sharpening that made CRPS better | One scale per site (or per AV31 cell), held to 0.9-1.4, and the rule asks for at least 80 % of the CRPS gain kept, not all of it |
| Coverage up and CRPS down cannot both be promised | Then the rule says which wins: coverage back within 0.01 of the pre-shift value, with CRPS still better and the interval below 0. If both cannot hold, the centre fix stays a referee-only result |
| It is one more knob per idea | It is the same 1-number fit in every case, so it is one helper, not one per idea. It also replaces the per-idea widening factors (AV6, x1.2), which is what idea 3 asks for |

**Final form.** One helper (shift -> held-out spread scale -> score), tried first on AV9 (a referee, so no risk), then AV7's merge, then UR12's centre signal. CPU only, scripts and data on disk.

### New idea 9 (11-14). The site factor as a small surface, learned from the first days

**From:** AV31's map (6 cells, 0.84-1.23, stable to 0.022 between seeds, worth 0.03-0.07 CRPS with no report), IL-207b (one number per site, PASS), AV10 / 32 / 33 (the steady part is the site, the daily swing is weather), SV step 0 (10 readings explain 53 % of a station's offset), UR4.

**First form.** UR4 learns the 6-cell map, not one factor, from a pad's first days.

| Attack | Rebuild |
|---|---|
| 6 cells from 10 days is about 2 days per cell | Two-level shrinkage: each cell shrinks toward the site's own mean factor, which shrinks toward the regional value (UR4's k). A new pad starts as one number and grows its shape as days come in |
| The shape itself may be regional | A regional mean **shape** (cell factor / site mean factor), pooled over the stations that can be served, as the cell prior. TCS and MAF have nearly opposite shapes, so test whether the shape groups by site type (basin vs airport vs ridge) before pooling all of them |
| Season cells need a year to see both | Cool and warm cells each get the site mean until their season has days. The leftover uncertainty goes into spread (UR4's rule), so the tool is wider in the unseen season |
| It overlaps AV31 and IL-207b | It is the same map, learned online from a short record instead of 120 prior hours per cell. That is the case a new pad actually has |

**Final form.** UR4 with a 6-cell surface and two-level shrinkage, judged in UR4's leave-one-out replay at n = 10 and n = 30 days, against UR4's one-number version. Rule proposal: better than one number at n = 30 with the interval below 0, and not worse at n = 10.

### New idea 10 (11-14). REPORT-AGE HANDOVER: how long to trust a pad report, then what takes over

**From:** AV31 (a 1 h old own report makes the map nearly redundant at TCS; with no report the map is worth 0.03-0.07), AV7 (two neighbours beat one), G2-2 (Student-t widening on a surprising report), the launch-day reality that the last report is often 1-6 h old at decision time.

**First form.** A fixed decay of the report's weight with age.

| Attack | Rebuild |
|---|---|
| A guessed decay is a tuned knob | Measure it: replay AV31 / AV7 at report ages 1, 3, 6 and 12 h, and score the four sources (own report, merged neighbours, map, none) at each age |
| The scripts may not take an age | Step 0: read whether `b4_debias_then_update` and the two-neighbour replay take a report age. If not, adding it is a new flag with the default unchanged |
| More combinations, more forking | One table (age x source -> weight) fitted on 2019-22, judged on 2023-25, one rule: the table beats "always trust the latest report" at 3 h and 6 h with the interval below 0 |
| A neighbour's report ages differently from the site's own | That is why the table is per source; the map does not age at all |

**Final form.** A 4 x 4 weight table in `Launch.observe`'s path (opt-in), from a replay with data on disk. It answers a question the launch team will ask ("the report is 4 h old: how much does it still count?").

### New idea 11 (11-14). Trust layer only where it learned something

**From:** AV17 (the gain sits in rh2m and v 0-1 km, no band worse, 18 of 179 columns blend), IL-10 (lost at T 12-18 km), section 0's "a measured table beside the network beats a new network body".

**First form.** Ship the trust layer for rh2m and v 0-1 km only (part 2, row 24).

| Attack | Rebuild |
|---|---|
| Choosing the bands after seeing them is a forking path | Choose them on the **calibration year** gain (the same min-gain test AV34 uses), not on the test rows, then judge only those bands, with the others required to be bit-identical |
| rh2m might be gaining for the wrong reason (a drifting humidity sensor) | Check that the rh2m gain also shows against station humidity readings, not only against ERA5 |
| u 0-1 km shows nothing while v 0-1 km gains | Expected if the trust layer is fixing a direction bias near the ground. Report u, v and speed separately; if speed gains nothing, the gain is direction only, which is still real for drift |

**Final form.** AV34's fit, scored per touched band, rule set before the run. Run it only if AV34 misses.

### Order I would run them in

1. TAILCAL on the shipped binned model, SIGMA and NEST (1 h CPU, no training, fixes a measured fault).
2. Idea 5 step 0 and idea 4 replay (CPU, data on disk).
3. Idea 3's 10 m test (CPU).
4. Idea 2 stage 3 (GPU, short fits), beside idea 6 step 0 (CPU).
5. The 2023-24 HRES pull whenever you can start it; it closes the open verdicts.

**Revised order (11-14).** The PIT measurement moves one cheap item to the front.

1. Idea 7 step 0: check that the tool ships the no-PIT range map (10 min CPU). Then the ledger, and the NEST / AV30 verdicts re-read on the shipped column as a report (part 2, row 18).
2. Idea 8 on AV9 (referee, no risk), then AV7's centre-only merge (part 2, row 20): CPU, scripts on disk.
3. Idea 10 step 0 and the AV31 age replay (part 2, row 21), beside UR4 with idea 9's surface as its second arm.
4. TAILCAL (idea 1) only on the cells the ledger still shows off; UR2 stage 3 on the shipped column.
5. Idea 11 only if AV34 misses.
6. The 2023-24 pull still closes the most verdicts, and it should be scored on the shipped column from the start.

---

## Outside sources used (search summaries only)

- Online conformal padding of ensemble ranges, CRPS nearly unchanged: [arXiv 2606.19642](https://arxiv.org/html/2606.19642); earlier: [arXiv 2406.14483](https://www.arxiv.org/pdf/2406.14483)
- Tail calibration is separate from ordinary calibration: [arXiv 2407.03167](https://arxiv.org/pdf/2407.03167); enforcing it in training costs overall skill: [arXiv 2506.13687](https://arxiv.org/html/2506.13687v1)
- Grid-to-point (representativeness) error added before scoring against stations: [ECMWF Tech. Memo 865](https://www.ecmwf.int/node/19544)
- Time-lagged runs: gain mostly at long range, plain averaging adds little: [QJRMS 1990 summary](https://zendy.io/title/10.1002/qj.49711649405); [lagged ensembles for deterministic models, arXiv 2501.19374](https://arxiv.org/pdf/2501.19374)
- One network across lead times; local vs global training: [arXiv 2606.08587](https://arxiv.org/pdf/2606.08587); [export.arxiv.org 2406.02141](https://export.arxiv.org/pdf/2406.02141)
- Pre-train wide, fine-tune local: [GMD 19, 5781 (2026)](https://gmd.copernicus.org/articles/19/5781/2026/gmd-19-5781-2026.pdf); [new-station transfer, EGU2020-3885](https://meetingorganizer.copernicus.org/EGU2020/EGU2020-3885.html)
- Short site records against ERA5 (one month close to twelve on average, risky at single sites): [Wind Energ. Sci. 10, 1451 (2025)](https://wes.copernicus.org/articles/10/1451/2025/); seasonal bias of short campaigns: [WES 6, 1473 (2021)](https://wes.copernicus.org/articles/6/1473/2021/)
- Lead-dependent blend weights, calibrate sources before blending: [arXiv 2004.06582](https://arxiv.org/pdf/2004.06582), [arXiv 2504.12672](https://arxiv.org/pdf/2504.12672)
