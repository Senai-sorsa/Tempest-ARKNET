# Beat Earth-GRAM: where we stand, what others did, five new ideas

Written 2026-11-12 (evening). Nothing here has been run except the comparison kit in section 2, which ran
before the section 15 gate of `New_Plan.md` was known. **The gate holds for everything below: no trial starts
until New_Plan 15.1-15.4 are done.** Each idea has its step 0, pass rule and kill rule set now.

## 1. What made Earth-GRAM good (from memory of the NASA documents, not re-read today)

1. **Simple statistics on a lot of data.** A monthly mean and spread per place and height is very hard to beat
   on average error. Our own number shows it (section 2): a bell curve with the right covariance is within
   0-8 % of our tool on every paired score.
2. **It never refuses.** Whole globe, ground to orbit, one program.
3. **Physically tied air.** Density, temperature and pressure always obey the gas law.
4. **Perturbations along the flight path**, with memory in height, distance and time.
5. **Site data can be loaded** (Range Reference Atmospheres), and decades of use make review boards accept it.

Its weak sides: nothing about the specific day, bell-shaped spread only, smooth profiles (no sharp shear
layers or inversions), coarse tables, little hour-of-day detail near the ground. NASA itself does not use it
for ascent wind loads: there it flies databases of **measured** wind profiles (Jimsphere balloons, the 50 MHz
wind profiler) and handles launch-day wind change with measured **wind pairs** 2 and 3.5 hours apart.

## 2. Where we stand today (new kit `new_plan_kit/b9_gram_compare.py`, log `kit_b9_gram_compare.log`)

The kit scores any set of atmospheres against the same balloons. Real Earth-GRAM output can be dropped in
later (`--extra gram=FILE.npz`; `--cases-out` writes the list of runs to make; `--from-csv` converts a table).
Until then the second source is `gaussfull`: a bell curve with the balloon station's own mean and full
covariance, 1991-2020. It is **not** Earth-GRAM. It is the ceiling for any bell-curve method at a balloon
station, so the real program should score at or below it. That is an expectation, not a result.

800 balloons (El Paso and Midland, 00Z and 12Z, 2024-25), 100 members each:

| Score | Tool | Bell-curve ceiling | Reading |
|---|---|---|---|
| CRPS u / v / T | 4.38 / 4.38 / 1.96 | 4.53 / 4.39 / 2.12 | tool better for u (3.4 %) and T (8.3 %), **tie for v** |
| Profile shape score (variogram) u / v / T | 1.318 / 1.139 / 0.209 | 1.379 / 1.142 / 0.215 | tool better for u and T, tie for v |
| Link between variables at one height | 0.1861 | 0.1855 | tie |
| Vertical correlation error | 0.060 | 0.043 | **ceiling better** |
| Shear, top 1 %, ratio to balloons (4 bands) | 0.71 / 0.91 / 0.75 / 0.76 | 0.65 / 0.84 / 0.81 / 0.74 | both too smooth |
| Share of unstable layers, 12-18 km (real 0.149) | 0.067 | 0.090 | both far too few |
| 90 % range holds (u / v / T) | 0.88 / 0.87 / 0.89 | 0.88 / 0.88 / 0.87 | both a little narrow against real air |

Limits: 2024-25 is the development window; neither source is blind at these stations; the intervals resample
single days (audit AU-4 says that is too narrow); only complete soundings are used (AU-6); `gaussfull` is the
all-years form (AU-7 asks for a recent-15-year form beside it: an option to add, one line).

**Plain reading.** Against a bell curve we are already level or ahead on accuracy and on profile shape. So
"coupling" is not weak against Earth-GRAM. It is weak against **real air**, and so is the bell curve:
shear tails 10-30 % short, half the unstable layers aloft, ranges a little narrow. The second real weakness
is the wind near the ground at a site without a record. The third is temperature at 12-18 km. In climate mode
the v-wind tie is close to the ceiling of what a date alone can tell: the win over Earth-GRAM has to come from
real-air structure, the site, all 24 hours and launch-day data, not from a better monthly average.

## 3. What others did about the same problems (searches of 2026-11-12; abstracts and summaries only)

