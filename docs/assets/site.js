/* ==========================================================================
   Tempest-ARKNET v4 Multi-Page Shell (9 Pages / 30 Focused Sections)
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
  if (entry && entry.url) window.open(entry.url, "_blank", "noopener,noreferrer");
}

/* Exactly 9 Pages / 30 Clean Sections */
const SITE_NAV = [
  {
    group: "Start",
    pages: [
      {
        id: "index",
        href: "index.html",
        title: "0. Overview & Pipeline Map",
        subs: [
          ["sec-0-1", "0.1 What Tempest-ARKNET solves"],
          ["sec-0-2", "0.2 Interactive end-to-end flow"],
          ["sec-0-3", "0.3 Chapter map & Colab labs"]
        ]
      }
    ]
  },
  {
    group: "Core Pipeline",
    pages: [
      {
        id: "01_data_physics",
        href: "pages/01_data_physics.html",
        title: "1. Data & Atmospheric Physics",
        subs: [
          ["s1-1", "1.1 Multi-source weather inputs"],
          ["s1-2", "1.2 The 44-level vertical height ladder"],
          ["s1-3", "1.3 Thermodynamics & dewpoint encoding"],
          ["s1-4", "1.4 Interactive: Atmosphere & density lab"]
        ]
      },
      {
        id: "02_ai_generator",
        href: "pages/02_ai_generator.html",
        title: "2. Generative AI Core",
        subs: [
          ["s2-1", "2.1 Why Engression beats mean forecasts"],
          ["s2-2", "2.2 Noise conditioning & architecture"],
          ["s2-3", "2.3 Training losses, gusts & vertical W"],
          ["s2-4", "2.4 Interactive: CRPS & spread-skill lab"]
        ]
      },
      {
        id: "03_calibration",
        href: "pages/03_calibration.html",
        title: "3. Calibration & Coherence",
        subs: [
          ["s3-1", "3.1 Weather balloon station calibration"],
          ["s3-2", "3.2 Restoring wind shear (Schaake Shuffle)"],
          ["s3-3", "3.3 Spatial maps & lead-time routing"],
          ["s3-4", "3.4 Interactive: Schaake Shuffle lab"]
        ]
      },
      {
        id: "04_metrics",
        href: "pages/04_metrics.html",
        title: "4. Metrics & Scoring Guide",
        subs: [
          ["s4-1", "4.1 Accuracy + spread (CRPS & Energy Score)"],
          ["s4-2", "4.2 Structure & honesty (Variogram, PIT, SSR)"],
          ["s4-3", "4.3 Launch decisions (Brier Skill Score)"],
          ["s4-4", "4.4 Interactive: Visual metric scorecard"]
        ]
      }
    ]
  },
  {
    group: "Launch Day & Flight Sim",
    pages: [
      {
        id: "05_serving_launch",
        href: "pages/05_serving_launch.html",
        title: "5. Serving & Launch-Day Obs",
        subs: [
          ["s5-1", "5.1 Pure-NumPy serving engine"],
          ["s5-2", "5.2 Live pad, METAR & radar assimilation"],
          ["s5-3", "5.3 v2 toolkit & Student-t copulas"],
          ["s5-4", "5.4 Interactive: Obs router & copula labs"]
        ]
      },
      {
        id: "06_flight_mc",
        href: "pages/06_flight_mc.html",
        title: "6. Flight-Sim & Monte Carlo",
        subs: [
          ["s6-1", "6.1 Profile readers & boundary defaults"],
          ["s6-2", "6.2 Dryden turbulence & variance attribution"],
          ["s6-3", "6.3 Interactive: 6-DOF dispersion lab"]
        ]
      }
    ]
  },
  {
    group: "Audit & Experiments",
    pages: [
      {
        id: "07_guardrails",
        href: "pages/07_guardrails.html",
        title: "7. Bugs (B1-B14) & Guardrails",
        subs: [
          ["s7-1", "7.1 Confirmed codebase bugs (B1-B14)"],
          ["s7-2", "7.2 Python 3.12 compatibility note"]
        ]
      },
      {
        id: "experiments",
        href: "tests/experiments.html",
        title: "8. Ranked Experiments (60)",
        subs: [
          ["s8-1", "8.1 Outcome distribution & charts"],
          ["s8-2", "8.2 Ranked experiment tiers (1-4)"]
        ]
      }
    ]
  }
];

