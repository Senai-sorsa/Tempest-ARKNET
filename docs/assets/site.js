/* ==========================================================================
   Tempest-ARKNET Multi-Page Monograph Shell (v3)
   Shared navigation manifest, expandable sidebar, right TOC scroll-spy,
   Glossary drawer, Mermaid light-editorial renderer, Zoom modal, Colab links.
   ========================================================================== */

const COLAB_LINKS = {
  lab_01: {
    title: "Lab 1: Thermodynamics & 44-Level Vertical Grid",
    url: "https://colab.research.google.com/drive/1oMBQoQit2cGR7SrLgL977LYCItUxbv1T?ouid=105583833647304009872"
  },
  lab_02: {
    title: "Lab 2: Engression Backbone & Proper Scoring Rules",
    url: "https://colab.research.google.com/drive/1YzVnOXrDNII3vBBVpAgK5iInHm-UYgjC?ouid=105583833647304009872"
  },
  lab_03: {
    title: "Lab 3: Balloon Calibration, Routing & Student-t Copulas",
    url: "https://colab.research.google.com/drive/1GrMTgcvqG3RioC6OTCNhOEnMxPjjo6D7?ouid=105583833647304009872"
  },
  lab_04: {
    title: "Lab 4: Launch-Day Assimilation & 6-DOF Flight Monte Carlo",
    url: "https://colab.research.google.com/drive/1JHgQvQqOYJ4wtY8XSYyMmJzrR9AxlhVp?ouid=105583833647304009872"
  }
};

function openColabLab(key) {
  const entry = COLAB_LINKS[key];
  if (entry && entry.url) {
    window.open(entry.url, "_blank", "noopener,noreferrer");
  }
}

