| flight | truth (ft) | S0 | S1 | S2 | S3 | S4 | RASAero | RocketPy (plain) |
|---|---|---|---|---|---|---|---|---|
| Prometheus | 12789 | 13776 (+7.7 %) | 13778 (+7.7 %) | 14248 (+11.4 %) ±233 | 13916 (+8.8 %) ±182 | 14211 (+11.1 %) ±68 | 13505 (+5.6 %) | 13840 (+8.2 %) |
| Juno3 | 10541 | 11117 (+5.5 %) | 11065 (+5.0 %) | 11217 (+6.4 %) ±107 | 11033 (+4.7 %) ±89 | 10835 (+2.8 %) ±64 | 10914 (+3.5 %) | 11167 (+5.9 %) |
| HeartOfSteel | 30411 | 29664 (-2.5 %) | 28667 (-5.7 %) | 29107 (-4.3 %) ±166 | 29210 (-4.0 %) ±162 | 29139 (-4.2 %) ±70 | 29964 (-1.5 %) | 28685 (-5.7 %) |

| scenario | mean abs error (3 flights) | mean signed error | flights closer than S0 |
|---|---|---|---|
| S0 branch as filed | 5.21 % | +3.57 % | 0 of 3 |
| S1 plain standard atmosphere at the true pad, no wind | 6.15 % | +2.32 % | 1 of 3 |
| S2 Tempest climate (date + hour) | 7.37 % | +4.51 % | 0 of 3 |
| S3 Tempest past (ERA5 + balloon correction) | 5.81 % | +3.18 % | 1 of 3 |
| S4 Tempest past + measured surface values | 6.03 % | +3.24 % | 1 of 3 |

Pad air (mean over the sampled atmospheres) and wind met along the climb:
| flight | scenario | pad T (C) | pad density (kg/m3) | max wind on the way up (m/s) |
|---|---|---|---|---|
| Prometheus | S0 | 5.9 | 1.069 | 0.0 |
| Prometheus | S1 | 5.9 | 1.069 | 0.0 |
| Prometheus | S2 | 28.8 | 0.989 | 9.1 |
| Prometheus | S3 | 26.3 | 0.996 | 10.3 |
| Prometheus | S4 | 23.7 | 1.006 | 9.6 |
| Juno3 | S0 | 5.4 | 1.060 | 0.0 |
| Juno3 | S1 | 5.9 | 1.069 | 0.0 |
| Juno3 | S2 | 35.2 | 0.966 | 8.7 |
| Juno3 | S3 | 36.2 | 0.964 | 18.0 |
| Juno3 | S4 | 37.1 | 0.961 | 19.3 |
| HeartOfSteel | S0 | 35.0 | 0.968 | 3.6 |
| HeartOfSteel | S1 | 5.9 | 1.069 | 0.0 |
| HeartOfSteel | S2 | 30.7 | 0.984 | 17.0 |
| HeartOfSteel | S3 | 34.2 | 0.968 | 11.6 |
| HeartOfSteel | S4 | 35.3 | 0.963 | 12.2 |