const GLOSSARY = [
  { term: "AGL / MSL (ASL)", cat: "Physics", plain: "Height above local ground (AGL) vs. above mean sea level (MSL). All 44 model heights are AGL (10 m to 18 km).", tech: "tempest/_core.py:6" },
  { term: "AdaLN / FiLM", cat: "ML", plain: "A conditioning layer that shifts and scales activations for each random noise vector z_eps so one network outputs diverse weather worlds.", tech: "LN(h) * (1 + s) + b" },
  { term: "Brier Skill Score (BSS)", cat: "Metrics", plain: "How much better a Go/No-Go probability is than guessing the historical base rate (0 = climatology, 1 = perfect).", tech: "BSS = 1 - BS / BS_ref" },
  { term: "Copula (Gaussian vs. Student-t)", cat: "ML", plain: "Mathematical glue binding altitude margins together. Student-t keeps simultaneous extreme gusts coupled; Gaussian lets them decouple.", tech: "lambda_U = 0 (Gaussian) vs. > 0 (Student-t)" },
  { term: "CRPS", cat: "Metrics", plain: "Continuous Ranked Probability Score — rewards ensembles for being both close to truth and honestly spread. Lower is better.", tech: "Unbiased spread denominator M(M-1)" },
  { term: "D = 179 State Vector", cat: "Physics", plain: "Every ensemble profile has 179 numbers: u, v, T, and RH/lnd across 44 heights plus surface t2m, sp, and rh2m.", tech: "tempest/_core.py:7-9, 39" },
  { term: "Dewpoint Depression (dpd)", cat: "Physics", plain: "T - T_d transformed with log(1 + dpd) so dry desert air doesn't slam into a 0% RH boundary.", tech: "dpd = max(T - T_d, 0)" },
  { term: "Dryden Turbulence", cat: "Physics", plain: "MIL-HDBK-1797 stochastic wind-gust filter turning white noise into altitude-correlated 3D gusts.", tech: "tempest_weather/flight/dryden.py (exact_ar=False default)" },
  { term: "Energy Score (ES)", cat: "Metrics", plain: "Multi-altitude version of CRPS scoring the entire 179-D vertical profile simultaneously.", tech: "Normalized by 1/sqrt(D)" },
  { term: "Engression", cat: "ML", plain: "Single-step generative regression taking weather inputs plus random noise to output realistic profiles without slow diffusion.", tech: "Shen & Meinshausen (2024)" },
  { term: "Hypsometric Equation", cat: "Physics", plain: "Links air pressure, virtual temperature, and layer thickness so warmer/moister air expands hydrostatically.", tech: "Delta Z = (R_d * T_v / g_0) * ln(p_1 / p_2)" },
  { term: "IGRAv2", cat: "Data", plain: "Global historical archive of real weather balloon soundings used as ground truth for calibration and verification.", tech: "NOAA/NCEI Radiosonde Archive" },
  { term: "M_CAL = 199", cat: "Calibration", plain: "Calibrated ensemble size placing members on clean 0.5% quantile steps from 0.5% to 99.5%.", tech: "tempest_weather/api.py:27" },
  { term: "PIT Histogram", cat: "Metrics", plain: "Shows where reality landed inside the forecast ensemble. Flat = honest; U-shaped = overconfident; dome = too wide.", tech: "Probability Integral Transform" },
  { term: "Schaake Shuffle", cat: "Calibration", plain: "Re-orders calibrated altitude values to match historical ERA5 (< 2021) vertical rank templates so wind shear stays physical.", tech: "tempest/export_tool.py:128-150" },
  { term: "Spread-Skill Ratio (SSR)", cat: "Metrics", plain: "Ratio of ensemble spread to mean RMSE. Ideal calibrated value is 1.00.", tech: "sqrt(mean variance) / RMSE" },
  { term: "TAU_H = 6.3 h / OWN_STATION_KM = 5.0", cat: "Launch Day", plain: "Live pad/METAR observation influence decays exponentially with 6.3 h timescale and full weight inside 5.0 km.", tech: "tempest_weather_v2/obs.py:22, 29" },
  { term: "UR5 Sequence", cat: "Calibration", plain: "Shipped-ON climate-mode 10 m wind sequence post-processor (speed map + spread scale + 2-regime Markov chain).", tech: "OPTIONS['ur5_sequence'] = True (api.py:28)" },
  { term: "Variogram Score", cat: "Metrics", plain: "Scores whether the ensemble gets vertical differences (wind shear between heights) right.", tech: "Pairwise |X_i - X_j|^0.5" },
  { term: "Virtual Temperature (T_v)", cat: "Physics", plain: "Equivalent dry-air temperature accounting for lighter water-vapor molecules in humid air.", tech: "T_v = T * (1 + 0.6078 * q)" }
];