/* Complete 16-Page Site Navigation Tree (populated dynamically across all pages) */
const SITE_NAV = [
  {
    group: "0 · Start Here",
    pages: [
      {
        id: "index",
        href: "index.html",
        title: "Overview & Architecture Map",
        subs: [
          ["sec-0-1", "0.1 Sixty-second executive summary"],
          ["sec-0-2", "0.2 Why standard forecasts fail rockets"],
          ["sec-0-3", "0.3 Core pipeline vs. modular add-ons"],
          ["sec-0-4", "0.4 Interactive add-on registry (30)"],
          ["sec-0-5", "0.5 How everything fits together"],
          ["sec-0-6", "0.6 Reading roadmap & Colab labs"]
        ]
      }
    ]
  },
  {
    group: "Stage 1 · Data & Physics",
    pages: [
      {
        id: "01_ingest",
        href: "pages/01_ingest.html",
        title: "1.1 Data ingest & alignment",
        subs: [
          ["s1-1-1", "1.1.1 Why multi-source alignment matters"],
          ["s1-1-2", "1.1.2 ERA5 reanalysis archive ingestion"],
          ["s1-1-3", "1.1.3 IGRAv2 radiosonde ground truth"],
          ["s1-1-4", "1.1.4 Live NWP feeds (HRRR, GFS, GEFS, IFS)"],
          ["s1-1-5", "1.1.5 Climate teleconnection drivers (ONI, QBO, WWV)"],
          ["s1-1-6", "1.1.6 Base 13 vs. P2 16 feature schemas"],
          ["s1-1-7", "1.1.7 Quality control, sentinels & leakage guards"]
        ]
      },
      {
        id: "02_thermo",
        href: "pages/02_thermo.html",
        title: "1.2 Thermodynamics & 44-level grid",
        subs: [
          ["s1-2-1", "1.2.1 The 44-level AGL height ladder"],
          ["s1-2-2", "1.2.2 Geopotential vs. geometric altitude"],
          ["s1-2-3", "1.2.3 Saturation vapor pressure & Buck/Bolton"],
          ["s1-2-4", "1.2.4 Log dewpoint depression encoding (dpd)"],
          ["s1-2-5", "1.2.5 Virtual temperature & moist density"],
          ["s1-2-6", "1.2.6 Two-pass hypsometric pressure integration"],
          ["s1-2-7", "1.2.7 Lossless telescoping vertical differences"],
          ["s1-2-8", "1.2.8 Anatomy of the D = 179 state vector"],
          ["s1-2-9", "1.2.9 Interactive lab: Thermo & height ladder"]
        ]
      }
    ]
  },
  {
    group: "Stage 2 · Generative AI Core",
    pages: [
      {
        id: "03_engression",
        href: "pages/03_engression.html",
        title: "2.1 Engression neural backbone",
        subs: [
          ["s2-1-1", "2.1.1 Why single-step Engression over diffusion"],
          ["s2-1-2", "2.1.2 Pre-additive noise injection theory"],
          ["s2-1-3", "2.1.3 AdaLN / FiLM conditioning mechanics"],
          ["s2-1-4", "2.1.4 Zero-initialized residual blocks"],
          ["s2-1-5", "2.1.5 Linear climate-trend bypass head"],
          ["s2-1-6", "2.1.6 Bimodal jet-streak representation"],
          ["s2-1-7", "2.1.7 Training hyperparameters & stability"]
        ]
      },
      {
        id: "04_losses",
        href: "pages/04_losses.html",
        title: "2.2 Proper scoring rules & losses",
        subs: [
          ["s2-2-1", "2.2.1 Why MSE collapses atmospheric ensembles"],
          ["s2-2-2", "2.2.2 Unbiased finite-sample Fair CRPS"],
          ["s2-2-3", "2.2.3 The crps_alpha = 0.95 stability blend"],
          ["s2-2-4", "2.2.4 Multivariate 179-D Energy Score"],
          ["s2-2-5", "2.2.5 Wind-shear tail loss & excess-std floor"],
          ["s2-2-6", "2.2.6 Low-wind rail-exit vector loss"],
          ["s2-2-7", "2.2.7 Interactive lab: CRPS & spread-skill"]
        ]
      },
      {
        id: "05_gusts_w",
        href: "pages/05_gusts_w.html",
        title: "2.3 Wind gusts, thermals & vertical W",
        subs: [
          ["s2-3-1", "2.3.1 Why rockets care about gusts & updrafts"],
          ["s2-3-2", "2.3.2 Gust factor & gust excess parameterization"],
          ["s2-3-3", "2.3.3 Convective velocity scale w* & CAPE"],
          ["s2-3-4", "2.3.4 Boundary-layer mixing height (PBLH)"],
          ["s2-3-5", "2.3.5 Bulk Richardson number & shear turbulence"],
          ["s2-3-6", "2.3.6 Coupling W-models to the 179-D profile"]
        ]
      }
    ]
  },
  {
    group: "Stage 3 · Calibration & Ops",
    pages: [
      {
        id: "06_calibration",
        href: "pages/06_calibration.html",
        title: "3.1 Balloon station calibration",
        subs: [
          ["s3-1-1", "3.1.1 Why ERA5-trained models need balloon truth"],
          ["s3-1-2", "3.1.2 M_CAL = 199 quantile grid standardization"],
          ["s3-1-3", "3.1.3 Additive bias & multiplicative spread correction"],
          ["s3-1-4", "3.1.4 Seasonal & diurnal harmonic modulation"],
          ["s3-1-5", "3.1.5 Conformalized quantile safety wrappers"],
          ["s3-1-6", "3.1.6 Elevation shifting (to_site) & dewpoint conservation"],
          ["s3-1-7", "3.1.7 Preventing overfitting on sparse stations"]
        ]
      },
      {
        id: "07_coherence",
        href: "pages/07_coherence.html",
        title: "3.2 Vertical coherence & spatial maps",
        subs: [
          ["s3-2-1", "3.2.1 How marginal calibration destroys wind shear"],
          ["s3-2-2", "3.2.2 Schaake Shuffle rank-template restoration"],
          ["s3-2-3", "3.2.3 Worked 3x2 Schaake Shuffle example"],
          ["s3-2-4", "3.2.4 ERA5 < 2021 template library & fallback"],
          ["s3-2-5", "3.2.5 Spatial kriging & terrain-aware maps"],
          ["s3-2-6", "3.2.6 Shear, lapse-rate & tail correction maps"],
          ["s3-2-7", "3.2.7 Interactive lab: Schaake Shuffle sandbox"]
        ]
      },
      {
        id: "08_routing",
        href: "pages/08_routing.html",
        title: "3.3 Lead-time routing & forecast modes",
        subs: [
          ["s3-3-1", "3.3.1 Three operational modes: Climate, Forecast, Launch"],
          ["s3-3-2", "3.3.2 Lead-time horizon regimes (0h to 16d+)"],
          ["s3-3-3", "3.3.3 Smooth crossfading between HRRR, GFS & IFS"],
          ["s3-3-4", "3.3.4 Near-term NWP ensemble ingestion"],
          ["s3-3-5", "3.3.5 UR5 climate wind-sequence post-processor"],
          ["s3-3-6", "3.3.6 Graceful degradation & offline fallbacks"]
        ]
      },
      {
        id: "09_scoring_ops",
        href: "pages/09_scoring_ops.html",
        title: "3.4 Verification, scoring & operations",
        subs: [
          ["s3-4-1", "3.4.1 Strict temporal holdout (1991-2026 timeline)"],
          ["s3-4-2", "3.4.2 CRPS, Energy Score & Variogram Score"],
          ["s3-4-3", "3.4.3 PIT histograms & Spread-Skill Ratio (SSR)"],
          ["s3-4-4", "3.4.4 Brier Skill Score for Go/No-Go gates"],
          ["s3-4-5", "3.4.5 Sonde verification harness & stack order"],
          ["s3-4-6", "3.4.6 Drift monitoring & promotion criteria"]
        ]
      }
    ]
  },
  {
    group: "Stage 4 · Serving Engine",
    pages: [
      {
        id: "10_serving",
        href: "pages/10_serving.html",
        title: "4.0 Pure-NumPy serving engine",
        subs: [
          ["s4-1", "4.1 Why zero-PyTorch serving matters at the pad"],
          ["s4-2", "4.2 Weight export (.npz) & memory footprint"],
          ["s4-3", "4.3 NumPy forward pass & float32 parity"],
          ["s4-4", "4.4 The public API (describe, sample, couple)"],
          ["s4-5", "4.5 Post-generation stack execution order"],
          ["s4-6", "4.6 Vectorized latency budgets (~20 ms)"],
          ["s4-7", "4.7 Known serving edge cases (B1, B13)"]
        ]
      }
    ]
  },
  {
    group: "Stage 5 · Launch Day & v2",
    pages: [
      {
        id: "11_assimilation",
        href: "pages/11_assimilation.html",
        title: "5.1 Launch-day observation assimilation",
        subs: [
          ["s5-1-1", "5.1.1 The launch-morning information gap"],
          ["s5-1-2", "5.1.2 Live METAR, ASOS, pad & pibal feeds"],
          ["s5-1-3", "5.1.3 Exponential lead-time decay (tau_h = 6.3 h)"],
          ["s5-1-4", "5.1.4 Own-station radius (5.0 km) & representativeness"],
          ["s5-1-5", "5.1.5 Kalman / Bayesian posterior ensemble update"],
          ["s5-1-6", "5.1.6 NEXRAD VAD radar wind profile assimilation"],
          ["s5-1-7", "5.1.7 Interactive lab: Lead-time & obs router"]
        ]
      },
      {
        id: "12_v2_toolkit",
        href: "pages/12_v2_toolkit.html",
        title: "5.2 v2 engineering toolkit & copulas",
        subs: [
          ["s5-2-1", "5.2.1 Launch & Window high-level ergonomics"],
          ["s5-2-2", "5.2.2 Aviation calculators (DA, crosswind, Mach)"],
          ["s5-2-3", "5.2.3 AERSURFACE roughness length & log-law"],
          ["s5-2-4", "5.2.4 Gaussian vs. Student-t copula theory"],
          ["s5-2-5", "5.2.5 Kendall-tau inversion & PSD projection"],
          ["s5-2-6", "5.2.6 Lazy imports & Python 3.12 PEP 701 note"],
          ["s5-2-7", "5.2.7 Interactive lab: Gaussian vs. Student-t copula"]
        ]
      }
    ]
  },
  {
    group: "Stage 6 · Flight-Sim & MC",
    pages: [
      {
        id: "13_flight_mc",
        href: "pages/13_flight_mc.html",
        title: "6.0 Flight-sim readers, Dryden & MC",
        subs: [
          ["s6-1", "6.1 Bridging atmospheric profiles to 6-DOF flight"],
          ["s6-2", "6.2 Profile readers & boundary defaults"],
          ["s6-3", "6.3 MIL-HDBK-1797 Dryden turbulence filters"],
          ["s6-4", "6.4 Euler sub-stepping vs. exact AR(2) stepping"],
          ["s6-5", "6.5 Acoustics, speed of sound & avionics altimetry"],
          ["s6-6", "6.6 Joint Monte Carlo & variance attribution"],
          ["s6-7", "6.7 Interactive lab: 6-DOF Monte Carlo sandbox"]
        ]
      }
    ]
  },
  {
    group: "Reference & Ledger",
    pages: [
      {
        id: "14_bugs_guardrails",
        href: "pages/14_bugs_guardrails.html",
        title: "7.0 Confirmed bugs (B1-B14) & guardrails",
        subs: [
          ["s7-1", "7.1 Training & loss bugs (B11, B12)"],
          ["s7-2", "7.2 Calibration, scoring & near-term bugs (B4, B5, B14)"],
          ["s7-3", "7.3 Serving & conditioning bugs (B1, B3, B13)"],
          ["s7-4", "7.4 Launch-day v2 & flight-sim bugs (B2, B6-B10)"],
          ["s7-5", "7.5 Python 3.12 PEP 701 compatibility guide"]
        ]
      },
      {
        id: "experiments",
        href: "tests/experiments.html",
        title: "Ranked experiments ledger (60)",
        subs: [
          ["tier-1", "Tier 1 · Major adopted wins (13)"],
          ["tier-2", "Tier 2 · Conditional / opt-in (12)"],
          ["tier-3", "Tier 3 · Neutral / tied (9)"],
          ["tier-4", "Tier 4 · Rejected / negative (26)"]
        ]
      }
    ]
  }
];

