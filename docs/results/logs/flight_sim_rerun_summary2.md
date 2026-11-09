## Apogee error vs the measured apogee: median of the sampled atmospheres (sd in ft; truth rank = share of the sampled apogees below the truth)

| flight | truth ft | S0 branch as | S1 standard air, | A climate | B past (ERA5+balloons) | C past + | D past + | E climate + | F past + | G past, wind |
|---|---|---|---|---|---|---|---|---|---|---|
| Prometheus | 12789 | 13776 (+7.7 %) | 13778 (+7.7 %) | 14248 (+11.4 %) ±233 r0.00 | 13917 (+8.8 %) ±183 r0.00 | 14255 (+11.5 %) ±73 r0.00 | 14110 (+10.3 %) ±146 r0.00 | 14247 (+11.4 %) ±192 r0.00 | 14049 (+9.9 %) ±162 r0.00 | 13918 (+8.8 %) ±202 r0.00 |
| Juno3 | 10541 | 11117 (+5.5 %) | 11065 (+5.0 %) | 11218 (+6.4 %) ±107 r0.00 | 11034 (+4.7 %) ±93 r0.00 | 10751 (+2.0 %) ±86 r0.02 | 10924 (+3.6 %) ±104 r0.01 | 11088 (+5.2 %) ±97 r0.00 | 11048 (+4.8 %) ±82 r0.00 | 11031 (+4.6 %) ±101 r0.00 |
| HeartOfSteel | 30411 | 29664 (-2.5 %) | 28667 (-5.7 %) | 29107 (-4.3 %) ±166 r1.00 | 29221 (-3.9 %) ±160 r1.00 | 29134 (-4.2 %) ±70 r1.00 | 29206 (-4.0 %) ±148 r1.00 | 28998 (-4.6 %) ±181 r1.00 | - | 29217 (-3.9 %) ±171 r1.00 |

| scenario | mean abs error (3 flights) | mean signed error | closer than S0 | closer than S1 |
|---|---|---|---|---|
| S0 branch as filed | 5.21 % | +3.57 % | 0 of 3 | 2 of 3 |
| S1 standard air, true pad, no wind | 6.15 % | +2.32 % | 1 of 3 | 0 of 3 |
| A climate | 7.37 % | +4.51 % | 0 of 3 | 1 of 3 |
| B past (ERA5+balloons) | 5.80 % | +3.20 % | 1 of 3 | 2 of 3 |
| C past + ASOS pinned | 5.89 % | +3.09 % | 1 of 3 | 2 of 3 |
| D past + ASOS weighted | 5.97 % | +3.33 % | 1 of 3 | 2 of 3 |
| E climate + ASOS weighted | 7.08 % | +3.98 % | 1 of 3 | 1 of 3 |
| F past + HRRR ground anchor | only 2 flights (no HRRR value for the Heart of Steel window) | | | |
| G past, wind spread x1.2 | 5.80 % | +3.18 % | 1 of 3 | 2 of 3 |

## What each scenario put on the pad and aloft (mean over sampled atmospheres)

| flight | scenario | pad T (C) | pad density | 10 m wind median (m/s) | wind 10-200 m mean (m/s) | max wind on the way up (m/s) | corr(apogee, pad density) | corr(apogee, mean wind <= 200 m) |
|---|---|---|---|---|---|---|---|---|
| Prometheus | A | 28.8 | 0.989 | 3.1 | 3.5 | 9.1 | -0.14 | -0.04 |
| Prometheus | B | 26.1 | 0.997 | 3.0 | 3.5 | 10.3 | -0.00 | -0.87 |
| Prometheus | C | 23.7 | 1.004 | 0.9 | 2.2 | 10.2 | -0.15 | +0.27 |
| Prometheus | D | 24.7 | 1.001 | 1.5 | 2.4 | 10.2 | +0.01 | -0.51 |
| Prometheus | E | 26.3 | 0.996 | 2.5 | 3.0 | 11.0 | -0.21 | -0.18 |
| Prometheus | F | 26.1 | 0.997 | 2.5 | 3.0 | 10.3 | +0.01 | -0.69 |
| Prometheus | G | 26.1 | 0.997 | 3.3 | 3.8 | 10.3 | -0.00 | -0.85 |
| Juno3 | A | 35.2 | 0.966 | 4.2 | 5.0 | 8.7 | -0.26 | -0.25 |
| Juno3 | B | 36.4 | 0.964 | 9.5 | 11.4 | 18.0 | -0.18 | -0.84 |
| Juno3 | C | 37.1 | 0.963 | 13.2 | 17.5 | 21.5 | -0.15 | -0.92 |
| Juno3 | D | 37.0 | 0.963 | 11.4 | 13.8 | 18.3 | -0.40 | -0.88 |
| Juno3 | E | 37.1 | 0.961 | 9.6 | 9.9 | 13.5 | -0.30 | -0.70 |
| Juno3 | F | 36.4 | 0.964 | 9.1 | 11.1 | 18.0 | -0.19 | -0.85 |
| Juno3 | G | 36.4 | 0.964 | 9.6 | 11.5 | 18.0 | -0.18 | -0.83 |
| HeartOfSteel | A | 30.7 | 0.984 | 3.6 | 3.9 | 17.0 | -0.05 | +0.04 |
| HeartOfSteel | B | 34.1 | 0.968 | 2.8 | 3.2 | 11.6 | +0.35 | +0.03 |
| HeartOfSteel | C | 35.3 | 0.963 | 2.1 | 2.4 | 12.5 | -0.18 | -0.29 |
| HeartOfSteel | D | 35.0 | 0.964 | 2.1 | 2.7 | 12.0 | +0.08 | -0.26 |
| HeartOfSteel | E | 33.8 | 0.975 | 2.8 | 3.3 | 17.4 | -0.03 | -0.49 |
| HeartOfSteel | G | 34.1 | 0.968 | 3.2 | 3.5 | 11.6 | +0.32 | -0.03 |

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