/**
 * Tempest-ARKNET Interactive Sandboxes v3 (assets/widgets.js)
 * Editorial light-theme Plotly.js + Vanilla JS module implementing ALL 6 sandboxes.
 * Styled to match the warm-paper Distill.pub / Bartosz Ciechanowski aesthetic of site.css.
 *
 * Renders into (only mounts widgets present on the current page):
 *   1. #widget-1-thermo  — Atmospheric Column & Elevation-Shift Explorer
 *   2. #widget-2-crps    — Almost-Fair CRPS & Spread-Calibration Sandbox
 *   3. #widget-3-router  — Lead-Time Router & Launch-Day Observation Assimilation
 *   4. #widget-4-schaake — Schaake Shuffle & Vertical Coherence Visualizer
 *   5. #widget-5-mc      — Rocket Apogee & Drift Variance Explorer: Vehicle vs. Atmosphere
 *   6. #widget-6-copula  — Gaussian vs. Student-t Conditional Copula Tail Explorer
 *
 * Equations are verbatim from senai-sorsa/tempest-arknet:
 *   - tempest/profiles/thermo.py, tempest/generator/sample.py, tempest_weather_v2/weather_calc.py
 *   - tempest/generator/model.py, tempest/scoring/score.py, tempest/forecast/tailcal.py
 *   - tempest/forecast/router.py, tempest_weather_v2/obs.py
 *   - tempest/calibrate/shuffle.py, tempest/calibrate/shear_map.py
 *   - tempest_weather_v2/montecarlo.py, tempest_weather_v2/stats.py
 */
