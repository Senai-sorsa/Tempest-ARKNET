/**
 * Tempest-ARKNET Interactive Sandboxes v4 (assets/widgets.js)
 * Self-contained Plotly.js + Vanilla JS module implementing ALL 8 sandboxes
 * in strict Carbon-Black & Dark Gray styling (strict neutral palette,
 * fixed 6px border-radius, 14.5-16px labels & ticks, 480-500px plots).
 *
 * Mount IDs (initialized ONLY when present on the current page):
 *   1. #widget-0-pipeline  (index.html)            — 5-Stage Launch Query Visual Simulator
 *   2. #widget-1-thermo    (01_data_physics.html)  — Atmosphere, T_v, Density & 44-Level Ladder
 *   3. #widget-2-crps      (02_ai_generator.html)  — Fair CRPS & Spread-Skill Explorer
 *   4. #widget-4-schaake   (03_calibration.html)   — Schaake Shuffle & Vertical Coherence
 *   5. #widget-7-metrics   (04_metrics.html)       — Interactive Visual Metric Scorecard
 *   6. #widget-3-router    (05_serving_launch.html)— Lead-Time & Live Obs Assimilation Router
 *   7. #widget-6-copula    (05_serving_launch.html)— Gaussian vs. Student-t Conditional Copula
 *   8. #widget-5-mc        (06_flight_mc.html)     — 6-DOF Rocket MC Dispersion & Attribution
 */