function getBase() {
  return document.body.dataset.base || "";
}

function buildNav() {
  const nav = document.getElementById("site-sidebar-nav");
  if (!nav) return;
  const base = getBase();
  const curId = document.body.dataset.pageId || "";

  nav.innerHTML = SITE_NAV.map(group => {
    const pagesHtml = group.pages.map(page => {
      const isCur = page.id === curId;
      const cls = isCur ? "is-open is-current" : "";
      const subs = (page.subs || []).map(([sid, stitle]) => {
        const href = isCur ? `#${sid}` : `${base}${page.href}#${sid}`;
        return `<li><a href="${href}" data-sub-target="${sid}">${stitle}</a></li>`;
      }).join("");
      return `
        <div class="nav-chapter ${cls}">
          <div class="nav-chapter-row">
            <button type="button" class="nav-expand-btn" aria-label="Toggle sections">&#9656;</button>
            <a class="nav-chapter-link" href="${base}${page.href}">${page.title}</a>
          </div>
          <ul class="nav-sublist">${subs}</ul>
        </div>
      `;
    }).join("");
    return `<div class="nav-group"><p class="nav-group-label">${group.group}</p>${pagesHtml}</div>`;
  }).join("");

  nav.querySelectorAll(".nav-expand-btn").forEach(btn => {
    btn.addEventListener("click", () => btn.closest(".nav-chapter")?.classList.toggle("is-open"));
  });
}

