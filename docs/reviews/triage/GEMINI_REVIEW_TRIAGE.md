# Gemini review (2026-11-06): triage

Source: [`../external/gemini-review.pdf`](../external/gemini-review.pdf). Both the PDF and the pasted copy stop partway through Novel Idea 3, so only 3 of the promised 6 ideas arrived. Every claim was checked against the code and the loop-3 results before anything changed.

All code changes are **options that are off by default**. The running loop-3 queue and the adopted p2f are bit-for-bit unchanged, and the old checkpoints (`l3_siren.pt`, `generator_80_p2f.pt`) load unchanged.

## 1. Code claims

| # | Claim | Verdict | Action |
|---|---|---|---|
| A1 | `Sampler._activate` skips `set_active` for overlay checkpoints; it would crash if overlay columns were added to `BASE_FEATURES` | **Not a bug.** The skip is deliberate (residual and overlay networks have their own inputs). A mismatched input crashes on shape at normalisation; it does not fail silently. The crash is the guard (review 1.7/5.5). | none |
| A2 | Mountain columns lose the top heights (z_sfc + 18 km > the 50 hPa level), and `build_dataset` drops the whole row | **Correct, and the most important finding.** The Denver build dropped **934,359 of 4.0 M rows (23 %)**; NM/TX dropped 0-1. Every Denver score so far covers the low ground only. | `to_heights.fill_top` + `build_dataset --fill-top`; L3-25 rebuilds Denver with it and rescores p2f |
| A3 | Context and noise share one FiLM (the sum has variance 2) | **Half right.** The variance is harmless because the FiLM layer is learned. The shared weights are real: film(z+c) = W·z + W·c. | model option `ctx_sep` / config `context_film_sep`; row L3-23 |
| A4 | SIREN without ω0 is "quasi-linear" | **Overstated.** The pre-activation sd is about 1.4 rad, which spans most of a period, and the measured siren row passed NM/TX + shape and gave the best Denver coordinate result (22 % of the gap). Higher ω0 adds high frequencies, which may hurt extrapolation. Worth one test. | config `geo_siren_w0`; row L3-24 (w0 = 15) |
| A5 | `l3_overlay` slope_ew has no cos(lat) and is in m per grid step | **Correct.** Inside loop 3 it is small: cos varies 0.82-0.86 over NM/TX and is 0.78 at Denver, a ~7 % scale error. | left unchanged in `l3_overlay.py` so loop 3 stays comparable; **`statics.py` (global) will use metric slopes m/m with cos(lat)** |
| A6a | Gust model uses UTC hour and a hard-coded MAF/TCS flag | **Correct, but only matters globally.** For the pilot both sites are UTC-6.5 h. | to-do: the global gust fit (ASOS global download) uses local solar hour + station statics |
| A6b | The w head runs before `to_site` | **Not a bug.** The head was trained on grid-elevation profiles, so it must see them; the code comment says so. | none |

## 2. Design claims

| Claim | Verdict | Action |
|---|---|---|
| SH tests on one 3°x7° box are ill-posed (collinear basis) | **Agree.** This fits sh10/sh20 (shape FAIL) and the caveat already in LOOP3. | retest sh10+siren on the G2 leave-one-box-out split |
| Need horizontal gradients (thermal wind) and flow-terrain alignment | **Agree on the physics**, for climatological fields (a climate generator cannot know the synoptic gradient). | to-do statics/clim: climatological ∇T at 850/500 hPa, climatological wind vector at 850/500, upslope projection u·∇z_sfc, bulk Froude U/(N·sdor) |
| `clim_u_d5000` is a step difference, not the wind | **Wrong.** `l3_overlay._cols` sums the steps, so it is the absolute wind at 5 km AGL. | none |
| SAMOS on steps ≠ standardised levels | **Correct caution.** | note on L3-8: standardise levels, or un-standardise per row in the loss |
| One global pm/ps in the loss under-weights T globally by 5-8x | **Correct for G2/G4** (harmless on one box). | note on L3-8 / G4: per-row climatological sd in `phys_std` |
| Output = climatology + σ·f, "guarantees skill15 = 0 at init" | **Idea good, claim wrong.** A zero residual is a point forecast with no spread, so its CRPS is worse than the climatological ensemble, not equal to it. | folded into L3-8 (SAMOS) |

## 3. The three novel ideas: how good are they?

The cited 2026 papers (NAGO arXiv:2610.38273, "Triangle Multiplication Is All You Need" listed as Dec 2025 under an Oct-2025 arXiv number, S³-TIR IJCAI 2026) have **not been checked**. One date is inconsistent; treat them as possibly invented until found.