const GLOSSARY = [
  { term: "AGL / MSL (ASL)", cat: "Physics", plain: "Height measured above the local ground (AGL) vs. above average sea level (MSL). Rockets care about AGL for launch pad wind shear, while weather models often report MSL.", tech: "All 44 Tempest-ARKNET model heights are AGL (10 m to 18 km); z_sfc / elevation_m is MSL." },
  { term: "AdaLN / FiLM", cat: "ML & Scoring", plain: "A dimmer switch inside a neural network that shifts and stretches hidden activations differently for every random noise seed so one backbone can draw diverse weather worlds.", tech: "Adaptive Layer Normalization / Feature-wise Linear Modulation: LN(h) * (1 + s) + b conditioned on noise embedding z_eps." },
  { term: "AERSURFACE / z_0", cat: "Physics", plain: "Aerodynamic surface roughness length — how much friction trees, buildings, or desert scrub exert on low-level wind, slowing down surface wind relative to wind aloft.", tech: "NLCD land-cover roughness lookup used in log-law wind profile extrapolation below 10 m AGL." },
  { term: "AR(1) / AR(2) Dryden", cat: "Physics", plain: "Memory-bearing stochastic filters that turn white noise into realistic 3D wind gusts with altitude-dependent eddy lengths.", tech: "MIL-HDBK-1797 forming filters in tempest_weather/flight/dryden.py (exact AR(1) vertical w_g; Euler or exact AR(2) transverse u_g, v_g)." },
  { term: "Brier Skill Score (BSS)", cat: "ML & Scoring", plain: "Measures how much better a Go/No-Go probability forecast is than just guessing the historical base rate (0 = climatology, 1 = perfect).", tech: "BSS = 1 - BS / BS_ref for binary threshold events." },
  { term: "CAPE / CIN", cat: "Physics", plain: "CAPE is convective fuel available for rising storm updrafts; CIN is the warm-air cap holding those updrafts down until broken.", tech: "Convective Available Potential Energy and Convective Inhibition (J/kg) via parcel buoyancy integration." },
  { term: "Cholesky Decomposition", cat: "ML & Scoring", plain: "Taking the matrix square root of a correlation table so independent random draws become realistically correlated across altitudes.", tech: "Factorization Sigma = L L^T used in MVN conditional updates and correlated copula draws." },
  { term: "Conformalized Quantile (CQR)", cat: "ML & Scoring", plain: "A distribution-free safety margin wrapper that adjusts uncertainty bands until empirical coverage matches the target (e.g., 90%).", tech: "Split-conformal calibration on holdout residuals guaranteeing finite-sample marginal coverage." },
  { term: "Copula (Gaussian vs. Student-t)", cat: "ML & Scoring", plain: "The mathematical glue binding separate altitude margins into a joint profile; Student-t keeps extreme tail gusts coupled together instead of letting them decouple.", tech: "Gaussian copula has zero tail dependence (lambda_U = 0); Student-t with nu df preserves positive tail dependence." },
  { term: "CRPS", cat: "ML & Scoring", plain: "Continuous Ranked Probability Score — rewards ensembles for being both close to truth and honestly spread.", tech: "Proper scoring rule E|X - y| - 0.5 E|X - X'|; unbiased estimator divides spread term by M(M-1)." },
  { term: "D = 179 State Vector", cat: "ML & Scoring", plain: "The complete 179-number atmospheric snapshot produced for every ensemble member: 4 variables across 44 heights plus 3 surface scalars.", tech: "[u(44), v(44), T(44), RH/lnd(44), t2m(1), sp(1), rh2m(1)] = 4*44 + 3 = 179 (tempest/_core.py:7-9, 39)." },
  { term: "Density Altitude (DA)", cat: "Physics", plain: "The altitude the rocket aerodynamically feels based on air thinness — hot desert days lower density, reducing drag and fin restoring force.", tech: "ISA pressure altitude where standard density equals local moist air density rho = p / (R_d T_v)." },
  { term: "Dewpoint Depression (dpd)", cat: "Physics", plain: "How many degrees warmer the air is than its dew point — transformed with log(1 + dpd) so bone-dry desert air never piles up against a 0% RH wall.", tech: "dpd = max(T - T_d, 0); log1p(dpd) eliminates boundary pile-up and enforces T_d <= T." },
  { term: "Energy Score (ES)", cat: "ML & Scoring", plain: "The multi-altitude cousin of CRPS that scores the entire 179-D vertical profile at once so the neural net learns realistic vertical wind shear.", tech: "Multivariate strictly proper scoring rule: E||X - y||_2 - 0.5 E||X - X'||_2 normalized by 1/sqrt(D)." },
  { term: "Engression", cat: "ML & Scoring", plain: "A single-step generative neural network that takes weather inputs plus random noise and directly outputs realistic weather profiles without slow diffusion steps.", tech: "Shen & Meinshausen (2024) pre-additive noise generative regression trained with Energy/CRPS loss." },
  { term: "ERA5 / HRRR / GFS / GEFS / IFS", cat: "Ops & Obs", plain: "The five NWP weather models Tempest ingests: ERA5 (reanalysis), HRRR (3 km US hourly), GFS/GEFS (global), and ECMWF IFS (global benchmark).", tech: "Projected onto the canonical 44-level AGL height grid with lead-time-aware routing." },
  { term: "Geopotential Height (Z)", cat: "Physics", plain: "Gravity-adjusted altitude used by weather models so a unit step in Z always represents equal gravitational work.", tech: "Converted to geometric height z via R_E * Z / (R_E - Z)." },
  { term: "Hypsometric Equation", cat: "Physics", plain: "The vertical ruler connecting pressure, temperature, and layer thickness — warmer, moister air puffs up thicker between two pressure surfaces.", tech: "Delta Z = (R_d * T_v_bar / g_0) * ln(p_1 / p_2)." },
  { term: "IGRAv2", cat: "Ops & Obs", plain: "Global historical archive of real weather balloon launches (radiosondes) — the ground-truth answer key for calibration and validation.", tech: "NOAA/NCEI Integrated Global Radiosonde Archive v2." },
  { term: "Kriging / Spatial Maps", cat: "ML & Scoring", plain: "Geographic interpolation that estimates calibration corrections at a new launch site from nearby balloon stations and terrain.", tech: "Distance- and terrain-weighted spatial fields for bias, spread, shear, and lapse corrections." },
  { term: "LIFT / Launch-Day Assimilation", cat: "Ops & Obs", plain: "Real-time launch-morning updating: blending live METAR airport readings, pad anemometers, and fresh balloons into the forecast ensemble.", tech: "Conditional update with exponential decay tau_h = 6.3 h and own-station radius 5.0 km (obs.py:22, 29)." },
  { term: "M_CAL = 199", cat: "ML & Scoring", plain: "Standardized calibrated ensemble size so quantile ranks fall on clean 0.5% grid points from 0.5% to 99.5%.", tech: "api.py:27; quantile grid p_k = k / (M_CAL + 1) for k = 1..199." },
  { term: "METAR / ASOS / Pibal", cat: "Ops & Obs", plain: "METAR/ASOS are hourly automated airport weather reports; a Pibal is a small helium pilot balloon tracked at the launch pad.", tech: "Ingested by tempest_weather_v2/metar.py and obs.py." },
  { term: "PIT Histogram", cat: "ML & Scoring", plain: "Probability Integral Transform — checks where reality landed inside the ensemble; flat = honest uncertainty, U-shaped = overconfident.", tech: "Empirical distribution of F_hat(y_i) across holdout test soundings." },
  { term: "Pure-NumPy Serving", cat: "Ops & Obs", plain: "Running the trained neural network at the launch site using only NumPy — zero PyTorch, zero GPU, ~20 ms on a field laptop.", tech: "Exported .npz weight bundles executed via tempest_weather/engine.py." },
  { term: "Richardson Number (Ri_b)", cat: "Physics", plain: "Tug-of-war ratio between buoyancy calming the air and wind shear churning it into turbulence (below 0.25 = turbulent mixing).", tech: "Bulk Richardson number Ri_b = (g / theta_v) * (Delta theta_v * Delta z) / ((Delta u)^2 + (Delta v)^2)." },
  { term: "Schaake Shuffle", cat: "ML & Scoring", plain: "Re-orders independently calibrated altitude forecasts to match the vertical rank structure of real historical atmospheres so wind shear stays physical.", tech: "Clark et al. (2004) template rank-matching using historical ERA5 training rows (yr < 2021; export_tool.py:128-150)." },
  { term: "Spread-Skill Ratio (SSR)", cat: "ML & Scoring", plain: "Compares how wide the ensemble is against how big its actual errors are — 1.00 means the model knows exactly how uncertain it is.", tech: "SSR = sqrt(mean ensemble variance) / RMSE of ensemble mean." },
  { term: "UR5 Sequence", cat: "ML & Scoring", plain: "Shipped-ON climate-mode 10 m wind sequence post-processor combining speed quantile mapping, spread scaling, and a two-regime calm/windy Markov chain.", tech: "OPTIONS['ur5_sequence'] = True in tempest_weather/api.py:28 (tempest_weather/ur5.py)." },
  { term: "Variogram Score", cat: "ML & Scoring", plain: "Measures whether an ensemble gets the differences between altitudes (like wind shear from 100 m to 3 km) right.", tech: "Scheuerer & Hamill (2015) multivariate score on pairwise |X_i - X_j|^0.5 differences." },
  { term: "Virtual Temperature (T_v)", cat: "Physics", plain: "Because water vapor molecules are lighter than dry air, humid air behaves like slightly warmer dry air — T_v is that equivalent dry temperature.", tech: "T_v = T * (1 + 0.6078 * q); enters moist density and hypsometric thickness." },
  { term: "Wind Rose (FROM vs. TO)", cat: "Ops & Obs", plain: "Meteorological wind direction reports where wind blows FROM, whereas flight dynamics uses velocity vector TO — dropping the minus sign flips crosswind 180 degrees.", tech: "u = -V sin(dir_rad), v = -V cos(dir_rad) (0 deg = North, 90 deg = East)." }
];