(function () {
  "use strict";

  // =========================================================================
  // Shared Utilities, Math Helpers & Editorial Light-Theme Styling
  // =========================================================================

  const GRID_COLOR = "rgba(23, 25, 28, 0.08)";
  const ZERO_COLOR = "rgba(23, 25, 28, 0.24)";
  const AXIS_LINE_COLOR = "#cfc9bc";
  const INK_PRIMARY = "#17191c";
  const INK_BODY = "#272b30";
  const INK_SECONDARY = "#525866";
  const ACCENT_COBALT = "#1d4ed8";
  const ACCENT_AMBER = "#b45309";
  const ACCENT_EMERALD = "#047857";
  const ACCENT_CRIMSON = "#b91c1c";
  const ACCENT_VIOLET = "#6d28d9";

  function clamp(x, lo, hi) {
    return x < lo ? lo : x > hi ? hi : x;
  }

  function interp1d(x, table) {
    if (x <= table[0][0]) return table[0][1];
    const last = table.length - 1;
    if (x >= table[last][0]) return table[last][1];
    for (let i = 0; i < last; i++) {
      const x0 = table[i][0], y0 = table[i][1];
      const x1 = table[i + 1][0], y1 = table[i + 1][1];
      if (x >= x0 && x <= x1) {
        const t = (x - x0) / (x1 - x0);
        return y0 + t * (y1 - y0);
      }
    }
    return table[last][1];
  }

  // Deterministic PRNG (Mulberry32) + Box-Muller Gaussian sampler
  function makeRng(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296.0;
    };
  }

  function boxMuller(rng) {
    let u1 = rng();
    const u2 = rng();
    if (u1 < 1e-12) u1 = 1e-12;
    return Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
  }

  function normalPdf(x, mu, sd) {
    const z = (x - mu) / sd;
    return Math.exp(-0.5 * z * z) / (sd * Math.sqrt(2.0 * Math.PI));
  }

  // Lanczos approximation for ln(Gamma(z))
  function logGamma(z) {
    const g = 7;
    const p = [
      0.99999999999980993,
      676.5203681218851,
      -1259.1392167224028,
      771.32342877765313,
      -176.61502916214059,
      12.507343278686905,
      -0.13857109526572012,
      9.9843695780195716e-6,
      1.5056327351493116e-7
    ];
    if (z < 0.5) {
      return Math.log(Math.PI / Math.sin(Math.PI * z)) - logGamma(1.0 - z);
    }
    z -= 1.0;
    let x = p[0];
    for (let i = 1; i < g + 2; i++) {
      x += p[i] / (z + i);
    }
    const t = z + g + 0.5;
    return 0.5 * Math.log(2.0 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
  }

  function studentTPdf(x, df, loc, scale) {
    const z = (x - loc) / scale;
    const logC =
      logGamma(0.5 * (df + 1.0)) -
      logGamma(0.5 * df) -
      0.5 * Math.log(df * Math.PI) -
      Math.log(scale);
    return Math.exp(logC - 0.5 * (df + 1.0) * Math.log(1.0 + (z * z) / df));
  }

  function quantileSorted(sorted, q) {
    const idx = q * (sorted.length - 1);
    const lo = Math.floor(idx);
    const hi = Math.ceil(idx);
    if (lo === hi) return sorted[lo];
    return sorted[lo] + (idx - lo) * (sorted[hi] - sorted[lo]);
  }

  function formatSigned(val, decimals, suffix) {
    const sign = val > 0 ? "+" : val < 0 ? "\u2212" : "\u00B1";
    return sign + Math.abs(val).toFixed(decimals) + (suffix || "");
  }

  function injectWidgetStyles() {
    if (document.getElementById("tempest-widget-styles")) return;
    const style = document.createElement("style");
    style.id = "tempest-widget-styles";
    style.textContent = `
      .tw-card {
        background: #fdfcfa;
        border: 1px solid #e4e1d8;
        border-radius: 12px;
        padding: 2rem 2.25rem;
        color: #17191c;
        font-family: var(--font-sans, 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
        box-shadow: 0 2px 14px rgba(23, 25, 28, 0.045);
        display: flex;
        flex-direction: column;
        gap: 1.75rem;
      }
      .tw-card code {
        font-family: var(--font-mono, 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace);
        font-size: 0.92em;
        background: #f6f5f1;
        border: 1px solid #e4e1d8;
        padding: 0.12em 0.42em;
        border-radius: 4px;
        color: #17191c;
      }
      .tw-header {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1.25rem;
        padding-bottom: 1.25rem;
        border-bottom: 1px solid #e4e1d8;
      }
      .tw-header-text {
        flex: 1 1 360px;
        min-width: 0;
      }
      .tw-header-actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.75rem;
      }
      .tw-kicker {
        font-family: var(--font-mono, 'JetBrains Mono', ui-monospace, monospace);
        font-size: 14.5px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #1d4ed8;
        margin: 0 0 0.35rem;
      }
      .tw-title {
        font-family: var(--font-serif, 'Source Serif 4', Georgia, serif);
        font-size: 1.55rem;
        font-weight: 700;
        line-height: 1.24;
        letter-spacing: -0.015em;
        color: #17191c;
        margin: 0 0 0.45rem;
      }
      .tw-subtitle {
        font-size: 15.5px;
        line-height: 1.6;
        color: #525866;
        margin: 0;
      }
      .tw-presets-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.65rem;
      }
      .tw-presets-label {
        font-size: 15px;
        font-weight: 600;
        color: #525866;
        margin-right: 0.25rem;
      }
      .tw-regime-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
      }
      .tw-regime-info {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.65rem;
        font-size: 15px;
        color: #525866;
      }
      .tw-controls-panel {
        background: #fdfcfa;
        border: 1px solid #e4e1d8;
        border-radius: 10px;
        padding: 1.5rem 1.75rem;
      }
      .tw-controls-grid {
        display: grid;
        gap: 1.5rem 1.75rem;
      }
      .tw-cols-2 {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .tw-cols-3 {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .tw-cols-4 {
        grid-template-columns: repeat(4, minmax(0, 1fr));
      }
      .tw-cols-5 {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .tw-control {
        display: flex;
        flex-direction: column;
        gap: 0.65rem;
        margin: 0;
      }
      .tw-control-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 0.6rem;
        font-size: 15px;
        font-weight: 500;
        color: #17191c;
        line-height: 1.35;
      }
      .tw-control-val {
        font-family: var(--font-mono, 'JetBrains Mono', ui-monospace, monospace);
        font-size: 15px;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        text-align: right;
        white-space: nowrap;
      }
      .tw-slider {
        -webkit-appearance: none;
        appearance: none;
        width: 100%;
        height: 8px;
        border-radius: 9999px;
        background: #e4e1d8;
        border: 1px solid #cfc9bc;
        outline: none;
        cursor: pointer;
      }
      .tw-slider::-webkit-slider-thumb {
        -webkit-appearance: none;
        appearance: none;
        width: 20px;
        height: 20px;
        border-radius: 9999px;
        background: #1d4ed8;
        border: 3px solid #ffffff;
        box-shadow: 0 1px 4px rgba(23, 25, 28, 0.28), 0 0 0 1px rgba(29, 78, 216, 0.35);
        transition: transform 0.12s ease, background-color 0.12s ease;
      }
      .tw-slider::-webkit-slider-thumb:hover {
        transform: scale(1.12);
        background: #1e40af;
      }
      .tw-slider::-moz-range-thumb {
        width: 20px;
        height: 20px;
        border-radius: 9999px;
        background: #1d4ed8;
        border: 3px solid #ffffff;
        box-shadow: 0 1px 4px rgba(23, 25, 28, 0.28), 0 0 0 1px rgba(29, 78, 216, 0.35);
        cursor: pointer;
      }
      .tw-metrics-grid {
        display: grid;
        gap: 1rem;
      }
      .tw-mcols-4 {
        grid-template-columns: repeat(4, minmax(0, 1fr));
      }
      .tw-mcols-5 {
        grid-template-columns: repeat(5, minmax(0, 1fr));
      }
      .tw-mcols-6 {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .tw-metric {
        background: #f4f2ed;
        border: 1px solid #e4e1d8;
        border-radius: 10px;
        padding: 1rem 1.15rem;
        display: flex;
        flex-direction: column;
        gap: 0.32rem;
      }
      .tw-metric-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.45rem;
        flex-wrap: wrap;
      }
      .tw-metric-label {
        font-size: 14.5px;
        font-weight: 600;
        color: #525866;
        line-height: 1.3;
      }
      .tw-metric-val {
        font-size: 1.25rem;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        line-height: 1.25;
        color: #17191c;
      }
      .tw-metric-sub {
        font-size: 14.5px;
        color: #525866;
        font-variant-numeric: tabular-nums;
        line-height: 1.35;
      }
      .tw-decomp-card {
        background: #f4f2ed;
        border: 1px solid #e4e1d8;
        border-radius: 10px;
        padding: 1.2rem 1.45rem;
        display: flex;
        flex-direction: column;
        gap: 0.8rem;
      }
      .tw-decomp-top {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        font-size: 15px;
        font-weight: 600;
        color: #17191c;
      }
      .tw-decomp-mono {
        font-family: var(--font-mono, 'JetBrains Mono', ui-monospace, monospace);
        font-size: 15px;
        font-weight: 600;
        color: #17191c;
        font-variant-numeric: tabular-nums;
      }
      .tw-decomp-track {
        width: 100%;
        height: 16px;
        border-radius: 9999px;
        background: #e4e1d8;
        border: 1px solid #cfc9bc;
        overflow: hidden;
        display: flex;
      }
      .tw-decomp-seg {
        height: 100%;
        transition: width 0.15s ease;
      }
      .tw-decomp-legend {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        font-size: 14.5px;
        color: #525866;
      }
      .tw-swatch {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 3px;
        vertical-align: middle;
        margin-right: 0.45rem;
      }
      .tw-plots-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1.5rem;
        align-items: stretch;
      }
      .tw-plot-col {
        display: flex;
        flex-direction: column;
        gap: 0.85rem;
        min-width: 0;
      }
      .tw-plot-box {
        background: #ffffff;
        border: 1px solid #e4e1d8;
        border-radius: 10px;
        padding: 1.15rem;
        min-height: 510px;
        flex: 1 1 auto;
        min-width: 0;
        overflow: hidden;
      }
      .tw-callout {
        background: #eff4ff;
        border: 1px solid #dbeafe;
        border-left: 4px solid #1d4ed8;
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        font-size: 15.5px;
        line-height: 1.65;
        color: #272b30;
      }
      .tw-callout strong {
        color: #17191c;
      }
      .tw-callout-lead {
        color: #1d4ed8;
        font-weight: 700;
      }
      .tw-note {
        background: #f4f2ed;
        border: 1px solid #e4e1d8;
        border-radius: 8px;
        padding: 1.05rem 1.35rem;
        font-size: 15px;
        line-height: 1.6;
        color: #525866;
      }
      .tw-note strong {
        color: #17191c;
      }
      .tw-btn {
        background: #ffffff;
        border: 1px solid #cfc9bc;
        color: #17191c;
        border-radius: 7px;
        padding: 0.55rem 1.1rem;
        font-size: 15px;
        font-weight: 600;
        cursor: pointer;
        transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
      }
      .tw-btn:hover {
        background: #eff4ff;
        border-color: #1d4ed8;
        color: #1d4ed8;
      }
      .tw-preset-btn {
        background: #ffffff;
        border: 1px solid #cfc9bc;
        color: #272b30;
        border-radius: 9999px;
        padding: 0.5rem 1.05rem;
        font-size: 14.5px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.15s ease;
      }
      .tw-preset-btn:hover {
        border-color: #1d4ed8;
        color: #1d4ed8;
        background: #eff4ff;
      }
      .tw-preset-btn.is-active {
        background: #1d4ed8;
        border-color: #1d4ed8;
        color: #ffffff;
      }
      .tw-toggle-group {
        display: inline-flex;
        flex-wrap: wrap;
        background: #f4f2ed;
        border: 1px solid #cfc9bc;
        border-radius: 8px;
        padding: 4px;
        gap: 4px;
      }
      .tw-toggle-btn {
        padding: 0.48rem 1rem;
        font-size: 14.5px;
        font-weight: 600;
        border-radius: 6px;
        border: none;
        cursor: pointer;
        color: #525866;
        background: transparent;
        transition: all 0.15s ease;
      }
      .tw-toggle-btn:hover {
        color: #17191c;
        background: rgba(23, 25, 28, 0.05);
      }
      .tw-toggle-btn.active-cobalt {
        background: #1d4ed8;
        color: #ffffff;
      }
      .tw-toggle-btn.active-day {
        background: #b45309;
        color: #ffffff;
      }
      .tw-toggle-btn.active-night {
        background: #6d28d9;
        color: #ffffff;
      }
      .tw-toggle-btn.active-emerald {
        background: #047857;
        color: #ffffff;
      }
      .tw-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        border-radius: 9999px;
        padding: 0.22rem 0.72rem;
        font-size: 14.5px;
        font-weight: 700;
        letter-spacing: 0.01em;
        white-space: nowrap;
      }
      .tw-pill-ok {
        background: #ecfdf5;
        color: #047857;
        border: 1px solid #a7f3d0;
      }
      .tw-pill-warn {
        background: #fef8ec;
        color: #b45309;
        border: 1px solid #fde68a;
      }
      .tw-pill-bad {
        background: #fef2f2;
        color: #b91c1c;
        border: 1px solid #fecaca;
      }
      .tw-pill-cobalt {
        background: #eff4ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
      }
      .tw-pill-violet {
        background: #f5f3ff;
        color: #6d28d9;
        border: 1px solid #ddd6fe;
      }
      .tw-banner {
        border-radius: 8px;
        padding: 0.85rem 1.15rem;
        font-size: 15px;
        line-height: 1.5;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.65rem;
      }
      .tw-banner-amber {
        background: #fef8ec;
        border: 1px solid #f5d08a;
        color: #92400e;
      }
      .tw-banner-ok {
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        color: #065f46;
      }
      .tw-banner-neutral {
        background: #f4f2ed;
        border: 1px solid #cfc9bc;
        color: #272b30;
      }
      .tw-ink-primary { color: #17191c; }
      .tw-ink-cobalt { color: #1d4ed8; }
      .tw-ink-amber { color: #b45309; }
      .tw-ink-emerald { color: #047857; }
      .tw-ink-crimson { color: #b91c1c; }
      .tw-ink-violet { color: #6d28d9; }

      @media (max-width: 1120px) {
        .tw-plots-grid {
          grid-template-columns: 1fr;
        }
        .tw-cols-4, .tw-cols-5 {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .tw-mcols-5 {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }
      }
      @media (max-width: 720px) {
        .tw-card {
          padding: 1.5rem 1.25rem;
        }
        .tw-controls-panel {
          padding: 1.25rem;
        }
        .tw-cols-2, .tw-cols-3, .tw-cols-4, .tw-cols-5 {
          grid-template-columns: 1fr;
        }
        .tw-mcols-4, .tw-mcols-5, .tw-mcols-6 {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }
    `;
    document.head.appendChild(style);
  }

  const PLOT_CONFIG = {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"]
  };

  function axisStyle(overrides) {
    return Object.assign(
      {
        gridcolor: GRID_COLOR,
        zerolinecolor: ZERO_COLOR,
        linecolor: AXIS_LINE_COLOR,
        linewidth: 1,
        titlefont: { size: 15, color: INK_PRIMARY },
        tickfont: { size: 14.5, color: INK_SECONDARY },
        automargin: true
      },
      overrides
    );
  }

  function baseLayout(overrides) {
    return Object.assign(
      {
        height: 510,
        paper_bgcolor: "#ffffff",
        plot_bgcolor: "#ffffff",
        font: {
          family: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
          color: INK_PRIMARY,
          size: 15
        },
        margin: { l: 70, r: 35, t: 55, b: 65 },
        hovermode: "closest",
        hoverlabel: {
          bgcolor: "#fdfcfa",
          bordercolor: "#cfc9bc",
          font: { size: 14.5, color: INK_PRIMARY, family: "Inter, sans-serif" }
        },
        legend: {
          orientation: "h",
          x: 0.5,
          xanchor: "center",
          y: -0.22,
          font: { size: 14.5, color: INK_BODY },
          bgcolor: "rgba(255, 255, 255, 0.9)"
        }
      },
      overrides
    );
  }

  function titleStyle(text, yPos) {
    return {
      text: text,
      font: {
        family: "'Source Serif 4', Georgia, serif",
        size: 17,
        color: INK_PRIMARY
      },
      y: yPos !== undefined ? yPos : 0.97
    };
  }

  // =========================================================================
  // WIDGET 1: Atmospheric Column & Elevation-Shift Explorer (#widget-1-thermo)
  // =========================================================================

  // Exact 44-level AGL altitude grid (m) from tempest/profiles/to_heights.py::HEIGHTS
  const HEIGHTS = [
    10, 50, 100, 150, 200, 300, 500, 750, 1000, 1250, 1500, 2000,
    2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000,
    8500, 9000, 9500, 10000, 10500, 11000, 11500, 12000, 12500, 13000, 13500, 14000,
    14500, 15000, 15500, 16000, 16500, 17000, 17500, 18000
  ];
  const HEIGHTS_KM = HEIGHTS.map(function (z) { return z / 1000.0; });

  // Verbatim constants from tempest/profiles/thermo.py & sample.py & weather_calc.py
  const RD = 287.05;
  const RV = 461.5;
  const G0 = 9.80665;
  const R_EARTH = 6371000.0;
  const GAMMA = 1.4;
  const EPS = RD / RV;
  const LAPSE = 0.0065;
  const SHIFT_SCALE = 1500.0;
  const Z_GRID_DEFAULT = 1400.0;

  function esLiquid(t) {
    return 611.21 * Math.exp((17.502 * (t - 273.16)) / (t - 32.19));
  }

  function mixingQ(t, rh, p) {
    const e = (clamp(rh, 0, 100) / 100.0) * esLiquid(t);
    return (EPS * e) / (p - (1.0 - EPS) * e);
  }

  function virtualT(t, q) {
    return t * (1.0 + (RV / RD - 1.0) * q);
  }

  function gravity(zAsl) {
    const ratio = R_EARTH / (R_EARTH + zAsl);
    return G0 * ratio * ratio;
  }

  function dpdFromLnd(lnd) {
    return Math.max(Math.expm1(Math.min(lnd, 5.0)), 0.0);
  }

  function rhFromDpd(t, lnd) {
    const td = t - dpdFromLnd(lnd);
    return clamp((100.0 * esLiquid(td)) / esLiquid(t), 0.0, 100.0);
  }

  function standardPressure(z) {
    return 101325.0 * Math.pow(1.0 - 2.25577e-5 * z, 5.25588);
  }

  function densityAltitudeM(rho) {
    const RD_STD = 287.05287;
    const T0 = 288.15;
    const RHO0 = 1.225;
    const expo = G0 / (RD_STD * LAPSE) - 1.0;
    return (T0 / LAPSE) * (1.0 - Math.pow(rho / RHO0, 1.0 / expo));
  }

  // Exact 2-pass hypsometric column from tempest/profiles/thermo.py::column
  function thermoColumn(zAgl, T, rh, ps, tSfc, rhSfc, zSfc) {
    const n = zAgl.length;
    const zEdges = new Array(n + 1);
    zEdges[0] = 0.0;
    for (let i = 0; i < n; i++) zEdges[i + 1] = zAgl[i];

    const dz = new Array(n);
    const gMid = new Array(n);
    for (let i = 0; i < n; i++) {
      dz[i] = zEdges[i + 1] - zEdges[i];
      gMid[i] = gravity(zSfc + 0.5 * (zEdges[i + 1] + zEdges[i]));
    }

    const tAll = new Array(n + 1);
    const rAll = new Array(n + 1);
    tAll[0] = tSfc;
    rAll[0] = rhSfc;
    for (let i = 0; i < n; i++) {
      tAll[i + 1] = T[i];
      rAll[i + 1] = rh[i];
    }

    let tv = tAll.slice();
    let pAll = new Array(n + 1);
    let qAll = new Array(n + 1);

    for (let pass = 0; pass < 2; pass++) {
      pAll[0] = ps;
      let cumInc = 0.0;
      for (let i = 0; i < n; i++) {
        const tvMean = 0.5 * (tv[i + 1] + tv[i]);
        cumInc += (gMid[i] * dz[i]) / (RD * tvMean);
        pAll[i + 1] = ps * Math.exp(-cumInc);
      }
      for (let i = 0; i <= n; i++) {
        qAll[i] = mixingQ(tAll[i], rAll[i], pAll[i]);
        tv[i] = virtualT(tAll[i], qAll[i]);
      }
    }

    const p = new Array(n);
    const rho = new Array(n);
    const a = new Array(n);
    const q = new Array(n);
    const tvl = new Array(n);
    for (let i = 0; i < n; i++) {
      p[i] = pAll[i + 1];
      q[i] = qAll[i + 1];
      tvl[i] = tv[i + 1];
      rho[i] = p[i] / (RD * tvl[i]);
      a[i] = Math.sqrt(GAMMA * RD * tvl[i]);
    }

    const rhoSfc = pAll[0] / (RD * tv[0]);
    const aSfc = Math.sqrt(GAMMA * RD * tv[0]);
    return { p, rho, a, q, tv: tvl, rhoSfc, aSfc };
  }

  function buildSyntheticColumn(t2m, lnd, jetPeak) {
    const n = HEIGHTS.length;
    const T = new Array(n);
    const rh = new Array(n);
    const u = new Array(n);
    const v = new Array(n);
    const ws = new Array(n);

    const tropZ = 13500.0;
    const tropScale = 1600.0;
    const tTropFloor = Math.max(200.0, t2m - LAPSE * tropZ);
    const rh2m = rhFromDpd(t2m, lnd);

    for (let i = 0; i < n; i++) {
      const z = HEIGHTS[i];
      const zEff = tropZ - tropScale * Math.log(1.0 + Math.exp((tropZ - z) / tropScale));
      const tLapse = t2m - LAPSE * zEff + (z > tropZ ? 0.0008 * (z - tropZ) : 0.0);
      T[i] = Math.max(tLapse, tTropFloor - 4.0);

      const lndZ = clamp(
        lnd - 0.25 * Math.exp(-Math.pow((z - 3500.0) / 2200.0, 2)) + 0.00014 * Math.max(0.0, z - 6000.0),
        0.05,
        4.9
      );
      rh[i] = rhFromDpd(T[i], lndZ);

      const sfcSpeed = 2.6 + 0.11 * jetPeak;
      const pblFactor = Math.log((z + 0.03) / 0.03) / Math.log((10.0 + 0.03) / 0.03);
      const baseWind = sfcSpeed * (1.0 + 0.42 * Math.min(pblFactor - 1.0, 1.35));
      const jetBump = Math.max(0.0, jetPeak - baseWind) * Math.exp(-0.5 * Math.pow((z - 11500.0) / 2700.0, 2));
      const speed = baseWind + jetBump;
      const dirRad = (210.0 + 62.0 * (1.0 - Math.exp(-z / 4000.0))) * (Math.PI / 180.0);
      u[i] = speed * Math.cos(dirRad);
      v[i] = speed * Math.sin(dirRad);
      ws[i] = speed;
    }

    let maxShearMsKm = 0.0;
    for (let i = 0; i < n - 1; i++) {
      const dzKm = (HEIGHTS[i + 1] - HEIGHTS[i]) / 1000.0;
      const du = u[i + 1] - u[i];
      const dv = v[i + 1] - v[i];
      const shear = Math.hypot(du, dv) / dzKm;
      if (shear > maxShearMsKm) maxShearMsKm = shear;
    }

    return { T, rh, t2m, rh2m, ps: standardPressure(Z_GRID_DEFAULT), ws, maxShearMsKm };
  }

  // Exact site elevation shift from tempest/generator/sample.py::to_site
  function applyToSite(gridCol, dz) {
    const n = HEIGHTS.length;
    const t = gridCol.t2m;
    const psSite = gridCol.ps * Math.exp((-G0 * dz) / (RD * (t - (LAPSE * dz) / 2.0)));
    const t2mSite = t - LAPSE * dz;
    const rh2mSite = clamp((gridCol.rh2m * esLiquid(t)) / esLiquid(t2mSite), 0.0, 100.0);

    const TSite = new Array(n);
    const rhSite = new Array(n);
    for (let i = 0; i < n; i++) {
      const w = Math.exp(-HEIGHTS[i] / SHIFT_SCALE);
      TSite[i] = gridCol.T[i] - LAPSE * dz * w;
      rhSite[i] = clamp((gridCol.rh[i] * esLiquid(gridCol.T[i])) / esLiquid(TSite[i]), 0.0, 100.0);
    }
    return { T: TSite, rh: rhSite, t2m: t2mSite, rh2m: rh2mSite, ps: psSite };
  }

  function initWidget1(root) {
    if (!root) return;

    const defaults = { dz: 0, t2m: 298, lnd: 2.5, jet: 28 };
    const presets = {
      spaceport: { dz: 450, t2m: 308, lnd: 3.1, jet: 22 },
      coldfront: { dz: 0, t2m: 278, lnd: 1.4, jet: 48 },
      sealevel: { dz: -500, t2m: 296, lnd: 0.4, jet: 18 }
    };

    root.innerHTML = `
      <div class="tw-card">
        <div class="tw-header">
          <div class="tw-header-text">
            <div class="tw-kicker">Interactive Sandbox 1</div>
            <h4 class="tw-title">Atmospheric Column &amp; Elevation-Shift Explorer</h4>
            <p class="tw-subtitle">44-level AGL 2-pass hypsometric column (<code>thermo.py</code>) with exponential site elevation shift (<code>e<sup>&minus;z/1500</sup></code>).</p>
          </div>
          <div class="tw-header-actions">
            <button type="button" id="w1-reset" class="tw-btn">Reset Defaults</button>
          </div>
        </div>

        <div class="tw-presets-row">
          <span class="tw-presets-label">Presets:</span>
          <button type="button" data-preset="spaceport" class="tw-preset-btn">Spaceport Hot Afternoon (+450m, 308K, lnd 3.1)</button>
          <button type="button" data-preset="coldfront" class="tw-preset-btn">Cold Front Jet (0m, 278K, 48 m/s)</button>
          <button type="button" data-preset="sealevel" class="tw-preset-btn">Humid Sea-Level Pad (&minus;500m, 296K, lnd 0.4)</button>
        </div>

        <div class="tw-controls-panel">
          <div class="tw-controls-grid tw-cols-2">
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Site Elevation Shift &Delta;z</span>
                <span id="w1-dz-val" class="tw-control-val tw-ink-cobalt">0 m</span>
              </div>
              <input id="w1-dz" type="range" min="-600" max="600" step="10" value="${defaults.dz}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Surface Temp T<sub>2m</sub></span>
                <span id="w1-t2m-val" class="tw-control-val tw-ink-cobalt">298.0 K</span>
              </div>
              <input id="w1-t2m" type="range" min="265" max="315" step="0.5" value="${defaults.t2m}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Log Dewpoint Dep. lnd</span>
                <span id="w1-lnd-val" class="tw-control-val tw-ink-cobalt">2.50 &rarr; T&minus;T<sub>d</sub> = 11.2 &deg;C</span>
              </div>
              <input id="w1-lnd" type="range" min="0.0" max="4.0" step="0.05" value="${defaults.lnd}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Jet-Stream Peak Wind</span>
                <span id="w1-jet-val" class="tw-control-val tw-ink-cobalt">28 m/s</span>
              </div>
              <input id="w1-jet" type="range" min="5" max="50" step="1" value="${defaults.jet}" class="tw-slider" />
            </label>
          </div>
        </div>

        <div class="tw-metrics-grid tw-mcols-6">
          <div class="tw-metric">
            <div class="tw-metric-label">Pad Pressure</div>
            <div id="w1-m-p" class="tw-metric-val tw-ink-primary">--</div>
            <div id="w1-d-p" class="tw-metric-sub">&Delta;p: --</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Pad Density &rho;<sub>sfc</sub></div>
            <div id="w1-m-rho" class="tw-metric-val tw-ink-emerald">--</div>
            <div id="w1-d-rho" class="tw-metric-sub">&Delta;&rho;: --</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Density Altitude</div>
            <div id="w1-m-da" class="tw-metric-val tw-ink-crimson">--</div>
            <div id="w1-d-da" class="tw-metric-sub">&Delta;DA: --</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Speed of Sound a<sub>sfc</sub></div>
            <div id="w1-m-a" class="tw-metric-val tw-ink-amber">--</div>
            <div class="tw-metric-sub">Moist &radic;(&gamma;R<sub>d</sub>T<sub>v</sub>)</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Pad RH</div>
            <div id="w1-m-rh" class="tw-metric-val tw-ink-cobalt">--</div>
            <div class="tw-metric-sub">Liquid-water</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Max Wind Shear</div>
            <div id="w1-m-shear" class="tw-metric-val tw-ink-violet">--</div>
            <div class="tw-metric-sub">Vector |dV/dz|</div>
          </div>
        </div>

        <div class="tw-plots-grid">
          <div id="w1-plot-left" class="tw-plot-box"></div>
          <div id="w1-plot-right" class="tw-plot-box"></div>
        </div>

        <div class="tw-callout">
          <span class="tw-callout-lead">Predict &rarr; Test:</span> Before clicking <em>Spaceport Hot Afternoon</em>, predict whether the +450 m pad elevation shift still changes temperature above <strong>4.0 km AGL</strong>, and by how much Density Altitude climbs. Click the preset and check the dashed <code>1.5 km</code> / <code>4.0 km</code> decay lines and signed <code>&Delta;&rho;</code>, <code>&Delta;DA</code>, <code>&Delta;p</code> readouts.
        </div>
      </div>
    `;

    const elDz = root.querySelector("#w1-dz");
    const elT2m = root.querySelector("#w1-t2m");
    const elLnd = root.querySelector("#w1-lnd");
    const elJet = root.querySelector("#w1-jet");
    const presetBtns = Array.from(root.querySelectorAll("[data-preset]"));

    function syncPresetHighlight() {
      const dz = parseFloat(elDz.value);
      const t2m = parseFloat(elT2m.value);
      const lnd = parseFloat(elLnd.value);
      const jet = parseFloat(elJet.value);
      presetBtns.forEach(function (btn) {
        const p = presets[btn.getAttribute("data-preset")];
        const match =
          Math.abs(dz - p.dz) < 1e-6 &&
          Math.abs(t2m - p.t2m) < 1e-6 &&
          Math.abs(lnd - p.lnd) < 1e-6 &&
          Math.abs(jet - p.jet) < 1e-6;
        btn.classList.toggle("is-active", match);
      });
    }

    const refShapes = [
      { type: "line", xref: "paper", x0: 0, x1: 1, y0: 1.5, y1: 1.5, line: { color: "rgba(29, 78, 216, 0.45)", width: 1.5, dash: "dash" } },
      { type: "line", xref: "paper", x0: 0, x1: 1, y0: 4.0, y1: 4.0, line: { color: "rgba(180, 83, 9, 0.50)", width: 1.5, dash: "dash" } },
      { type: "line", xref: "paper", x0: 0, x1: 1, y0: 13.5, y1: 13.5, line: { color: "rgba(109, 40, 217, 0.50)", width: 1.5, dash: "dash" } }
    ];

    const refAnnotations = [
      { xref: "paper", x: 0.99, y: 1.5, xanchor: "right", yanchor: "bottom", text: "1.5 km (1/e shift)", showarrow: false, font: { size: 14.5, color: ACCENT_COBALT }, bgcolor: "rgba(255,255,255,0.88)", borderpad: 2 },
      { xref: "paper", x: 0.99, y: 4.0, xanchor: "right", yanchor: "bottom", text: "4.0 km (fade-out)", showarrow: false, font: { size: 14.5, color: ACCENT_AMBER }, bgcolor: "rgba(255,255,255,0.88)", borderpad: 2 },
      { xref: "paper", x: 0.99, y: 13.5, xanchor: "right", yanchor: "bottom", text: "13.5 km (tropopause)", showarrow: false, font: { size: 14.5, color: ACCENT_VIOLET }, bgcolor: "rgba(255,255,255,0.88)", borderpad: 2 }
    ];

    function update() {
      const dz = parseFloat(elDz.value);
      const t2m = parseFloat(elT2m.value);
      const lnd = parseFloat(elLnd.value);
      const jet = parseFloat(elJet.value);

      const dpdC = dpdFromLnd(lnd);
      root.querySelector("#w1-dz-val").textContent = (dz > 0 ? "+" : "") + dz + " m";
      root.querySelector("#w1-t2m-val").textContent = t2m.toFixed(1) + " K";
      root.querySelector("#w1-lnd-val").textContent = lnd.toFixed(2) + " \u2192 T\u2212Td = " + dpdC.toFixed(1) + " \u00B0C";
      root.querySelector("#w1-jet-val").textContent = jet.toFixed(0) + " m/s";
      syncPresetHighlight();

      const gridCol = buildSyntheticColumn(t2m, lnd, jet);
      const siteCol = applyToSite(gridCol, dz);

      const gridThermo = thermoColumn(HEIGHTS, gridCol.T, gridCol.rh, gridCol.ps, gridCol.t2m, gridCol.rh2m, Z_GRID_DEFAULT);
      const siteThermo = thermoColumn(HEIGHTS, siteCol.T, siteCol.rh, siteCol.ps, siteCol.t2m, siteCol.rh2m, Z_GRID_DEFAULT + dz);

      const daGrid = densityAltitudeM(gridThermo.rhoSfc);
      const daSite = densityAltitudeM(siteThermo.rhoSfc);
      const dpHpa = (siteCol.ps - gridCol.ps) / 100.0;
      const dRho = siteThermo.rhoSfc - gridThermo.rhoSfc;
      const dDa = daSite - daGrid;

      root.querySelector("#w1-m-p").textContent = (siteCol.ps / 100.0).toFixed(1) + " hPa";
      root.querySelector("#w1-d-p").textContent = "\u0394p: " + formatSigned(dpHpa, 1, " hPa vs grid");

      root.querySelector("#w1-m-rho").textContent = siteThermo.rhoSfc.toFixed(4) + " kg/m\u00B3";
      root.querySelector("#w1-d-rho").textContent = "\u0394\u03C1: " + formatSigned(dRho, 4, " kg/m\u00B3");

      root.querySelector("#w1-m-da").textContent = Math.round(daSite).toLocaleString() + " m";
      root.querySelector("#w1-d-da").textContent = "\u0394DA: " + formatSigned(Math.round(dDa), 0, " m vs grid");

      root.querySelector("#w1-m-a").textContent = siteThermo.aSfc.toFixed(1) + " m/s";
      root.querySelector("#w1-m-rh").textContent = siteCol.rh2m.toFixed(1) + "%";
      root.querySelector("#w1-m-shear").textContent = gridCol.maxShearMsKm.toFixed(1) + " m/s/km";

      if (typeof Plotly === "undefined") return;

      const leftTraces = [
        {
          x: gridCol.T,
          y: HEIGHTS_KM,
          name: "T Grid (K)",
          mode: "lines",
          line: { color: "#d97706", width: 2.2, dash: "dot" },
          xaxis: "x",
          hovertemplate: "T_grid: %{x:.1f} K<extra></extra>"
        },
        {
          x: siteCol.T,
          y: HEIGHTS_KM,
          name: "T Site (K)",
          mode: "lines",
          line: { color: ACCENT_AMBER, width: 3.0 },
          xaxis: "x",
          hovertemplate: "T_site: %{x:.1f} K<extra></extra>"
        },
        {
          x: gridCol.rh,
          y: HEIGHTS_KM,
          name: "RH Grid (%)",
          mode: "lines",
          line: { color: "#3b82f6", width: 2.0, dash: "dot" },
          xaxis: "x2",
          hovertemplate: "RH_grid: %{x:.1f}%<extra></extra>"
        },
        {
          x: siteCol.rh,
          y: HEIGHTS_KM,
          name: "RH Site (%)",
          mode: "lines",
          line: { color: ACCENT_COBALT, width: 2.8 },
          xaxis: "x2",
          hovertemplate: "RH_site: %{x:.1f}%<extra></extra>"
        }
      ];

      const leftLayout = baseLayout({
        height: 525,
        title: titleStyle("Temperature & Relative Humidity (44 AGL Levels)", 0.985),
        margin: { l: 70, r: 35, t: 92, b: 68 },
        hovermode: "y unified",
        yaxis: axisStyle({ title: "Altitude (km AGL)", range: [0, 18.2] }),
        xaxis: axisStyle({ title: "Temperature (K)", range: [195, 325], titlefont: { size: 15, color: ACCENT_AMBER }, tickfont: { size: 14.5, color: ACCENT_AMBER } }),
        xaxis2: axisStyle({ title: "Relative Humidity (%)", overlaying: "x", side: "top", range: [0, 105], showgrid: false, titlefont: { size: 15, color: ACCENT_COBALT }, tickfont: { size: 14.5, color: ACCENT_COBALT } }),
        shapes: refShapes,
        annotations: refAnnotations
      });

      const rightTraces = [
        {
          x: gridThermo.rho,
          y: HEIGHTS_KM,
          name: "\u03C1 Grid (kg/m\u00B3)",
          mode: "lines",
          line: { color: "#10b981", width: 2.2, dash: "dot" },
          xaxis: "x",
          hovertemplate: "\u03C1_grid: %{x:.4f} kg/m\u00B3<extra></extra>"
        },
        {
          x: siteThermo.rho,
          y: HEIGHTS_KM,
          name: "\u03C1 Site (kg/m\u00B3)",
          mode: "lines",
          line: { color: ACCENT_EMERALD, width: 3.0 },
          xaxis: "x",
          hovertemplate: "\u03C1_site: %{x:.4f} kg/m\u00B3<extra></extra>"
        },
        {
          x: gridCol.ws,
          y: HEIGHTS_KM,
          name: "Wind Speed (m/s)",
          mode: "lines",
          line: { color: ACCENT_VIOLET, width: 2.8 },
          xaxis: "x2",
          hovertemplate: "Wind: %{x:.1f} m/s<extra></extra>"
        }
      ];

      const rightLayout = baseLayout({
        height: 525,
        title: titleStyle("Hypsometric Air Density & Wind Profile", 0.985),
        margin: { l: 70, r: 35, t: 92, b: 68 },
        hovermode: "y unified",
        yaxis: axisStyle({ title: "Altitude (km AGL)", range: [0, 18.2] }),
        xaxis: axisStyle({ title: "Air Density (kg/m\u00B3)", range: [0, 1.35], titlefont: { size: 15, color: ACCENT_EMERALD }, tickfont: { size: 14.5, color: ACCENT_EMERALD } }),
        xaxis2: axisStyle({ title: "Wind Speed (m/s)", overlaying: "x", side: "top", range: [0, 56], showgrid: false, titlefont: { size: 15, color: ACCENT_VIOLET }, tickfont: { size: 14.5, color: ACCENT_VIOLET } }),
        shapes: refShapes,
        annotations: refAnnotations
      });

      Plotly.react(root.querySelector("#w1-plot-left"), leftTraces, leftLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w1-plot-right"), rightTraces, rightLayout, PLOT_CONFIG);
    }

    [elDz, elT2m, elLnd, elJet].forEach(function (el) {
      el.addEventListener("input", update);
    });

    presetBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        const p = presets[btn.getAttribute("data-preset")];
        elDz.value = p.dz;
        elT2m.value = p.t2m;
        elLnd.value = p.lnd;
        elJet.value = p.jet;
        update();
      });
    });

    root.querySelector("#w1-reset").addEventListener("click", function () {
      elDz.value = defaults.dz;
      elT2m.value = defaults.t2m;
      elLnd.value = defaults.lnd;
      elJet.value = defaults.jet;
      update();
    });

    update();
  }

  // =========================================================================
  // WIDGET 2: Almost-Fair CRPS & Spread-Calibration Sandbox (#widget-2-crps)
  // =========================================================================

  const W2_N = 400;
  const W2_M_MAX = 32;
  const W2_DATA = (function () {
    const rng = makeRng(20260401);
    const truth = new Float64Array(W2_N);
    const pitJitter = new Float64Array(W2_N);
    const rawZ = new Array(W2_N);

    for (let b = 0; b < W2_N; b++) {
      const isTail = rng() < 0.08;
      truth[b] = boxMuller(rng) * (isTail ? 1.80 : 0.90);
      pitJitter[b] = rng();
      const row = new Float64Array(W2_M_MAX);
      for (let i = 0; i < W2_M_MAX; i++) {
        row[i] = boxMuller(rng);
      }
      rawZ[b] = row;
    }
    return { truth, pitJitter, rawZ };
  })();

  // Exact verbatim afcrps decomposition from tempest/generator/model.py::afcrps
  function afcrpsDecompCase(samples, y, alpha) {
    const m = samples.length;
    const eps = (1.0 - alpha) / m;
    let fitSum = 0.0;
    for (let i = 0; i < m; i++) {
      fitSum += Math.abs(samples[i] - y);
    }
    const fit = fitSum / m;

    let spreadSum = 0.0;
    for (let i = 0; i < m; i++) {
      for (let j = 0; j < m; j++) {
        spreadSum += Math.abs(samples[i] - samples[j]);
      }
    }
    const denom = 2.0 * m * (m - 1);
    const fairBonus = spreadSum / denom;
    const afBonus = (1.0 - eps) * fairBonus;
    return {
      fit: fit,
      afBonus: afBonus,
      fairBonus: fairBonus,
      af: fit - afBonus,
      fair: fit - fairBonus
    };
  }

  // Exact verbatim crps_fair from tempest/scoring/score.py::crps_fair
  function crpsFairCase(sortedSamples, y) {
    const m = sortedSamples.length;
    let fitSum = 0.0;
    let spreadTerm = 0.0;
    for (let i = 0; i < m; i++) {
      fitSum += Math.abs(sortedSamples[i] - y);
      spreadTerm += (2 * (i + 1) - m - 1) * sortedSamples[i];
    }
    return fitSum / m - spreadTerm / Math.max(m * (m - 1), 1);
  }

  function covK(m, p) {
    return Math.max(1, Math.round(((1.0 - p) / 2.0) * (m + 1)));
  }

  function applyTailcalCase(sortedRaw, fStretch) {
    const m = sortedRaw.length;
    const k90 = covK(m, 0.90);
    const q05 = k90 >= 2 ? sortedRaw[k90 - 1] : quantileSorted(sortedRaw, 0.05);
    const q95 = k90 >= 2 ? sortedRaw[m - k90] : quantileSorted(sortedRaw, 0.95);
    const out = new Array(m);
    for (let i = 0; i < m; i++) {
      const x = sortedRaw[i];
      if (x < q05) {
        out[i] = q05 - fStretch * (q05 - x);
      } else if (x > q95) {
        out[i] = q95 + fStretch * (x - q95);
      } else {
        out[i] = x;
      }
    }
    return { cal: out, q05: q05, q95: q95 };
  }

  function statusPillHtml(status) {
    if (status === "ok") return '<span class="tw-pill tw-pill-ok">On Target</span>';
    if (status === "under") return '<span class="tw-pill tw-pill-bad">Under-dispersed</span>';
    return '<span class="tw-pill tw-pill-warn">Over-dispersed</span>';
  }

  function initWidget2(root) {
    if (!root) return;

    const defaults = { m: 20, alpha: 0.95, spread: 0.85, f: 1.25 };
    const presets = {
      under: { m: 24, alpha: 0.95, spread: 0.55, f: 1.00 },
      repaired: { m: 24, alpha: 0.95, spread: 1.00, f: 1.60 },
      smallm: { m: 4, alpha: 0.80, spread: 1.00, f: 1.00 }
    };

    root.innerHTML = `
      <div class="tw-card">
        <div class="tw-header">
          <div class="tw-header-text">
            <div class="tw-kicker">Interactive Sandbox 2</div>
            <h4 class="tw-title">Almost-Fair CRPS &amp; Spread-Calibration Sandbox</h4>
            <p class="tw-subtitle">Live <code>afcrps(&alpha;)</code> fit-vs-spread decomposition, <code>q05/q95</code> outer-tail hinges, and PIT rank uniformity across 400 synthetic cases.</p>
          </div>
          <div class="tw-header-actions">
            <button type="button" id="w2-reset" class="tw-btn">Reset Defaults</button>
          </div>
        </div>

        <div class="tw-presets-row">
          <span class="tw-presets-label">Presets:</span>
          <button type="button" data-preset="under" class="tw-preset-btn">Under-Dispersed (m=24, 0.55&times;)</button>
          <button type="button" data-preset="repaired" class="tw-preset-btn">Heavy-Tail Repaired (m=24, 1.0&times;, f=1.6&times;)</button>
          <button type="button" data-preset="smallm" class="tw-preset-btn">Small-Ensemble Bias (m=4, &alpha;=0.80)</button>
        </div>

        <div class="tw-controls-panel">
          <div class="tw-controls-grid tw-cols-2">
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Ensemble Size m</span>
                <span id="w2-m-val" class="tw-control-val tw-ink-cobalt">20</span>
              </div>
              <input id="w2-m" type="range" min="4" max="32" step="1" value="${defaults.m}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Fairness &alpha;</span>
                <span id="w2-alpha-val" class="tw-control-val tw-ink-cobalt">0.95</span>
              </div>
              <input id="w2-alpha" type="range" min="0.80" max="1.00" step="0.01" value="${defaults.alpha}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Raw Spread Multiplier</span>
                <span id="w2-spread-val" class="tw-control-val tw-ink-cobalt">0.85&times;</span>
              </div>
              <input id="w2-spread" type="range" min="0.40" max="2.00" step="0.05" value="${defaults.spread}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Far-Tail Stretch f</span>
                <span id="w2-f-val" class="tw-control-val tw-ink-cobalt">1.25&times;</span>
              </div>
              <input id="w2-f" type="range" min="0.80" max="2.50" step="0.05" value="${defaults.f}" class="tw-slider" />
            </label>
          </div>
        </div>

        <div class="tw-metrics-grid tw-mcols-5">
          <div class="tw-metric">
            <div class="tw-metric-label">afCRPS (&alpha;)</div>
            <div id="w2-m-afcrps" class="tw-metric-val tw-ink-cobalt">--</div>
            <div id="w2-m-gap" class="tw-metric-sub">&alpha;-penalty: --</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">CRPS<sub>fair</sub> (&alpha;=1)</div>
            <div id="w2-m-fair" class="tw-metric-val tw-ink-emerald">--</div>
            <div class="tw-metric-sub">Unbiased score</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-head">
              <span class="tw-metric-label">90% Cov</span>
              <span id="w2-p-cov90"></span>
            </div>
            <div id="w2-m-cov90" class="tw-metric-val tw-ink-amber">--</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-head">
              <span class="tw-metric-label">99% Cov</span>
              <span id="w2-p-cov99"></span>
            </div>
            <div id="w2-m-cov99" class="tw-metric-val tw-ink-crimson">--</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-head">
              <span class="tw-metric-label">Spread-Skill</span>
              <span id="w2-p-ssr"></span>
            </div>
            <div id="w2-m-ssr" class="tw-metric-val tw-ink-violet">--</div>
          </div>
        </div>

        <div class="tw-decomp-card">
          <div class="tw-decomp-top">
            <span>Live afCRPS Decomposition: <span class="tw-ink-crimson">Fit Penalty</span> &minus; <span class="tw-ink-cobalt">Spread Bonus (&alpha;)</span> = <span class="tw-ink-emerald">Net afCRPS</span></span>
            <span id="w2-decomp-txt" class="tw-decomp-mono">--</span>
          </div>
          <div class="tw-decomp-track">
            <div id="w2-bar-net" class="tw-decomp-seg" style="background:#047857;width:55%"></div>
            <div id="w2-bar-bonus" class="tw-decomp-seg" style="background:#1d4ed8;width:42%"></div>
            <div id="w2-bar-pen" class="tw-decomp-seg" style="background:#b45309;width:3%"></div>
          </div>
          <div class="tw-decomp-legend">
            <span><span class="tw-swatch" style="background:#047857"></span>Net afCRPS</span>
            <span><span class="tw-swatch" style="background:#1d4ed8"></span>Active Spread Bonus (1&minus;&epsilon;)</span>
            <span><span class="tw-swatch" style="background:#b45309"></span>&alpha;-Shrinkage withheld (&epsilon; = (1&minus;&alpha;)/m)</span>
          </div>
        </div>

        <div class="tw-plots-grid">
          <div id="w2-plot-left" class="tw-plot-box"></div>
          <div id="w2-plot-right" class="tw-plot-box"></div>
        </div>

        <div class="tw-note">
          <strong>Production note:</strong> Outer-tail stretch (<code>tailcal.py</code>) was killed in <code>UR1/X2</code> after ablations showed no net gain on held-out sondes; production Tempest-ARKNET calibrates both core and tail quantiles via the 109-knot <code>spread.py</code> map.
        </div>

        <div class="tw-callout">
          <span class="tw-callout-lead">Predict &rarr; Test:</span> Click <em>Small-Ensemble Bias (m=4, &alpha;=0.80)</em>, then drag <em>Fairness &alpha;</em> from <code>0.80</code> to <code>1.00</code> and watch the amber <code>&alpha;-Shrinkage</code> segment vanish from the decomposition bar as <code>afCRPS</code> converges to <code>CRPS<sub>fair</sub></code>. Next, switch to <em>Heavy-Tail Repaired</em> and verify that raising <em>f</em> lifts <code>99% Cov</code> without shifting the <code>q05/q95</code> hinges.
        </div>
      </div>
    `;

    const elM = root.querySelector("#w2-m");
    const elAlpha = root.querySelector("#w2-alpha");
    const elSpread = root.querySelector("#w2-spread");
    const elF = root.querySelector("#w2-f");
    const presetBtns = Array.from(root.querySelectorAll("[data-preset]"));

    function syncPresetHighlight() {
      const m = parseInt(elM.value, 10);
      const alpha = parseFloat(elAlpha.value);
      const spread = parseFloat(elSpread.value);
      const f = parseFloat(elF.value);
      presetBtns.forEach(function (btn) {
        const p = presets[btn.getAttribute("data-preset")];
        const match =
          m === p.m &&
          Math.abs(alpha - p.alpha) < 1e-6 &&
          Math.abs(spread - p.spread) < 1e-6 &&
          Math.abs(f - p.f) < 1e-6;
        btn.classList.toggle("is-active", match);
      });
    }

    function update() {
      const m = parseInt(elM.value, 10);
      const alpha = parseFloat(elAlpha.value);
      const spreadMult = parseFloat(elSpread.value);
      const fStretch = parseFloat(elF.value);

      root.querySelector("#w2-m-val").textContent = String(m);
      root.querySelector("#w2-alpha-val").textContent = alpha.toFixed(2);
      root.querySelector("#w2-spread-val").textContent = spreadMult.toFixed(2) + "\u00D7";
      root.querySelector("#w2-f-val").textContent = fStretch.toFixed(2) + "\u00D7";
      syncPresetHighlight();

      const k99 = covK(m, 0.99);

      let sumAf = 0.0;
      let sumFair = 0.0;
      let sumFit = 0.0;
      let sumAfBonus = 0.0;
      let sumFairBonus = 0.0;
      let sumQ05 = 0.0;
      let sumQ95 = 0.0;
      let hit90 = 0;
      let hit99 = 0;
      let sumVar = 0.0;
      let sumSqErr = 0.0;

      const pitCounts = new Array(10).fill(0);
      const rawPool = new Array(W2_N * m);
      const calPool = new Array(W2_N * m);
      let poolIdx = 0;

      for (let b = 0; b < W2_N; b++) {
        const y = W2_DATA.truth[b];
        const rowZ = W2_DATA.rawZ[b];

        const rawSorted = new Array(m);
        for (let i = 0; i < m; i++) {
          const val = rowZ[i] * spreadMult;
          rawSorted[i] = val;
          rawPool[poolIdx + i] = val;
        }
        rawSorted.sort(function (a, c) { return a - c; });

        const tc = applyTailcalCase(rawSorted, fStretch);
        const calSorted = tc.cal;
        sumQ05 += tc.q05;
        sumQ95 += tc.q95;
        for (let i = 0; i < m; i++) {
          calPool[poolIdx + i] = calSorted[i];
        }
        poolIdx += m;

        const dec = afcrpsDecompCase(calSorted, y, alpha);
        sumAf += dec.af;
        sumFit += dec.fit;
        sumAfBonus += dec.afBonus;
        sumFairBonus += dec.fairBonus;
        sumFair += crpsFairCase(calSorted, y);

        // 90% coverage uses the exact q05/q95 hinge so fStretch strictly isolates the outer tail
        if (y >= tc.q05 && y <= tc.q95) hit90++;
        if (y >= calSorted[k99 - 1] && y <= calSorted[m - k99]) hit99++;

        let mean = 0.0;
        for (let i = 0; i < m; i++) mean += calSorted[i];
        mean /= m;
        let vSum = 0.0;
        for (let i = 0; i < m; i++) {
          const d = calSorted[i] - mean;
          vSum += d * d;
        }
        sumVar += vSum / Math.max(m - 1, 1);
        sumSqErr += (mean - y) * (mean - y);

        let rank = 0;
        for (let i = 0; i < m; i++) {
          if (calSorted[i] < y) rank++;
        }
        const pit = (rank + W2_DATA.pitJitter[b]) / (m + 1);
        const bin = Math.min(9, Math.floor(pit * 10));
        pitCounts[bin]++;
      }

      const afMean = sumAf / W2_N;
      const fairMean = sumFair / W2_N;
      const fitMean = sumFit / W2_N;
      const afBonusMean = sumAfBonus / W2_N;
      const alphaPen = (sumFairBonus - sumAfBonus) / W2_N;
      const meanQ05 = sumQ05 / W2_N;
      const meanQ95 = sumQ95 / W2_N;
      const cov90Pct = (100.0 * hit90) / W2_N;
      const cov99Pct = (100.0 * hit99) / W2_N;
      const ssr = Math.sqrt(sumVar / W2_N) / Math.max(Math.sqrt(sumSqErr / W2_N), 1e-9);

      root.querySelector("#w2-m-afcrps").textContent = afMean.toFixed(4);
      root.querySelector("#w2-m-gap").textContent = "\u03B1-penalty: +" + alphaPen.toFixed(4);
      root.querySelector("#w2-m-fair").textContent = fairMean.toFixed(4);
      root.querySelector("#w2-m-cov90").textContent = cov90Pct.toFixed(1) + "%";
      root.querySelector("#w2-m-cov99").textContent = cov99Pct.toFixed(1) + "%";
      root.querySelector("#w2-m-ssr").textContent = ssr.toFixed(2);

      root.querySelector("#w2-p-cov90").innerHTML = statusPillHtml(
        cov90Pct < 86.0 ? "under" : cov90Pct > 94.0 ? "over" : "ok"
      );
      root.querySelector("#w2-p-cov99").innerHTML = statusPillHtml(
        cov99Pct < 96.5 ? "under" : cov90Pct > 95.5 ? "over" : "ok"
      );
      root.querySelector("#w2-p-ssr").innerHTML = statusPillHtml(
        ssr < 0.90 ? "under" : ssr > 1.12 ? "over" : "ok"
      );

      // Update live Fit-Penalty vs Spread-Bonus decomposition bar
      const totalBar = Math.max(fitMean, 1e-6);
      const pctNet = clamp((afMean / totalBar) * 100.0, 0, 100);
      const pctBonus = clamp((afBonusMean / totalBar) * 100.0, 0, 100 - pctNet);
      const pctPen = clamp((alphaPen / totalBar) * 100.0, 0, 100);
      root.querySelector("#w2-bar-net").style.width = pctNet.toFixed(1) + "%";
      root.querySelector("#w2-bar-bonus").style.width = pctBonus.toFixed(1) + "%";
      root.querySelector("#w2-bar-pen").style.width = Math.max(pctPen, alphaPen > 0.0005 ? 1.2 : 0).toFixed(1) + "%";
      root.querySelector("#w2-decomp-txt").textContent =
        "Fit " + fitMean.toFixed(3) + " \u2212 Bonus " + afBonusMean.toFixed(3) + " = " + afMean.toFixed(3);

      if (typeof Plotly === "undefined") return;

      const histTraces = [
        {
          x: rawPool,
          name: "Raw Ensemble",
          type: "histogram",
          histnorm: "probability density",
          xbins: { start: -5.0, end: 5.0, size: 0.25 },
          marker: { color: "rgba(185, 28, 28, 0.24)", line: { color: ACCENT_CRIMSON, width: 1.2 } }
        },
        {
          x: calPool,
          name: "Tail-Calibrated",
          type: "histogram",
          histnorm: "probability density",
          xbins: { start: -5.0, end: 5.0, size: 0.25 },
          marker: { color: "rgba(29, 78, 216, 0.30)", line: { color: ACCENT_COBALT, width: 1.2 } }
        },
        {
          x: Array.from(W2_DATA.truth),
          name: "Truth (N=400)",
          type: "histogram",
          histnorm: "probability density",
          xbins: { start: -5.0, end: 5.0, size: 0.25 },
          marker: { color: "rgba(4, 120, 87, 0.24)", line: { color: ACCENT_EMERALD, width: 1.6 } }
        }
      ];

      const histLayout = baseLayout({
        height: 500,
        title: titleStyle("Standardized Anomaly Distribution & q05/q95 Hinges"),
        barmode: "overlay",
        xaxis: axisStyle({ title: "Standardized Anomaly (\u03C3)", range: [-4.5, 4.5] }),
        yaxis: axisStyle({ title: "Probability Density" }),
        shapes: [
          { type: "line", yref: "paper", x0: meanQ05, x1: meanQ05, y0: 0, y1: 1, line: { color: ACCENT_AMBER, width: 2.0, dash: "dash" } },
          { type: "line", yref: "paper", x0: meanQ95, x1: meanQ95, y0: 0, y1: 1, line: { color: ACCENT_AMBER, width: 2.0, dash: "dash" } }
        ],
        annotations: [
          { x: meanQ05, y: 0.97, yref: "paper", xanchor: "right", text: "q05 (" + meanQ05.toFixed(2) + "\u03C3)", showarrow: false, font: { size: 14.5, color: ACCENT_AMBER }, bgcolor: "rgba(255,255,255,0.88)", borderpad: 2, xshift: -6 },
          { x: meanQ95, y: 0.97, yref: "paper", xanchor: "left", text: "q95 (+" + meanQ95.toFixed(2) + "\u03C3)", showarrow: false, font: { size: 14.5, color: ACCENT_AMBER }, bgcolor: "rgba(255,255,255,0.88)", borderpad: 2, xshift: 6 }
        ]
      });

      const pitBins = ["0.05", "0.15", "0.25", "0.35", "0.45", "0.55", "0.65", "0.75", "0.85", "0.95"];
      const pitFracs = pitCounts.map(function (c) { return c / W2_N; });
      const pitMax = Math.max(0.24, Math.max.apply(null, pitFracs) * 1.18);

      const pitTraces = [
        {
          x: pitBins,
          y: pitFracs,
          name: "Calibrated PIT",
          type: "bar",
          marker: {
            color: pitFracs.map(function (v) {
              return Math.abs(v - 0.10) > 0.04 ? "rgba(180, 83, 9, 0.78)" : "rgba(29, 78, 216, 0.78)";
            }),
            line: { color: "#ffffff", width: 1.5 }
          },
          hovertemplate: "PIT bin %{x}<br>Share=%{y:.3f}<extra></extra>"
        },
        {
          x: [pitBins[0], pitBins[9]],
          y: [0.10, 0.10],
          name: "Uniform Target (0.10)",
          mode: "lines",
          line: { color: ACCENT_EMERALD, width: 2.6, dash: "dash" }
        }
      ];

      const pitLayout = baseLayout({
        height: 500,
        title: titleStyle("PIT Histogram (Flat = Calibrated, U-Shape = Under-Dispersed)"),
        xaxis: axisStyle({ title: "PIT Rank Bin Center" }),
        yaxis: axisStyle({ title: "Relative Frequency", range: [0, pitMax] })
      });

      Plotly.react(root.querySelector("#w2-plot-left"), histTraces, histLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w2-plot-right"), pitTraces, pitLayout, PLOT_CONFIG);
    }

    [elM, elAlpha, elSpread, elF].forEach(function (el) {
      el.addEventListener("input", update);
    });

    presetBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        const p = presets[btn.getAttribute("data-preset")];
        elM.value = p.m;
        elAlpha.value = p.alpha;
        elSpread.value = p.spread;
        elF.value = p.f;
        update();
      });
    });

    root.querySelector("#w2-reset").addEventListener("click", function () {
      elM.value = defaults.m;
      elAlpha.value = defaults.alpha;
      elSpread.value = defaults.spread;
      elF.value = defaults.f;
      update();
    });

    update();
  }

  // =========================================================================
  // WIDGET 3: Lead-Time Router & Launch-Day Obs Assimilation (#widget-3-router)
  // =========================================================================

  const ROUTER_DEFAULTS = {
    p_days: -6.0,
    p0_days: 0.0,
    f_days: 7.0,
    f2_days: 15.0,
    m_days: 46.0,
    ens_blend: [10.0, 15.0],
    m_blend: [35.0, 46.0]
  };

  function routerRamp(x, a, b) {
    const t = clamp((x - a) / (b - a), 0.0, 1.0);
    return 0.5 - 0.5 * Math.cos(Math.PI * t);
  }

  function routerMode(lead) {
    if (lead <= ROUTER_DEFAULTS.p_days) return "P";
    if (lead <= ROUTER_DEFAULTS.p0_days) return "P0";
    if (lead <= ROUTER_DEFAULTS.f_days) return "F";
    if (lead <= ROUTER_DEFAULTS.f2_days) return "F2";
    if (lead <= ROUTER_DEFAULTS.m_days) return "M";
    return "C";
  }

  const MODE_LABELS = {
    P: "P (Past ERA5)",
    P0: "P0 (Recent Past)",
    F: "F (Forecast 0\u20137d)",
    F2: "F2 (Ens Blend 7\u201315d)",
    M: "M (Sub-Seasonal 15\u201346d)",
    C: "C (Climate >46d)"
  };

  function routerClimateWeight(lead) {
    return lead > ROUTER_DEFAULTS.f2_days
      ? routerRamp(lead, ROUTER_DEFAULTS.m_blend[0], ROUTER_DEFAULTS.m_blend[1])
      : 0.0;
  }

  const OWN_STATION_KM = 5.0;
  const TAU_H = 6.3;
  const REP_TABLE = {
    day: [[0.0, 0.66], [50.0, 0.62], [150.0, 0.46], [275.0, 0.36], [500.0, 0.32]],
    night: [[0.0, 0.52], [50.0, 0.48], [150.0, 0.31], [275.0, 0.20], [500.0, 0.18]]
  };
  const REP_DZ = { day: 1317.0, night: 919.0 };
  const AGE_TABLE = {
    day: [[0, 1.0], [1, 1.0], [2, 1.0], [3, 0.97], [6, 0.81]],
    night: [[0, 1.0], [1, 0.98], [2, 0.92], [3, 0.83], [6, 0.60]]
  };
  const TAU_X = { day: 27.0, night: 12.0 };

  function obsPersistenceGain(ageHours) {
    return Math.exp(-Math.max(ageHours, 0.0) / TAU_H);
  }

  function obsRepresentativenessGain(distKm, dzM, regime) {
    const g = interp1d(Math.max(distKm, 0.0), REP_TABLE[regime]);
    return g * Math.exp(-Math.abs(dzM) / REP_DZ[regime]);
  }

  function obsCrossAgeFactor(ageHours, regime) {
    const a = Math.max(ageHours, 0.0);
    const tbl = AGE_TABLE[regime];
    if (a <= 6.0) return interp1d(a, tbl);
    return tbl[tbl.length - 1][1] * Math.exp(-(a - 6.0) / TAU_X[regime]);
  }

  function obsEffectiveGain(ageHours, distKm, dzM, regime) {
    if (distKm < OWN_STATION_KM) {
      return Math.max(obsPersistenceGain(ageHours), 0.02);
    }
    return Math.max(obsRepresentativenessGain(distKm, dzM, regime) * obsCrossAgeFactor(ageHours, regime), 0.02);
  }

  function obsSigmaRatio(gain) {
    const g = clamp(gain, 0.02, 1.0);
    return Math.max(Math.sqrt(1.0 / g - 1.0), 1e-3);
  }

  function initWidget3(root) {
    if (!root) return;

    const defaults = { lead: 0.5, age: 1.5, dist: 25, dz: 150, xObs: 10.5, regime: "day" };
    let regime = defaults.regime;

    const leadGrid = [];
    const wP = [], wP0 = [], wF = [], wF2 = [], wM = [], wC = [];
    for (let x = -15; x <= 60.001; x += 0.5) {
      const ld = Math.round(x * 10) / 10;
      leadGrid.push(ld);
      const rEns = routerRamp(ld, ROUTER_DEFAULTS.ens_blend[0], ROUTER_DEFAULTS.ens_blend[1]);
      const rClim = routerRamp(ld, ROUTER_DEFAULTS.m_blend[0], ROUTER_DEFAULTS.m_blend[1]);

      wP.push(ld <= -6.0 ? 1.0 : 0.0);
      wP0.push(ld > -6.0 && ld <= 0.0 ? 1.0 : 0.0);
      wF.push(ld > 0.0 && ld <= 7.0 ? 1.0 : 0.0);
      wF2.push(ld > 7.0 && ld <= 15.0 ? 1.0 - rEns : 0.0);
      wM.push(ld > 7.0 && ld <= 15.0 ? rEns : ld > 15.0 && ld <= 46.0 ? 1.0 - rClim : 0.0);
      wC.push(ld > 15.0 ? rClim : 0.0);
    }

    root.innerHTML = `
      <div class="tw-card">
        <div class="tw-header">
          <div class="tw-header-text">
            <div class="tw-kicker">Interactive Sandbox 3</div>
            <h4 class="tw-title">Lead-Time Router &amp; Launch-Day Observation Assimilation</h4>
            <p class="tw-subtitle">Cosine mode blending (<code>router.py</code>) paired with soft Gaussian-copula observation gain (<code>obs.py</code>).</p>
          </div>
          <div class="tw-header-actions">
            <div class="tw-toggle-group" role="group" aria-label="Diurnal Regime">
              <button type="button" id="w3-btn-day" class="tw-toggle-btn active-day">Day</button>
              <button type="button" id="w3-btn-night" class="tw-toggle-btn">Night</button>
            </div>
            <button type="button" id="w3-reset" class="tw-btn">Reset Defaults</button>
          </div>
        </div>

        <div class="tw-regime-row">
          <div class="tw-regime-info">
            <span>Active Assimilation Formula (5 km threshold):</span>
            <span id="w3-regime-badge" class="tw-pill tw-pill-violet">Off-Site Representativeness &times; Cross-Age</span>
          </div>
        </div>

        <div class="tw-controls-panel">
          <div class="tw-controls-grid tw-cols-5">
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Forecast Lead Time</span>
                <span id="w3-lead-val" class="tw-control-val tw-ink-cobalt">+0.5 d</span>
              </div>
              <input id="w3-lead" type="range" min="-15" max="60" step="0.5" value="${defaults.lead}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Observation Age &Delta;t</span>
                <span id="w3-age-val" class="tw-control-val tw-ink-cobalt">1.5 h</span>
              </div>
              <input id="w3-age" type="range" min="0" max="24" step="0.5" value="${defaults.age}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Station Distance d</span>
                <span id="w3-dist-val" class="tw-control-val tw-ink-cobalt">25 km</span>
              </div>
              <input id="w3-dist" type="range" min="0" max="100" step="1" value="${defaults.dist}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Elevation Diff |&Delta;z|</span>
                <span id="w3-dz-val" class="tw-control-val tw-ink-cobalt">150 m</span>
              </div>
              <input id="w3-dz" type="range" min="0" max="1500" step="25" value="${defaults.dz}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Observed Wind x<sub>obs</sub></span>
                <span id="w3-xobs-val" class="tw-control-val tw-ink-amber">10.5 m/s</span>
              </div>
              <input id="w3-xobs" type="range" min="2" max="20" step="0.5" value="${defaults.xObs}" class="tw-slider" />
            </label>
          </div>
        </div>

        <div class="tw-metrics-grid tw-mcols-5">
          <div class="tw-metric">
            <div class="tw-metric-label">Active Mode</div>
            <div id="w3-m-mode" class="tw-metric-val tw-ink-cobalt">--</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Climate Weight</div>
            <div id="w3-m-clim" class="tw-metric-val tw-ink-amber">--</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Effective Obs Gain r</div>
            <div id="w3-m-gain" class="tw-metric-val tw-ink-emerald">--</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">&sigma;<sub>obs</sub> / &sigma;<sub>prior</sub></div>
            <div id="w3-m-sig" class="tw-metric-val tw-ink-violet">--</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Uncertainty Reduction</div>
            <div id="w3-m-red" class="tw-metric-val tw-ink-crimson">--</div>
          </div>
        </div>

        <div class="tw-plots-grid">
          <div id="w3-plot-left" class="tw-plot-box"></div>
          <div class="tw-plot-col">
            <div id="w3-right-banner" class="tw-banner tw-banner-ok"></div>
            <div id="w3-plot-right" class="tw-plot-box"></div>
          </div>
        </div>

        <div class="tw-callout">
          <span class="tw-callout-lead">Predict &rarr; Test:</span> Drag <em>Station Distance d</em> across <strong>5 km</strong> and watch the regime badge flip from <code>Off-Site Representativeness &times; Cross-Age</code> to <code>Own-Pad Persistence: exp(&minus;&Delta;t/6.3)</code>. Then push <em>Observed Wind x<sub>obs</sub></em> to <strong>16 m/s</strong> and toggle <em>Day / Night</em> at <code>d = 40 km</code> to see why nighttime inversions slash off-site METAR trust.
        </div>
      </div>
    `;

    const elLead = root.querySelector("#w3-lead");
    const elAge = root.querySelector("#w3-age");
    const elDist = root.querySelector("#w3-dist");
    const elDz = root.querySelector("#w3-dz");
    const elXobs = root.querySelector("#w3-xobs");
    const btnDay = root.querySelector("#w3-btn-day");
    const btnNight = root.querySelector("#w3-btn-night");

    function setRegime(next) {
      regime = next;
      btnDay.className = "tw-toggle-btn" + (regime === "day" ? " active-day" : "");
      btnNight.className = "tw-toggle-btn" + (regime === "night" ? " active-night" : "");
      update();
    }

    function update() {
      const lead = parseFloat(elLead.value);
      const age = parseFloat(elAge.value);
      const dist = parseFloat(elDist.value);
      const dz = parseFloat(elDz.value);
      const xObs = parseFloat(elXobs.value);

      const isOwnPad = dist < OWN_STATION_KM;
      root.querySelector("#w3-lead-val").textContent = (lead > 0 ? "+" : "") + lead.toFixed(1) + " d";
      root.querySelector("#w3-age-val").textContent = age.toFixed(1) + " h";
      root.querySelector("#w3-dist-val").textContent = dist.toFixed(0) + " km" + (isOwnPad ? " (pad)" : "");
      root.querySelector("#w3-dz-val").textContent = dz.toFixed(0) + " m";
      root.querySelector("#w3-xobs-val").textContent = xObs.toFixed(1) + " m/s";

      const badge = root.querySelector("#w3-regime-badge");
      if (isOwnPad) {
        badge.className = "tw-pill tw-pill-ok";
        badge.textContent = "Own-Pad Persistence: exp(\u2212\u0394t/6.3)";
      } else {
        badge.className = "tw-pill tw-pill-violet";
        badge.textContent = "Off-Site Representativeness \u00D7 Cross-Age (" + (regime === "day" ? "Day" : "Night") + ")";
      }

      const banner = root.querySelector("#w3-right-banner");
      if (lead > 1.0) {
        banner.className = "tw-banner tw-banner-amber";
        banner.innerHTML = "<span><strong>Preview only (Lead &gt; 1.0 d):</strong> Launch-morning observation assimilation activates inside <code>T&minus;24 h</code>.</span>";
      } else if (lead < -0.5) {
        banner.className = "tw-banner tw-banner-neutral";
        banner.innerHTML = "<span><strong>Historical Mode (Lead &lt; 0 d):</strong> Past ERA5 / Mode P reanalysis is active; live METAR assimilation is offline.</span>";
      } else {
        banner.className = "tw-banner tw-banner-ok";
        banner.innerHTML = "<span><strong>Launch-Day Assimilation Active (inside T&minus;24 h):</strong> Live METAR / pad sensor updates the forecast prior.</span>";
      }

      const mCode = routerMode(lead);
      const climW = routerClimateWeight(lead);
      const gain = obsEffectiveGain(age, dist, dz, regime);
      const sigRatio = obsSigmaRatio(gain);
      const postStdRatio = Math.sqrt(Math.max(1.0 - gain, 0.0));
      const reductionPct = (1.0 - postStdRatio) * 100.0;

      root.querySelector("#w3-m-mode").textContent = MODE_LABELS[mCode];
      root.querySelector("#w3-m-clim").textContent = (climW * 100.0).toFixed(1) + "%";
      root.querySelector("#w3-m-gain").textContent = gain.toFixed(3);
      root.querySelector("#w3-m-sig").textContent = sigRatio.toFixed(2) + "\u00D7";
      root.querySelector("#w3-m-red").textContent = reductionPct.toFixed(1) + "%";

      if (typeof Plotly === "undefined") return;

      const leftTraces = [
        { x: leadGrid, y: wP, name: "P (\u2264-6d)", mode: "lines", line: { color: "#667085", width: 2.2 }, fill: "tozeroy", fillcolor: "rgba(102, 112, 133, 0.14)" },
        { x: leadGrid, y: wP0, name: "P0 (-6..0d)", mode: "lines", line: { color: "#525866", width: 2.2 }, fill: "tozeroy", fillcolor: "rgba(82, 88, 102, 0.12)" },
        { x: leadGrid, y: wF, name: "F (0..7d)", mode: "lines", line: { color: ACCENT_COBALT, width: 2.8 }, fill: "tozeroy", fillcolor: "rgba(29, 78, 216, 0.15)" },
        { x: leadGrid, y: wF2, name: "F2 (7..15d)", mode: "lines", line: { color: ACCENT_EMERALD, width: 2.8 }, fill: "tozeroy", fillcolor: "rgba(4, 120, 87, 0.15)" },
        { x: leadGrid, y: wM, name: "M (15..46d)", mode: "lines", line: { color: ACCENT_VIOLET, width: 2.8 }, fill: "tozeroy", fillcolor: "rgba(109, 40, 217, 0.14)" },
        { x: leadGrid, y: wC, name: "C (>46d)", mode: "lines", line: { color: ACCENT_AMBER, width: 2.8 }, fill: "tozeroy", fillcolor: "rgba(180, 83, 9, 0.14)" }
      ];

      const leftLayout = baseLayout({
        height: 520,
        title: titleStyle("Cosine Lead-Time Mode Blend Weights"),
        xaxis: axisStyle({ title: "Forecast Lead Time (days)", range: [-15, 60] }),
        yaxis: axisStyle({ title: "Source Weight", range: [-0.04, 1.18] }),
        shapes: [
          { type: "rect", x0: 10, x1: 15, y0: 0, y1: 1, fillcolor: "rgba(4, 120, 87, 0.10)", line: { color: "rgba(4, 120, 87, 0.45)", width: 1.2, dash: "dot" } },
          { type: "rect", x0: 35, x1: 46, y0: 0, y1: 1, fillcolor: "rgba(180, 83, 9, 0.10)", line: { color: "rgba(180, 83, 9, 0.45)", width: 1.2, dash: "dot" } },
          { type: "line", x0: lead, x1: lead, y0: 0, y1: 1.09, line: { color: INK_PRIMARY, width: 2.6, dash: "dash" } }
        ],
        annotations: [
          { x: 12.5, y: 1.11, text: "Blend 10\u201315d", showarrow: false, font: { size: 14.5, color: ACCENT_EMERALD }, bgcolor: "rgba(255,255,255,0.88)", borderpad: 2 },
          { x: 40.5, y: 1.11, text: "Blend 35\u201346d", showarrow: false, font: { size: 14.5, color: ACCENT_AMBER }, bgcolor: "rgba(255,255,255,0.88)", borderpad: 2 }
        ]
      });

      const muPrior = 6.5;
      const sdPrior = 2.8;
      const muPost = muPrior + gain * (xObs - muPrior);
      const sdPost = Math.max(sdPrior * postStdRatio, 0.14);
      const xMax = Math.max(22.0, xObs + 4.0);

      const wx = [];
      const yPrior = [];
      const yPost = [];
      for (let w = 0.0; w <= xMax + 0.001; w += 0.15) {
        wx.push(w);
        yPrior.push(normalPdf(w, muPrior, sdPrior));
        yPost.push(normalPdf(w, muPost, sdPost));
      }
      const peakPdf = Math.max(Math.max.apply(null, yPrior), Math.max.apply(null, yPost));

      const rightTraces = [
        {
          x: wx,
          y: yPrior,
          name: "Prior (\u03BC=6.5, \u03C3=2.8 m/s)",
          mode: "lines",
          line: { color: INK_SECONDARY, width: 2.4, dash: "dot" },
          fill: "tozeroy",
          fillcolor: "rgba(82, 88, 102, 0.14)",
          hovertemplate: "Wind=%{x:.1f} m/s<br>Prior PDF=%{y:.3f}<extra></extra>"
        },
        {
          x: wx,
          y: yPost,
          name: "Posterior (\u03BC=" + muPost.toFixed(1) + ", \u03C3=" + sdPost.toFixed(2) + ")",
          mode: "lines",
          line: { color: ACCENT_COBALT, width: 3.0 },
          fill: "tozeroy",
          fillcolor: "rgba(29, 78, 216, 0.18)",
          hovertemplate: "Wind=%{x:.1f} m/s<br>Posterior PDF=%{y:.3f}<extra></extra>"
        },
        {
          x: [xObs, xObs],
          y: [0, peakPdf * 1.06],
          name: "Observed x_obs (" + xObs.toFixed(1) + " m/s)",
          mode: "lines",
          line: { color: ACCENT_AMBER, width: 2.6, dash: "dash" }
        }
      ];

      const rightLayout = baseLayout({
        height: 485,
        title: titleStyle("Prior vs. Posterior 10 m Wind PDF (Gaussian Update)"),
        xaxis: axisStyle({ title: "10 m Wind Speed (m/s)", range: [0, xMax] }),
        yaxis: axisStyle({ title: "Probability Density", range: [0, peakPdf * 1.15] })
      });

      Plotly.react(root.querySelector("#w3-plot-left"), leftTraces, leftLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w3-plot-right"), rightTraces, rightLayout, PLOT_CONFIG);
    }

    [elLead, elAge, elDist, elDz, elXobs].forEach(function (el) {
      el.addEventListener("input", update);
    });
    btnDay.addEventListener("click", function () { setRegime("day"); });
    btnNight.addEventListener("click", function () { setRegime("night"); });
    root.querySelector("#w3-reset").addEventListener("click", function () {
      elLead.value = defaults.lead;
      elAge.value = defaults.age;
      elDist.value = defaults.dist;
      elDz.value = defaults.dz;
      elXobs.value = defaults.xObs;
      setRegime(defaults.regime);
    });

    update();
  }

  // =========================================================================
  // WIDGET 4: Schaake Shuffle & Vertical Coherence Visualizer (#widget-4-schaake)
  // =========================================================================

  const W4_M = 60; // Full ensemble pool for smooth marginal histogram
  const W4_SHOW = 12; // 12 vertical profiles displayed on left panel
  const W4_INSPECT_LEVELS = HEIGHTS.filter(function (z) { return z >= 100 && z <= 15000; });

  const W4_DATA = (function () {
    const rng = makeRng(20260404);
    const L = HEIGHTS.length;

    // Marginal wind speed distributions at each of the 44 AGL levels
    const rawPool = new Array(L); // rawPool[k][m]
    const uncoupled = new Array(L); // uncoupled[k][m] (independent permutation per level)
    const smoothTpl = new Array(L); // smoothTpl[k][m] (physically coherent sounding templates)
    const noiseTpl = new Array(L); // noiseTpl[k][m] (white noise to mix with coherence)

    // Pre-generate 3 smooth vertical basis coefficients per member
    const cJet = new Float64Array(W4_M);
    const cAlt = new Float64Array(W4_M);
    const cPbl = new Float64Array(W4_M);
    for (let m = 0; m < W4_M; m++) {
      cJet[m] = boxMuller(rng);
      cAlt[m] = boxMuller(rng);
      cPbl[m] = boxMuller(rng);
    }

    for (let k = 0; k < L; k++) {
      const z = HEIGHTS[k];
      const meanU =
        4.2 +
        5.5 * (1.0 - Math.exp(-z / 2400.0)) +
        21.0 * Math.exp(-0.5 * Math.pow((z - 11500.0) / 3000.0, 2));
      const sdU =
        2.1 +
        1.6 * (1.0 - Math.exp(-z / 3000.0)) +
        5.8 * Math.exp(-0.5 * Math.pow((z - 11500.0) / 3400.0, 2));

      const vals = new Float64Array(W4_M);
      const unc = new Float64Array(W4_M);
      const st = new Float64Array(W4_M);
      const nt = new Float64Array(W4_M);

      for (let m = 0; m < W4_M; m++) {
        const v = Math.max(0.4, meanU + sdU * boxMuller(rng));
        vals[m] = v;
        unc[m] = v;
        const wPbl = Math.exp(-z / 2600.0);
        const wJet = Math.exp(-0.5 * Math.pow((z - 11500.0) / 4200.0, 2));
        const wAlt = ((z - 11500.0) / 4500.0) * wJet;
        st[m] = 0.65 * wJet * cJet[m] + 0.45 * wAlt * cAlt[m] + 0.55 * wPbl * cPbl[m] + 0.25 * cJet[m];
        nt[m] = boxMuller(rng);
      }
      rawPool[k] = vals;
      uncoupled[k] = unc;
      smoothTpl[k] = st;
      noiseTpl[k] = nt;
    }

    return { rawPool, uncoupled, smoothTpl, noiseTpl };
  })();

  function rankReorderLevel(sortedVals, templateScores) {
    const n = sortedVals.length;
    const idx = new Array(n);
    for (let i = 0; i < n; i++) idx[i] = i;
    idx.sort(function (a, b) { return templateScores[a] - templateScores[b]; });
    const out = new Float64Array(n);
    for (let rank = 0; rank < n; rank++) {
      out[idx[rank]] = sortedVals[rank];
    }
    return out;
  }

  function pearsonCorr(a, b) {
    const n = a.length;
    let ma = 0.0, mb = 0.0;
    for (let i = 0; i < n; i++) {
      ma += a[i];
      mb += b[i];
    }
    ma /= n;
    mb /= n;
    let num = 0.0, da = 0.0, db = 0.0;
    for (let i = 0; i < n; i++) {
      const xa = a[i] - ma;
      const xb = b[i] - mb;
      num += xa * xb;
      da += xa * xa;
      db += xb * xb;
    }
    return num / Math.max(Math.sqrt(da * db), 1e-12);
  }

  function initWidget4(root) {
    if (!root) return;

    const defaults = { mode: "shuffled", coherence: 0.90, zIdx: W4_INSPECT_LEVELS.indexOf(10000) };
    let mode = defaults.mode;

    // Pre-sort each level once for fast O(M log M) Schaake rank reordering
    const sortedByLevel = HEIGHTS.map(function (_, k) {
      const arr = Array.from(W4_DATA.rawPool[k]);
      arr.sort(function (a, b) { return a - b; });
      return arr;
    });

    root.innerHTML = `
      <div class="tw-card">
        <div class="tw-header">
          <div class="tw-header-text">
            <div class="tw-kicker">Interactive Sandbox 4</div>
            <h4 class="tw-title">Schaake Shuffle &amp; Vertical Coherence Visualizer</h4>
            <p class="tw-subtitle">Rank-reordering (<code>shuffle.py</code>) restores smooth vertical jet structure while leaving every level&rsquo;s marginal distribution 100% unchanged.</p>
          </div>
          <div class="tw-header-actions">
            <div class="tw-toggle-group" role="group" aria-label="Coherence Mode">
              <button type="button" data-mode="raw" class="tw-toggle-btn">Raw Uncoupled Margins</button>
              <button type="button" data-mode="shuffled" class="tw-toggle-btn active-cobalt">Schaake-Shuffled</button>
              <button type="button" data-mode="shearmap" class="tw-toggle-btn">Shuffle + Shear Map</button>
            </div>
            <button type="button" id="w4-reset" class="tw-btn">Reset Defaults</button>
          </div>
        </div>

        <div class="tw-controls-panel">
          <div class="tw-controls-grid tw-cols-2">
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Template Coherence</span>
                <span id="w4-coh-val" class="tw-control-val tw-ink-cobalt">0.90</span>
              </div>
              <input id="w4-coh" type="range" min="0.00" max="1.00" step="0.05" value="${defaults.coherence}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Inspect Altitude z</span>
                <span id="w4-z-val" class="tw-control-val tw-ink-amber">10.0 km AGL</span>
              </div>
              <input id="w4-z" type="range" min="0" max="${W4_INSPECT_LEVELS.length - 1}" step="1" value="${defaults.zIdx}" class="tw-slider" />
            </label>
          </div>
        </div>

        <div class="tw-metrics-grid tw-mcols-4">
          <div class="tw-metric">
            <div class="tw-metric-label">Lag-1 Vertical Corr</div>
            <div id="w4-m-corr" class="tw-metric-val tw-ink-cobalt">--</div>
            <div class="tw-metric-sub">Mean r(z<sub>k</sub>, z<sub>k+1</sub>)</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Max Wind Shear</div>
            <div id="w4-m-shear" class="tw-metric-val tw-ink-amber">--</div>
            <div class="tw-metric-sub">Highlighted member</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Marginal Mean &Delta;</div>
            <div id="w4-m-delta" class="tw-metric-val tw-ink-emerald">0.00 m/s</div>
            <div class="tw-metric-sub">Exact at selected z</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Level Marginal (z)</div>
            <div id="w4-m-lvl" class="tw-metric-val tw-ink-violet">--</div>
            <div class="tw-metric-sub">Mean &plusmn; SD (m/s)</div>
          </div>
        </div>

        <div class="tw-plots-grid">
          <div id="w4-plot-left" class="tw-plot-box"></div>
          <div id="w4-plot-right" class="tw-plot-box"></div>
        </div>

        <div class="tw-callout">
          <span class="tw-callout-lead">Predict &rarr; Test:</span> Switch between <em>Raw Uncoupled Margins</em> and <em>Schaake-Shuffled</em> while watching the right-hand histogram at <code>z = 10.0 km</code>. Notice how the left profiles collapse from jagged, unphysical wind-shear zigzags into smooth jet streams while the marginal histogram and <code>Marginal Mean &Delta; = 0.00 m/s</code> remain completely identical.
        </div>
      </div>
    `;

    const elCoh = root.querySelector("#w4-coh");
    const elZ = root.querySelector("#w4-z");
    const modeBtns = Array.from(root.querySelectorAll("[data-mode]"));

    function setMode(next) {
      mode = next;
      modeBtns.forEach(function (btn) {
        const isMe = btn.getAttribute("data-mode") === mode;
        btn.className = "tw-toggle-btn" + (isMe ? (mode === "shearmap" ? " active-emerald" : " active-cobalt") : "");
      });
      update();
    }

    function update() {
      const coh = parseFloat(elCoh.value);
      const zSliderIdx = parseInt(elZ.value, 10);
      const zInspectM = W4_INSPECT_LEVELS[zSliderIdx];
      const zLevelIdx = HEIGHTS.indexOf(zInspectM);
      const zInspectKm = zInspectM / 1000.0;

      root.querySelector("#w4-coh-val").textContent = coh.toFixed(2);
      root.querySelector("#w4-z-val").textContent =
        zInspectM < 1000 ? zInspectM + " m AGL" : zInspectKm.toFixed(1) + " km AGL";

      const L = HEIGHTS.length;
      const levels = new Array(L);

      if (mode === "raw") {
        for (let k = 0; k < L; k++) {
          levels[k] = W4_DATA.uncoupled[k];
        }
      } else {
        const wS = coh;
        const wN = Math.sqrt(Math.max(1.0 - coh * coh, 0.0));
        for (let k = 0; k < L; k++) {
          const scores = new Float64Array(W4_M);
          for (let m = 0; m < W4_M; m++) {
            scores[m] = wS * W4_DATA.smoothTpl[k][m] + wN * W4_DATA.noiseTpl[k][m];
          }
          levels[k] = rankReorderLevel(sortedByLevel[k], scores);
        }

        // Mode 2: Shuffle + Shear Map (calibrates extreme layer-to-layer shear while preserving level mean)
        if (mode === "shearmap") {
          for (let k = 1; k < L; k++) {
            const dzKm = (HEIGHTS[k] - HEIGHTS[k - 1]) / 1000.0;
            const prev = levels[k - 1];
            const curr = levels[k];
            const adjusted = new Float64Array(W4_M);
            let meanRaw = 0.0, meanAdj = 0.0;
            for (let m = 0; m < W4_M; m++) {
              meanRaw += curr[m];
              const du = curr[m] - prev[m];
              const shear = Math.abs(du) / dzKm;
              // Soft-map excessive synthetic shear > 14 m/s/km toward sonde shear quantile
              const damp = shear > 14.0 ? 0.72 : 1.0;
              adjusted[m] = prev[m] + du * damp;
              meanAdj += adjusted[m];
            }
            const shift = (meanRaw - meanAdj) / W4_M;
            for (let m = 0; m < W4_M; m++) {
              adjusted[m] = Math.max(0.2, adjusted[m] + shift);
            }
            levels[k] = adjusted;
          }
        }
      }

      // Compute Lag-1 vertical correlation averaged across consecutive levels
      let corrSum = 0.0;
      for (let k = 0; k < L - 1; k++) {
        corrSum += pearsonCorr(levels[k], levels[k + 1]);
      }
      const meanLag1 = corrSum / (L - 1);

      // Compute max vertical wind shear (m/s/km) on highlighted member 0
      let maxShear = 0.0;
      for (let k = 0; k < L - 1; k++) {
        const dzKm = (HEIGHTS[k + 1] - HEIGHTS[k]) / 1000.0;
        const sh = Math.abs(levels[k + 1][0] - levels[k][0]) / dzKm;
        if (sh > maxShear) maxShear = sh;
      }

      // Marginal stats at inspected level z
      const rawAtZ = Array.from(W4_DATA.uncoupled[zLevelIdx]);
      const actAtZ = Array.from(levels[zLevelIdx]);
      let meanRawZ = 0.0, meanActZ = 0.0;
      for (let m = 0; m < W4_M; m++) {
        meanRawZ += rawAtZ[m];
        meanActZ += actAtZ[m];
      }
      meanRawZ /= W4_M;
      meanActZ /= W4_M;
      let varActZ = 0.0;
      for (let m = 0; m < W4_M; m++) {
        const d = actAtZ[m] - meanActZ;
        varActZ += d * d;
      }
      const sdActZ = Math.sqrt(varActZ / (W4_M - 1));
      const deltaMean = Math.abs(meanActZ - meanRawZ);

      root.querySelector("#w4-m-corr").textContent = meanLag1.toFixed(2);
      root.querySelector("#w4-m-shear").textContent = maxShear.toFixed(1) + " m/s/km";
      root.querySelector("#w4-m-delta").textContent = deltaMean.toFixed(2) + " m/s";
      root.querySelector("#w4-m-lvl").textContent = meanActZ.toFixed(1) + " \u00B1 " + sdActZ.toFixed(1);

      if (typeof Plotly === "undefined") return;

      const leftTraces = [];
      const bgColor =
        mode === "raw"
          ? "rgba(185, 28, 28, 0.24)"
          : mode === "shearmap"
            ? "rgba(4, 120, 87, 0.24)"
            : "rgba(29, 78, 216, 0.22)";

      for (let m = 1; m < W4_SHOW; m++) {
        const prof = new Array(L);
        for (let k = 0; k < L; k++) prof[k] = levels[k][m];
        leftTraces.push({
          x: prof,
          y: HEIGHTS_KM,
          mode: "lines",
          line: { color: bgColor, width: 1.5 },
          showlegend: m === 1,
          name: "Ensemble Members (11)",
          hoverinfo: "skip"
        });
      }

      const hiProf = new Array(L);
      for (let k = 0; k < L; k++) hiProf[k] = levels[k][0];
      leftTraces.push({
        x: hiProf,
        y: HEIGHTS_KM,
        mode: "lines",
        line: { color: mode === "raw" ? ACCENT_CRIMSON : mode === "shearmap" ? ACCENT_EMERALD : ACCENT_COBALT, width: 3.2 },
        name: "Highlighted Member #1",
        hovertemplate: "z=%{y:.2f} km<br>u(z)=%{x:.1f} m/s<extra></extra>"
      });

      const leftLayout = baseLayout({
        height: 510,
        title: titleStyle("12 Ensemble Wind Profiles u(z) across 44 AGL Levels"),
        xaxis: axisStyle({ title: "Wind Speed u(z) (m/s)", range: [0, 48] }),
        yaxis: axisStyle({ title: "Altitude (km AGL)", range: [0, 18.2] }),
        shapes: [
          { type: "line", xref: "paper", x0: 0, x1: 1, y0: zInspectKm, y1: zInspectKm, line: { color: ACCENT_AMBER, width: 2.2, dash: "dash" } }
        ],
        annotations: [
          { xref: "paper", x: 0.99, y: zInspectKm, xanchor: "right", yanchor: "bottom", text: "Inspect z = " + zInspectKm.toFixed(1) + " km", showarrow: false, font: { size: 14.5, color: ACCENT_AMBER }, bgcolor: "rgba(255,255,255,0.88)", borderpad: 2 }
        ]
      });

      const minVal = Math.floor(Math.min.apply(null, rawAtZ) - 2);
      const maxVal = Math.ceil(Math.max.apply(null, rawAtZ) + 2);
      const binSize = Math.max(1.0, (maxVal - minVal) / 14.0);

      const rightTraces = [
        {
          x: rawAtZ,
          name: "Raw Uncoupled Marginal",
          type: "histogram",
          xbins: { start: minVal, end: maxVal, size: binSize },
          marker: { color: "rgba(82, 88, 102, 0.24)", line: { color: INK_SECONDARY, width: 1.5 } }
        },
        {
          x: actAtZ,
          name: mode === "raw" ? "Active (Raw Uncoupled)" : mode === "shuffled" ? "Active (Schaake-Shuffled)" : "Active (Shuffle + Shear Map)",
          type: "histogram",
          xbins: { start: minVal, end: maxVal, size: binSize },
          marker: {
            color: mode === "shearmap" ? "rgba(4, 120, 87, 0.36)" : "rgba(29, 78, 216, 0.34)",
            line: { color: mode === "shearmap" ? ACCENT_EMERALD : ACCENT_COBALT, width: 1.6 }
          }
        }
      ];

      const rightLayout = baseLayout({
        height: 510,
        title: titleStyle("Marginal Histogram at z = " + zInspectKm.toFixed(1) + " km (Invariant under Shuffle)"),
        barmode: "overlay",
        xaxis: axisStyle({ title: "Wind Speed at z (m/s)" }),
        yaxis: axisStyle({ title: "Member Count (M=60)" })
      });

      Plotly.react(root.querySelector("#w4-plot-left"), leftTraces, leftLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w4-plot-right"), rightTraces, rightLayout, PLOT_CONFIG);
    }

    [elCoh, elZ].forEach(function (el) {
      el.addEventListener("input", update);
    });
    modeBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        setMode(btn.getAttribute("data-mode"));
      });
    });
    root.querySelector("#w4-reset").addEventListener("click", function () {
      elCoh.value = defaults.coherence;
      elZ.value = defaults.zIdx;
      setMode(defaults.mode);
    });

    setMode(defaults.mode);
  }

  // =========================================================================
  // WIDGET 5: Rocket Apogee & Drift Variance Explorer (#widget-5-mc)
  // =========================================================================

  const W5_N = 120;
  const W5_DRAWS = (function () {
    const rng = makeRng(20260405);
    const zVeh = new Float64Array(W5_N);
    const zBlU = new Float64Array(W5_N);
    const zBlV = new Float64Array(W5_N);
    const zJetU = new Float64Array(W5_N);
    const zJetV = new Float64Array(W5_N);
    const zRho = new Float64Array(W5_N);
    for (let i = 0; i < W5_N; i++) {
      zVeh[i] = boxMuller(rng);
      zBlU[i] = boxMuller(rng);
      zBlV[i] = boxMuller(rng);
      zJetU[i] = boxMuller(rng);
      zJetV[i] = boxMuller(rng);
      zRho[i] = boxMuller(rng);
    }
    return { zVeh, zBlU, zBlV, zJetU, zJetV, zRho };
  })();

  function initWidget5(root) {
    if (!root) return;

    const defaults = { sigVeh: 5.0, sigBl: 2.5, sigJet: 6.0, waiver: 1500, airMode: "coupled" };
    let airMode = defaults.airMode;

    // Precompute unit circle points for Waiver Boundary
    const circleTheta = [];
    for (let a = 0; a <= 360; a += 4) circleTheta.push((a * Math.PI) / 180.0);

    root.innerHTML = `
      <div class="tw-card">
        <div class="tw-header">
          <div class="tw-header-text">
            <div class="tw-kicker">Interactive Sandbox 5</div>
            <h4 class="tw-title">Rocket Apogee &amp; Drift Variance Explorer: Vehicle vs. Atmosphere</h4>
            <p class="tw-subtitle">120-flight joint Monte Carlo dispersion (<code>montecarlo.py</code>) comparing vehicle drag/thrust, boundary-layer wind, upper jet, and pad air density.</p>
          </div>
          <div class="tw-header-actions">
            <div class="tw-toggle-group" role="group" aria-label="Air Model">
              <button type="button" id="w5-btn-coupled" class="tw-toggle-btn active-cobalt">Full Coupled Air</button>
              <button type="button" id="w5-btn-hybrid" class="tw-toggle-btn">Hybrid air="standard" + Wind</button>
            </div>
            <button type="button" id="w5-reset" class="tw-btn">Reset Defaults</button>
          </div>
        </div>

        <div class="tw-controls-panel">
          <div class="tw-controls-grid tw-cols-2">
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Vehicle Drag/Thrust &sigma;<sub>veh</sub></span>
                <span id="w5-veh-val" class="tw-control-val tw-ink-cobalt">5.0%</span>
              </div>
              <input id="w5-veh" type="range" min="1.0" max="10.0" step="0.5" value="${defaults.sigVeh}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Boundary-Layer Wind (0&ndash;300 m)</span>
                <span id="w5-bl-val" class="tw-control-val tw-ink-cobalt">2.50 m/s</span>
              </div>
              <input id="w5-bl" type="range" min="0.5" max="6.0" step="0.25" value="${defaults.sigBl}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Upper-Jet Wind (3&ndash;18 km)</span>
                <span id="w5-jet-val" class="tw-control-val tw-ink-cobalt">6.0 m/s</span>
              </div>
              <input id="w5-jet" type="range" min="1.0" max="15.0" step="0.5" value="${defaults.sigJet}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Waiver Radius</span>
                <span id="w5-waiver-val" class="tw-control-val tw-ink-amber">1,500 m</span>
              </div>
              <input id="w5-waiver" type="range" min="500" max="3000" step="100" value="${defaults.waiver}" class="tw-slider" />
            </label>
          </div>
        </div>

        <div class="tw-metrics-grid tw-mcols-4">
          <div class="tw-metric">
            <div class="tw-metric-label">Inside Waiver</div>
            <div id="w5-m-in" class="tw-metric-val tw-ink-emerald">--</div>
            <div id="w5-m-incnt" class="tw-metric-sub">-- / 120 flights</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">90% Apogee Interval</div>
            <div id="w5-m-apo" class="tw-metric-val tw-ink-cobalt">--</div>
            <div id="w5-m-apow" class="tw-metric-sub">Nominal 9,150 m</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Dominant Risk Driver</div>
            <div id="w5-m-dom" class="tw-metric-val tw-ink-amber">--</div>
            <div class="tw-metric-sub">Landing dispersion share</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Mean Radial Drift</div>
            <div id="w5-m-rad" class="tw-metric-val tw-ink-violet">--</div>
            <div class="tw-metric-sub">From pad origin</div>
          </div>
        </div>

        <div class="tw-plots-grid">
          <div id="w5-plot-left" class="tw-plot-box"></div>
          <div id="w5-plot-right" class="tw-plot-box"></div>
        </div>

        <div class="tw-callout">
          <span class="tw-callout-lead">Predict &rarr; Test:</span> Toggle from <em>Full Coupled Air</em> to <em>Hybrid air="standard" + Wind</em> and check how little <code>% Inside Waiver</code> moves&mdash;proving why pad air density is a small fraction of total variance compared to <strong>0&ndash;300 m boundary-layer wind</strong> (weathercocking + main chute drift) and <strong>vehicle &sigma;<sub>veh</sub></strong>.
        </div>
      </div>
    `;

    const elVeh = root.querySelector("#w5-veh");
    const elBl = root.querySelector("#w5-bl");
    const elJet = root.querySelector("#w5-jet");
    const elWaiver = root.querySelector("#w5-waiver");
    const btnCoupled = root.querySelector("#w5-btn-coupled");
    const btnHybrid = root.querySelector("#w5-btn-hybrid");

    function setAirMode(next) {
      airMode = next;
      btnCoupled.className = "tw-toggle-btn" + (airMode === "coupled" ? " active-cobalt" : "");
      btnHybrid.className = "tw-toggle-btn" + (airMode === "hybrid" ? " active-emerald" : "");
      update();
    }

    function update() {
      const sigVeh = parseFloat(elVeh.value);
      const sigBl = parseFloat(elBl.value);
      const sigJet = parseFloat(elJet.value);
      const waiver = parseFloat(elWaiver.value);
      const rhoScale = airMode === "coupled" ? 1.0 : 0.0;

      root.querySelector("#w5-veh-val").textContent = sigVeh.toFixed(1) + "%";
      root.querySelector("#w5-bl-val").textContent = sigBl.toFixed(2) + " m/s";
      root.querySelector("#w5-jet-val").textContent = sigJet.toFixed(1) + " m/s";
      root.querySelector("#w5-waiver-val").textContent = Math.round(waiver).toLocaleString() + " m";

      const H0 = 9150.0;
      const inX = [], inY = [], outX = [], outY = [];
      const apogees = new Array(W5_N);
      let sumRad = 0.0;
      let inCount = 0;

      // Sensitivity lever arms (m per unit perturbation) for 30k-ft IREC-class flight
      const kBl = 165.0; // 0-300 m weathercocking + main-chute drift lever arm
      const kJet = 34.0; // 3-18 km drogue descent lever arm
      const kVehDrift = 72.0; // vehicle impulse/drag dispersion coupling into trajectory & drift
      const kRhoDrift = 55.0 * rhoScale; // pad air density effect on apogee & chute sink rate

      for (let i = 0; i < W5_N; i++) {
        const zv = W5_DRAWS.zVeh[i];
        const zbu = W5_DRAWS.zBlU[i];
        const zbv = W5_DRAWS.zBlV[i];
        const zju = W5_DRAWS.zJetU[i];
        const zjv = W5_DRAWS.zJetV[i];
        const zr = W5_DRAWS.zRho[i];

        const blU = sigBl * zbu;
        const blV = sigBl * zbv;
        const jetU = sigJet * zju;
        const jetV = sigJet * zjv;

        // Apogee (m AGL)
        const dHveh = H0 * 1.15 * (sigVeh / 100.0) * zv;
        const dHrho = H0 * -0.0125 * rhoScale * zr;
        const dHbl = -14.0 * Math.hypot(3.2 + blU, blV) + 44.8;
        const apo = Math.max(2500.0, H0 + dHveh + dHrho + dHbl);
        apogees[i] = apo;

        // 2D Landing point (m): mean downwind bias + stochastic perturbations
        const x = 320.0 + kBl * blU + kJet * jetU + kVehDrift * sigVeh * zv * 0.85 + kRhoDrift * zr;
        const y = 40.0 + kBl * blV + kJet * jetV + kVehDrift * sigVeh * (0.52 * zv + 0.25 * zbu);
        const rad = Math.hypot(x, y);
        sumRad += rad;
        if (rad <= waiver) {
          inCount++;
          inX.push(x);
          inY.push(y);
        } else {
          outX.push(x);
          outY.push(y);
        }
      }

      apogees.sort(function (a, b) { return a - b; });
      const apoQ05 = quantileSorted(apogees, 0.05);
      const apoQ95 = quantileSorted(apogees, 0.95);
      const inPct = (100.0 * inCount) / W5_N;
      const meanRad = sumRad / W5_N;

      // Variance share decomposition across the 4 independent sources
      const varVeh = Math.pow(kVehDrift * sigVeh, 2) * (0.85 * 0.85 + 0.52 * 0.52);
      const varBl = 2.0 * Math.pow(kBl * sigBl, 2);
      const varJet = 2.0 * Math.pow(kJet * sigJet, 2);
      const varRho = Math.pow(kRhoDrift, 2);
      const varTot = Math.max(varVeh + varBl + varJet + varRho, 1e-6);

      const shares = [
        { label: "0\u2013300 m Wind", pct: (100.0 * varBl) / varTot, color: ACCENT_COBALT },
        { label: "Vehicle \u03C3_veh", pct: (100.0 * varVeh) / varTot, color: ACCENT_AMBER },
        { label: "3\u201318 km Jet", pct: (100.0 * varJet) / varTot, color: ACCENT_VIOLET },
        { label: "Pad Air Density", pct: (100.0 * varRho) / varTot, color: ACCENT_EMERALD }
      ];
      let dom = shares[0];
      for (let i = 1; i < shares.length; i++) {
        if (shares[i].pct > dom.pct) dom = shares[i];
      }

      const elIn = root.querySelector("#w5-m-in");
      elIn.textContent = inPct.toFixed(1) + "%";
      elIn.className =
        "tw-metric-val " +
        (inPct >= 95 ? "tw-ink-emerald" : inPct >= 85 ? "tw-ink-amber" : "tw-ink-crimson");
      root.querySelector("#w5-m-incnt").textContent = inCount + " / " + W5_N + " flights";
      root.querySelector("#w5-m-apo").textContent =
        Math.round(apoQ05).toLocaleString() + "\u2013" + Math.round(apoQ95).toLocaleString() + " m";
      root.querySelector("#w5-m-apow").textContent = "90% width: \u00B1" + Math.round((apoQ95 - apoQ05) / 2).toLocaleString() + " m";
      root.querySelector("#w5-m-dom").textContent = dom.label + " (" + dom.pct.toFixed(0) + "%)";
      root.querySelector("#w5-m-rad").textContent = Math.round(meanRad).toLocaleString() + " m";

      if (typeof Plotly === "undefined") return;

      const circX = circleTheta.map(function (t) { return waiver * Math.cos(t); });
      const circY = circleTheta.map(function (t) { return waiver * Math.sin(t); });
      const span = Math.max(waiver * 1.25, 2200);

      const leftTraces = [
        {
          x: circX,
          y: circY,
          name: "Waiver Boundary (" + Math.round(waiver) + " m)",
          mode: "lines",
          line: { color: ACCENT_AMBER, width: 2.4, dash: "dash" },
          hoverinfo: "skip"
        },
        {
          x: inX,
          y: inY,
          name: "Inside Waiver (" + inCount + ")",
          mode: "markers",
          marker: { color: "rgba(4, 120, 87, 0.78)", size: 7.5, line: { color: "#ffffff", width: 0.9 } },
          hovertemplate: "Downrange=%{x:.0f} m<br>Crossrange=%{y:.0f} m<extra>Inside</extra>"
        },
        {
          x: outX,
          y: outY,
          name: "Outside Waiver (" + (W5_N - inCount) + ")",
          mode: "markers",
          marker: { color: "rgba(185, 28, 28, 0.88)", size: 8, symbol: "x" },
          hovertemplate: "Downrange=%{x:.0f} m<br>Crossrange=%{y:.0f} m<extra>Outside</extra>"
        },
        {
          x: [0],
          y: [0],
          name: "Launch Pad",
          mode: "markers",
          marker: { color: INK_PRIMARY, size: 12, symbol: "star" },
          hovertemplate: "Launch Pad (0, 0)<extra></extra>"
        }
      ];

      const leftLayout = baseLayout({
        height: 510,
        title: titleStyle("2D Landing Dispersion (N=120 Trajectories)"),
        xaxis: axisStyle({ title: "Downrange East (m)", range: [-span, span] }),
        yaxis: axisStyle({ title: "Crossrange North (m)", range: [-span, span], scaleanchor: "x", scaleratio: 1 })
      });

      const rightTraces = [
        {
          y: shares.map(function (s) { return s.label; }).reverse(),
          x: shares.map(function (s) { return s.pct; }).reverse(),
          type: "bar",
          orientation: "h",
          marker: {
            color: shares.map(function (s) { return s.color; }).reverse(),
            line: { color: "#ffffff", width: 1.5 }
          },
          text: shares.map(function (s) { return s.pct.toFixed(1) + "%"; }).reverse(),
          textposition: "outside",
          textfont: { color: INK_PRIMARY, size: 15 },
          hovertemplate: "%{y}: %{x:.1f}% of variance<extra></extra>"
        }
      ];

      const rightLayout = baseLayout({
        height: 510,
        title: titleStyle("Landing Dispersion Variance Share (Sobol Attribution)"),
        margin: { l: 150, r: 62, t: 55, b: 65 },
        showlegend: false,
        xaxis: axisStyle({ title: "Share of Total Landing Variance (%)", range: [0, 112] }),
        yaxis: axisStyle({})
      });

      Plotly.react(root.querySelector("#w5-plot-left"), leftTraces, leftLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w5-plot-right"), rightTraces, rightLayout, PLOT_CONFIG);
    }

    [elVeh, elBl, elJet, elWaiver].forEach(function (el) {
      el.addEventListener("input", update);
    });
    btnCoupled.addEventListener("click", function () { setAirMode("coupled"); });
    btnHybrid.addEventListener("click", function () { setAirMode("hybrid"); });
    root.querySelector("#w5-reset").addEventListener("click", function () {
      elVeh.value = defaults.sigVeh;
      elBl.value = defaults.sigBl;
      elJet.value = defaults.sigJet;
      elWaiver.value = defaults.waiver;
      setAirMode(defaults.airMode);
    });

    setAirMode(defaults.airMode);
  }

  // =========================================================================
  // WIDGET 6: Gaussian vs. Student-t Conditional Copula (#widget-6-copula)
  // =========================================================================

  const W6_N = 280;
  const W6_NU_MAX = 30;
  const W6_DRAWS = (function () {
    const rng = makeRng(20260406);
    const z1 = new Float64Array(W6_N);
    const z2 = new Float64Array(W6_N);
    // Pre-generate 30 independent squared standard normals per point for exact chi^2_nu
    const chiSq = new Array(W6_N);
    for (let i = 0; i < W6_N; i++) {
      z1[i] = boxMuller(rng);
      z2[i] = boxMuller(rng);
      const c = new Float64Array(W6_NU_MAX);
      for (let d = 0; d < W6_NU_MAX; d++) {
        const g = boxMuller(rng);
        c[d] = g * g;
      }
      chiSq[i] = c;
    }
    return { z1, z2, chiSq };
  })();

  function initWidget6(root) {
    if (!root) return;

    const defaults = { uObs: 14.5, rho: 0.70, nu: 4 };
    const MU_X = 6.5;
    const SD_X = 3.0;
    const MU_Y = 10.0;
    const SD_Y = 4.2;
    const SHEAR_THRESH = 22.0;

    root.innerHTML = `
      <div class="tw-card">
        <div class="tw-header">
          <div class="tw-header-text">
            <div class="tw-kicker">Interactive Sandbox 6</div>
            <h4 class="tw-title">Gaussian vs. Student-<em>t</em> Conditional Copula Tail Explorer</h4>
            <p class="tw-subtitle">Exact conditional Student-<em>t</em> scale inflation (<code>stats.py::Coupled</code>) showing why Gaussian copulas under-predict extreme wind shear during storms.</p>
          </div>
          <div class="tw-header-actions">
            <button type="button" id="w6-reset" class="tw-btn">Reset Defaults</button>
          </div>
        </div>

        <div class="tw-controls-panel">
          <div class="tw-controls-grid tw-cols-3">
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Observed Pad Wind u<sub>obs</sub></span>
                <span id="w6-uobs-val" class="tw-control-val tw-ink-amber">14.5 m/s</span>
              </div>
              <input id="w6-uobs" type="range" min="4.0" max="18.0" step="0.5" value="${defaults.uObs}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Correlation &rho;</span>
                <span id="w6-rho-val" class="tw-control-val tw-ink-cobalt">0.70</span>
              </div>
              <input id="w6-rho" type="range" min="0.20" max="0.90" step="0.05" value="${defaults.rho}" class="tw-slider" />
            </label>
            <label class="tw-control">
              <div class="tw-control-head">
                <span>Student-<em>t</em> Tail Heaviness &nu;</span>
                <span id="w6-nu-val" class="tw-control-val tw-ink-crimson">&nu; = 4</span>
              </div>
              <input id="w6-nu" type="range" min="3" max="30" step="1" value="${defaults.nu}" class="tw-slider" />
            </label>
          </div>
        </div>

        <div class="tw-metrics-grid tw-mcols-4">
          <div class="tw-metric">
            <div class="tw-metric-label">Gaussian Cond. SD</div>
            <div id="w6-m-gsd" class="tw-metric-val tw-ink-cobalt">--</div>
            <div class="tw-metric-sub">Constant vs u<sub>obs</sub></div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Student-<em>t</em> Cond. SD</div>
            <div id="w6-m-tsd" class="tw-metric-val tw-ink-crimson">--</div>
            <div id="w6-m-tsdr" class="tw-metric-sub">-- vs Gaussian</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Gaussian P(Shear &gt; 22)</div>
            <div id="w6-m-gp" class="tw-metric-val tw-ink-cobalt">--</div>
            <div class="tw-metric-sub">Tail-collapse risk</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-label">Student-<em>t</em> P(Shear &gt; 22)</div>
            <div id="w6-m-tp" class="tw-metric-val tw-ink-crimson">--</div>
            <div id="w6-m-tpr" class="tw-metric-sub">Storm-tail persistence</div>
          </div>
        </div>

        <div class="tw-plots-grid">
          <div id="w6-plot-left" class="tw-plot-box"></div>
          <div id="w6-plot-right" class="tw-plot-box"></div>
        </div>

        <div class="tw-callout">
          <span class="tw-callout-lead">Predict &rarr; Test:</span> Sweep <em>Observed Pad Wind u<sub>obs</sub></em> from <strong>6 m/s</strong> up to <strong>18 m/s</strong> with <code>&nu; = 4</code>. Notice that the cobalt Gaussian conditional curve merely shifts right with an unchanging width, whereas the crimson Student-<em>t</em> curve visibly widens&mdash;capturing joint extreme wind shear during storm outbreaks.
        </div>
      </div>
    `;

    const elUobs = root.querySelector("#w6-uobs");
    const elRho = root.querySelector("#w6-rho");
    const elNu = root.querySelector("#w6-nu");

    function update() {
      const uObs = parseFloat(elUobs.value);
      const rho = parseFloat(elRho.value);
      const nu = parseInt(elNu.value, 10);

      root.querySelector("#w6-uobs-val").textContent = uObs.toFixed(1) + " m/s";
      root.querySelector("#w6-rho-val").textContent = rho.toFixed(2);
      root.querySelector("#w6-nu-val").textContent = "\u03BD = " + nu + (nu <= 5 ? " (heavy)" : nu >= 20 ? " (near-Gauss)" : "");

      const rootOneMinusR2 = Math.sqrt(Math.max(1.0 - rho * rho, 1e-6));
      const scaleMarg = Math.sqrt((nu - 2.0) / nu);

      // Build 2D joint scatter clouds (unit-variance marginals mapped to physical wind & shear)
      const gx = new Array(W6_N), gy = new Array(W6_N);
      const tx = new Array(W6_N), ty = new Array(W6_N);

      for (let i = 0; i < W6_N; i++) {
        const z1 = W6_DRAWS.z1[i];
        const z2 = rho * z1 + rootOneMinusR2 * W6_DRAWS.z2[i];

        gx[i] = clamp(MU_X + SD_X * z1, 0.2, 24.0);
        gy[i] = clamp(MU_Y + SD_Y * z2, 0.5, 42.0);

        let sumChi = 0.0;
        const cArr = W6_DRAWS.chiSq[i];
        for (let d = 0; d < nu; d++) sumChi += cArr[d];
        const tMult = scaleMarg / Math.sqrt(sumChi / nu);

        tx[i] = clamp(MU_X + SD_X * z1 * tMult, 0.2, 24.0);
        ty[i] = clamp(MU_Y + SD_Y * z2 * tMult, 0.5, 42.0);
      }

      // Exact conditional distributions of 500 m Wind Shear given u_obs
      const xO = (uObs - MU_X) / SD_X;
      const condMean = MU_Y + SD_Y * rho * xO;
      const gaussCondSd = SD_Y * rootOneMinusR2;

      // Exact Student-t conditional (df' = nu + 1)
      const nuPost = nu + 1;
      const xRaw = xO / scaleMarg;
      const tCondScale = SD_Y * scaleMarg * Math.sqrt(((nu + xRaw * xRaw) / nuPost) * (1.0 - rho * rho));
      const tCondSd = tCondScale * Math.sqrt(nuPost / (nuPost - 2.0));

      // Evaluate smooth conditional PDFs and integrate P(Shear > 22 m/s/km)
      const yMin = -2.0;
      const yMax = 44.0;
      const dy = 0.25;
      const ys = [];
      const pdfG = [];
      const pdfT = [];
      let pExtG = 0.0;
      let pExtT = 0.0;

      for (let y = yMin; y <= yMax + 1e-6; y += dy) {
        const pg = normalPdf(y, condMean, gaussCondSd);
        const pt = studentTPdf(y, nuPost, condMean, tCondScale);
        ys.push(y);
        pdfG.push(pg);
        pdfT.push(pt);
        if (y >= SHEAR_THRESH) {
          const w = y === SHEAR_THRESH ? 0.5 : 1.0;
          pExtG += w * pg * dy;
          pExtT += w * pt * dy;
        }
      }
      // Integrate far right tail beyond yMax for high uObs
      for (let y = yMax + dy; y <= 90.0; y += 0.5) {
        pExtG += normalPdf(y, condMean, gaussCondSd) * 0.5;
        pExtT += studentTPdf(y, nuPost, condMean, tCondScale) * 0.5;
      }
      pExtG = clamp(pExtG * 100.0, 0.0, 100.0);
      pExtT = clamp(pExtT * 100.0, 0.0, 100.0);

      root.querySelector("#w6-m-gsd").textContent = gaussCondSd.toFixed(2) + " m/s/km";
      root.querySelector("#w6-m-tsd").textContent = tCondSd.toFixed(2) + " m/s/km";
      root.querySelector("#w6-m-tsdr").textContent = (tCondSd / gaussCondSd).toFixed(2) + "\u00D7 Gaussian SD";
      root.querySelector("#w6-m-gp").textContent = pExtG.toFixed(1) + "%";
      root.querySelector("#w6-m-tp").textContent = pExtT.toFixed(1) + "%";
      root.querySelector("#w6-m-tpr").textContent =
        pExtG > 0.15 ? (pExtT / pExtG).toFixed(2) + "\u00D7 Gaussian tail" : "Heavy-tail excess";

      if (typeof Plotly === "undefined") return;

      const leftTraces = [
        {
          x: gx,
          y: gy,
          name: "Gaussian Copula",
          mode: "markers",
          marker: { color: "rgba(29, 78, 216, 0.45)", size: 6.5 },
          hovertemplate: "10m Wind=%{x:.1f} m/s<br>500m Shear=%{y:.1f} m/s/km<extra>Gaussian</extra>"
        },
        {
          x: tx,
          y: ty,
          name: "Student-t (\u03BD=" + nu + ")",
          mode: "markers",
          marker: { color: "rgba(185, 28, 28, 0.52)", size: 6.5, symbol: "diamond" },
          hovertemplate: "10m Wind=%{x:.1f} m/s<br>500m Shear=%{y:.1f} m/s/km<extra>Student-t</extra>"
        }
      ];

      const leftLayout = baseLayout({
        height: 510,
        title: titleStyle("Joint Distribution: 10 m Pad Wind vs. 500 m Wind Shear"),
        xaxis: axisStyle({ title: "10 m Pad Wind (m/s)", range: [0, 22] }),
        yaxis: axisStyle({ title: "500 m Wind Shear (m/s/km)", range: [0, 38] }),
        shapes: [
          { type: "line", x0: uObs, x1: uObs, y0: 0, y1: 38, line: { color: ACCENT_AMBER, width: 2.6, dash: "dash" } },
          { type: "line", x0: 0, x1: 22, y0: SHEAR_THRESH, y1: SHEAR_THRESH, line: { color: "rgba(185, 28, 28, 0.55)", width: 1.8, dash: "dot" } }
        ],
        annotations: [
          { x: uObs, y: 36.2, text: "u_obs = " + uObs.toFixed(1), showarrow: false, font: { size: 14.5, color: ACCENT_AMBER }, bgcolor: "rgba(255,255,255,0.88)", borderpad: 2, xanchor: uObs > 15 ? "right" : "left", xshift: uObs > 15 ? -6 : 6 },
          { x: 0.6, y: SHEAR_THRESH + 0.9, xanchor: "left", text: "Extreme Shear (22 m/s/km)", showarrow: false, font: { size: 14.5, color: ACCENT_CRIMSON }, bgcolor: "rgba(255,255,255,0.88)", borderpad: 2 }
        ]
      });

      const peakPdf = Math.max(Math.max.apply(null, pdfG), Math.max.apply(null, pdfT));
      const rightTraces = [
        {
          x: ys,
          y: pdfG,
          name: "Gaussian | u_obs (\u03C3=" + gaussCondSd.toFixed(2) + ")",
          mode: "lines",
          line: { color: ACCENT_COBALT, width: 2.8 },
          fill: "tozeroy",
          fillcolor: "rgba(29, 78, 216, 0.18)",
          hovertemplate: "Shear=%{x:.1f} m/s/km<br>Gauss PDF=%{y:.4f}<extra></extra>"
        },
        {
          x: ys,
          y: pdfT,
          name: "Student-t | u_obs (\u03C3=" + tCondSd.toFixed(2) + ")",
          mode: "lines",
          line: { color: ACCENT_CRIMSON, width: 3.0 },
          fill: "tozeroy",
          fillcolor: "rgba(185, 28, 28, 0.18)",
          hovertemplate: "Shear=%{x:.1f} m/s/km<br>Student-t PDF=%{y:.4f}<extra></extra>"
        },
        {
          x: [SHEAR_THRESH, SHEAR_THRESH],
          y: [0, peakPdf * 1.06],
          name: "Extreme Threshold (22 m/s/km)",
          mode: "lines",
          line: { color: ACCENT_AMBER, width: 2.4, dash: "dash" }
        }
      ];

      const rightLayout = baseLayout({
        height: 510,
        title: titleStyle("Conditional 500 m Wind Shear PDF given u_obs = " + uObs.toFixed(1) + " m/s"),
        xaxis: axisStyle({ title: "500 m Wind Shear (m/s/km)", range: [0, 40] }),
        yaxis: axisStyle({ title: "Conditional Density", range: [0, peakPdf * 1.15] }),
        shapes: [
          { type: "rect", x0: SHEAR_THRESH, x1: 40, y0: 0, y1: peakPdf * 1.12, fillcolor: "rgba(185, 28, 28, 0.08)", line: { width: 0 } }
        ]
      });

      Plotly.react(root.querySelector("#w6-plot-left"), leftTraces, leftLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w6-plot-right"), rightTraces, rightLayout, PLOT_CONFIG);
    }

    [elUobs, elRho, elNu].forEach(function (el) {
      el.addEventListener("input", update);
    });
    root.querySelector("#w6-reset").addEventListener("click", function () {
      elUobs.value = defaults.uObs;
      elRho.value = defaults.rho;
      elNu.value = defaults.nu;
      update();
    });

    update();
  }

  // =========================================================================
  // Page-Aware Auto-Initialization (mounts only widgets present on page)
  // =========================================================================

  const WIDGET_REGISTRY = [
    { id: "widget-1-thermo", init: initWidget1 },
    { id: "widget-2-crps", init: initWidget2 },
    { id: "widget-3-router", init: initWidget3 },
    { id: "widget-4-schaake", init: initWidget4 },
    { id: "widget-5-mc", init: initWidget5 },
    { id: "widget-6-copula", init: initWidget6 }
  ];

  function initAllWidgets() {
    const present = [];
    for (let i = 0; i < WIDGET_REGISTRY.length; i++) {
      const entry = WIDGET_REGISTRY[i];
      const el = document.getElementById(entry.id);
      if (el && el.dataset.twInitialized !== "1") {
        present.push({ el: el, init: entry.init });
      }
    }
    if (present.length === 0) return;

    injectWidgetStyles();
    for (let i = 0; i < present.length; i++) {
      present[i].el.dataset.twInitialized = "1";
      present[i].init(present[i].el);
    }
  }

  window.initAllWidgets = initAllWidgets;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAllWidgets);
  } else {
    initAllWidgets();
  }
})();