### Idea 1: heavy-tailed noise. **Score 5/10 as given → 6.5/10 improved; being tested (L3-26 studt)**
Gemini's version adds Student-t noise numbers (heavy tails) plus a 44-height correlated noise field.

What we learned that changes it:
- **The layer norms erase the tails.** The noise reaches the output only through two layer norms: the end of the noise embedding, and just before the output head. Both rescale the vector, so an extreme draw loses most of its size. Student-t inputs alone would mostly be wasted.
- **The tail problem sits at jet level.** The worst shape metric is the tail metric: event_cov_gap is 0.059 for p2f and 0.077 for siren, worst at u 5-12 km, and shear_ks is worst in shear 5-12 km. The targets are height steps, so a tail term on the outputs lands directly on shear.
- **The correlated-noise part adds nothing.** vcorr already passes (0.075), so it is dropped.
- **The existing tail loss pushes the same way.** p2f already trains with `shear_tail_weight` (q 0.9), which rewards a head that can produce rare large steps.

The improved version (`noise_t_dims = 8`, `noise_t_head = 4`): 8 of the 32 noise numbers are Student-t (ν = 4, unit variance). The first 4 also scale a zero-initialised output head *after* the last layer norm: out += Σ t_k·g_k(h). Because the network sees those same t values in its input, it can decide which columns a rare draw moves, e.g. a jet core with its shear. At the start it equals the p2f network exactly, so it can only drift from p2f as far as the data supports.

Why only 6.5: engression is already near the shape tolerance, and the spread calibration after training may absorb part of any gain. A heavier tail also risks cov99 over-coverage. Score it on event_cov_gap / shear_ks, then cov99.

### Idea 2: Pairformer trunk. **Removed (user, 2026-11-06).**

### Idea 3: Jump primitives for inversions and jets. **Score 4/10 as given → 7/10 improved, once the balloon data is in. Not run until then (user).**
The physics is right, but the ERA5 targets on 44 heights (500 m apart above 2.5 km) contain no jumps sharper than ERA5's own levels. The code exists (`jump_k`, off); the config waits as `configs/generator_l3_jump_igra.toml`.

What we learned that changes it:
- **Few balloons, so freeze the base.** IGRA rows are ~2 per day per station, so a whole-network retrain would overfit. Freeze p2f and fit only the zero-initialised jump head on IGRA-matched rows. It starts at p2f exactly, so it cannot lose skill at the start, and it is cheap (minutes).
- **Two shapes, not one.**
  - Inversions are steps (tanh). Their centre prior is the boundary-layer top: ERA5 BLH is in the extras download, and it can become a generated output that the jump uses as its centre, so the two stay consistent.
  - The tropopause is a *kink* in T, a lapse-rate change, not a step. Use a softplus basis with the climatological tropopause (already in the L3-7 climatology data) as the centre prior. That band is our worst Denver band: T 12-18 km, siren -0.30.
  - A kink is visible even at 500 m spacing.
- **Score on what it targets.** Use event_cov_gap T/0-1 km (the worst band of sh20), shear_ks, and inversion strength / tropopause-height error against IGRA, besides skill15.
- **Balloons vs ERA5.** Earlier balloon work (IL-72 offsets, L3-17 pooled correction) showed systematic balloon-ERA5 differences. Fit the jump head on balloon targets *after* the offset correction, so it learns sharpness, not bias.

Why 7: it is the one idea that adds something the network cannot learn from ERA5 targets, and the cost is small. It depends on the IGRA processing working and on enough stations near the test sites.

## 4. Applied now
- `tempest/profiles/to_heights.py`: `fill_top` (+ assert self-check).
- `tempest/generator/build_dataset.py`: `--fill-top`.
- `tempest/generator/model.py`: `ctx_sep`, `geo["w0"]`.
- `tempest/generator/model.py`: `noise_t` + its tail head (idea 1), `jump` (idea 3, waits for IGRA).
- `tempest/generator/train.py`: `context_film_sep`, `geo_siren_w0`, `noise_t_dims`/`noise_t_nu`/`noise_t_head`, `jump_k`/`jump_top`.
- `configs/generator_l3_ctxsep.toml`, `configs/generator_l3_sirenw15.toml`, `configs/generator_l3_studt.toml`, `configs/generator_l3_jump_igra.toml` (not queued).
- `scripts/ap_l3_lean.sh` (the loop-3 queue was cut to this, see LOOP3): Denver fill-top rebuild + p2f rescore → w768 → terrain → ctxsep → sirenw15 → studt.
- Checked: a CPU forward/backward pass of every option combination; jump steps add up to the tanh profile (assert); the default network is unchanged; existing checkpoints load; the scripts and configs parse.