function buildTocAndPager() {
  const base = getBase();
  const curId = document.body.dataset.pageId || "";
  const sections = Array.from(document.querySelectorAll("main section.doc-section[id]"));
  const tocList = document.getElementById("on-this-page-list");
  if (tocList && sections.length) {
    tocList.innerHTML = sections.map(sec => {
      const h2 = sec.querySelector("h2");
      const num = sec.querySelector(".sec-num");
      const label = h2 ? h2.textContent.trim() : sec.id;
      const prefix = num ? `${num.textContent.trim()} ` : "";
      return `<li><a href="#${sec.id}" data-toc-target="${sec.id}">${prefix}${label}</a></li>`;
    }).join("");
  }

  const pager = document.getElementById("chapter-pager");
  if (pager) {
    const flat = SITE_NAV.flatMap(g => g.pages);
    const idx = flat.findIndex(p => p.id === curId);
    const prev = idx > 0 ? flat[idx - 1] : null;
    const next = idx >= 0 && idx < flat.length - 1 ? flat[idx + 1] : null;
    pager.innerHTML = `
      ${prev ? `<a class="pager-link" href="${base}${prev.href}"><span class="pager-dir">&larr; Previous</span><span class="pager-name">${prev.title}</span></a>` : `<div></div>`}
      ${next ? `<a class="pager-link is-next" href="${base}${next.href}"><span class="pager-dir">Next &rarr;</span><span class="pager-name">${next.title}</span></a>` : `<div></div>`}
    `;
  }

  const fill = document.getElementById("progress-fill");
  const tocLinks = Array.from(document.querySelectorAll("[data-toc-target]"));
  const sideLinks = Array.from(document.querySelectorAll(".nav-chapter.is-current [data-sub-target]"));

  function onScroll() {
    const st = window.scrollY || document.documentElement.scrollTop;
    const dh = document.documentElement.scrollHeight - window.innerHeight;
    if (fill && dh > 0) fill.style.width = `${Math.min(100, Math.max(0, (st / dh) * 100))}%`;
    if (!sections.length) return;
    let active = sections[0].id;
    for (const s of sections) {
      if (s.getBoundingClientRect().top <= 160) active = s.id;
    }
    tocLinks.forEach(a => a.classList.toggle("is-active", a.getAttribute("data-toc-target") === active));
    sideLinks.forEach(a => a.classList.toggle("is-active", a.getAttribute("data-sub-target") === active));
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

let activeGlossaryCat = "All";

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderGlossary() {
  const list = document.getElementById("glossary-list");
  if (!list) return;
  const q = (document.getElementById("glossary-search")?.value || "").trim().toLowerCase();
  const items = GLOSSARY.filter(g => {
    const catOk = activeGlossaryCat === "All" || g.cat === activeGlossaryCat;
    const txtOk = !q || g.term.toLowerCase().includes(q) || g.plain.toLowerCase().includes(q) || g.tech.toLowerCase().includes(q);
    return catOk && txtOk;
  });
  const cnt = document.getElementById("glossary-count");
  if (cnt) cnt.textContent = `${items.length} of ${GLOSSARY.length} terms`;
  list.innerHTML = items.map(g => `
    <div class="glossary-entry">
      <div style="display:flex;justify-content:space-between;align-items:baseline;gap:0.75rem;margin-bottom:0.4rem;">
        <strong style="font-family:var(--font-display);font-size:1.08rem;color:var(--ink-primary);">${g.term}</strong>
        <span style="font-family:var(--font-mono);font-size:0.76rem;color:var(--accent);text-transform:uppercase;">${g.cat}</span>
      </div>
      <p style="margin:0 0 0.45rem;font-size:0.96rem;color:var(--ink-body);">${g.plain}</p>
      <div style="font-family:var(--font-mono);font-size:0.82rem;color:var(--ink-muted);">${g.tech}</div>
    </div>
  `).join("") || `<div class="status-empty">No glossary terms match "${escapeHtml(q)}". Clear the search box to see all ${GLOSSARY.length} terms.</div>`;
}

function openGlossary() {
  document.getElementById("overlay-dim")?.classList.add("is-open");
  document.getElementById("glossary-drawer")?.classList.add("is-open");
  renderGlossary();
}

function closeGlossary() {
  document.getElementById("overlay-dim")?.classList.remove("is-open");
  document.getElementById("glossary-drawer")?.classList.remove("is-open");
}

let zoomScale = 1.0;
function openSvgZoom(trigger) {
  const stage = trigger.closest(".visual-stage, section");
  const svg = stage ? stage.querySelector("svg") : null;
  const target = document.getElementById("zoom-content");
  const modal = document.getElementById("zoom-modal");
  if (!svg || !target || !modal) return;
  target.innerHTML = "";
  const clone = svg.cloneNode(true);
  clone.style.maxWidth = "none";
  clone.style.minWidth = "860px";
  clone.style.height = "auto";
  target.appendChild(clone);
  zoomScale = 1.0;
  applyZoom();
  modal.classList.add("is-open");
}
function applyZoom() {
  const t = document.getElementById("zoom-content");
  const p = document.getElementById("zoom-pct");
  if (t) t.style.transform = `scale(${zoomScale})`;
  if (p) p.textContent = `${Math.round(zoomScale * 100)}%`;
}
function adjustZoom(d) { zoomScale = Math.min(2.5, Math.max(0.5, zoomScale + d)); applyZoom(); }
function resetZoom() { zoomScale = 1.0; applyZoom(); }
function closeZoom() { document.getElementById("zoom-modal")?.classList.remove("is-open"); }

function injectModals() {
  const d = document.createElement("div");
  d.innerHTML = `
    <div id="overlay-dim" class="overlay-dim" onclick="closeGlossary()"></div>
    <aside id="glossary-drawer" class="glossary-drawer" aria-label="Glossary">
      <div class="glossary-head">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.85rem;">
          <h2 style="font-family:var(--font-display);font-size:1.4rem;margin:0;color:var(--ink-primary);">Glossary</h2>
          <button type="button" class="action-btn" onclick="closeGlossary()">Close</button>
        </div>
        <input id="glossary-search" type="search" placeholder="Filter terms (CRPS, Schaake, Dryden)..." style="width:100%;padding:0.65rem 0.9rem;border:1px solid var(--border-strong);border-radius:var(--radius);background:var(--bg-elevated);color:var(--ink-primary);font-size:0.95rem;" />
        <div style="display:flex;flex-wrap:wrap;gap:0.45rem;margin-top:0.75rem;">
          <button type="button" class="action-btn action-btn-active gcat-btn" data-gcat="All">All</button>
          <button type="button" class="action-btn gcat-btn" data-gcat="Physics">Physics</button>
          <button type="button" class="action-btn gcat-btn" data-gcat="Data">Data</button>
          <button type="button" class="action-btn gcat-btn" data-gcat="ML">ML</button>
          <button type="button" class="action-btn gcat-btn" data-gcat="Metrics">Metrics</button>
          <button type="button" class="action-btn gcat-btn" data-gcat="Calibration">Calibration</button>
          <button type="button" class="action-btn gcat-btn" data-gcat="Launch Day">Launch Day</button>
        </div>
        <div id="glossary-count" style="margin-top:0.65rem;font-family:var(--font-mono);font-size:0.8rem;color:var(--ink-muted);"></div>
      </div>
      <div id="glossary-list" class="glossary-body"></div>
    </aside>
    <div id="zoom-modal" class="zoom-modal">
      <div class="zoom-bar">
        <span style="font-family:var(--font-display);font-size:1.15rem;font-weight:600;color:var(--ink-primary);">Diagram Inspector</span>
        <div style="display:flex;align-items:center;gap:0.5rem;">
          <button type="button" class="action-btn" onclick="adjustZoom(-0.2)">&minus;</button>
          <span id="zoom-pct" style="font-family:var(--font-mono);min-width:52px;text-align:center;">100%</span>
          <button type="button" class="action-btn" onclick="adjustZoom(0.2)">+</button>
          <button type="button" class="action-btn" onclick="resetZoom()">Reset</button>
          <button type="button" class="action-btn" onclick="closeZoom()" style="border-color:var(--sem-red);color:var(--sem-red);">Close (Esc)</button>
        </div>
      </div>
      <div class="zoom-stage"><div id="zoom-content" style="transform-origin:center;"></div></div>
    </div>
  `;
  document.body.appendChild(d);
}

document.addEventListener("DOMContentLoaded", () => {
  injectModals();
  buildNav();
  buildTocAndPager();

  const sb = document.getElementById("site-sidebar");
  document.getElementById("mobile-nav-btn")?.addEventListener("click", () => sb?.classList.toggle("is-open"));
  document.getElementById("glossary-search")?.addEventListener("input", renderGlossary);
  document.querySelectorAll(".gcat-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      activeGlossaryCat = btn.getAttribute("data-gcat") || "All";
      document.querySelectorAll(".gcat-btn").forEach(b => b.classList.toggle("action-btn-active", b === btn));
      renderGlossary();
    });
  });

  document.addEventListener("keydown", e => {
    if (e.key === "Escape") { closeGlossary(); closeZoom(); sb?.classList.remove("is-open"); }
  });

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