| Problem | Who | What they did | Use for us |
|---|---|---|---|
| Reanalysis wind wrong at a site | wind-energy field | Scale ERA5 by the **Global Wind Atlas** (a 250 m map of mean wind at several heights). Standard practice; errors about 8 % in flat land, 14-17 % in mountains; a 2026 preprint cuts mean bias by a third with atlas speed, elevation and quantiles as inputs | E1 |
| No truth between balloon hours | boundary-layer research | **Aircraft reports** (AMDAR) at 54 US airports give hourly wind and temperature profiles; against balloons 2.0-2.3 m/s per wind component, 1.2-1.5 K. ERA5's daytime boundary layer is 18-41 % too deep and peaks 1-2 h early in the western US | E2 |
| Launch-day wind change | NASA (Shuttle, Ares) | Measured **wind pairs** 2 and 3.5 h apart from balloons and the wind profiler, not a model | E3 |
| Tropopause smeared out | Birner; Randel and others | Averaging at fixed heights hides a 3-5 K inversion above the tropopause; averaging **relative to the tropopause** keeps it | E4 |
| Order of members across heights | Lerch and others, 2020 | The Schaake shuffle (what we use) is "difficult to outperform"; copula variants give no significant gain | no new ordering idea; matches our own failed tries (C2, O5, G1-4) |
| Measured profiles instead of a model | NASA loads work | Monte Carlo over databases of individual measured profiles | E5 (as a bar) |

Checked against our logs before writing: no file mentions the Global Wind Atlas, aircraft reports, wind pairs
or tropopause-relative heights. Nearest relatives are named per idea.

## 4. The five ideas

### E1. Atlas anchor: the site's wind from a 250 m map, no pad record needed

- **Weakness:** wind at 10-200 m at a site with no record. TCS is 1.44 m/s too calm; the tower check gave
  -2 to -2.6 m/s at 47-200 m; real 10-200 m speed gain is 1.45 x ERA5's. Every site fix so far needed a record.
- **Idea:** per height (10, 50, 100, 150, 200 m), factor = atlas mean speed at the site / atlas mean speed
  averaged over the ERA5 cell. Apply it to the members' speeds in quantile space, fading out by 300 m. The
  scatter of "atlas factor minus measured factor" over all sites with a record becomes extra spread at any
  site without one, so the tool is honestly wider at an unknown pad.
- **Why it may work here:** it is a simple step beside the network with almost no free numbers, the kind that
  has worked. It is physics from terrain and roughness at 250 m, not a fit at 2-3 airports.
- **Nearest relatives:** IL-207b (one site, needs a record), SV (guess from terrain facts, 12.4), the failed
  WTK and HRRR tries (those used a model as truth; here the atlas is only a prior, judged against stations).
- **Step 0 (small download, CPU minutes):** atlas values at the 71 stations of the SV step 0. Does the atlas
  factor predict the measured real / ERA5 speed ratio (0.61-1.33 between stations)?
- **Pass:** correlation at least 0.5 across stations, and leave-station-out 10 m CRPS better than "no site term"
  with an interval excluding 0; tower check at 47-200 m bias at least halved. **Kill:** correlation under 0.3.
- **Honest odds:** medium. Atlases are known to be weaker in mountains; airports are flat and open.

### E2. Aircraft profiles: a referee and a correction for all 24 hours

- **Weakness:** real profiles exist only at 5 am and 5 pm local. Midday, when rockets fly, is checked against
  ERA5 only. Denver has no balloons after 2022. The all-hours model is 20-25 % too sharp at 100-300 m at dawn
  and nobody can say what is right at noon.
- **Idea:** aircraft climbing and landing at El Paso, Midland, Albuquerque, Lubbock and Denver. (a) A referee
  for every 3-hour bin, 0-8 km, wind and temperature. (b) A small table "real minus tool" by hour bin and
  height band (bias and spread), added the way the real-air gap rule A1 was (6 numbers lifted coverage to
  0.90-0.92). (c) A third instrument beside balloon and radar to bound instrument noise.
- **Nearest relatives:** RA covers the hours by pooling balloons around the world (section 11, risk named there:
  hour and region are tied together). This measures the hours at home.
- **Step 0:** needs the user: the public archive (MADIS, data older than 48 h is public, free account; or the
  NCAR EOL archive). Count profiles per airport and 3-hour bin, 2021-23.
- **Pass (step 0):** at least 200 profiles in every 3-hour bin at two airports of the NM/TX box. **Kill:** fewer.
- **Honest odds:** high as a referee (it is new truth), medium as a correction.

### E3. Wind pairs: how fast a measured profile goes stale, from radar

- **Weakness and strength at once:** launch-day measurements are our largest gain (radar +31 % aloft), but how
  an observation ages is an assumed curve (0.72 per hour), fitted at 10 m only.
