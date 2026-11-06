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

### Idea 1: Structured vertical noise prior (multi-scale correlated + heavy-tailed noise). **Score 5/10; cheap part worth a test**
- What it is: replace the 32 white-Gaussian noise numbers with noise that already has the boundary-layer and free-troposphere vertical correlation lengths and heavy-tailed innovations.
- Reality check:
  - Engression feeds the noise through the network, so any smooth transform of the noise can already be learned. A pre-shaped prior is a reparametrisation, not new capacity.
  - Our shape metrics already pass (vcorr_err 0.075, shear_ks 0.019). The claim that it "eliminates shear_tail.py" is unlikely.
- What is worth testing: **heavy-tailed noise** (Student-t, ν≈4, on a few of the 32 dims). Heavy tails are hard to make from a Gaussian with a smooth MLP, and the shear tail is our weakest shape metric (event_cov_gap). It is a 3-line option.
- Verdict: the Student-t part is being tested now as **L3-26 studt** (`noise_t_dims = 8`, ν = 4). The 44-height correlated-GP part is skipped.

### Idea 2: Pairformer trunk with "hydrostatic triangle updates". **Score 2/10; not worth building**
- The pair features it wants (Δθ_ij, Δu_ij, Ri_ij) are properties of the **output** profile, which does not exist yet at generation time. It only works inside an iterative or diffusion sampler, which our single-pass, <250 ms design rules out.
- The "exact additive triangle consistency" (Δθ_ij = Δθ_ik + Δθ_kj) is already automatic in our parametrisation: steps plus cumulative sum. There is nothing left to learn.
- Our own attention-over-heights try (IL-8 TokenGenerator) was slower (1,700 s per 500 steps) and worse.
- **Not built** (it cannot run single-pass; our IL-8 attention-over-heights test already covers the closest buildable version). It will be built only if you still want it after reading this.
- The one useful part is clamping a partial observation (a balloon or surface reading) at inference. That is Stage 6 `observe()`, and conditioning or reweighting the samples does it without a new trunk.

### Idea 3: Jump primitives for inversions and jet shear sheets (tanh × generalised-exponential bumps). **Score 4/10 now, 6/10 once trained on balloon-resolution targets**
- The physics is right: profiles are smooth layers with sharp inversions and shear sheets.
- But our training targets are ERA5 interpolated to 44 heights, 500 m apart above 2.5 km. The targets themselves contain no jumps sharper than ERA5's levels, so the primitives would have nothing sharper to learn, and a jump thinner than 250 m is invisible on the grid anyway.
- It becomes useful when targets carry balloon detail: the IGRA plain files for 987 stations are downloading now (fetch_chain).
- Tested now anyway (user asked for the ideas to be tried), on ERA5 targets: **L3-27 jump** (`jump_k = 2`, below 3 km). Expect little until IGRA targets; rerun it then.
- Cheapest test then: K = 2 zero-initialised tanh-step bases added to the output in the 0-3 km band (dense heights), scored on IGRA-corrected rows with the shear_ks / event_cov_gap metrics.

## 4. Applied now
- `tempest/profiles/to_heights.py`: `fill_top` (+ assert self-check).
- `tempest/generator/build_dataset.py`: `--fill-top`.
- `tempest/generator/model.py`: `ctx_sep`, `geo["w0"]`.
- `tempest/generator/model.py`: `noise_t` (idea 1), `jump` (idea 3).
- `tempest/generator/train.py`: `context_film_sep`, `geo_siren_w0`, `noise_t_dims`/`noise_t_nu`, `jump_k`/`jump_top`.
- `configs/generator_l3_ctxsep.toml`, `configs/generator_l3_sirenw15.toml`, `configs/generator_l3_studt.toml`, `configs/generator_l3_jump.toml`.
- `scripts/ap_l3_lean.sh` (the loop-3 queue was cut to this, see LOOP3): Denver fill-top rebuild + p2f rescore → w768 → terrain → ctxsep → sirenw15 → studt → jump.
- Checked: a CPU forward/backward pass of every option combination; jump steps add up to the tanh profile (assert); the default network is unchanged; existing checkpoints load; the scripts and configs parse.
