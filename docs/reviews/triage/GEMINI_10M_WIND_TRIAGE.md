# Gemini's answer on the 10 m wind (2026-11-08): triage and the condensed list

Source: the answer to `docs/reviews/GEMINI_PROMPT_10M_WIND.md`, pasted by the user. **The paste was cut off in the middle of idea 4**; ideas 5-8 exist only as table rows. Gemini's expected-gain numbers are estimates, not measurements, and several of its specific claims are unverified (listed at the end). This file records what we keep, what we merge and what we sideline, judged against our own measurements.

## What our own measurements say (ground-wind benchmark GW-1, ASOS at TCS and MAF, test 2024-25, 240 cases)
| variant | CRPS (m/s) | 90 % coverage | spread / rmse |
|---|---|---|---|
| climate mode as is | 1.838 | 0.88 | 1.06 (calibrated; best spread scale 1.0) |
| past mode (ERA5 + balloons) | 1.126 | 0.80 | 0.77 (over-confident) |
| past mode, spread x 1.2 | 1.116 | 0.88 | 0.92 |
| climate + the report 1 h earlier | 1.125 (vs 1.897 same cases) | 0.84 | 0.94 |
| climate + the report 3 h earlier | 1.540 (vs 1.974) | 0.86 | 1.03 |
| past mode + report 1 h earlier | 1.021 (vs 1.151 past alone) | 0.85 | 0.86 |
| climate + local month x hour climatology (w 0.6) | 1.764 | 0.89 | 1.04 |
Plus the flight-sim result: only the wind below 200 m changes apogee (about 2 % per 3 m/s), and one distant calm station report moved Prometheus 2.3 %.

## Gemini's ideas, one verdict each
| Gemini idea | Verdict | Why |
|---|---|---|
| 1 Multi-sample M = 16 + speed-aware vector energy loss + 3x weight below 300 m | **Keep, recast inside idea 4** | The premise (the unconditional mode is under-dispersed) is NOT supported at stations: climate mode is calibrated. The real gap is past mode (spread/rmse 0.77) and balloon coverage. The loss change is still a cheap one-GPU-run test; its claimed alpha bias (6.7 %) needs a derivation before we trust it |
| 2 Terrain-blocked, stability- and age-aware localisation of the observation update | **Keep as idea 1** | Directly addresses the largest measured lever (observations, -41 % CRPS) and the Prometheus pinning problem; our current weights (age decay fitted, distance and elevation scales assumed) are the weak part |
| 3 Monin-Obukhov + low-level-jet physical basis, speed and turning instead of u, v | **Keep as idea 2** | Fits the user's pick (finer near-surface levels), removes interpolation kinks and chord shortening, gives rail-height (2-5 m) winds, and embeds physics constraints |
| 4 HRRR / NREL WTK point-distilled transfer head | **Keep as idea 3** | Best way to give the pad its own terrain physics without pad data; the same point extraction also feeds the forecast modes (the user's other pick) |
| 5 Observation-conditioned neural process | **Merge into idea 1 (stage 2)** | Same goal as our "Mode O" (generator sees the latest reports) |
| 6 Skew-Student-t + von Mises mixture heads | Sideline | Tail refinement; only after ideas 1-4 and only if the tails fail |
| 7 Conformal joint wind envelopes | Merge into idea 4 (later) | Useful as the final calibration wrapper |
| 8 Ornstein-Uhlenbeck / Kaimal sub-hourly cascade | Sideline | Real for rail-exit transients but needs the simulator in the loop to score; revisit after the flight-sim set is larger |

## Unverified claims to check before relying on them
- The almost-fair CRPS bias with alpha 0.95 and M = 4 (derive it).
- ERA5 horizontal correlation between TCS and the pad of 0.85 against a true 0.35-0.55 (measure it from station pairs).
- Data access details: NREL WTK / WTK-LED variable names, years covered and API key; the `hrrrzarr` bucket layout; the 1-second radiosonde archive location; the HRRR native level heights below 300 m.
- All "expected gain" percentages.

## The condensed list (maximum five; everything else sidelined)
1. **Observation assimilation done right** (rows IL-156, IL-152 stage 2).
2. **A real near-surface profile** (IL-148, IL-151): ERA5 model levels + a physical basis + speed/turning output.
3. **HRRR / WTK point data as teacher and as short-range forecast** (IL-149).
4. **Ground-wind calibration and loss** (IL-153 folded in).
5. **Domain-of-applicability check and local adaptation** (IL-150).
Sidelined: sub-hourly cascade, skew/mixture heads, extra predictors (soil moisture, cloud, radiation), bounded-variable heads (kept as an option, humidity matters little for rockets), conformal envelopes until idea 4's calibration is done. The independent confirmation window (IL-155) stays as a rule applied to every final verdict, not an idea.