(function () {
  "use strict";

  // =========================================================================
  // Carbon-Dark Palette Constants & Shared Math Helpers
  // =========================================================================

  const PALETTE = {
    bgBase: "#09090b",
    bgSurface: "#111114",
    bgElevated: "#18181b",
    grid: "#27272a",
    borderStrong: "#3f3f46",
    inkPrimary: "#f4f4f5",
    inkBody: "#d4d4d8",
    inkMuted: "#a1a1aa",
    inkDim: "#71717a",
    sky: "#38bdf8",
    emerald: "#34d399",
    amber: "#fbbf24",
    coral: "#f87171"
  };

  const GRID_COLOR = "#27272a";
  const ZERO_COLOR = "#3f3f46";

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

  // =========================================================================
  // Self-Contained Carbon-Dark Widget Styles (Fixed 6px radius, no Tailwind)
  // =========================================================================

  function injectWidgetStyles() {
    if (document.getElementById("tempest-widget-styles")) return;
    const style = document.createElement("style");
    style.id = "tempest-widget-styles";
    style.textContent = `
      .tw-card {
        background: #111114;
        border: 1px solid #27272a;
        border-radius: 6px;
        padding: 1.65rem;
        color: #d4d4d8;
        font-family: 'DM Sans', system-ui, -apple-system, sans-serif;
        display: flex;
        flex-direction: column;
        gap: 1.25rem;
        container-type: inline-size;
        container-name: tw-widget;
      }
      .tw-head {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #27272a;
      }
      .tw-kicker {
        font-family: 'JetBrains Mono', ui-monospace, monospace;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #38bdf8;
        margin: 0 0 0.25rem;
      }
      .tw-title {
        font-family: 'Space Grotesk', system-ui, sans-serif;
        font-size: 1.28rem;
        font-weight: 700;
        color: #f4f4f5;
        margin: 0 0 0.3rem;
        line-height: 1.28;
      }
      .tw-sub {
        font-size: 0.94rem;
        color: #a1a1aa;
        margin: 0;
        line-height: 1.5;
      }
      .tw-actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.5rem;
      }
      .tw-row-wrap {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.5rem;
      }
      .tw-row-label {
        font-size: 0.88rem;
        font-weight: 600;
        color: #a1a1aa;
        margin-right: 0.25rem;
      }
      .tw-controls {
        display: grid;
        gap: 1rem;
      }
      .tw-cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .tw-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .tw-cols-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
      .tw-cols-5 { grid-template-columns: repeat(5, minmax(0, 1fr)); }
      .tw-cols-6 { grid-template-columns: repeat(6, minmax(0, 1fr)); }
      .tw-metrics {
        display: grid;
        gap: 0.75rem;
      }
      .tw-plots {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
      }
      .tw-control {
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 6px;
        padding: 0.75rem 0.9rem;
      }
      .tw-control-top {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 0.5rem;
        font-size: 0.92rem;
        color: #d4d4d8;
      }
      .tw-control-val {
        font-family: 'JetBrains Mono', ui-monospace, monospace;
        font-size: 0.92rem;
        font-weight: 600;
        color: #38bdf8;
        font-variant-numeric: tabular-nums;
        text-align: right;
      }
      .tw-slider {
        -webkit-appearance: none;
        appearance: none;
        width: 100%;
        height: 6px;
        border-radius: 6px;
        background: #27272a;
        outline: none;
        cursor: pointer;
        margin: 0.2rem 0;
      }
      .tw-slider::-webkit-slider-thumb {
        -webkit-appearance: none;
        appearance: none;
        width: 16px;
        height: 16px;
        border-radius: 6px;
        background: #38bdf8;
        border: 2px solid #09090b;
        cursor: pointer;
      }
      .tw-slider::-webkit-slider-thumb:hover {
        background: #f4f4f5;
      }
      .tw-slider::-moz-range-thumb {
        width: 16px;
        height: 16px;
        border-radius: 6px;
        background: #38bdf8;
        border: 2px solid #09090b;
        cursor: pointer;
      }
      .tw-metric {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 6px;
        padding: 0.75rem 0.9rem;
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
      }
      .tw-metric-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.4rem;
      }
      .tw-metric-lbl {
        font-size: 0.875rem;
        color: #a1a1aa;
        line-height: 1.3;
      }
      .tw-metric-val {
        font-family: 'JetBrains Mono', ui-monospace, monospace;
        font-size: 1.05rem;
        font-weight: 700;
        color: #f4f4f5;
        font-variant-numeric: tabular-nums;
        line-height: 1.3;
      }
      .tw-metric-sub {
        font-family: 'JetBrains Mono', ui-monospace, monospace;
        font-size: 0.875rem;
        color: #a1a1aa;
        font-variant-numeric: tabular-nums;
      }
      .tw-c-sky { color: #38bdf8 !important; }
      .tw-c-emerald { color: #34d399 !important; }
      .tw-c-amber { color: #fbbf24 !important; }
      .tw-c-coral { color: #f87171 !important; }
      .tw-c-primary { color: #f4f4f5 !important; }
      .tw-plot-box {
        background: #09090b;
        border: 1px solid #27272a;
        border-radius: 6px;
        padding: 0.5rem;
        min-height: 490px;
        min-width: 0;
        display: flex;
        flex-direction: column;
      }
      .tw-plot-box .status-empty {
        flex: 1 1 auto;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        gap: 0.5rem;
        padding: 2rem 1.5rem;
        background: #111114;
        border: 1px dashed #3f3f46;
        border-radius: 6px;
        color: #a1a1aa;
        font-size: 0.94rem;
        line-height: 1.55;
      }
      .tw-plot-box .tw-empty-title {
        color: #f4f4f5;
        font-family: 'Space Grotesk', system-ui, sans-serif;
        font-size: 1rem;
        font-weight: 700;
      }
      .tw-plot-box .tw-empty-body {
        margin: 0;
        max-width: 44ch;
        font-size: 0.9rem;
        color: #a1a1aa;
      }
      .tw-plot-col {
        display: flex;
        flex-direction: column;
        gap: 0.6rem;
        min-width: 0;
      }
      .tw-btn, .tw-preset-btn, .tw-stage-btn {
        background: #18181b;
        border: 1px solid #3f3f46;
        color: #d4d4d8;
        border-radius: 6px;
        padding: 0.48rem 0.88rem;
        font-family: 'DM Sans', system-ui, sans-serif;
        font-size: 0.88rem;
        font-weight: 600;
        cursor: pointer;
        transition: border-color 0.15s ease, color 0.15s ease, background-color 0.15s ease;
      }
      .tw-btn:hover, .tw-preset-btn:hover, .tw-stage-btn:hover {
        border-color: #38bdf8;
        color: #f4f4f5;
      }
      .tw-preset-btn.is-active, .tw-stage-btn.is-active {
        background: rgba(56, 189, 248, 0.14);
        border-color: #38bdf8;
        color: #38bdf8;
      }
      .tw-stage-bar {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 0.5rem;
      }
      .tw-stage-btn {
        text-align: left;
        padding: 0.65rem 0.8rem;
        display: flex;
        flex-direction: column;
        gap: 0.18rem;
      }
      .tw-stage-num {
        font-family: 'JetBrains Mono', ui-monospace, monospace;
        font-size: 0.875rem;
        color: #a1a1aa;
        text-transform: uppercase;
      }
      .tw-stage-btn.is-active .tw-stage-num {
        color: #38bdf8;
      }
      .tw-stage-name {
        font-size: 0.9rem;
        font-weight: 700;
        color: #f4f4f5;
        line-height: 1.25;
      }
      .tw-stage-btn.is-active .tw-stage-name {
        color: #38bdf8;
      }
      .tw-toggle-group {
        display: inline-flex;
        flex-wrap: wrap;
        background: #09090b;
        border: 1px solid #3f3f46;
        border-radius: 6px;
        padding: 3px;
        gap: 3px;
      }
      .tw-toggle-btn {
        padding: 0.42rem 0.85rem;
        font-family: 'DM Sans', system-ui, sans-serif;
        font-size: 0.875rem;
        font-weight: 600;
        border-radius: 6px;
        border: 1px solid transparent;
        cursor: pointer;
        color: #a1a1aa;
        background: transparent;
      }
      .tw-toggle-btn:hover {
        color: #f4f4f5;
      }
      .tw-toggle-btn.active-sky {
        background: rgba(56, 189, 248, 0.18);
        border-color: #38bdf8;
        color: #38bdf8;
      }
      .tw-toggle-btn.active-amber {
        background: rgba(251, 191, 36, 0.16);
        border-color: #fbbf24;
        color: #fbbf24;
      }
      .tw-toggle-btn.active-emerald {
        background: rgba(52, 211, 153, 0.16);
        border-color: #34d399;
        color: #34d399;
      }
      .tw-pill {
        display: inline-flex;
        align-items: center;
        border-radius: 6px;
        padding: 0.14rem 0.5rem;
        font-family: 'JetBrains Mono', ui-monospace, monospace;
        font-size: 0.875rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        white-space: nowrap;
      }
      .tw-pill-ok {
        background: rgba(52, 211, 153, 0.14);
        color: #34d399;
        border: 1px solid rgba(52, 211, 153, 0.45);
      }
      .tw-pill-warn {
        background: rgba(251, 191, 36, 0.14);
        color: #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.45);
      }
      .tw-pill-bad {
        background: rgba(248, 113, 113, 0.14);
        color: #f87171;
        border: 1px solid rgba(248, 113, 113, 0.45);
      }
      .tw-pill-sky {
        background: rgba(56, 189, 248, 0.14);
        color: #38bdf8;
        border: 1px solid rgba(56, 189, 248, 0.45);
      }
      .tw-banner {
        border-radius: 6px;
        padding: 0.65rem 0.9rem;
        font-size: 0.88rem;
        line-height: 1.45;
      }
      .tw-banner-ok {
        background: rgba(52, 211, 153, 0.10);
        border: 1px solid rgba(52, 211, 153, 0.35);
        color: #d4d4d8;
      }
      .tw-banner-amber {
        background: rgba(251, 191, 36, 0.10);
        border: 1px solid rgba(251, 191, 36, 0.35);
        color: #d4d4d8;
      }
      .tw-banner-neutral {
        background: #18181b;
        border: 1px solid #3f3f46;
        color: #d4d4d8;
      }
      .tw-takeaway {
        background: #18181b;
        border: 1px solid #3f3f46;
        border-radius: 6px;
        padding: 0.95rem 1.15rem;
        font-size: 0.96rem;
        line-height: 1.6;
        color: #d4d4d8;
      }
      .tw-takeaway strong {
        color: #f4f4f5;
      }
      .tw-callout {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 6px;
        padding: 0.9rem 1.1rem;
        font-size: 0.94rem;
        line-height: 1.6;
        color: #d4d4d8;
      }
      .tw-callout strong {
        color: #38bdf8;
      }
      .tw-note {
        background: #09090b;
        border: 1px solid #27272a;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        font-size: 0.88rem;
        line-height: 1.55;
        color: #a1a1aa;
      }
      .tw-decomp {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 6px;
        padding: 0.85rem 1rem;
        display: flex;
        flex-direction: column;
        gap: 0.6rem;
      }
      .tw-decomp-bar {
        width: 100%;
        height: 14px;
        border-radius: 6px;
        background: #09090b;
        border: 1px solid #27272a;
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
        justify-content: space-between;
        gap: 0.75rem;
        font-size: 0.875rem;
        color: #a1a1aa;
      }
      .tw-swatch {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 6px;
        vertical-align: middle;
        margin-right: 0.35rem;
      }
      @container tw-widget (max-width: 1099px) {
        .tw-plots { grid-template-columns: 1fr; }
        .tw-cols-5, .tw-cols-6 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .tw-stage-bar { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
      @container tw-widget (max-width: 720px) {
        .tw-cols-2, .tw-cols-3, .tw-cols-4, .tw-cols-5, .tw-cols-6 { grid-template-columns: 1fr; }
        .tw-stage-bar { grid-template-columns: 1fr; }
      }
      @media (max-width: 1100px) {
        .tw-plots { grid-template-columns: 1fr; }
        .tw-cols-5, .tw-cols-6 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .tw-stage-bar { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
      @media (max-width: 720px) {
        .tw-card { padding: 1.1rem; }
        .tw-cols-2, .tw-cols-3, .tw-cols-4, .tw-cols-5, .tw-cols-6 { grid-template-columns: 1fr; }
        .tw-stage-bar { grid-template-columns: 1fr; }
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
    const out = Object.assign(
      {
        gridcolor: GRID_COLOR,
        zerolinecolor: ZERO_COLOR,
        linecolor: "#3f3f46",
        tickfont: { size: 14.5, color: "#d4d4d8" },
        titlefont: { size: 15, color: "#f4f4f5" },
        automargin: true
      },
      overrides || {}
    );
    if (typeof out.title === "string" && out.title.length > 0) {
      out.title = {
        text: out.title,
        font: Object.assign({ size: 15, color: "#f4f4f5" }, out.titlefont || {})
      };
    } else if (out.title && typeof out.title === "object" && !out.title.font) {
      out.title = Object.assign({}, out.title, {
        font: Object.assign({ size: 15, color: "#f4f4f5" }, out.titlefont || {})
      });
    }
    return out;
  }

  function renderPlotlyUnavailable(root, plotEntries) {
    for (let i = 0; i < plotEntries.length; i++) {
      const entry = plotEntries[i];
      const el = root.querySelector(entry[0]);
      if (!el || el.querySelector(".status-empty")) continue;
      el.innerHTML =
        '<div class="status-empty" role="status" aria-live="polite">' +
          '<strong class="tw-empty-title">' + entry[1] + '</strong>' +
          '<p class="tw-empty-body">Interactive Plotly chart unavailable (Plotly.js not loaded). All controls and live metric readouts above remain active.</p>' +
        '</div>';
    }
  }

  function baseLayout(overrides) {
    const out = Object.assign(
      {
        height: 490,
        paper_bgcolor: "#09090b",
        plot_bgcolor: "#111114",
        font: {
          family: "DM Sans, system-ui, -apple-system, sans-serif",
          color: "#d4d4d8",
          size: 15
        },
        margin: { l: 74, r: 28, t: 62, b: 84 },
        hovermode: "closest",
        hoverlabel: {
          bgcolor: "#18181b",
          bordercolor: "#3f3f46",
          font: { size: 14.5, color: "#f4f4f5", family: "JetBrains Mono, monospace" }
        },
        legend: {
          orientation: "h",
          x: 0.5,
          xanchor: "center",
          y: -0.22,
          font: { size: 14.5, color: "#d4d4d8" },
          bgcolor: "rgba(9, 9, 11, 0)"
        }
      },
      overrides || {}
    );
    return out;
  }

  // =========================================================================
  // Exact 44-Level AGL Grid & Thermodynamic Constants
  // =========================================================================

  const HEIGHTS = [
    10, 50, 100, 150, 200, 300, 500, 750, 1000, 1250, 1500, 2000,
    2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000,
    8500, 9000, 9500, 10000, 10500, 11000, 11500, 12000, 12500, 13000, 13500, 14000,
    14500, 15000, 15500, 16000, 16500, 17000, 17500, 18000
  ];
  const HEIGHTS_KM = HEIGHTS.map(function (z) { return z / 1000.0; });

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

    const tv = tAll.slice();
    const pAll = new Array(n + 1);
    const qAll = new Array(n + 1);

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
    const tvSfc = tv[0];
    return { p, rho, a, q, tv: tvl, rhoSfc, aSfc, tvSfc };
  }

  // =========================================================================
  // WIDGET 0: 5-Stage Launch Query Visual Simulator (#widget-0-pipeline)
  // =========================================================================

  const W0_M = 24;
  const W0_DATA = (function () {
    const rng = makeRng(20261122);
    const L = HEIGHTS.length;

    const nwpMean = new Float64Array(L);
    const truthProf = new Float64Array(L);
    for (let k = 0; k < L; k++) {
      const z = HEIGHTS[k];
      nwpMean[k] =
        5.8 +
        4.6 * (1.0 - Math.exp(-z / 2200.0)) +
        19.5 * Math.exp(-0.5 * Math.pow((z - 11500.0) / 3100.0, 2));
      // True launch-day atmosphere has stronger pad breeze (9.8 m/s) & sharper 11.5 km jet
      truthProf[k] =
        nwpMean[k] +
        3.6 * Math.exp(-z / 1800.0) +
        4.2 * Math.exp(-0.5 * Math.pow((z - 11200.0) / 2400.0, 2)) +
        1.1 * Math.sin(z / 1900.0);
    }

    const engRaw = [];
    const calSchaake = [];
    const obsAssimilated = [];
    const mcFlight = [];

    for (let m = 0; m < W0_M; m++) {
      const cPbl = boxMuller(rng);
      const cJet = boxMuller(rng);
      const cAlt = boxMuller(rng);
      const cVeh = boxMuller(rng);

      const pRaw = new Float64Array(L);
      const pCal = new Float64Array(L);
      const pObs = new Float64Array(L);
      const pMc = new Float64Array(L);

      for (let k = 0; k < L; k++) {
        const z = HEIGHTS[k];
        const wPbl = Math.exp(-z / 2400.0);
        const wJet = Math.exp(-0.5 * Math.pow((z - 11500.0) / 3600.0, 2));
        const wAlt = ((z - 11500.0) / 4200.0) * wJet;
        const jitter = boxMuller(rng);

        // Stage 2: Raw Engression — realistic jet fan but slightly narrow (0.72x) & slightly jagged
        const baseSpread = 1.9 + 1.4 * (1.0 - Math.exp(-z / 3000.0)) + 4.8 * wJet;
        pRaw[k] = Math.max(
          0.5,
          nwpMean[k] + 0.72 * baseSpread * (0.58 * wJet * cJet + 0.48 * wPbl * cPbl + 0.35 * jitter)
        );

        // Stage 3: Balloon Cal + Schaake — calibrated honest spread (1.05x) & smooth coherent vertical shear
        pCal[k] = Math.max(
          0.5,
          nwpMean[k] +
            0.9 * wPbl +
            1.08 * baseSpread * (0.68 * wJet * cJet + 0.38 * wAlt * cAlt + 0.62 * wPbl * cPbl)
        );

        // Stage 4: Launch-Day Obs — pad sensor (9.8 m/s, age 0.5h, d=1 km -> gain ~0.92) pulls 0-3 km toward truth
        const obsGainZ = 0.88 * Math.exp(-z / 2100.0);
        const pullMean = obsGainZ * (truthProf[k] - nwpMean[k] - 0.9 * wPbl);
        const shrinkSd = Math.sqrt(Math.max(1.0 - obsGainZ * 0.78, 0.22));
        pObs[k] = Math.max(
          0.5,
          nwpMean[k] +
            0.9 * wPbl +
            pullMean +
            1.08 * baseSpread * shrinkSd * (0.68 * wJet * cJet + 0.38 * wAlt * cAlt + 0.62 * wPbl * cPbl)
        );

        // Stage 5: 6-DOF Flight Dispersion — Obs-assimilated profile + Dryden micro-gust realization
        pMc[k] = Math.max(0.5, pObs[k] + (0.65 + 0.55 * wPbl) * jitter);
      }

      engRaw.push({ prof: pRaw, cVeh: cVeh });
      calSchaake.push({ prof: pCal, cVeh: cVeh });
      obsAssimilated.push({ prof: pObs, cVeh: cVeh });
      mcFlight.push({ prof: pMc, cVeh: cVeh });
    }

    function simFlight(prof, cVeh, includeVeh) {
      // Mean 0-300m wind and 3-18km wind
      let wBl = 0.0, nBl = 0, wJet = 0.0, nJet = 0;
      for (let k = 0; k < L; k++) {
        if (HEIGHTS[k] <= 300) { wBl += prof[k]; nBl++; }
        if (HEIGHTS[k] >= 3000) { wJet += prof[k]; nJet++; }
      }
      wBl /= nBl;
      wJet /= nJet;
      const vehApo = includeVeh ? 420.0 * cVeh : 0.0;
      const vehDrift = includeVeh ? 210.0 * cVeh : 0.0;
      const apogee = 9180.0 - 48.0 * (wBl - 6.0) - 9.0 * (wJet - 16.0) + vehApo;
      const drift = 180.0 + 112.0 * wBl + 16.5 * wJet + vehDrift;
      return { apogee: apogee, drift: drift };
    }

    const truthFlight = simFlight(truthProf, 0.25, true);

    return { nwpMean, truthProf, engRaw, calSchaake, obsAssimilated, mcFlight, simFlight, truthFlight };
  })();

  function initWidget0() {
    const root = document.getElementById("widget-0-pipeline");
    if (!root) return;

    const WAIVER_M = 1500;
    const stages = [
      {
        id: 1,
        short: "1. Raw NWP",
        label: "Stage 1: Raw Deterministic NWP",
        spreadTxt: "0.0 m/s (single line)",
        statusPill: '<span class="tw-pill tw-pill-bad">Zero Uncertainty</span>',
        takeaway:
          "<strong>Takeaway:</strong> A single NWP forecast gives one smooth wind profile and one optimistic landing point, hiding all tail risk. When launch-day pad winds run 3.6 m/s stronger than forecast, the real rocket lands far outside the single predicted dot."
      },
      {
        id: 2,
        short: "2. Engression Fan",
        label: "Stage 2: Engression Generative Fan",
        spreadTxt: "Raw AI fan (~0.72\u00D7)",
        statusPill: '<span class="tw-pill tw-pill-warn">Uncalibrated</span>',
        takeaway:
          "<strong>Takeaway:</strong> Single-step Engression injects noise z_\u03B5 to generate a full 44-level ensemble in milliseconds instead of a single mean. However, raw AI profiles are slightly under-dispersed and still show layer-to-layer shear roughness."
      },
      {
        id: 3,
        short: "3. Balloon Cal + Schaake",
        label: "Stage 3: Balloon Calibration + Schaake Shuffle",
        spreadTxt: "Honest 10\u201390% fan",
        statusPill: '<span class="tw-pill tw-pill-sky">Calibrated Prior</span>',
        takeaway:
          "<strong>Takeaway:</strong> IGRAv2 weather-balloon quantile calibration restores honest spread across every altitude, while the Schaake Shuffle re-orders ranks onto ERA5 vertical templates so wind shear stays physically smooth without changing any marginal distribution."
      },
      {
        id: 4,
        short: "4. Launch-Day Obs",
        label: "Stage 4: Live Pad & METAR Assimilation",
        spreadTxt: "Tightened 0\u20133 km PBL",
        statusPill: '<span class="tw-pill tw-pill-ok">Obs-Updated</span>',
        takeaway:
          "<strong>Takeaway:</strong> Inside T\u221224 h, a live pad anemometer reading (9.8 m/s, \u03C4_h = 6.3 h) shifts the 0\u20133 km boundary layer directly onto reality and trims low-altitude variance. The predicted landing cluster immediately moves downwind to bracket the true impact."
      },
      {
        id: 5,
        short: "5. 6-DOF Flight Dispersion",
        label: "Stage 5: Coupled 6-DOF Monte Carlo + Dryden",
        spreadTxt: "Full Atmos + Vehicle",
        statusPill: '<span class="tw-pill tw-pill-ok">Go / No-Go Ready</span>',
        takeaway:
          "<strong>Takeaway:</strong> Passing every calibrated, obs-updated profile with Dryden gusts and vehicle drag/thrust variance through the 6-DOF solver yields actionable apogee intervals and exact waiver-breach probability for launch control."
      }
    ];

    let activeStage = 1;

    root.innerHTML = `
      <div class="tw-card">
        <div class="tw-head">
          <div>
            <div class="tw-kicker">Interactive Pipeline Simulator</div>
            <h4 class="tw-title">5-Stage Launch Query Visual Simulator</h4>
            <p class="tw-sub">Click each stage to watch how Tempest-ARKNET transforms a single coarse NWP profile into a calibrated, launch-day 6-DOF dispersion cloud.</p>
          </div>
          <div class="tw-actions">
            <button type="button" id="w0-prev" class="tw-btn">&larr; Prev Stage</button>
            <button type="button" id="w0-next" class="tw-btn">Next Stage &rarr;</button>
          </div>
        </div>

        <div class="tw-stage-bar" role="tablist" aria-label="Pipeline stages">
          ${stages.map(function (s) {
            return `<button type="button" data-stage="${s.id}" class="tw-stage-btn${s.id === 1 ? " is-active" : ""}">
              <span class="tw-stage-num">Stage ${s.id}</span>
              <span class="tw-stage-name">${s.short.replace(/^\d+\.\s*/, "")}</span>
            </button>`;
          }).join("")}
        </div>

        <div class="tw-metrics tw-cols-4">
          <div class="tw-metric">
            <div class="tw-metric-top">
              <span class="tw-metric-lbl">Active Stage</span>
              <span id="w0-pill"></span>
            </div>
            <div id="w0-m-stage" class="tw-metric-val tw-c-sky">--</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Profile Ensemble State</div>
            <div id="w0-m-spread" class="tw-metric-val tw-c-primary">--</div>
            <div class="tw-metric-sub">44 AGL levels (10 m &ndash; 18 km)</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Predicted Apogee (90%)</div>
            <div id="w0-m-apo" class="tw-metric-val tw-c-emerald">--</div>
            <div class="tw-metric-sub">True apogee: ${Math.round(W0_DATA.truthFlight.apogee).toLocaleString()} m</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Waiver Breach Risk (&gt;1.5 km)</div>
            <div id="w0-m-risk" class="tw-metric-val tw-c-amber">--</div>
            <div class="tw-metric-sub">True drift: ${Math.round(W0_DATA.truthFlight.drift).toLocaleString()} m</div>
          </div>
        </div>

        <div class="tw-plots">
          <div id="w0-plot-left" class="tw-plot-box"></div>
          <div id="w0-plot-right" class="tw-plot-box"></div>
        </div>

        <div id="w0-takeaway" class="tw-takeaway"></div>
      </div>
    `;

    const stageBtns = Array.from(root.querySelectorAll("[data-stage]"));

    function renderStage(id) {
      activeStage = clamp(id, 1, 5);
      const st = stages[activeStage - 1];

      stageBtns.forEach(function (b) {
        b.classList.toggle("is-active", parseInt(b.getAttribute("data-stage"), 10) === activeStage);
      });

      root.querySelector("#w0-pill").innerHTML = st.statusPill;
      root.querySelector("#w0-m-stage").textContent = st.short;
      root.querySelector("#w0-m-spread").textContent = st.spreadTxt;
      root.querySelector("#w0-takeaway").innerHTML = st.takeaway;

      const leftTraces = [];
      let flights = [];

      if (activeStage === 1) {
        leftTraces.push({
          x: Array.from(W0_DATA.nwpMean),
          y: HEIGHTS_KM,
          mode: "lines",
          name: "Raw NWP Deterministic",
          line: { color: "#38bdf8", width: 3.2 },
          hovertemplate: "z=%{y:.2f} km<br>NWP=%{x:.1f} m/s<extra></extra>"
        });
        flights = [W0_DATA.simFlight(W0_DATA.nwpMean, 0.0, false)];
      } else {
        const pool =
          activeStage === 2
            ? W0_DATA.engRaw
            : activeStage === 3
              ? W0_DATA.calSchaake
              : activeStage === 4
                ? W0_DATA.obsAssimilated
                : W0_DATA.mcFlight;
        const includeVeh = activeStage === 5;
        const fanColor =
          activeStage === 2
            ? "rgba(251, 191, 36, 0.30)"
            : activeStage === 3
              ? "rgba(56, 189, 248, 0.28)"
              : activeStage === 4
                ? "rgba(52, 211, 153, 0.32)"
                : "rgba(56, 189, 248, 0.34)";
        const hiColor =
          activeStage === 2 ? "#fbbf24" : activeStage === 4 ? "#34d399" : "#38bdf8";

        for (let m = 0; m < W0_M; m++) {
          const prof = pool[m].prof;
          leftTraces.push({
            x: Array.from(prof),
            y: HEIGHTS_KM,
            mode: "lines",
            line: { color: m === 0 ? hiColor : fanColor, width: m === 0 ? 2.6 : 1.3 },
            showlegend: m === 0,
            name: activeStage === 5 ? "Coupled + Dryden Fan (24)" : "Ensemble Fan (24)",
            hoverinfo: m === 0 ? "x+y" : "skip"
          });
          flights.push(W0_DATA.simFlight(prof, pool[m].cVeh, includeVeh));
        }
      }

      // Always overlay launch-day balloon truth on left panel
      leftTraces.push({
        x: Array.from(W0_DATA.truthProf),
        y: HEIGHTS_KM,
        mode: "lines",
        name: "Launch-Day Truth",
        line: { color: "#f87171", width: 2.8, dash: "dash" },
        hovertemplate: "z=%{y:.2f} km<br>Truth=%{x:.1f} m/s<extra></extra>"
      });

      if (activeStage >= 4) {
        leftTraces.push({
          x: [W0_DATA.truthProf[0]],
          y: [0.05],
          mode: "markers",
          name: "Live Pad Obs (9.8 m/s)",
          marker: { color: "#fbbf24", size: 12, symbol: "diamond", line: { color: "#09090b", width: 1.5 } },
          hovertemplate: "Pad Sensor: %{x:.1f} m/s<extra></extra>"
        });
      }

      const apos = flights.map(function (f) { return f.apogee; }).sort(function (a, b) { return a - b; });
      const breachCount = flights.filter(function (f) { return f.drift > WAIVER_M; }).length;
      const breachPct = (100.0 * breachCount) / flights.length;

      if (flights.length === 1) {
        root.querySelector("#w0-m-apo").textContent = Math.round(apos[0]).toLocaleString() + " m (point)";
      } else {
        const q05 = quantileSorted(apos, 0.05);
        const q95 = quantileSorted(apos, 0.95);
        root.querySelector("#w0-m-apo").textContent =
          Math.round(q05).toLocaleString() + "\u2013" + Math.round(q95).toLocaleString() + " m";
      }

      const elRisk = root.querySelector("#w0-m-risk");
      elRisk.textContent = breachPct.toFixed(0) + "% (" + breachCount + "/" + flights.length + ")";
      elRisk.className =
        "tw-metric-val " + (activeStage === 1 ? "tw-c-coral" : breachPct > 25 ? "tw-c-amber" : "tw-c-emerald");

      if (typeof Plotly === "undefined") {
        renderPlotlyUnavailable(root, [
          ["#w0-plot-left", "0\u201318 km Wind Profile Ensemble Fan"],
          ["#w0-plot-right", "Predicted Rocket Apogee vs. Landing Drift"]
        ]);
        return;
      }

      const leftShapes = [];
      const leftAnn = [];
      if (activeStage === 4) {
        leftShapes.push({
          type: "rect",
          xref: "paper",
          x0: 0,
          x1: 1,
          y0: 0,
          y1: 3.0,
          fillcolor: "rgba(52, 211, 153, 0.08)",
          line: { color: "rgba(52, 211, 153, 0.35)", width: 1, dash: "dot" }
        });
        leftAnn.push({
          xref: "paper",
          x: 0.98,
          y: 2.7,
          xanchor: "right",
          text: "0\u20133 km obs-assimilated zone",
          showarrow: false,
          font: { size: 14, color: "#34d399" }
        });
      }

      const leftLayout = baseLayout({
        title: { text: "0\u201318 km Wind Profile Ensemble Fan", font: { size: 16, color: "#f4f4f5" }, y: 0.97 },
        xaxis: axisStyle({ title: "Wind Speed (m/s)", range: [0, 42] }),
        yaxis: axisStyle({ title: "Altitude (km AGL)", range: [0, 18.2] }),
        shapes: leftShapes,
        annotations: leftAnn
      });

      const inPtsX = [], inPtsY = [], outPtsX = [], outPtsY = [];
      for (let i = 0; i < flights.length; i++) {
        if (flights[i].drift <= WAIVER_M) {
          inPtsX.push(flights[i].drift);
          inPtsY.push(flights[i].apogee);
        } else {
          outPtsX.push(flights[i].drift);
          outPtsY.push(flights[i].apogee);
        }
      }

      const rightTraces = [
        {
          x: inPtsX,
          y: inPtsY,
          mode: "markers",
          name: "Inside Waiver (\u22641.5 km)",
          marker: { color: "#34d399", size: activeStage === 1 ? 13 : 9.5, line: { color: "#09090b", width: 1 } },
          hovertemplate: "Drift=%{x:.0f} m<br>Apogee=%{y:.0f} m<extra>Inside</extra>"
        },
        {
          x: outPtsX,
          y: outPtsY,
          mode: "markers",
          name: "Outside Waiver (>1.5 km)",
          marker: { color: "#f87171", size: 10, symbol: "x", line: { width: 2 } },
          hovertemplate: "Drift=%{x:.0f} m<br>Apogee=%{y:.0f} m<extra>Breach</extra>"
        },
        {
          x: [W0_DATA.truthFlight.drift],
          y: [W0_DATA.truthFlight.apogee],
          mode: "markers",
          name: "Actual Launch Flight",
          marker: { color: "#fbbf24", size: 14, symbol: "star", line: { color: "#09090b", width: 1 } },
          hovertemplate: "Actual Drift=%{x:.0f} m<br>Actual Apogee=%{y:.0f} m<extra>Truth</extra>"
        }
      ];

      const rightLayout = baseLayout({
        title: { text: "Predicted Rocket Apogee vs. Landing Drift", font: { size: 16, color: "#f4f4f5" }, y: 0.97 },
        xaxis: axisStyle({ title: "Downrange Landing Drift (m)", range: [600, 2300] }),
        yaxis: axisStyle({ title: "Predicted Apogee (m AGL)", range: [8100, 10200] }),
        shapes: [
          {
            type: "line",
            x0: WAIVER_M,
            x1: WAIVER_M,
            y0: 8100,
            y1: 10200,
            line: { color: "#fbbf24", width: 2.2, dash: "dash" }
          }
        ],
        annotations: [
          {
            x: WAIVER_M,
            y: 10120,
            xanchor: "right",
            xshift: -6,
            text: "1,500 m Waiver Limit",
            showarrow: false,
            font: { size: 14, color: "#fbbf24" }
          }
        ]
      });

      Plotly.react(root.querySelector("#w0-plot-left"), leftTraces, leftLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w0-plot-right"), rightTraces, rightLayout, PLOT_CONFIG);
    }

    stageBtns.forEach(function (b) {
      b.addEventListener("click", function () {
        renderStage(parseInt(b.getAttribute("data-stage"), 10));
      });
    });
    root.querySelector("#w0-prev").addEventListener("click", function () {
      renderStage(activeStage > 1 ? activeStage - 1 : 5);
    });
    root.querySelector("#w0-next").addEventListener("click", function () {
      renderStage(activeStage < 5 ? activeStage + 1 : 1);
    });

    renderStage(1);
  }

  // =========================================================================
  // WIDGET 1: Atmosphere, T_v, Density & 44-Level Ladder (#widget-1-thermo)
  // =========================================================================

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

  function initWidget1() {
    const root = document.getElementById("widget-1-thermo");
    if (!root) return;

    const defaults = { dz: 0, t2m: 298, lnd: 2.5, jet: 28 };
    const presets = {
      spaceport: { dz: 450, t2m: 308, lnd: 3.1, jet: 22 },
      coldfront: { dz: 0, t2m: 278, lnd: 1.4, jet: 48 },
      sealevel: { dz: -500, t2m: 296, lnd: 0.4, jet: 18 }
    };

    root.innerHTML = `
      <div class="tw-card">
        <div class="tw-head">
          <div>
            <div class="tw-kicker">Interactive Sandbox 1</div>
            <h4 class="tw-title">Atmosphere, Virtual Temperature, Density &amp; 44-Level Ladder</h4>
            <p class="tw-sub">44-level AGL 2-pass hypsometric column (<code>thermo.py</code>) with moist virtual temperature <code>T_v</code> and site elevation shift <code>e<sup>&minus;z/1500</sup></code>.</p>
          </div>
          <button type="button" id="w1-reset" class="tw-btn">Reset Defaults</button>
        </div>

        <div class="tw-row-wrap">
          <span class="tw-row-label">Presets:</span>
          <button type="button" data-preset="spaceport" class="tw-preset-btn">Spaceport Hot Afternoon (+450 m, 308 K)</button>
          <button type="button" data-preset="coldfront" class="tw-preset-btn">Cold Front Jet (0 m, 278 K, 48 m/s)</button>
          <button type="button" data-preset="sealevel" class="tw-preset-btn">Humid Sea-Level Pad (&minus;500 m, lnd 0.4)</button>
        </div>

        <div class="tw-controls tw-cols-4">
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Site Elevation Shift &Delta;z</span>
              <span id="w1-dz-val" class="tw-control-val">0 m</span>
            </div>
            <input id="w1-dz" type="range" min="-600" max="600" step="10" value="${defaults.dz}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Surface Temp T<sub>2m</sub></span>
              <span id="w1-t2m-val" class="tw-control-val">298.0 K</span>
            </div>
            <input id="w1-t2m" type="range" min="265" max="315" step="0.5" value="${defaults.t2m}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Log Dewpoint Dep. lnd</span>
              <span id="w1-lnd-val" class="tw-control-val">2.50</span>
            </div>
            <input id="w1-lnd" type="range" min="0.0" max="4.0" step="0.05" value="${defaults.lnd}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Jet-Stream Peak Wind</span>
              <span id="w1-jet-val" class="tw-control-val">28 m/s</span>
            </div>
            <input id="w1-jet" type="range" min="5" max="50" step="1" value="${defaults.jet}" class="tw-slider" />
          </label>
        </div>

        <div class="tw-metrics tw-cols-6">
          <div class="tw-metric">
            <div class="tw-metric-lbl">Pad Pressure</div>
            <div id="w1-m-p" class="tw-metric-val tw-c-primary">--</div>
            <div id="w1-d-p" class="tw-metric-sub">&Delta;p: --</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Pad Density &rho;<sub>sfc</sub></div>
            <div id="w1-m-rho" class="tw-metric-val tw-c-emerald">--</div>
            <div id="w1-d-rho" class="tw-metric-sub">&Delta;&rho;: --</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Density Altitude</div>
            <div id="w1-m-da" class="tw-metric-val tw-c-coral">--</div>
            <div id="w1-d-da" class="tw-metric-sub">&Delta;DA: --</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Virtual Temp T<sub>v</sub></div>
            <div id="w1-m-tv" class="tw-metric-val tw-c-amber">--</div>
            <div id="w1-d-tv" class="tw-metric-sub">T<sub>v</sub>&minus;T: --</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Speed of Sound a<sub>sfc</sub></div>
            <div id="w1-m-a" class="tw-metric-val tw-c-sky">--</div>
            <div id="w1-m-rh" class="tw-metric-sub">RH: --</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Max Wind Shear</div>
            <div id="w1-m-shear" class="tw-metric-val tw-c-coral">--</div>
            <div class="tw-metric-sub">Vector |dV/dz|</div>
          </div>
        </div>

        <div class="tw-plots">
          <div id="w1-plot-left" class="tw-plot-box"></div>
          <div id="w1-plot-right" class="tw-plot-box"></div>
        </div>

        <div class="tw-callout">
          <strong>Predict &rarr; Test:</strong> Click <em>Spaceport Hot Afternoon</em> and check whether the +450 m pad elevation shift still changes temperature above <strong>4.0 km AGL</strong>, then switch to <em>Humid Sea-Level Pad</em> to see moist <code>T<sub>v</sub> &minus; T</code> jump above +2 K.
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
      { type: "line", xref: "paper", x0: 0, x1: 1, y0: 1.5, y1: 1.5, line: { color: "rgba(56,189,248,0.5)", width: 1.4, dash: "dash" } },
      { type: "line", xref: "paper", x0: 0, x1: 1, y0: 4.0, y1: 4.0, line: { color: "rgba(251,191,36,0.5)", width: 1.4, dash: "dash" } },
      { type: "line", xref: "paper", x0: 0, x1: 1, y0: 13.5, y1: 13.5, line: { color: "rgba(161,161,170,0.55)", width: 1.4, dash: "dash" } }
    ];

    const refAnnotations = [
      { xref: "paper", x: 0.99, y: 1.5, xanchor: "right", yanchor: "bottom", text: "1.5 km (1/e shift)", showarrow: false, font: { size: 14, color: "#38bdf8" } },
      { xref: "paper", x: 0.99, y: 4.0, xanchor: "right", yanchor: "bottom", text: "4.0 km (fade-out)", showarrow: false, font: { size: 14, color: "#fbbf24" } },
      { xref: "paper", x: 0.99, y: 13.5, xanchor: "right", yanchor: "bottom", text: "13.5 km (tropopause)", showarrow: false, font: { size: 14, color: "#a1a1aa" } }
    ];

    function update() {
      const dz = parseFloat(elDz.value);
      const t2m = parseFloat(elT2m.value);
      const lnd = parseFloat(elLnd.value);
      const jet = parseFloat(elJet.value);

      const dpdC = dpdFromLnd(lnd);
      root.querySelector("#w1-dz-val").textContent = (dz > 0 ? "+" : "") + dz + " m";
      root.querySelector("#w1-t2m-val").textContent = t2m.toFixed(1) + " K";
      root.querySelector("#w1-lnd-val").textContent = lnd.toFixed(2) + " (" + dpdC.toFixed(1) + " \u00B0C)";
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
      const tvDiff = siteThermo.tvSfc - siteCol.t2m;

      root.querySelector("#w1-m-p").textContent = (siteCol.ps / 100.0).toFixed(1) + " hPa";
      root.querySelector("#w1-d-p").textContent = "\u0394p: " + formatSigned(dpHpa, 1, " hPa");
      root.querySelector("#w1-m-rho").textContent = siteThermo.rhoSfc.toFixed(4) + " kg/m\u00B3";
      root.querySelector("#w1-d-rho").textContent = "\u0394\u03C1: " + formatSigned(dRho, 4, "");
      root.querySelector("#w1-m-da").textContent = Math.round(daSite).toLocaleString() + " m";
      root.querySelector("#w1-d-da").textContent = "\u0394DA: " + formatSigned(Math.round(dDa), 0, " m");
      root.querySelector("#w1-m-tv").textContent = siteThermo.tvSfc.toFixed(2) + " K";
      root.querySelector("#w1-d-tv").textContent = "T_v\u2212T: +" + tvDiff.toFixed(2) + " K";
      root.querySelector("#w1-m-a").textContent = siteThermo.aSfc.toFixed(1) + " m/s";
      root.querySelector("#w1-m-rh").textContent = "RH: " + siteCol.rh2m.toFixed(1) + "%";
      root.querySelector("#w1-m-shear").textContent = gridCol.maxShearMsKm.toFixed(1) + " m/s/km";

      if (typeof Plotly === "undefined") {
        renderPlotlyUnavailable(root, [
          ["#w1-plot-left", "Temperature & Relative Humidity (44 AGL Levels)"],
          ["#w1-plot-right", "Hypsometric Air Density & Wind Profile"]
        ]);
        return;
      }

      const leftTraces = [
        {
          x: gridCol.T,
          y: HEIGHTS_KM,
          name: "T Grid (K)",
          mode: "lines",
          line: { color: "#a1a1aa", width: 2.0, dash: "dot" },
          xaxis: "x",
          hovertemplate: "T_grid: %{x:.1f} K<extra></extra>"
        },
        {
          x: siteCol.T,
          y: HEIGHTS_KM,
          name: "T Site (K)",
          mode: "lines",
          line: { color: "#fbbf24", width: 2.8 },
          xaxis: "x",
          hovertemplate: "T_site: %{x:.1f} K<extra></extra>"
        },
        {
          x: gridCol.rh,
          y: HEIGHTS_KM,
          name: "RH Grid (%)",
          mode: "lines",
          line: { color: "#38bdf8", width: 1.8, dash: "dot" },
          xaxis: "x2",
          hovertemplate: "RH_grid: %{x:.1f}%<extra></extra>"
        },
        {
          x: siteCol.rh,
          y: HEIGHTS_KM,
          name: "RH Site (%)",
          mode: "lines",
          line: { color: "#38bdf8", width: 2.8 },
          xaxis: "x2",
          hovertemplate: "RH_site: %{x:.1f}%<extra></extra>"
        }
      ];

      const leftLayout = baseLayout({
        title: { text: "Temperature & Relative Humidity (44 AGL Levels)", font: { size: 16, color: "#f4f4f5" }, y: 0.99 },
        margin: { l: 74, r: 24, t: 88, b: 86 },
        hovermode: "y unified",
        yaxis: axisStyle({ title: "Altitude (km AGL)", range: [0, 18.2] }),
        xaxis: axisStyle({ title: "Temperature (K)", range: [195, 325], titlefont: { size: 15, color: "#fbbf24" }, tickfont: { size: 14.5, color: "#fbbf24" } }),
        xaxis2: axisStyle({ title: "Relative Humidity (%)", overlaying: "x", side: "top", range: [0, 105], showgrid: false, titlefont: { size: 15, color: "#38bdf8" }, tickfont: { size: 14.5, color: "#38bdf8" } }),
        shapes: refShapes,
        annotations: refAnnotations
      });

      const rightTraces = [
        {
          x: gridThermo.rho,
          y: HEIGHTS_KM,
          name: "\u03C1 Grid (kg/m\u00B3)",
          mode: "lines",
          line: { color: "#a1a1aa", width: 2.0, dash: "dot" },
          xaxis: "x",
          hovertemplate: "\u03C1_grid: %{x:.4f} kg/m\u00B3<extra></extra>"
        },
        {
          x: siteThermo.rho,
          y: HEIGHTS_KM,
          name: "\u03C1 Site (kg/m\u00B3)",
          mode: "lines",
          line: { color: "#34d399", width: 2.8 },
          xaxis: "x",
          hovertemplate: "\u03C1_site: %{x:.4f} kg/m\u00B3<extra></extra>"
        },
        {
          x: gridCol.ws,
          y: HEIGHTS_KM,
          name: "Wind Speed (m/s)",
          mode: "lines",
          line: { color: "#f87171", width: 2.8 },
          xaxis: "x2",
          hovertemplate: "Wind: %{x:.1f} m/s<extra></extra>"
        }
      ];

      const rightLayout = baseLayout({
        title: { text: "Hypsometric Air Density & Wind Profile", font: { size: 16, color: "#f4f4f5" }, y: 0.99 },
        margin: { l: 74, r: 24, t: 88, b: 86 },
        hovermode: "y unified",
        yaxis: axisStyle({ title: "Altitude (km AGL)", range: [0, 18.2] }),
        xaxis: axisStyle({ title: "Air Density (kg/m\u00B3)", range: [0, 1.35], titlefont: { size: 15, color: "#34d399" }, tickfont: { size: 14.5, color: "#34d399" } }),
        xaxis2: axisStyle({ title: "Wind Speed (m/s)", overlaying: "x", side: "top", range: [0, 56], showgrid: false, titlefont: { size: 15, color: "#f87171" }, tickfont: { size: 14.5, color: "#f87171" } }),
        shapes: refShapes,
        annotations: refAnnotations
      });

      Plotly.react(root.querySelector("#w1-plot-left"), leftTraces, leftLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w1-plot-right"), rightTraces, rightLayout, PLOT_CONFIG);
    }

    [elDz, elT2m, elLnd, elJet].forEach(function (el) { el.addEventListener("input", update); });
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
  // WIDGET 2: Almost-Fair CRPS & Spread-Skill Explorer (#widget-2-crps)
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
    if (status === "under") return '<span class="tw-pill tw-pill-bad">Under</span>';
    return '<span class="tw-pill tw-pill-warn">Over</span>';
  }

  function initWidget2() {
    const root = document.getElementById("widget-2-crps");
    if (!root) return;

    const defaults = { m: 20, alpha: 0.95, spread: 0.85, f: 1.25 };
    const presets = {
      under: { m: 24, alpha: 0.95, spread: 0.55, f: 1.00 },
      repaired: { m: 24, alpha: 0.95, spread: 1.00, f: 1.60 },
      smallm: { m: 4, alpha: 0.80, spread: 1.00, f: 1.00 }
    };

    root.innerHTML = `
      <div class="tw-card">
        <div class="tw-head">
          <div>
            <div class="tw-kicker">Interactive Sandbox 2</div>
            <h4 class="tw-title">Fair CRPS &amp; Spread-Skill Explorer</h4>
            <p class="tw-sub">Live <code>afcrps(&alpha;)</code> fit-vs-spread decomposition, <code>q05/q95</code> outer-tail hinges, and PIT rank uniformity across 400 synthetic cases.</p>
          </div>
          <button type="button" id="w2-reset" class="tw-btn">Reset Defaults</button>
        </div>

        <div class="tw-row-wrap">
          <span class="tw-row-label">Presets:</span>
          <button type="button" data-preset="under" class="tw-preset-btn">Under-Dispersed (m=24, 0.55&times;)</button>
          <button type="button" data-preset="repaired" class="tw-preset-btn">Heavy-Tail Repaired (m=24, f=1.6&times;)</button>
          <button type="button" data-preset="smallm" class="tw-preset-btn">Small-Ensemble Bias (m=4, &alpha;=0.80)</button>
        </div>

        <div class="tw-controls tw-cols-4">
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Ensemble Size m</span>
              <span id="w2-m-val" class="tw-control-val">20</span>
            </div>
            <input id="w2-m" type="range" min="4" max="32" step="1" value="${defaults.m}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Fairness &alpha;</span>
              <span id="w2-alpha-val" class="tw-control-val">0.95</span>
            </div>
            <input id="w2-alpha" type="range" min="0.80" max="1.00" step="0.01" value="${defaults.alpha}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Raw Spread Multiplier</span>
              <span id="w2-spread-val" class="tw-control-val">0.85&times;</span>
            </div>
            <input id="w2-spread" type="range" min="0.40" max="2.00" step="0.05" value="${defaults.spread}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Far-Tail Stretch f</span>
              <span id="w2-f-val" class="tw-control-val">1.25&times;</span>
            </div>
            <input id="w2-f" type="range" min="0.80" max="2.50" step="0.05" value="${defaults.f}" class="tw-slider" />
          </label>
        </div>

        <div class="tw-metrics tw-cols-5">
          <div class="tw-metric">
            <div class="tw-metric-lbl">afCRPS (&alpha;)</div>
            <div id="w2-m-afcrps" class="tw-metric-val tw-c-sky">--</div>
            <div id="w2-m-gap" class="tw-metric-sub">&alpha;-penalty: --</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">CRPS<sub>fair</sub> (&alpha;=1)</div>
            <div id="w2-m-fair" class="tw-metric-val tw-c-emerald">--</div>
            <div class="tw-metric-sub">Unbiased score</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-top">
              <span class="tw-metric-lbl">90% Cov</span>
              <span id="w2-p-cov90"></span>
            </div>
            <div id="w2-m-cov90" class="tw-metric-val tw-c-amber">--</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-top">
              <span class="tw-metric-lbl">99% Cov</span>
              <span id="w2-p-cov99"></span>
            </div>
            <div id="w2-m-cov99" class="tw-metric-val tw-c-coral">--</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-top">
              <span class="tw-metric-lbl">Spread-Skill</span>
              <span id="w2-p-ssr"></span>
            </div>
            <div id="w2-m-ssr" class="tw-metric-val tw-c-primary">--</div>
          </div>
        </div>

        <div class="tw-decomp">
          <div class="tw-control-top">
            <span><strong>afCRPS Decomposition:</strong> <span class="tw-c-coral">Fit Penalty</span> &minus; <span class="tw-c-sky">Spread Bonus (&alpha;)</span> = <span class="tw-c-emerald">Net afCRPS</span></span>
            <span id="w2-decomp-txt" class="tw-control-val">--</span>
          </div>
          <div class="tw-decomp-bar">
            <div id="w2-bar-net" class="tw-decomp-seg" style="background:#34d399;width:55%"></div>
            <div id="w2-bar-bonus" class="tw-decomp-seg" style="background:#38bdf8;width:42%"></div>
            <div id="w2-bar-pen" class="tw-decomp-seg" style="background:#fbbf24;width:3%"></div>
          </div>
          <div class="tw-decomp-legend">
            <span><span class="tw-swatch" style="background:#34d399"></span>Net afCRPS</span>
            <span><span class="tw-swatch" style="background:#38bdf8"></span>Active Spread Bonus (1&minus;&epsilon;)</span>
            <span><span class="tw-swatch" style="background:#fbbf24"></span>&alpha;-Shrinkage withheld (&epsilon; = (1&minus;&alpha;)/m)</span>
          </div>
        </div>

        <div class="tw-plots">
          <div id="w2-plot-left" class="tw-plot-box"></div>
          <div id="w2-plot-right" class="tw-plot-box"></div>
        </div>

        <div class="tw-note">
          <strong>Production note:</strong> Outer-tail stretch (<code>tailcal.py</code>) was retired in <code>UR1/X2</code> after ablations showed no net gain on held-out sondes; production Tempest-ARKNET calibrates both core and tail quantiles via the 109-knot <code>spread.py</code> map.
        </div>

        <div class="tw-callout">
          <strong>Predict &rarr; Test:</strong> Click <em>Small-Ensemble Bias (m=4, &alpha;=0.80)</em>, then drag <em>Fairness &alpha;</em> from <code>0.80</code> to <code>1.00</code> and watch the amber shrinkage segment vanish as <code>afCRPS</code> converges to <code>CRPS<sub>fair</sub></code>.
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
      let sumAf = 0.0, sumFair = 0.0, sumFit = 0.0, sumAfBonus = 0.0, sumFairBonus = 0.0;
      let sumQ05 = 0.0, sumQ95 = 0.0, hit90 = 0, hit99 = 0, sumVar = 0.0, sumSqErr = 0.0;

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
        for (let i = 0; i < m; i++) calPool[poolIdx + i] = calSorted[i];
        poolIdx += m;

        const dec = afcrpsDecompCase(calSorted, y, alpha);
        sumAf += dec.af;
        sumFit += dec.fit;
        sumAfBonus += dec.afBonus;
        sumFairBonus += dec.fairBonus;
        sumFair += crpsFairCase(calSorted, y);

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

      const totalBar = Math.max(fitMean, 1e-6);
      const pctNet = clamp((afMean / totalBar) * 100.0, 0, 100);
      const pctBonus = clamp((afBonusMean / totalBar) * 100.0, 0, 100 - pctNet);
      const pctPen = clamp((alphaPen / totalBar) * 100.0, 0, 100);
      root.querySelector("#w2-bar-net").style.width = pctNet.toFixed(1) + "%";
      root.querySelector("#w2-bar-bonus").style.width = pctBonus.toFixed(1) + "%";
      root.querySelector("#w2-bar-pen").style.width = Math.max(pctPen, alphaPen > 0.0005 ? 1.4 : 0).toFixed(1) + "%";
      root.querySelector("#w2-decomp-txt").textContent =
        "Fit " + fitMean.toFixed(3) + " \u2212 Bonus " + afBonusMean.toFixed(3) + " = " + afMean.toFixed(3);

      if (typeof Plotly === "undefined") {
        renderPlotlyUnavailable(root, [
          ["#w2-plot-left", "Anomaly Distribution & q05/q95 Hinges"],
          ["#w2-plot-right", "PIT Histogram (Flat = Honest, U = Overconfident)"]
        ]);
        return;
      }

      const histTraces = [
        {
          x: rawPool,
          name: "Raw Ensemble",
          type: "histogram",
          histnorm: "probability density",
          xbins: { start: -5.0, end: 5.0, size: 0.25 },
          marker: { color: "rgba(248, 113, 113, 0.36)", line: { color: "#f87171", width: 1.2 } }
        },
        {
          x: calPool,
          name: "Tail-Calibrated",
          type: "histogram",
          histnorm: "probability density",
          xbins: { start: -5.0, end: 5.0, size: 0.25 },
          marker: { color: "rgba(56, 189, 248, 0.42)", line: { color: "#38bdf8", width: 1.2 } }
        },
        {
          x: Array.from(W2_DATA.truth),
          name: "Truth (N=400)",
          type: "histogram",
          histnorm: "probability density",
          xbins: { start: -5.0, end: 5.0, size: 0.25 },
          marker: { color: "rgba(52, 211, 153, 0.28)", line: { color: "#34d399", width: 1.6 } }
        }
      ];

      const histLayout = baseLayout({
        title: { text: "Anomaly Distribution & q05/q95 Hinges", font: { size: 16, color: "#f4f4f5" }, y: 0.97 },
        barmode: "overlay",
        xaxis: axisStyle({ title: "Standardized Anomaly (\u03C3)", range: [-4.5, 4.5] }),
        yaxis: axisStyle({ title: "Probability Density" }),
        shapes: [
          { type: "line", yref: "paper", x0: meanQ05, x1: meanQ05, y0: 0, y1: 1, line: { color: "#fbbf24", width: 2.0, dash: "dash" } },
          { type: "line", yref: "paper", x0: meanQ95, x1: meanQ95, y0: 0, y1: 1, line: { color: "#fbbf24", width: 2.0, dash: "dash" } }
        ],
        annotations: [
          { x: meanQ05, y: 0.98, yref: "paper", xanchor: "right", text: "q05 (" + meanQ05.toFixed(2) + "\u03C3)", showarrow: false, font: { size: 14, color: "#fbbf24" }, xshift: -6 },
          { x: meanQ95, y: 0.98, yref: "paper", xanchor: "left", text: "q95 (+" + meanQ95.toFixed(2) + "\u03C3)", showarrow: false, font: { size: 14, color: "#fbbf24" }, xshift: 6 }
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
              return Math.abs(v - 0.10) > 0.04 ? "rgba(251, 191, 36, 0.80)" : "rgba(56, 189, 248, 0.80)";
            }),
            line: { color: "#09090b", width: 1.2 }
          },
          hovertemplate: "PIT bin %{x}<br>Share=%{y:.3f}<extra></extra>"
        },
        {
          x: [pitBins[0], pitBins[9]],
          y: [0.10, 0.10],
          name: "Uniform Target (0.10)",
          mode: "lines",
          line: { color: "#34d399", width: 2.6, dash: "dash" }
        }
      ];

      const pitLayout = baseLayout({
        title: { text: "PIT Histogram (Flat = Honest, U = Overconfident)", font: { size: 16, color: "#f4f4f5" }, y: 0.97 },
        xaxis: axisStyle({ title: "PIT Rank Bin Center" }),
        yaxis: axisStyle({ title: "Relative Frequency", range: [0, pitMax] })
      });

      Plotly.react(root.querySelector("#w2-plot-left"), histTraces, histLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w2-plot-right"), pitTraces, pitLayout, PLOT_CONFIG);
    }

    [elM, elAlpha, elSpread, elF].forEach(function (el) { el.addEventListener("input", update); });
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
  // WIDGET 4: Schaake Shuffle & Vertical Coherence (#widget-4-schaake)
  // =========================================================================

  const W4_M = 60;
  const W4_SHOW = 12;
  const W4_INSPECT_LEVELS = HEIGHTS.filter(function (z) { return z >= 100 && z <= 15000; });

  const W4_DATA = (function () {
    const rng = makeRng(20260404);
    const L = HEIGHTS.length;

    const rawPool = new Array(L);
    const uncoupled = new Array(L);
    const smoothTpl = new Array(L);
    const noiseTpl = new Array(L);

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

  function initWidget4() {
    const root = document.getElementById("widget-4-schaake");
    if (!root) return;

    const defaults = { mode: "shuffled", coherence: 0.90, zIdx: W4_INSPECT_LEVELS.indexOf(10000) };
    let mode = defaults.mode;

    const sortedByLevel = HEIGHTS.map(function (_, k) {
      const arr = Array.from(W4_DATA.rawPool[k]);
      arr.sort(function (a, b) { return a - b; });
      return arr;
    });

    root.innerHTML = `
      <div class="tw-card">
        <div class="tw-head">
          <div>
            <div class="tw-kicker">Interactive Sandbox 3</div>
            <h4 class="tw-title">Schaake Shuffle Vertical Coherence &amp; Wind-Shear Explorer</h4>
            <p class="tw-sub">Rank-reordering (<code>shuffle.py</code>) restores smooth vertical jet structure while leaving every level&rsquo;s marginal distribution 100% unchanged.</p>
          </div>
          <div class="tw-actions">
            <div class="tw-toggle-group" role="group" aria-label="Coherence Mode">
              <button type="button" data-mode="raw" class="tw-toggle-btn">Raw Uncoupled</button>
              <button type="button" data-mode="shuffled" class="tw-toggle-btn active-sky">Schaake-Shuffled</button>
              <button type="button" data-mode="shearmap" class="tw-toggle-btn">Shuffle + Shear Map</button>
            </div>
            <button type="button" id="w4-reset" class="tw-btn">Reset Defaults</button>
          </div>
        </div>

        <div class="tw-controls tw-cols-2">
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Template Coherence</span>
              <span id="w4-coh-val" class="tw-control-val">0.90</span>
            </div>
            <input id="w4-coh" type="range" min="0.00" max="1.00" step="0.05" value="${defaults.coherence}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Inspect Altitude z</span>
              <span id="w4-z-val" class="tw-control-val tw-c-amber">10.0 km AGL</span>
            </div>
            <input id="w4-z" type="range" min="0" max="${W4_INSPECT_LEVELS.length - 1}" step="1" value="${defaults.zIdx}" class="tw-slider" />
          </label>
        </div>

        <div class="tw-metrics tw-cols-4">
          <div class="tw-metric">
            <div class="tw-metric-lbl">Lag-1 Vertical Corr</div>
            <div id="w4-m-corr" class="tw-metric-val tw-c-sky">--</div>
            <div class="tw-metric-sub">Mean r(z<sub>k</sub>, z<sub>k+1</sub>)</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Max Wind Shear</div>
            <div id="w4-m-shear" class="tw-metric-val tw-c-amber">--</div>
            <div class="tw-metric-sub">Highlighted member</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Marginal Mean &Delta;</div>
            <div id="w4-m-delta" class="tw-metric-val tw-c-emerald">0.00 m/s</div>
            <div class="tw-metric-sub">Exact at selected z</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Level Marginal (z)</div>
            <div id="w4-m-lvl" class="tw-metric-val tw-c-primary">--</div>
            <div class="tw-metric-sub">Mean &plusmn; SD (m/s)</div>
          </div>
        </div>

        <div class="tw-plots">
          <div id="w4-plot-left" class="tw-plot-box"></div>
          <div id="w4-plot-right" class="tw-plot-box"></div>
        </div>

        <div class="tw-callout">
          <strong>Predict &rarr; Test:</strong> Switch between <em>Raw Uncoupled</em> and <em>Schaake-Shuffled</em> while watching the right-hand histogram at <code>z = 10.0 km</code>. The left profiles transform from unphysical zigzags into smooth jets while <code>Marginal Mean &Delta; = 0.00 m/s</code> stays invariant.
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
        btn.className = "tw-toggle-btn" + (isMe ? (mode === "shearmap" ? " active-emerald" : " active-sky") : "");
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
        for (let k = 0; k < L; k++) levels[k] = W4_DATA.uncoupled[k];
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

      let corrSum = 0.0;
      for (let k = 0; k < L - 1; k++) corrSum += pearsonCorr(levels[k], levels[k + 1]);
      const meanLag1 = corrSum / (L - 1);

      let maxShear = 0.0;
      for (let k = 0; k < L - 1; k++) {
        const dzKm = (HEIGHTS[k + 1] - HEIGHTS[k]) / 1000.0;
        const sh = Math.abs(levels[k + 1][0] - levels[k][0]) / dzKm;
        if (sh > maxShear) maxShear = sh;
      }

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

      if (typeof Plotly === "undefined") {
        renderPlotlyUnavailable(root, [
          ["#w4-plot-left", "12 Ensemble Wind Profiles u(z) across 44 Levels"],
          ["#w4-plot-right", "Marginal Histogram at Inspected Altitude"]
        ]);
        return;
      }

      const leftTraces = [];
      const bgColor =
        mode === "raw"
          ? "rgba(248, 113, 113, 0.28)"
          : mode === "shearmap"
            ? "rgba(52, 211, 153, 0.28)"
            : "rgba(56, 189, 248, 0.26)";

      for (let m = 1; m < W4_SHOW; m++) {
        const prof = new Array(L);
        for (let k = 0; k < L; k++) prof[k] = levels[k][m];
        leftTraces.push({
          x: prof,
          y: HEIGHTS_KM,
          mode: "lines",
          line: { color: bgColor, width: 1.4 },
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
        line: { color: mode === "raw" ? "#f87171" : mode === "shearmap" ? "#34d399" : "#38bdf8", width: 3.2 },
        name: "Highlighted Member #1",
        hovertemplate: "z=%{y:.2f} km<br>u(z)=%{x:.1f} m/s<extra></extra>"
      });

      const leftLayout = baseLayout({
        title: { text: "12 Ensemble Wind Profiles u(z) across 44 Levels", font: { size: 16, color: "#f4f4f5" }, y: 0.97 },
        xaxis: axisStyle({ title: "Wind Speed u(z) (m/s)", range: [0, 48] }),
        yaxis: axisStyle({ title: "Altitude (km AGL)", range: [0, 18.2] }),
        shapes: [
          { type: "line", xref: "paper", x0: 0, x1: 1, y0: zInspectKm, y1: zInspectKm, line: { color: "#fbbf24", width: 2.0, dash: "dash" } }
        ],
        annotations: [
          { xref: "paper", x: 0.99, y: zInspectKm, xanchor: "right", yanchor: "bottom", text: "Inspect z = " + zInspectKm.toFixed(1) + " km", showarrow: false, font: { size: 14, color: "#fbbf24" } }
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
          marker: { color: "rgba(161, 161, 170, 0.32)", line: { color: "#d4d4d8", width: 1.5 } }
        },
        {
          x: actAtZ,
          name: mode === "raw" ? "Active (Raw)" : mode === "shuffled" ? "Active (Shuffled)" : "Active (Shear Map)",
          type: "histogram",
          xbins: { start: minVal, end: maxVal, size: binSize },
          marker: {
            color: mode === "shearmap" ? "rgba(52, 211, 153, 0.45)" : "rgba(56, 189, 248, 0.45)",
            line: { color: mode === "shearmap" ? "#34d399" : "#38bdf8", width: 1.5 }
          }
        }
      ];

      const rightLayout = baseLayout({
        title: { text: "Marginal Histogram at z = " + zInspectKm.toFixed(1) + " km", font: { size: 16, color: "#f4f4f5" }, y: 0.97 },
        barmode: "overlay",
        xaxis: axisStyle({ title: "Wind Speed at z (m/s)" }),
        yaxis: axisStyle({ title: "Member Count (M=60)" })
      });

      Plotly.react(root.querySelector("#w4-plot-left"), leftTraces, leftLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w4-plot-right"), rightTraces, rightLayout, PLOT_CONFIG);
    }

    [elCoh, elZ].forEach(function (el) { el.addEventListener("input", update); });
    modeBtns.forEach(function (btn) {
      btn.addEventListener("click", function () { setMode(btn.getAttribute("data-mode")); });
    });
    root.querySelector("#w4-reset").addEventListener("click", function () {
      elCoh.value = defaults.coherence;
      elZ.value = defaults.zIdx;
      setMode(defaults.mode);
    });

    setMode(defaults.mode);
  }

  // =========================================================================
  // WIDGET 7: Interactive Visual Metric Scorecard (#widget-7-metrics)
  // =========================================================================

  const W7_N = 180;
  const W7_M = 20;
  const W7_TRUE_RHO = 0.88;
  const W7_THRESH = 9.5; // Go/No-Go 10m wind limit (m/s)

  const W7_DATA = (function () {
    const rng = makeRng(20260707);
    const muCase = new Float64Array(W7_N);
    const y1 = new Float64Array(W7_N);
    const y2 = new Float64Array(W7_N);
    const pitJ = new Float64Array(W7_N);
    const z1 = new Array(W7_N);
    const z2 = new Array(W7_N);

    const rootR = Math.sqrt(1.0 - W7_TRUE_RHO * W7_TRUE_RHO);
    for (let b = 0; b < W7_N; b++) {
      // Synoptic forecast mean varies across launch days (4.5 to 12.5 m/s)
      const base = 7.8 + 2.4 * boxMuller(rng);
      muCase[b] = base;
      const e1 = boxMuller(rng);
      const e2 = W7_TRUE_RHO * e1 + rootR * boxMuller(rng);
      // True 10m & 500m winds with sigma = 1.8 m/s around synoptic mean
      y1[b] = base + 1.8 * e1;
      y2[b] = base + 3.2 + 1.8 * e2;
      pitJ[b] = rng();

      const r1 = new Float64Array(W7_M);
      const r2 = new Float64Array(W7_M);
      for (let m = 0; m < W7_M; m++) {
        r1[m] = boxMuller(rng);
        r2[m] = boxMuller(rng);
      }
      z1[b] = r1;
      z2[b] = r2;
    }

    // Climatology base rate for BSS reference
    let hits = 0;
    for (let b = 0; b < W7_N; b++) {
      if (y1[b] > W7_THRESH) hits++;
    }
    const baseRate = hits / W7_N;
    let bsRef = 0.0;
    for (let b = 0; b < W7_N; b++) {
      const obs = y1[b] > W7_THRESH ? 1.0 : 0.0;
      bsRef += Math.pow(baseRate - obs, 2);
    }
    bsRef /= W7_N;

    return { muCase, y1, y2, pitJ, z1, z2, bsRef };
  })();

  function initWidget7() {
    const root = document.getElementById("widget-7-metrics");
    if (!root) return;

    const defaults = { bias: 0.0, spread: 1.00, shearCorr: 0.88 };
    const presets = {
      calibrated: { bias: 0.0, spread: 1.00, shearCorr: 0.88 },
      overconf: { bias: 1.6, spread: 0.45, shearCorr: 0.85 },
      uncoupled: { bias: 0.0, spread: 1.00, shearCorr: 0.05 },
      wide: { bias: -0.6, spread: 1.75, shearCorr: 0.70 }
    };

    root.innerHTML = `
      <div class="tw-card">
        <div class="tw-head">
          <div>
            <div class="tw-kicker">Interactive Sandbox 4</div>
            <h4 class="tw-title">Interactive Visual Metric Scorecard</h4>
            <p class="tw-sub">Adjust mean bias, ensemble spread, and vertical shear correlation to see how CRPS, Energy Score, Variogram Score, SSR, PIT, and Brier Skill Score respond together.</p>
          </div>
          <button type="button" id="w7-reset" class="tw-btn">Reset Defaults</button>
        </div>

        <div class="tw-row-wrap">
          <span class="tw-row-label">Presets:</span>
          <button type="button" data-preset="calibrated" class="tw-preset-btn">Calibrated Target</button>
          <button type="button" data-preset="overconf" class="tw-preset-btn">Biased + Overconfident</button>
          <button type="button" data-preset="uncoupled" class="tw-preset-btn">Uncoupled Vertical Shear</button>
          <button type="button" data-preset="wide" class="tw-preset-btn">Over-Dispersed Dome</button>
        </div>

        <div class="tw-controls tw-cols-3">
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Mean Bias (&Delta;&mu;)</span>
              <span id="w7-bias-val" class="tw-control-val">0.0 m/s</span>
            </div>
            <input id="w7-bias" type="range" min="-3.0" max="3.0" step="0.1" value="${defaults.bias}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Ensemble Spread (&sigma; mult)</span>
              <span id="w7-spread-val" class="tw-control-val">1.00&times;</span>
            </div>
            <input id="w7-spread" type="range" min="0.35" max="2.00" step="0.05" value="${defaults.spread}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Vertical Shear Correlation (&rho;<sub>z</sub>)</span>
              <span id="w7-corr-val" class="tw-control-val">0.88</span>
            </div>
            <input id="w7-corr" type="range" min="0.00" max="0.98" step="0.02" value="${defaults.shearCorr}" class="tw-slider" />
          </label>
        </div>

        <div class="tw-metrics tw-cols-5">
          <div class="tw-metric">
            <div class="tw-metric-top"><span class="tw-metric-lbl">CRPS (m/s)</span><span id="w7-p-crps"></span></div>
            <div id="w7-m-crps" class="tw-metric-val">--</div>
            <div class="tw-metric-sub">Target &le; 1.12</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-top"><span class="tw-metric-lbl">Energy Score</span><span id="w7-p-es"></span></div>
            <div id="w7-m-es" class="tw-metric-val">--</div>
            <div class="tw-metric-sub">Target &le; 1.65</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-top"><span class="tw-metric-lbl">Variogram</span><span id="w7-p-vs"></span></div>
            <div id="w7-m-vs" class="tw-metric-val">--</div>
            <div class="tw-metric-sub">Shear &le; 0.14</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-top"><span class="tw-metric-lbl">Spread-Skill</span><span id="w7-p-ssr"></span></div>
            <div id="w7-m-ssr" class="tw-metric-val">--</div>
            <div class="tw-metric-sub">Ideal 1.00</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-top"><span class="tw-metric-lbl">Brier Skill</span><span id="w7-p-bss"></span></div>
            <div id="w7-m-bss" class="tw-metric-val">--</div>
            <div class="tw-metric-sub">Target &ge; 0.35</div>
          </div>
        </div>

        <div class="tw-plots">
          <div id="w7-plot-left" class="tw-plot-box"></div>
          <div id="w7-plot-right" class="tw-plot-box"></div>
        </div>

        <div class="tw-callout">
          <strong>Predict &rarr; Test:</strong> Click <em>Uncoupled Vertical Shear</em> (&rho;<sub>z</sub> = 0.05). Notice that <code>CRPS</code>, <code>SSR</code>, and the <code>PIT</code> bars stay green—only the <strong>Variogram Score</strong> turns red, proving why marginal scores alone cannot detect broken vertical wind shear.
        </div>
      </div>
    `;

    const elBias = root.querySelector("#w7-bias");
    const elSpread = root.querySelector("#w7-spread");
    const elCorr = root.querySelector("#w7-corr");
    const presetBtns = Array.from(root.querySelectorAll("[data-preset]"));

    function badge(level) {
      if (level === "good") return '<span class="tw-pill tw-pill-ok">PASS</span>';
      if (level === "warn") return '<span class="tw-pill tw-pill-warn">WARN</span>';
      return '<span class="tw-pill tw-pill-bad">FAIL</span>';
    }

    function levelColor(level) {
      return level === "good" ? "#34d399" : level === "warn" ? "#fbbf24" : "#f87171";
    }

    function syncPresets() {
      const bias = parseFloat(elBias.value);
      const spread = parseFloat(elSpread.value);
      const corr = parseFloat(elCorr.value);
      presetBtns.forEach(function (btn) {
        const p = presets[btn.getAttribute("data-preset")];
        const ok =
          Math.abs(bias - p.bias) < 1e-6 &&
          Math.abs(spread - p.spread) < 1e-6 &&
          Math.abs(corr - p.shearCorr) < 1e-6;
        btn.classList.toggle("is-active", ok);
      });
    }

    function update() {
      const bias = parseFloat(elBias.value);
      const spread = parseFloat(elSpread.value);
      const rhoZ = parseFloat(elCorr.value);

      root.querySelector("#w7-bias-val").textContent = (bias > 0 ? "+" : "") + bias.toFixed(1) + " m/s";
      root.querySelector("#w7-spread-val").textContent = spread.toFixed(2) + "\u00D7";
      root.querySelector("#w7-corr-val").textContent = rhoZ.toFixed(2);
      syncPresets();

      const rootR = Math.sqrt(Math.max(1.0 - rhoZ * rhoZ, 0.0));
      let sumCrps = 0.0, sumEs = 0.0, sumVs = 0.0, sumVar = 0.0, sumSqErr = 0.0, sumBs = 0.0;
      const pitCounts = new Array(10).fill(0);

      for (let b = 0; b < W7_N; b++) {
        const base = W7_DATA.muCase[b];
        const y1 = W7_DATA.y1[b];
        const y2 = W7_DATA.y2[b];
        const r1 = W7_DATA.z1[b];
        const r2 = W7_DATA.z2[b];

        const x1 = new Array(W7_M);
        const x2 = new Array(W7_M);
        let m1 = 0.0;
        let exceed = 0;

        for (let m = 0; m < W7_M; m++) {
          const g1 = r1[m];
          const g2 = rhoZ * g1 + rootR * r2[m];
          const v1 = base + bias + 1.8 * spread * g1;
          const v2 = base + 3.2 + bias + 1.8 * spread * g2;
          x1[m] = v1;
          x2[m] = v2;
          m1 += v1;
          if (v1 > W7_THRESH) exceed++;
        }
        m1 /= W7_M;

        // Fair CRPS on level 1
        const x1Sorted = x1.slice().sort(function (a, c) { return a - c; });
        sumCrps += crpsFairCase(x1Sorted, y1);

        // Energy Score on 2-level vector (x1, x2)
        let fit2 = 0.0;
        let spread2 = 0.0;
        for (let i = 0; i < W7_M; i++) {
          fit2 += Math.hypot(x1[i] - y1, x2[i] - y2);
          for (let j = i + 1; j < W7_M; j++) {
            spread2 += Math.hypot(x1[i] - x1[j], x2[i] - x2[j]);
          }
        }
        sumEs += fit2 / W7_M - spread2 / (W7_M * (W7_M - 1));

        // Variogram Score (p = 0.5) on vertical shear |x2 - x1|
        const obsDiff = Math.sqrt(Math.abs(y2 - y1));
        let fcDiffMean = 0.0;
        for (let i = 0; i < W7_M; i++) {
          fcDiffMean += Math.sqrt(Math.abs(x2[i] - x1[i]));
        }
        fcDiffMean /= W7_M;
        sumVs += Math.pow(obsDiff - fcDiffMean, 2);

        // Spread-skill
        let vSum = 0.0;
        for (let i = 0; i < W7_M; i++) {
          const d = x1[i] - m1;
          vSum += d * d;
        }
        sumVar += vSum / (W7_M - 1);
        sumSqErr += (m1 - y1) * (m1 - y1);

        // Brier Score on exceedance > 9.5 m/s
        const prob = exceed / W7_M;
        const obsBin = y1 > W7_THRESH ? 1.0 : 0.0;
        sumBs += Math.pow(prob - obsBin, 2);

        // PIT rank
        let rank = 0;
        for (let i = 0; i < W7_M; i++) {
          if (x1Sorted[i] < y1) rank++;
        }
        const pit = (rank + W7_DATA.pitJ[b]) / (W7_M + 1);
        pitCounts[Math.min(9, Math.floor(pit * 10))]++;
      }

      const crps = sumCrps / W7_N;
      const es = sumEs / W7_N;
      const vs = sumVs / W7_N;
      const ssr = Math.sqrt(sumVar / W7_N) / Math.max(Math.sqrt(sumSqErr / W7_N), 1e-9);
      const bss = 1.0 - (sumBs / W7_N) / Math.max(W7_DATA.bsRef, 1e-6);

      const stCrps = crps <= 1.15 ? "good" : crps <= 1.50 ? "warn" : "bad";
      const stEs = es <= 1.72 ? "good" : es <= 2.25 ? "warn" : "bad";
      const stVs = vs <= 0.145 ? "good" : vs <= 0.21 ? "warn" : "bad";
      const stSsr = ssr >= 0.88 && ssr <= 1.14 ? "good" : ssr >= 0.70 && ssr <= 1.35 ? "warn" : "bad";
      const stBss = bss >= 0.35 ? "good" : bss >= 0.10 ? "warn" : "bad";

      root.querySelector("#w7-m-crps").textContent = crps.toFixed(3);
      root.querySelector("#w7-m-crps").style.color = levelColor(stCrps);
      root.querySelector("#w7-p-crps").innerHTML = badge(stCrps);

      root.querySelector("#w7-m-es").textContent = es.toFixed(3);
      root.querySelector("#w7-m-es").style.color = levelColor(stEs);
      root.querySelector("#w7-p-es").innerHTML = badge(stEs);

      root.querySelector("#w7-m-vs").textContent = vs.toFixed(3);
      root.querySelector("#w7-m-vs").style.color = levelColor(stVs);
      root.querySelector("#w7-p-vs").innerHTML = badge(stVs);

      root.querySelector("#w7-m-ssr").textContent = ssr.toFixed(2);
      root.querySelector("#w7-m-ssr").style.color = levelColor(stSsr);
      root.querySelector("#w7-p-ssr").innerHTML = badge(stSsr);

      root.querySelector("#w7-m-bss").textContent = bss.toFixed(2);
      root.querySelector("#w7-m-bss").style.color = levelColor(stBss);
      root.querySelector("#w7-p-bss").innerHTML = badge(stBss);

      if (typeof Plotly === "undefined") {
        renderPlotlyUnavailable(root, [
          ["#w7-plot-left", "Forecast vs. Truth & PIT Histogram"],
          ["#w7-plot-right", "Live 5-Metric Verification Scorecard"]
        ]);
        return;
      }

      // Left panel: Top subplot = Forecast vs Truth PDF; Bottom subplot = PIT Histogram
      const xs = [];
      const yTruth = [];
      const yFc = [];
      for (let x = -6.0; x <= 6.001; x += 0.15) {
        xs.push(x);
        yTruth.push(normalPdf(x, 0.0, 1.8));
        yFc.push(normalPdf(x, bias, 1.8 * spread));
      }

      const pitBins = ["0.05", "0.15", "0.25", "0.35", "0.45", "0.55", "0.65", "0.75", "0.85", "0.95"];
      const pitFracs = pitCounts.map(function (c) { return c / W7_N; });
      const pitMax = Math.max(0.24, Math.max.apply(null, pitFracs) * 1.18);

      const leftTraces = [
        {
          x: xs,
          y: yTruth,
          name: "Truth Error PDF",
          mode: "lines",
          line: { color: "#34d399", width: 2.8 },
          fill: "tozeroy",
          fillcolor: "rgba(52, 211, 153, 0.16)",
          xaxis: "x",
          yaxis: "y",
          hovertemplate: "Err=%{x:.1f} m/s<br>Truth=%{y:.3f}<extra></extra>"
        },
        {
          x: xs,
          y: yFc,
          name: "Forecast PDF",
          mode: "lines",
          line: { color: "#38bdf8", width: 2.8 },
          fill: "tozeroy",
          fillcolor: "rgba(56, 189, 248, 0.18)",
          xaxis: "x",
          yaxis: "y",
          hovertemplate: "Err=%{x:.1f} m/s<br>Forecast=%{y:.3f}<extra></extra>"
        },
        {
          x: pitBins,
          y: pitFracs,
          name: "PIT Histogram",
          type: "bar",
          xaxis: "x2",
          yaxis: "y2",
          marker: {
            color: pitFracs.map(function (v) {
              return Math.abs(v - 0.10) > 0.05 ? "#f87171" : Math.abs(v - 0.10) > 0.03 ? "#fbbf24" : "#38bdf8";
            }),
            line: { color: "#09090b", width: 1 }
          },
          hovertemplate: "PIT %{x}<br>Freq=%{y:.3f}<extra></extra>"
        },
        {
          x: [pitBins[0], pitBins[9]],
          y: [0.10, 0.10],
          name: "Uniform 0.10",
          mode: "lines",
          xaxis: "x2",
          yaxis: "y2",
          line: { color: "#34d399", width: 2.2, dash: "dash" }
        }
      ];

      const leftLayout = baseLayout({
        height: 500,
        title: { text: "Forecast vs. Truth (Top) & PIT Histogram (Bottom)", font: { size: 16, color: "#f4f4f5" }, y: 0.98 },
        margin: { l: 68, r: 22, t: 58, b: 84 },
        xaxis: axisStyle({ domain: [0, 1], anchor: "y", title: "Wind Anomaly (m/s)", range: [-5.8, 5.8] }),
        yaxis: axisStyle({ domain: [0.56, 0.98], anchor: "x", title: "Density" }),
        xaxis2: axisStyle({ domain: [0, 1], anchor: "y2", title: "PIT Rank Bin" }),
        yaxis2: axisStyle({ domain: [0.02, 0.40], anchor: "x2", title: "Freq", range: [0, pitMax] })
      });

      // Right panel: Live Health Score Bars (0-100 quality index with exact metric readout labels)
      const qCrps = clamp((1.0 - (crps - 0.95) / 1.45) * 100, 6, 100);
      const qEs = clamp((1.0 - (es - 1.45) / 2.0) * 100, 6, 100);
      const qVs = clamp((1.0 - (vs - 0.10) / 0.24) * 100, 6, 100);
      const qSsr = clamp((1.0 - Math.abs(ssr - 1.0) / 0.65) * 100, 6, 100);
      const qBss = clamp(((bss + 0.25) / 0.85) * 100, 6, 100);

      const barRows = [
        { name: "Brier Skill (BSS)", q: qBss, txt: bss.toFixed(2) + " (" + stBss.toUpperCase() + ")", st: stBss },
        { name: "Spread-Skill (SSR)", q: qSsr, txt: ssr.toFixed(2) + " (" + stSsr.toUpperCase() + ")", st: stSsr },
        { name: "Variogram (Shear)", q: qVs, txt: vs.toFixed(3) + " (" + stVs.toUpperCase() + ")", st: stVs },
        { name: "Energy Score", q: qEs, txt: es.toFixed(3) + " (" + stEs.toUpperCase() + ")", st: stEs },
        { name: "CRPS (m/s)", q: qCrps, txt: crps.toFixed(3) + " (" + stCrps.toUpperCase() + ")", st: stCrps }
      ];

      const rightTraces = [
        {
          y: barRows.map(function (r) { return r.name; }),
          x: barRows.map(function (r) { return r.q; }),
          type: "bar",
          orientation: "h",
          marker: {
            color: barRows.map(function (r) { return levelColor(r.st); }),
            line: { color: "#09090b", width: 1.2 }
          },
          text: barRows.map(function (r) { return r.txt; }),
          textposition: "outside",
          textfont: { size: 14.5, color: "#f4f4f5", family: "JetBrains Mono, monospace" },
          hovertemplate: "%{y}: %{text}<extra></extra>"
        }
      ];

      const rightLayout = baseLayout({
        height: 500,
        title: { text: "Live 5-Metric Verification Scorecard", font: { size: 16, color: "#f4f4f5" }, y: 0.98 },
        margin: { l: 160, r: 120, t: 58, b: 74 },
        showlegend: false,
        xaxis: axisStyle({ title: "Calibration Health Index (0\u2013100)", range: [0, 128] }),
        yaxis: axisStyle({ title: "" }),
        shapes: [
          { type: "line", x0: 70, x1: 70, y0: -0.5, y1: 4.5, line: { color: "#34d399", width: 1.6, dash: "dash" } }
        ],
        annotations: [
          { x: 70, y: 4.55, text: "Pass Gate", showarrow: false, font: { size: 14, color: "#34d399" } }
        ]
      });

      Plotly.react(root.querySelector("#w7-plot-left"), leftTraces, leftLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w7-plot-right"), rightTraces, rightLayout, PLOT_CONFIG);
    }

    [elBias, elSpread, elCorr].forEach(function (el) { el.addEventListener("input", update); });
    presetBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        const p = presets[btn.getAttribute("data-preset")];
        elBias.value = p.bias;
        elSpread.value = p.spread;
        elCorr.value = p.shearCorr;
        update();
      });
    });
    root.querySelector("#w7-reset").addEventListener("click", function () {
      elBias.value = defaults.bias;
      elSpread.value = defaults.spread;
      elCorr.value = defaults.shearCorr;
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

  function initWidget3() {
    const root = document.getElementById("widget-3-router");
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
        <div class="tw-head">
          <div>
            <div class="tw-kicker">Interactive Sandbox 5</div>
            <h4 class="tw-title">Lead-Time &amp; Live Observation Assimilation Router</h4>
            <p class="tw-sub">Cosine mode blending (<code>router.py</code>) paired with soft Gaussian-copula observation gain (<code>obs.py</code>, &tau;<sub>h</sub> = 6.3 h, 5.0 km own-pad gate).</p>
          </div>
          <div class="tw-actions">
            <div class="tw-toggle-group" role="group" aria-label="Diurnal Regime">
              <button type="button" id="w3-btn-day" class="tw-toggle-btn active-amber">Day</button>
              <button type="button" id="w3-btn-night" class="tw-toggle-btn">Night</button>
            </div>
            <button type="button" id="w3-reset" class="tw-btn">Reset Defaults</button>
          </div>
        </div>

        <div class="tw-row-wrap">
          <span class="tw-row-label">Active Assimilation Formula (5.0 km threshold):</span>
          <span id="w3-regime-badge" class="tw-pill tw-pill-sky">Off-Site Representativeness &times; Cross-Age</span>
        </div>

        <div class="tw-controls tw-cols-5">
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Lead Time</span>
              <span id="w3-lead-val" class="tw-control-val">+0.5 d</span>
            </div>
            <input id="w3-lead" type="range" min="-15" max="60" step="0.5" value="${defaults.lead}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Obs Age &Delta;t</span>
              <span id="w3-age-val" class="tw-control-val">1.5 h</span>
            </div>
            <input id="w3-age" type="range" min="0" max="24" step="0.5" value="${defaults.age}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Distance d</span>
              <span id="w3-dist-val" class="tw-control-val">25 km</span>
            </div>
            <input id="w3-dist" type="range" min="0" max="100" step="1" value="${defaults.dist}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Elev Diff |&Delta;z|</span>
              <span id="w3-dz-val" class="tw-control-val">150 m</span>
            </div>
            <input id="w3-dz" type="range" min="0" max="1500" step="25" value="${defaults.dz}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Obs Wind x<sub>obs</sub></span>
              <span id="w3-xobs-val" class="tw-control-val tw-c-amber">10.5 m/s</span>
            </div>
            <input id="w3-xobs" type="range" min="2" max="20" step="0.5" value="${defaults.xObs}" class="tw-slider" />
          </label>
        </div>

        <div class="tw-metrics tw-cols-5">
          <div class="tw-metric">
            <div class="tw-metric-lbl">Active Mode</div>
            <div id="w3-m-mode" class="tw-metric-val tw-c-sky">--</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Climate Weight</div>
            <div id="w3-m-clim" class="tw-metric-val tw-c-amber">--</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Effective Obs Gain r</div>
            <div id="w3-m-gain" class="tw-metric-val tw-c-emerald">--</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">&sigma;<sub>obs</sub> / &sigma;<sub>prior</sub></div>
            <div id="w3-m-sig" class="tw-metric-val tw-c-primary">--</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Uncertainty Reduction</div>
            <div id="w3-m-red" class="tw-metric-val tw-c-coral">--</div>
          </div>
        </div>

        <div class="tw-plots">
          <div id="w3-plot-left" class="tw-plot-box"></div>
          <div class="tw-plot-col">
            <div id="w3-right-banner" class="tw-banner tw-banner-ok"></div>
            <div id="w3-plot-right" class="tw-plot-box"></div>
          </div>
        </div>

        <div class="tw-callout">
          <strong>Predict &rarr; Test:</strong> Drag <em>Distance d</em> below <strong>5.0 km</strong> to watch the badge flip to <code>Own-Pad Persistence: exp(&minus;&Delta;t/6.3)</code>. Then push <em>Obs Wind</em> to <strong>16 m/s</strong> and toggle <em>Day / Night</em> at <code>d = 40 km</code> to see how nighttime inversions reduce off-site METAR trust.
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
      btnDay.className = "tw-toggle-btn" + (regime === "day" ? " active-amber" : "");
      btnNight.className = "tw-toggle-btn" + (regime === "night" ? " active-sky" : "");
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
        badge.className = "tw-pill tw-pill-sky";
        badge.textContent = "Off-Site Representativeness \u00D7 Cross-Age (" + (regime === "day" ? "Day" : "Night") + ")";
      }

      const banner = root.querySelector("#w3-right-banner");
      if (lead > 1.0) {
        banner.className = "tw-banner tw-banner-amber";
        banner.innerHTML = "<strong>Preview only (Lead &gt; 1.0 d):</strong> Launch-morning observation assimilation activates inside <code>T&minus;24 h</code>.";
      } else if (lead < -0.5) {
        banner.className = "tw-banner tw-banner-neutral";
        banner.innerHTML = "<strong>Historical Mode (Lead &lt; 0 d):</strong> Past ERA5 / Mode P reanalysis is active; live METAR assimilation is offline.";
      } else {
        banner.className = "tw-banner tw-banner-ok";
        banner.innerHTML = "<strong>Launch-Day Assimilation Active (inside T&minus;24 h):</strong> Live METAR / pad sensor updates the forecast prior.";
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

      if (typeof Plotly === "undefined") {
        renderPlotlyUnavailable(root, [
          ["#w3-plot-left", "Cosine Lead-Time Mode Blend Weights"],
          ["#w3-plot-right", "Prior vs. Posterior 10 m Wind PDF"]
        ]);
        return;
      }

      const leftTraces = [
        { x: leadGrid, y: wP, name: "P (\u2264-6d)", mode: "lines", line: { color: "#71717a", width: 2.2 }, fill: "tozeroy", fillcolor: "rgba(113,113,122,0.14)" },
        { x: leadGrid, y: wP0, name: "P0 (-6..0d)", mode: "lines", line: { color: "#a1a1aa", width: 2.2 }, fill: "tozeroy", fillcolor: "rgba(161,161,170,0.14)" },
        { x: leadGrid, y: wF, name: "F (0..7d)", mode: "lines", line: { color: "#38bdf8", width: 2.6 }, fill: "tozeroy", fillcolor: "rgba(56,189,248,0.16)" },
        { x: leadGrid, y: wF2, name: "F2 (7..15d)", mode: "lines", line: { color: "#34d399", width: 2.6 }, fill: "tozeroy", fillcolor: "rgba(52,211,153,0.16)" },
        { x: leadGrid, y: wM, name: "M (15..46d)", mode: "lines", line: { color: "#fbbf24", width: 2.6 }, fill: "tozeroy", fillcolor: "rgba(251,191,36,0.16)" },
        { x: leadGrid, y: wC, name: "C (>46d)", mode: "lines", line: { color: "#f87171", width: 2.6 }, fill: "tozeroy", fillcolor: "rgba(248,113,113,0.16)" }
      ];

      const leftLayout = baseLayout({
        title: { text: "Cosine Lead-Time Mode Blend Weights", font: { size: 16, color: "#f4f4f5" }, y: 0.97 },
        xaxis: axisStyle({ title: "Forecast Lead Time (days)", range: [-15, 60] }),
        yaxis: axisStyle({ title: "Source Weight", range: [-0.04, 1.15] }),
        shapes: [
          { type: "rect", x0: 10, x1: 15, y0: 0, y1: 1, fillcolor: "rgba(52,211,153,0.10)", line: { color: "rgba(52,211,153,0.40)", width: 1.2, dash: "dot" } },
          { type: "rect", x0: 35, x1: 46, y0: 0, y1: 1, fillcolor: "rgba(251,191,36,0.10)", line: { color: "rgba(251,191,36,0.40)", width: 1.2, dash: "dot" } },
          { type: "line", x0: lead, x1: lead, y0: 0, y1: 1.09, line: { color: "#f4f4f5", width: 2.4, dash: "dash" } }
        ],
        annotations: [
          { x: 12.5, y: 1.08, text: "10\u201315d", showarrow: false, font: { size: 14, color: "#34d399" } },
          { x: 40.5, y: 1.08, text: "35\u201346d", showarrow: false, font: { size: 14, color: "#fbbf24" } }
        ]
      });

      const muPrior = 6.5;
      const sdPrior = 2.8;
      const muPost = muPrior + gain * (xObs - muPrior);
      const sdPost = Math.max(sdPrior * postStdRatio, 0.14);
      const xMax = Math.max(22.0, xObs + 4.0);

      const wx = [], yPrior = [], yPost = [];
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
          name: "Prior (\u03BC=6.5, \u03C3=2.8)",
          mode: "lines",
          line: { color: "#a1a1aa", width: 2.4, dash: "dot" },
          fill: "tozeroy",
          fillcolor: "rgba(161,161,170,0.14)",
          hovertemplate: "Wind=%{x:.1f} m/s<br>Prior=%{y:.3f}<extra></extra>"
        },
        {
          x: wx,
          y: yPost,
          name: "Posterior (\u03BC=" + muPost.toFixed(1) + ", \u03C3=" + sdPost.toFixed(2) + ")",
          mode: "lines",
          line: { color: "#38bdf8", width: 2.8 },
          fill: "tozeroy",
          fillcolor: "rgba(56,189,248,0.20)",
          hovertemplate: "Wind=%{x:.1f} m/s<br>Posterior=%{y:.3f}<extra></extra>"
        },
        {
          x: [xObs, xObs],
          y: [0, peakPdf * 1.06],
          name: "Obs x_obs (" + xObs.toFixed(1) + " m/s)",
          mode: "lines",
          line: { color: "#fbbf24", width: 2.4, dash: "dash" }
        }
      ];

      const rightLayout = baseLayout({
        height: 465,
        title: { text: "Prior vs. Posterior 10 m Wind PDF", font: { size: 16, color: "#f4f4f5" }, y: 0.97 },
        xaxis: axisStyle({ title: "10 m Wind Speed (m/s)", range: [0, xMax] }),
        yaxis: axisStyle({ title: "Probability Density", range: [0, peakPdf * 1.16] })
      });

      Plotly.react(root.querySelector("#w3-plot-left"), leftTraces, leftLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w3-plot-right"), rightTraces, rightLayout, PLOT_CONFIG);
    }

    [elLead, elAge, elDist, elDz, elXobs].forEach(function (el) { el.addEventListener("input", update); });
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
  // WIDGET 6: Gaussian vs. Student-t Conditional Copula (#widget-6-copula)
  // =========================================================================

  const W6_N = 280;
  const W6_NU_MAX = 30;
  const W6_DRAWS = (function () {
    const rng = makeRng(20260406);
    const z1 = new Float64Array(W6_N);
    const z2 = new Float64Array(W6_N);
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

  function initWidget6() {
    const root = document.getElementById("widget-6-copula");
    if (!root) return;

    const defaults = { uObs: 14.5, rho: 0.70, nu: 4 };
    const MU_X = 6.5;
    const SD_X = 3.0;
    const MU_Y = 10.0;
    const SD_Y = 4.2;
    const SHEAR_THRESH = 22.0;

    root.innerHTML = `
      <div class="tw-card">
        <div class="tw-head">
          <div>
            <div class="tw-kicker">Interactive Sandbox 6</div>
            <h4 class="tw-title">Gaussian vs. Student-<em>t</em> Copula Tail-Dependence Explorer</h4>
            <p class="tw-sub">Exact conditional Student-<em>t</em> scale inflation (<code>stats.py::Coupled</code>) showing why Gaussian copulas under-predict extreme wind shear during storms.</p>
          </div>
          <button type="button" id="w6-reset" class="tw-btn">Reset Defaults</button>
        </div>

        <div class="tw-controls tw-cols-3">
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Observed Pad Wind u<sub>obs</sub></span>
              <span id="w6-uobs-val" class="tw-control-val tw-c-amber">14.5 m/s</span>
            </div>
            <input id="w6-uobs" type="range" min="4.0" max="18.0" step="0.5" value="${defaults.uObs}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Correlation &rho;</span>
              <span id="w6-rho-val" class="tw-control-val">0.70</span>
            </div>
            <input id="w6-rho" type="range" min="0.20" max="0.90" step="0.05" value="${defaults.rho}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Student-<em>t</em> Tail Heaviness &nu;</span>
              <span id="w6-nu-val" class="tw-control-val tw-c-coral">&nu; = 4</span>
            </div>
            <input id="w6-nu" type="range" min="3" max="30" step="1" value="${defaults.nu}" class="tw-slider" />
          </label>
        </div>

        <div class="tw-metrics tw-cols-4">
          <div class="tw-metric">
            <div class="tw-metric-lbl">Gaussian Cond. SD</div>
            <div id="w6-m-gsd" class="tw-metric-val tw-c-sky">--</div>
            <div class="tw-metric-sub">Constant vs u<sub>obs</sub></div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Student-<em>t</em> Cond. SD</div>
            <div id="w6-m-tsd" class="tw-metric-val tw-c-coral">--</div>
            <div id="w6-m-tsdr" class="tw-metric-sub">-- vs Gaussian</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Gaussian P(Shear &gt; 22)</div>
            <div id="w6-m-gp" class="tw-metric-val tw-c-sky">--</div>
            <div class="tw-metric-sub">Tail-collapse risk</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Student-<em>t</em> P(Shear &gt; 22)</div>
            <div id="w6-m-tp" class="tw-metric-val tw-c-coral">--</div>
            <div id="w6-m-tpr" class="tw-metric-sub">Storm-tail persistence</div>
          </div>
        </div>

        <div class="tw-plots">
          <div id="w6-plot-left" class="tw-plot-box"></div>
          <div id="w6-plot-right" class="tw-plot-box"></div>
        </div>

        <div class="tw-callout">
          <strong>Predict &rarr; Test:</strong> Sweep <em>Observed Pad Wind u<sub>obs</sub></em> from <strong>6 m/s</strong> up to <strong>18 m/s</strong> with <code>&nu; = 4</code>. The sky Gaussian curve shifts right with fixed width, whereas the coral Student-<em>t</em> curve visibly widens to capture joint extreme shear.
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

      const xO = (uObs - MU_X) / SD_X;
      const condMean = MU_Y + SD_Y * rho * xO;
      const gaussCondSd = SD_Y * rootOneMinusR2;

      const nuPost = nu + 1;
      const xRaw = xO / scaleMarg;
      const tCondScale = SD_Y * scaleMarg * Math.sqrt(((nu + xRaw * xRaw) / nuPost) * (1.0 - rho * rho));
      const tCondSd = tCondScale * Math.sqrt(nuPost / (nuPost - 2.0));

      const yMin = -2.0, yMax = 44.0, dy = 0.25;
      const ys = [], pdfG = [], pdfT = [];
      let pExtG = 0.0, pExtT = 0.0;

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

      if (typeof Plotly === "undefined") {
        renderPlotlyUnavailable(root, [
          ["#w6-plot-left", "Joint Distribution: 10 m Wind vs. 500 m Shear"],
          ["#w6-plot-right", "Conditional 500 m Shear PDF"]
        ]);
        return;
      }

      const leftTraces = [
        {
          x: gx,
          y: gy,
          name: "Gaussian Copula",
          mode: "markers",
          marker: { color: "rgba(56, 189, 248, 0.48)", size: 6.5 },
          hovertemplate: "10m Wind=%{x:.1f} m/s<br>500m Shear=%{y:.1f} m/s/km<extra>Gaussian</extra>"
        },
        {
          x: tx,
          y: ty,
          name: "Student-t (\u03BD=" + nu + ")",
          mode: "markers",
          marker: { color: "rgba(248, 113, 113, 0.55)", size: 6.5, symbol: "diamond" },
          hovertemplate: "10m Wind=%{x:.1f} m/s<br>500m Shear=%{y:.1f} m/s/km<extra>Student-t</extra>"
        }
      ];

      const leftLayout = baseLayout({
        title: { text: "Joint Distribution: 10 m Wind vs. 500 m Shear", font: { size: 16, color: "#f4f4f5" }, y: 0.97 },
        xaxis: axisStyle({ title: "10 m Pad Wind (m/s)", range: [0, 22] }),
        yaxis: axisStyle({ title: "500 m Wind Shear (m/s/km)", range: [0, 38] }),
        shapes: [
          { type: "line", x0: uObs, x1: uObs, y0: 0, y1: 38, line: { color: "#fbbf24", width: 2.4, dash: "dash" } },
          { type: "line", x0: 0, x1: 22, y0: SHEAR_THRESH, y1: SHEAR_THRESH, line: { color: "rgba(248,113,113,0.55)", width: 1.6, dash: "dot" } }
        ],
        annotations: [
          { x: uObs, y: 36.5, text: "u_obs = " + uObs.toFixed(1), showarrow: false, font: { size: 14, color: "#fbbf24" }, xanchor: uObs > 15 ? "right" : "left", xshift: uObs > 15 ? -6 : 6 },
          { x: 0.5, y: SHEAR_THRESH + 0.8, xanchor: "left", text: "Extreme Shear (22 m/s/km)", showarrow: false, font: { size: 14, color: "#f87171" } }
        ]
      });

      const peakPdf = Math.max(Math.max.apply(null, pdfG), Math.max.apply(null, pdfT));
      const rightTraces = [
        {
          x: ys,
          y: pdfG,
          name: "Gaussian | u_obs (\u03C3=" + gaussCondSd.toFixed(2) + ")",
          mode: "lines",
          line: { color: "#38bdf8", width: 2.8 },
          fill: "tozeroy",
          fillcolor: "rgba(56, 189, 248, 0.18)",
          hovertemplate: "Shear=%{x:.1f}<br>Gauss=%{y:.4f}<extra></extra>"
        },
        {
          x: ys,
          y: pdfT,
          name: "Student-t | u_obs (\u03C3=" + tCondSd.toFixed(2) + ")",
          mode: "lines",
          line: { color: "#f87171", width: 2.8 },
          fill: "tozeroy",
          fillcolor: "rgba(248, 113, 113, 0.20)",
          hovertemplate: "Shear=%{x:.1f}<br>Student-t=%{y:.4f}<extra></extra>"
        },
        {
          x: [SHEAR_THRESH, SHEAR_THRESH],
          y: [0, peakPdf * 1.06],
          name: "Threshold (22 m/s/km)",
          mode: "lines",
          line: { color: "#fbbf24", width: 2.2, dash: "dash" }
        }
      ];

      const rightLayout = baseLayout({
        title: { text: "Conditional 500 m Shear PDF | u_obs = " + uObs.toFixed(1) + " m/s", font: { size: 16, color: "#f4f4f5" }, y: 0.97 },
        xaxis: axisStyle({ title: "500 m Wind Shear (m/s/km)", range: [0, 40] }),
        yaxis: axisStyle({ title: "Conditional Density", range: [0, peakPdf * 1.16] }),
        shapes: [
          { type: "rect", x0: SHEAR_THRESH, x1: 40, y0: 0, y1: peakPdf * 1.12, fillcolor: "rgba(248,113,113,0.08)", line: { width: 0 } }
        ]
      });

      Plotly.react(root.querySelector("#w6-plot-left"), leftTraces, leftLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w6-plot-right"), rightTraces, rightLayout, PLOT_CONFIG);
    }

    [elUobs, elRho, elNu].forEach(function (el) { el.addEventListener("input", update); });
    root.querySelector("#w6-reset").addEventListener("click", function () {
      elUobs.value = defaults.uObs;
      elRho.value = defaults.rho;
      elNu.value = defaults.nu;
      update();
    });

    update();
  }

  // =========================================================================
  // WIDGET 5: 6-DOF Rocket MC Dispersion & Variance Attribution (#widget-5-mc)
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

  function initWidget5() {
    const root = document.getElementById("widget-5-mc");
    if (!root) return;

    const defaults = { sigVeh: 5.0, sigBl: 2.5, sigJet: 6.0, waiver: 1500, airMode: "coupled" };
    let airMode = defaults.airMode;

    const circleTheta = [];
    for (let a = 0; a <= 360; a += 4) circleTheta.push((a * Math.PI) / 180.0);

    root.innerHTML = `
      <div class="tw-card">
        <div class="tw-head">
          <div>
            <div class="tw-kicker">Interactive Sandbox 7</div>
            <h4 class="tw-title">6-DOF Rocket Monte Carlo Dispersion &amp; Variance Attribution</h4>
            <p class="tw-sub">120-flight joint dispersion (<code>montecarlo.py</code>) attributing landing spread across <code>mean_wind_0_200m</code>, <code>mean_wind_0_3km</code>, <code>pad_air_density</code>, and vehicle &sigma;<sub>veh</sub>.</p>
          </div>
          <div class="tw-actions">
            <div class="tw-toggle-group" role="group" aria-label="Air Model">
              <button type="button" id="w5-btn-coupled" class="tw-toggle-btn active-sky">Full Coupled Air</button>
              <button type="button" id="w5-btn-hybrid" class="tw-toggle-btn">Hybrid air="standard" + Wind</button>
            </div>
            <button type="button" id="w5-reset" class="tw-btn">Reset Defaults</button>
          </div>
        </div>

        <div class="tw-controls tw-cols-4">
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Vehicle Drag/Thrust &sigma;<sub>veh</sub></span>
              <span id="w5-veh-val" class="tw-control-val">5.0%</span>
            </div>
            <input id="w5-veh" type="range" min="1.0" max="10.0" step="0.5" value="${defaults.sigVeh}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>mean_wind_0_200m</span>
              <span id="w5-bl-val" class="tw-control-val">2.50 m/s</span>
            </div>
            <input id="w5-bl" type="range" min="0.5" max="6.0" step="0.25" value="${defaults.sigBl}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>mean_wind_0_3km</span>
              <span id="w5-jet-val" class="tw-control-val">6.0 m/s</span>
            </div>
            <input id="w5-jet" type="range" min="1.0" max="15.0" step="0.5" value="${defaults.sigJet}" class="tw-slider" />
          </label>
          <label class="tw-control">
            <div class="tw-control-top">
              <span>Waiver Radius</span>
              <span id="w5-waiver-val" class="tw-control-val tw-c-amber">1,500 m</span>
            </div>
            <input id="w5-waiver" type="range" min="500" max="3000" step="100" value="${defaults.waiver}" class="tw-slider" />
          </label>
        </div>

        <div class="tw-metrics tw-cols-4">
          <div class="tw-metric">
            <div class="tw-metric-lbl">Inside Waiver</div>
            <div id="w5-m-in" class="tw-metric-val tw-c-emerald">--</div>
            <div id="w5-m-incnt" class="tw-metric-sub">-- / 120 flights</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">90% Apogee Interval</div>
            <div id="w5-m-apo" class="tw-metric-val tw-c-sky">--</div>
            <div id="w5-m-apow" class="tw-metric-sub">Nominal 9,150 m</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Dominant Risk Driver</div>
            <div id="w5-m-dom" class="tw-metric-val tw-c-amber">--</div>
            <div class="tw-metric-sub">Landing dispersion share</div>
          </div>
          <div class="tw-metric">
            <div class="tw-metric-lbl">Mean Radial Drift</div>
            <div id="w5-m-rad" class="tw-metric-val tw-c-primary">--</div>
            <div class="tw-metric-sub">From pad origin</div>
          </div>
        </div>

        <div class="tw-plots">
          <div id="w5-plot-left" class="tw-plot-box"></div>
          <div id="w5-plot-right" class="tw-plot-box"></div>
        </div>

        <div class="tw-callout">
          <strong>Predict &rarr; Test:</strong> Toggle from <em>Full Coupled Air</em> to <em>Hybrid air="standard" + Wind</em> and check how little <code>% Inside Waiver</code> moves—showing why <code>pad_air_density</code> is a small fraction of total landing variance compared to <code>mean_wind_0_200m</code> and <code>mean_wind_0_3km</code>.
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
      btnCoupled.className = "tw-toggle-btn" + (airMode === "coupled" ? " active-sky" : "");
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

      const kBl = 165.0;
      const kJet = 34.0;
      const kVehDrift = 72.0;
      const kRhoDrift = 55.0 * rhoScale;

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

        const dHveh = H0 * 1.15 * (sigVeh / 100.0) * zv;
        const dHrho = H0 * -0.0125 * rhoScale * zr;
        const dHbl = -14.0 * Math.hypot(3.2 + blU, blV) + 44.8;
        apogees[i] = Math.max(2500.0, H0 + dHveh + dHrho + dHbl);

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

      const varVeh = Math.pow(kVehDrift * sigVeh, 2) * (0.85 * 0.85 + 0.52 * 0.52);
      const varBl = 2.0 * Math.pow(kBl * sigBl, 2);
      const varJet = 2.0 * Math.pow(kJet * sigJet, 2);
      const varRho = Math.pow(kRhoDrift, 2);
      const varTot = Math.max(varVeh + varBl + varJet + varRho, 1e-6);

      const shares = [
        { label: "mean_wind_0_200m", pct: (100.0 * varBl) / varTot, color: "#38bdf8" },
        { label: "vehicle_\u03C3_veh", pct: (100.0 * varVeh) / varTot, color: "#fbbf24" },
        { label: "mean_wind_0_3km", pct: (100.0 * varJet) / varTot, color: "#f87171" },
        { label: "pad_air_density", pct: (100.0 * varRho) / varTot, color: "#34d399" }
      ];
      let dom = shares[0];
      for (let i = 1; i < shares.length; i++) {
        if (shares[i].pct > dom.pct) dom = shares[i];
      }

      const elIn = root.querySelector("#w5-m-in");
      elIn.textContent = inPct.toFixed(1) + "%";
      elIn.className = "tw-metric-val " + (inPct >= 95 ? "tw-c-emerald" : inPct >= 85 ? "tw-c-amber" : "tw-c-coral");
      root.querySelector("#w5-m-incnt").textContent = inCount + " / " + W5_N + " flights";
      root.querySelector("#w5-m-apo").textContent =
        Math.round(apoQ05).toLocaleString() + "\u2013" + Math.round(apoQ95).toLocaleString() + " m";
      root.querySelector("#w5-m-apow").textContent = "90% width: \u00B1" + Math.round((apoQ95 - apoQ05) / 2).toLocaleString() + " m";
      root.querySelector("#w5-m-dom").textContent = dom.label + " (" + dom.pct.toFixed(0) + "%)";
      root.querySelector("#w5-m-rad").textContent = Math.round(meanRad).toLocaleString() + " m";

      if (typeof Plotly === "undefined") {
        renderPlotlyUnavailable(root, [
          ["#w5-plot-left", "2D Landing Dispersion (N=120 Trajectories)"],
          ["#w5-plot-right", "Landing Dispersion Variance Attribution"]
        ]);
        return;
      }

      const circX = circleTheta.map(function (t) { return waiver * Math.cos(t); });
      const circY = circleTheta.map(function (t) { return waiver * Math.sin(t); });
      const span = Math.max(waiver * 1.25, 2200);

      const leftTraces = [
        {
          x: circX,
          y: circY,
          name: "Waiver (" + Math.round(waiver) + " m)",
          mode: "lines",
          line: { color: "#fbbf24", width: 2.2, dash: "dash" },
          hoverinfo: "skip"
        },
        {
          x: inX,
          y: inY,
          name: "Inside Waiver (" + inCount + ")",
          mode: "markers",
          marker: { color: "rgba(52, 211, 153, 0.82)", size: 7.5, line: { color: "#09090b", width: 0.8 } },
          hovertemplate: "East=%{x:.0f} m<br>North=%{y:.0f} m<extra>Inside</extra>"
        },
        {
          x: outX,
          y: outY,
          name: "Outside Waiver (" + (W5_N - inCount) + ")",
          mode: "markers",
          marker: { color: "#f87171", size: 8.5, symbol: "x" },
          hovertemplate: "East=%{x:.0f} m<br>North=%{y:.0f} m<extra>Outside</extra>"
        },
        {
          x: [0],
          y: [0],
          name: "Launch Pad",
          mode: "markers",
          marker: { color: "#f4f4f5", size: 12, symbol: "star" },
          hovertemplate: "Launch Pad (0, 0)<extra></extra>"
        }
      ];

      const leftLayout = baseLayout({
        title: { text: "2D Landing Dispersion (N=120 Trajectories)", font: { size: 16, color: "#f4f4f5" }, y: 0.97 },
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
            line: { color: "#09090b", width: 1.2 }
          },
          text: shares.map(function (s) { return s.pct.toFixed(1) + "%"; }).reverse(),
          textposition: "outside",
          textfont: { color: "#f4f4f5", size: 14.5, family: "JetBrains Mono, monospace" },
          hovertemplate: "%{y}: %{x:.1f}% of variance<extra></extra>"
        }
      ];

      const rightLayout = baseLayout({
        title: { text: "Landing Dispersion Variance Attribution", font: { size: 16, color: "#f4f4f5" }, y: 0.97 },
        margin: { l: 170, r: 62, t: 62, b: 74 },
        showlegend: false,
        xaxis: axisStyle({ title: "Share of Total Landing Variance (%)", range: [0, 112] }),
        yaxis: axisStyle({ title: "" })
      });

      Plotly.react(root.querySelector("#w5-plot-left"), leftTraces, leftLayout, PLOT_CONFIG);
      Plotly.react(root.querySelector("#w5-plot-right"), rightTraces, rightLayout, PLOT_CONFIG);
    }

    [elVeh, elBl, elJet, elWaiver].forEach(function (el) { el.addEventListener("input", update); });
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
  // Page-Scoped Auto-Initialization (ONLY mounts whose ID exists on page)
  // =========================================================================

  const WIDGET_REGISTRY = [
    ["widget-0-pipeline", initWidget0],
    ["widget-1-thermo", initWidget1],
    ["widget-2-crps", initWidget2],
    ["widget-4-schaake", initWidget4],
    ["widget-7-metrics", initWidget7],
    ["widget-3-router", initWidget3],
    ["widget-6-copula", initWidget6],
    ["widget-5-mc", initWidget5]
  ];

  function initMountedWidgets() {
    let anyMounted = false;
    for (let i = 0; i < WIDGET_REGISTRY.length; i++) {
      if (document.getElementById(WIDGET_REGISTRY[i][0])) {
        anyMounted = true;
        break;
      }
    }
    if (!anyMounted) return;

    injectWidgetStyles();
    for (let i = 0; i < WIDGET_REGISTRY.length; i++) {
      if (document.getElementById(WIDGET_REGISTRY[i][0])) {
        WIDGET_REGISTRY[i][1]();
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initMountedWidgets);
  } else {
    initMountedWidgets();
  }
})();