- **Idea (NASA's method with our radar):** from all-hours radar wind profiles (El Paso, Holloman, Midland,
  Denver) build pairs 1, 2, 3 and 6 h apart. (a) Measured change per height, lag, season and hour replaces the
  assumed ageing aloft. (b) A new product: last measured profile + whole real change profiles drawn from the
  pairs = a measured-persistence ensemble for the last hours before launch. Earth-GRAM has nothing like it.
- **Nearest relatives:** A1 / G1-6 (10 m persistence only), O2 (radar over distance). No file has wind pairs.
- **Step 0:** the radar files on disk are one volume at 23 and 11 UTC only; an all-hours pull for one site and
  one year is needed first (small, approved kind of download). Count pairs with wind at 4 or more levels.
- **Pass:** at 1-3 h the pair ensemble beats tool + `observe_radar` by 10 % CRPS at 0.5-5 km, coverage 0.85-0.95,
  on days not used for the pairs. **Kill:** under 3 %, or under 500 usable pairs per lag.
- **Honest odds:** medium to high for (a), medium for (b); clear air gives no radar wind on many days.

### E4. Tropopause anchor for 9-18 km

- **Weakness:** temperature at 12-18 km is worse than plain climatology (-0.030 / -0.039); unstable layers at
  12-18 km are 0.067 against 0.149 real; this band also changed around 2020.
- **Idea:** at a fixed height near 12-16 km the air is sometimes below and sometimes above the tropopause, so
  the spread is really two cases mixed, and any fixed-height method smears the sharp step. Take each member's
  own tropopause height, and add back fine temperature and wind structure from real balloon leftovers stored
  **relative to the tropopause**, placed at the member's tropopause. Values at the coarse heights stay locked,
  as in VS. The 2020 change is then tested as a shift in tropopause height, which one number can follow.
- **Nearest relatives:** VS and its library bar (12.3: same leftovers, but stored at fixed heights); L3-7
  (tropopause height as a network input). New: the coordinate.
- **Step 0 (balloons only, no tool scoring):** spread of balloon temperature at 10-16 km at fixed heights against
  the spread at fixed distance from the tropopause; and whether the post-2020 change is a height shift.
- **Pass (step 0):** tropopause-relative spread under 70 % of the fixed-height spread at three or more levels.
  **Kill:** over 90 %: the coordinate adds nothing, close.
- **Honest odds:** step 0 passing, high (it is a textbook effect). A skill gain in the tool, medium.

### E5. The measured-profile bank as a third bar

- **Why:** NASA's real alternative to Earth-GRAM for winds is a database of measured profiles. We compare
  ourselves with a bell curve only. A bank of real balloons of the same month and hour is the bar for
  "real-air structure": it has true shear, true unstable layers and true coupling by construction, and no skill
  beyond climatology.
- **Idea:** add `bank` as a source in the kit (same file path as Earth-GRAM will use). It says, score by score,
  how much of our gap to real air is structure (the bank wins) and how much is truth-data limits (the bank
  loses too). It also settles whether the v-wind tie is the ceiling: if tool, bell curve and bank all tie,
  nothing is left to gain there in climate mode.
- **Nearest relatives:** G1-2 mixed pool (15 % real ERA5 profiles as members; not a bar, not balloons).
- **Cost:** 30 lines in the kit, 10 minutes CPU. Report only, no rule. It is still a scoring run, so it waits
  for the gate.

## 5. Order

1. After the gate: E5 (bar) and the recent-15-year form of `gaussfull`, then real Earth-GRAM when it arrives.
2. Step 0 of E4 (balloons on disk) and E1 (small download) side by side.
3. E3 step 0 (one radar site, one year). E2 when the user has an archive account.
4. What already exists stays first in line for real-air structure: RA (coarse gap), VS (fine layers), SV (site).
   E1 gives SV a physical first guess, E2 checks RA's hours, E4 gives VS its upper-band coordinate.

## 6. Sources

Global Wind Atlas scaling and its limits: wes.copernicus.org/preprints/wes-2026-75, frontiersin.org
10.3389/fclim.2023.1017774, iris.cnr.it (Gualtieri, tall towers). Aircraft profiles: Zhang et al. 2019 and 2020
(JGR Atmospheres), madis.ncep.noaa.gov/madis_acars.shtml, data.eol.ucar.edu/dataset/100.016. NASA measured
wind databases and wind pairs: ntrs.nasa.gov 20050092294, 20110002632, 19990008476. Tropopause-relative
averaging: Randel, Wu and Forster 2007 (J. Atmos. Sci.), acp.copernicus.org/articles/19/6985/2019.
Ordering methods: Lerch et al. 2020 (npg.copernicus.org/articles/27/349/2020), arXiv 2206.10237.