/* Helpers for relative path resolution between root index.html and pages/*.html or tests/*.html */
function getBasePrefix() {
  return document.body.dataset.base || "";
}

function buildSidebar() {
  const container = document.getElementById("site-sidebar-nav");
  if (!container) return;
  const base = getBasePrefix();
  const currentPageId = document.body.dataset.pageId || "";

  container.innerHTML = SITE_NAV.map(group => {
    const pagesHtml = group.pages.map(page => {
      const isCurrent = page.id === currentPageId;
      const openClass = isCurrent ? "is-open is-current" : "";
      const subsHtml = (page.subs || []).map(([subId, subTitle]) => {
        const href = isCurrent ? `#${subId}` : `${base}${page.href}#${subId}`;
        return `<li><a href="${href}" data-sub-target="${subId}">${subTitle}</a></li>`;
      }).join("");
      return `
        <div class="sidebar-chapter ${openClass}" data-chapter-id="${page.id}">
          <div class="sidebar-chapter-row">
            <button type="button" class="sidebar-expand-btn" aria-label="Toggle subsections" title="Toggle subsections">&#9656;</button>
            <a class="sidebar-chapter-link" href="${base}${page.href}">${page.title}</a>
          </div>
          <ul class="sidebar-sublist">${subsHtml}</ul>
        </div>
      `;
    }).join("");
    return `
      <div class="sidebar-group">
        <p class="sidebar-group-label">${group.group}</p>
        ${pagesHtml}
      </div>
    `;
  }).join("");

  container.querySelectorAll(".sidebar-expand-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      btn.closest(".sidebar-chapter")?.classList.toggle("is-open");
    });
  });
}

