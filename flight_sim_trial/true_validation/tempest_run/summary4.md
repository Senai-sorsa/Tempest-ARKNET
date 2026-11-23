## Apogee error vs the measured apogee: median of the sampled atmospheres (sd in ft; truth rank = share of the sampled apogees below the truth)

| flight | truth ft | S0 branch as | S1 standard air, | A climate | B past (ERA5+balloons) | C past + | D past + | E climate + | F past + | G past, wind |
|---|---|---|---|---|---|---|---|---|---|---|
| Prometheus | 12789 | 13776 (+7.7 %) | 13778 (+7.7 %) | 14221 (+11.2 %) ±250 r0.00 | 13864 (+8.4 %) ±179 r0.00 | 14300 (+11.8 %) ±78 r0.00 | 14111 (+10.3 %) ±152 r0.00 | 14255 (+11.5 %) ±233 r0.00 | 14049 (+9.9 %) ±163 r0.00 | 13863 (+8.4 %) ±198 r0.00 |
| Juno3 | 10541 | 11117 (+5.5 %) | 11065 (+5.0 %) | 11233 (+6.6 %) ±91 r0.00 | 11030 (+4.6 %) ±93 r0.00 | 10774 (+2.2 %) ±86 r0.00 | 10925 (+3.6 %) ±105 r0.00 | 11057 (+4.9 %) ±79 r0.00 | 11046 (+4.8 %) ±82 r0.00 | 11029 (+4.6 %) ±101 r0.00 |
| HeartOfSteel | 30411 | 29664 (-2.5 %) | 28667 (-5.7 %) | 29132 (-4.2 %) ±142 r1.00 | 29184 (-4.0 %) ±163 r1.00 | 29141 (-4.2 %) ±71 r1.00 | 29211 (-3.9 %) ±125 r1.00 | 29044 (-4.5 %) ±175 r1.00 | - | 29194 (-4.0 %) ±175 r1.00 |

| scenario | mean abs error (3 flights) | mean signed error | closer than S0 | closer than S1 |
|---|---|---|---|---|
| S0 branch as filed | 5.21 % | +3.57 % | 0 of 3 | 2 of 3 |
| S1 standard air, true pad, no wind | 6.15 % | +2.32 % | 1 of 3 | 0 of 3 |
| A climate | 7.32 % | +4.52 % | 0 of 3 | 1 of 3 |
| B past (ERA5+balloons) | 5.69 % | +3.00 % | 1 of 3 | 2 of 3 |
| C past + ASOS pinned | 6.07 % | +3.28 % | 1 of 3 | 2 of 3 |
| D past + ASOS weighted | 5.98 % | +3.35 % | 1 of 3 | 2 of 3 |
| E climate + ASOS weighted | 6.95 % | +3.95 % | 1 of 3 | 2 of 3 |
| F past + HRRR ground anchor | only 2 flights (no HRRR value for the Heart of Steel window) | | | |
| G past, wind spread x1.2 | 5.68 % | +3.01 % | 1 of 3 | 2 of 3 |

## What each scenario put on the pad and aloft (mean over sampled atmospheres)

| flight | scenario | pad T (C) | pad density | 10 m wind median (m/s) | wind 10-200 m mean (m/s) | max wind on the way up (m/s) | corr(apogee, pad density) | corr(apogee, mean wind <= 200 m) |
|---|---|---|---|---|---|---|---|---|
| Prometheus | A | 27.6 | 0.993 | 3.0 | 3.4 | 10.8 | -0.05 | +0.24 |
| Prometheus | B | 26.1 | 0.997 | 3.7 | 4.0 | 10.2 | -0.00 | -0.91 |
| Prometheus | C | 23.7 | 1.004 | 0.9 | 2.5 | 10.1 | -0.19 | +0.45 |
| Prometheus | D | 24.7 | 1.001 | 1.5 | 2.5 | 10.0 | +0.01 | -0.28 |
| Prometheus | E | 25.4 | 0.999 | 2.5 | 3.2 | 13.1 | -0.08 | +0.27 |
| Prometheus | F | 26.1 | 0.997 | 2.5 | 3.0 | 10.3 | +0.01 | -0.69 |
| Prometheus | G | 26.1 | 0.997 | 3.9 | 4.2 | 10.2 | -0.00 | -0.89 |
| Juno3 | A | 33.9 | 0.970 | 4.5 | 5.0 | 8.8 | -0.07 | -0.32 |
| Juno3 | B | 36.4 | 0.964 | 9.7 | 11.5 | 18.0 | -0.18 | -0.85 |
| Juno3 | C | 37.1 | 0.963 | 13.2 | 17.0 | 20.8 | -0.26 | -0.89 |
| Juno3 | D | 37.0 | 0.963 | 11.5 | 14.0 | 18.5 | -0.27 | -0.88 |
| Juno3 | E | 35.3 | 0.965 | 9.2 | 10.3 | 17.0 | -0.09 | -0.57 |
| Juno3 | F | 36.4 | 0.964 | 9.1 | 11.1 | 18.0 | -0.19 | -0.85 |
| Juno3 | G | 36.4 | 0.964 | 9.8 | 11.6 | 18.0 | -0.17 | -0.84 |
| HeartOfSteel | A | 29.9 | 0.986 | 3.1 | 3.4 | 18.2 | -0.10 | +0.40 |
| HeartOfSteel | B | 34.1 | 0.968 | 3.1 | 3.3 | 11.6 | +0.35 | -0.14 |
| HeartOfSteel | C | 35.3 | 0.963 | 2.1 | 2.6 | 12.4 | -0.03 | -0.40 |
| HeartOfSteel | D | 34.5 | 0.966 | 2.0 | 2.6 | 12.0 | +0.16 | +0.18 |
| HeartOfSteel | E | 32.7 | 0.977 | 2.3 | 2.8 | 18.0 | -0.17 | -0.09 |
| HeartOfSteel | G | 34.1 | 0.968 | 3.4 | 3.5 | 11.6 | +0.32 | -0.19 |

## Ground wind at the launch hour vs what the stations / reanalysis saw

- Prometheus: ASOS TCS at the hour: 0.9 m/s from 190 deg, 23.2 C (stations ['2022-06-24 14:53:00+00:00', '2022-06-24 15:53:00+00:00']).
- Juno3: ASOS TCS at the hour: 13.2 m/s from 250 deg, 36.6 C (stations ['2023-06-23 22:53:00+00:00', '2023-06-23 23:53:00+00:00']).
- HeartOfSteel: ASOS TCS at the hour: 2.1 m/s from 67 deg, 34.8 C (stations ['2017-06-22 16:53:00+00:00', '2017-06-22 17:53:00+00:00']).
- Prometheus reference: RocketPy ERA5 notebook print: 26.8 C, 0.2 m/s
- Juno3 reference: RocketPy ERA5 notebook print: 33.8 C, 10.8 m/s from 244 deg

## Context from the branch (same flights)

- Prometheus: RASAero 13505 ft (+5.6 %), RocketPy plain 13840 ft (+8.2 %)
- Juno3: RASAero 10914 ft (+3.5 %), RocketPy plain 11167 ft (+5.9 %)
- HeartOfSteel: RASAero 29964 ft (-1.5 %), RocketPy plain 28685 ft (-5.7 %)