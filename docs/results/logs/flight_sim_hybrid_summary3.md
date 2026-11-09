| flight | truth ft | S0 | S1 | B | H0 | H1 | H2 |
|---|---|---|---|---|---|---|---|
| Prometheus | 12789 | 13776 (+7.7 %) | 13778 (+7.7 %) | 13917 (+8.8 %) ±183 | 13534 (+5.8 %) ±179 | 13536 (+5.8 %) ±207 | 13530 (+5.8 %) ±207 |
| Juno3 | 10541 | 11117 (+5.5 %) | 11065 (+5.0 %) | 11034 (+4.7 %) ±93 | 10861 (+3.0 %) ±94 | 10869 (+3.1 %) ±126 | 10869 (+3.1 %) ±127 |
| HeartOfSteel | 30411 | 29664 (-2.5 %) | 28667 (-5.7 %) | 29221 (-3.9 %) ±160 | 28641 (-5.8 %) ±168 | 28641 (-5.8 %) ±184 | 28636 (-5.8 %) ±184 |

| scenario | what it is | mean abs error (3 flights) | mean signed error | closer than S0 | closer than S1 |
|---|---|---|---|---|---|
| S0 branch as filed | the branch's own air and wind | 5.21 % | +3.57 % | 0 of 3 | 2 of 3 |
| S1 standard air, true pad, no wind | standard air at the true pad, no wind | 6.15 % | +2.32 % | 1 of 3 | 0 of 3 |
| B Tempest past (full atmosphere) | all Tempest (past mode) | 5.80 % | +3.20 % | 1 of 3 | 2 of 3 |
| H0 standard air + Tempest wind | standard air + Tempest wind | 4.89 % | +1.01 % | 2 of 3 | 2 of 3 |
| H1 H0 + turbulence | + Dryden turbulence | 4.92 % | +1.04 % | 2 of 3 | 2 of 3 |
| H2 H1 + discrete gust | + discrete gust | 4.91 % | +1.02 % | 2 of 3 | 2 of 3 |

Paired differences of the median apogee (ft) between scenarios, per flight (same atmosphere index k): wind effect = H0 - S1, air effect = B - H0, turbulence = H1 - H0, gust = H2 - H1
| flight | wind (H0 - S1) | Tempest air instead of standard (B - H0) | turbulence (H1 - H0) | gust (H2 - H1) | sd of H0 | sd of H1 | sd of H2 |
|---|---|---|---|---|---|---|---|
| Prometheus | -244 | +390 | +5 | +0 | 178 | 206 | 206 |
| Juno3 | -204 | +172 | -10 | +0 | 94 | 125 | 126 |
| HeartOfSteel | -27 | +573 | -3 | -5 | 167 | 183 | 184 |

Truth rank inside the sampled apogees (share of the 100 below the truth; 0 or 1 = outside the whole sample):
- Prometheus: B 0.00, H0 0.00, H1 0.00, H2 0.00
- Juno3: B 0.00, H0 0.00, H1 0.01, H2 0.01
- HeartOfSteel: B 1.00, H0 1.00, H1 1.00, H2 1.00