function buildRightTocAndPager() {
  const base = getBasePrefix();
  const currentPageId = document.body.dataset.pageId || "";

  // Build Right "On This Page" TOC from actual .subsection elements in DOM
  const tocList = document.getElementById("on-this-page-list");
  const sections = Array.from(document.querySelectorAll("main section.subsection[id]"));
  if (tocList && sections.length > 0) {
    tocList.innerHTML = sections.map(sec => {
      const h2 = sec.querySelector("h2");
      const num = sec.querySelector(".subsection-num");
      const label = h2 ? h2.textContent.trim() : sec.id;
      const prefix = num ? `${num.textContent.trim()} ` : "";
      return `<li><a href="#${sec.id}" data-toc-target="${sec.id}">${prefix}${label}</a></li>`;
    }).join("");
  }

  // Build Prev / Next chapter pager
  const pager = document.getElementById("chapter-pager");
  if (pager) {
    const flat = SITE_NAV.flatMap(g => g.pages);
    const idx = flat.findIndex(p => p.id === currentPageId);
    const prev = idx > 0 ? flat[idx - 1] : null;
    const next = idx >= 0 && idx < flat.length - 1 ? flat[idx + 1] : null;
    pager.innerHTML = `
      ${prev ? `<a class="pager-card" href="${base}${prev.href}"><span class="pager-dir">&larr; Previous chapter</span><span class="pager-title">${prev.title}</span></a>` : `<div></div>`}
      ${next ? `<a class="pager-card pager-next" href="${base}${next.href}"><span class="pager-dir">Next chapter &rarr;</span><span class="pager-title">${next.title}</span></a>` : `<div></div>`}
    `;
  }

  // Reading progress + ScrollSpy for both Right TOC and current page's Left Sidebar subsections
  const progressFill = document.getElementById("reading-progress-fill");
  const tocLinks = Array.from(document.querySelectorAll("[data-toc-target]"));
  const sideSubLinks = Array.from(document.querySelectorAll(".sidebar-chapter.is-current [data-sub-target]"));

  function onScroll() {
    const scrollTop = window.scrollY || document.documentElement.scrollTop;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    if (progressFill && docHeight > 0) {
      progressFill.style.width = `${Math.min(100, Math.max(0, (scrollTop / docHeight) * 100))}%`;
    }
    if (sections.length === 0) return;
    let activeId = sections[0].id;
    for (const sec of sections) {
      if (sec.getBoundingClientRect().top <= 160) activeId = sec.id;
    }
    tocLinks.forEach(a => a.classList.toggle("is-active", a.getAttribute("data-toc-target") === activeId));
    sideSubLinks.forEach(a => a.classList.toggle("is-active", a.getAttribute("data-sub-target") === activeId));
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

/* Glossary Drawer */
let activeGlossaryCat = "All";

function renderGlossary() {
  const list = document.getElementById("glossary-list");
  if (!list) return;
  const q = (document.getElementById("glossary-search")?.value || "").trim().toLowerCase();
  const filtered = GLOSSARY.filter(item => {
    const catOk = activeGlossaryCat === "All" || item.cat === activeGlossaryCat;
    const textOk = !q || item.term.toLowerCase().includes(q) || item.plain.toLowerCase().includes(q) || item.tech.toLowerCase().includes(q);
    return catOk && textOk;
  });
  const countEl = document.getElementById("glossary-count");
  if (countEl) countEl.textContent = `${filtered.length} of ${GLOSSARY.length} terms`;
  list.innerHTML = filtered.map(item => `
    <div class="glossary-item">
      <div style="display:flex;justify-content:space-between;align-items:baseline;gap:1rem;">
        <h3 class="glossary-term">${item.term}</h3>
        <span class="glossary-cat">${item.cat}</span>
      </div>
      <p style="font-size:1.02rem;line-height:1.7;margin:0 0 0.6rem;color:var(--ink-body);">${item.plain}</p>
      <p style="font-family:var(--font-mono);font-size:0.88rem;line-height:1.55;margin:0;color:var(--ink-secondary);">${item.tech}</p>
    </div>
  `).join("") || `<p style="color:var(--ink-secondary);">No matching terms.</p>`;
}

function openGlossary() {
  document.getElementById("glossary-backdrop")?.classList.add("is-open");
  document.getElementById("glossary-drawer")?.classList.add("is-open");
  renderGlossary();
}

function closeGlossary() {
  document.getElementById("glossary-backdrop")?.classList.remove("is-open");
  document.getElementById("glossary-drawer")?.classList.remove("is-open");
}

/* Fullscreen Diagram Zoom Modal */
let zoomScale = 1.0;

function openMermaidZoom(trigger) {
  const container = trigger.closest(".figure-stage, figure, section");
  const svg = container ? container.querySelector(".mermaid-render svg, .mermaid svg, svg") : null;
  const content = document.getElementById("zoom-modal-content");
  const modal = document.getElementById("zoom-modal");
  if (!svg || !content || !modal) return;
  content.innerHTML = "";
  const clone = svg.cloneNode(true);
  clone.style.maxWidth = "none";
  clone.style.minWidth = "860px";
  clone.style.height = "auto";
  content.appendChild(clone);
  zoomScale = 1.0;
  applyZoom();
  modal.classList.add("is-open");
}

function applyZoom() {
  const content = document.getElementById("zoom-modal-content");
  const pct = document.getElementById("zoom-pct");
  if (content) content.style.transform = `scale(${zoomScale})`;
  if (pct) pct.textContent = `${Math.round(zoomScale * 100)}%`;
}

function adjustZoom(delta) {
  zoomScale = Math.min(2.6, Math.max(0.5, zoomScale + delta));
  applyZoom();
}

function resetZoom() {
  zoomScale = 1.0;
  applyZoom();
}

function closeZoom() {
  document.getElementById("zoom-modal")?.classList.remove("is-open");
}

/* Inject shared Glossary Drawer & Zoom Modal DOM automatically */
function injectSharedModals() {
  const wrap = document.createElement("div");
  wrap.innerHTML = `
    <div id="glossary-backdrop" class="modal-backdrop" onclick="closeGlossary()"></div>
    <aside id="glossary-drawer" class="glossary-drawer" aria-label="Glossary">
      <div class="glossary-header">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
          <div>
            <div style="font-family:var(--font-mono);font-size:0.8rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--accent);">Plain-English First</div>
            <h2 style="font-family:var(--font-serif);font-size:1.65rem;margin:0.2rem 0 0;color:var(--ink-primary);">Glossary</h2>
          </div>
          <button type="button" class="figure-btn" onclick="closeGlossary()">Close</button>
        </div>
        <input id="glossary-search" type="search" placeholder="Search terms (CRPS, Dryden, Schaake, T_v)..." style="width:100%;padding:0.75rem 1rem;border:1px solid var(--border-strong);border-radius:6px;font-size:1rem;background:var(--bg-white);color:var(--ink-primary);" />
        <div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-top:0.85rem;">
          <button type="button" class="figure-btn gcat-btn" data-gcat="All" style="border-color:var(--accent);color:var(--accent);background:var(--bg-accent-soft);">All</button>
          <button type="button" class="figure-btn gcat-btn" data-gcat="Physics">Physics</button>
          <button type="button" class="figure-btn gcat-btn" data-gcat="ML & Scoring">ML &amp; Scoring</button>
          <button type="button" class="figure-btn gcat-btn" data-gcat="Ops & Obs">Ops &amp; Obs</button>
        </div>
        <div id="glossary-count" style="margin-top:0.75rem;font-size:0.875rem;color:var(--ink-secondary);font-family:var(--font-mono);"></div>
      </div>
      <div id="glossary-list" class="glossary-body"></div>
    </aside>

    <div id="zoom-modal" class="zoom-modal">
      <div class="zoom-toolbar">
        <span style="font-family:var(--font-serif);font-size:1.25rem;font-weight:700;color:var(--ink-primary);">Diagram Inspector</span>
        <div style="display:flex;align-items:center;gap:0.6rem;">
          <button type="button" class="figure-btn" onclick="adjustZoom(-0.2)">&minus;</button>
          <span id="zoom-pct" style="font-family:var(--font-mono);min-width:56px;text-align:center;">100%</span>
          <button type="button" class="figure-btn" onclick="adjustZoom(0.2)">+</button>
          <button type="button" class="figure-btn" onclick="resetZoom()">Reset</button>
          <button type="button" class="figure-btn" onclick="closeZoom()" style="border-color:var(--accent-red);color:var(--accent-red);">Close (Esc)</button>
        </div>
      </div>
      <div class="zoom-stage">
        <div id="zoom-modal-content" style="transform-origin:center;transition:transform 0.15s ease;"></div>
      </div>
    </div>
  `;
  document.body.appendChild(wrap);
}

document.addEventListener("DOMContentLoaded", () => {
  injectSharedModals();
  buildSidebar();
  buildRightTocAndPager();

  // Mobile sidebar toggle
  const sidebar = document.getElementById("site-sidebar");
  document.getElementById("mobile-nav-toggle")?.addEventListener("click", () => {
    sidebar?.classList.toggle("is-open");
  });

  // Glossary events
  document.getElementById("glossary-search")?.addEventListener("input", renderGlossary);
  document.querySelectorAll(".gcat-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      activeGlossaryCat = btn.getAttribute("data-gcat") || "All";
      document.querySelectorAll(".gcat-btn").forEach(b => {
        const active = b === btn;
        b.style.borderColor = active ? "var(--accent)" : "var(--border-strong)";
        b.style.color = active ? "var(--accent)" : "var(--ink-primary)";
        b.style.background = active ? "var(--bg-accent-soft)" : "var(--bg-page)";
      });
      renderGlossary();
    });
  });

  // Escape closes modals
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      closeGlossary();
      closeZoom();
      sidebar?.classList.remove("is-open");
    }
  });

  // KaTeX auto-render
  if (typeof renderMathInElement === "function") {
    renderMathInElement(document.body, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
        { left: "\\[", right: "\\]", display: true }
      ],
      throwOnError: false
    });
  }
});
