/* ============================================================
   Competitor Monitor — Dashboard JavaScript
   Vanilla JS, no framework, fetch() API
   ============================================================ */

// --------------- State ---------------

const state = {
  domain: "",
  competitor: "",
  type: "",
  days: "30",
  changes: [],       // filtered changes for timeline
  allChanges: [],    // unfiltered, used for per-competitor counts
  stats: {},
  competitors: [],   // [{domain, page_count, last_seen}]
  pages: [],         // inventory pages
  selectedChange: null,
  activeTab: "changes",
  inventoryLoaded: false,
};

// --------------- Type config ---------------

const TYPE_LABELS = {
  new_page:        "Nouvelle page",
  removed_page:    "Page supprimée",
  schema_changed:  "Schéma modifié",
  meta_changed:    "Meta modifiée",
  title_changed:   "Titre modifié",
  h1_changed:      "H1 modifié",
  content_updated: "Contenu MàJ",
};

const TYPE_ICONS = {
  new_page:        "✨",
  removed_page:    "🗑",
  schema_changed:  "🔧",
  meta_changed:    "📝",
  title_changed:   "✏️",
  h1_changed:      "🔤",
  content_updated: "📄",
};

const SEVERITY_LABELS = {
  high:   "Haute",
  medium: "Moyenne",
  low:    "Faible",
};

const TYPE_VAR = {
  new_page:        "new-page",
  removed_page:    "removed-page",
  schema_changed:  "schema-changed",
  meta_changed:    "meta-changed",
  title_changed:   "title-changed",
  h1_changed:      "h1-changed",
  content_updated: "content-updated",
};

// --------------- DOM helpers ---------------

function el(id) { return document.getElementById(id); }

function escHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
    return d.toLocaleDateString("fr-FR", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
  } catch (e) { return iso; }
}

function formatDateShort(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
    return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });
  } catch (e) { return iso; }
}

// --------------- Word diff ---------------

function wordDiff(before, after) {
  const bw = String(before || "").trim().split(/\s+/).filter(Boolean);
  const aw = String(after  || "").trim().split(/\s+/).filter(Boolean);
  const m = bw.length, n = aw.length;

  // LCS dynamic programming
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = bw[i-1] === aw[j-1] ? dp[i-1][j-1] + 1 : Math.max(dp[i-1][j], dp[i][j-1]);

  // Backtrack
  const ops = [];
  let i = m, j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && bw[i-1] === aw[j-1]) {
      ops.unshift({ t: "=", w: bw[i-1] }); i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j-1] >= dp[i-1][j])) {
      ops.unshift({ t: "+", w: aw[j-1] }); j--;
    } else {
      ops.unshift({ t: "-", w: bw[i-1] }); i--;
    }
  }

  return ops.map(op => {
    if (op.t === "=") return escHtml(op.w);
    if (op.t === "+") return `<ins class="wdiff-add">${escHtml(op.w)}</ins>`;
    return `<del class="wdiff-del">${escHtml(op.w)}</del>`;
  }).join(" ");
}

function schemaDiff(before, after) {
  const bTypes = (before.schema_types || []);
  const aTypes = (after.schema_types  || []);
  const removed = bTypes.filter(t => !aTypes.includes(t));
  const added   = aTypes.filter(t => !bTypes.includes(t));
  const kept    = bTypes.filter(t =>  aTypes.includes(t));

  let html = '<div class="schema-diff">';
  if (removed.length)
    html += removed.map(t => `<span class="sdiff-pill sdiff-removed">${escHtml(t)}</span>`).join("");
  if (added.length)
    html += added.map(t => `<span class="sdiff-pill sdiff-added">${escHtml(t)}</span>`).join("");
  if (kept.length)
    html += kept.map(t => `<span class="sdiff-pill sdiff-kept">${escHtml(t)}</span>`).join("");
  html += '</div>';
  return html;
}

// --------------- API ---------------

async function apiFetch(path) {
  try {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error("API error:", path, err);
    return null;
  }
}

// --------------- Data loading ---------------

async function fetchDomains() {
  const domains = await apiFetch("/api/domains");
  if (!domains) return;

  const select = el("domain-select");
  if (!select) return;

  if (domains.length === 0) {
    select.innerHTML = '<option value="">Aucun domaine trouvé</option>';
    return;
  }

  select.innerHTML = domains.map(d =>
    `<option value="${escHtml(d.slug)}">${escHtml(d.slug)} (${d.run_count} run${d.run_count > 1 ? "s" : ""})</option>`
  ).join("");

  state.domain = domains[0].slug;
  select.value = state.domain;
  await loadData();
}

async function fetchStats() {
  if (!state.domain) return;
  const params = new URLSearchParams({ domain: state.domain, days: state.days });
  const data = await apiFetch(`/api/stats?${params}`);
  if (!data) return;
  state.stats = data;
  const bt = data.by_type || {};
  const setText = (id, val) => { const n = el(id); if (n) n.textContent = val || 0; };
  setText("stat-new",     bt.new_page);
  setText("stat-removed", bt.removed_page);
  setText("stat-schema",  bt.schema_changed);
  setText("stat-meta",    bt.meta_changed);
  setText("stat-title",   bt.title_changed);
  setText("stat-h1",      bt.h1_changed);
}

async function fetchCompetitors() {
  if (!state.domain) return;
  const params = new URLSearchParams({ domain: state.domain });
  const data = await apiFetch(`/api/competitors?${params}`);
  if (!data) return;
  state.competitors = data;

  // Populate filter selects
  [el("filter-competitor"), el("inventory-filter-comp")].forEach(select => {
    if (!select) return;
    const cur = select.value;
    select.innerHTML = '<option value="">Tous les concurrents</option>';
    data.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.domain;
      opt.textContent = `${c.domain} (${c.page_count} pages)`;
      select.appendChild(opt);
    });
    if (cur) select.value = cur;
  });

  if (state.activeTab === "competitors") renderCompetitorsTab();
}

async function fetchChanges() {
  if (!state.domain) return;
  const timeline = el("timeline");
  if (timeline) timeline.innerHTML = '<div class="loading-spinner">Chargement…</div>';

  const params = new URLSearchParams({ domain: state.domain, days: state.days, limit: "500" });
  if (state.competitor) params.set("competitor", state.competitor);
  if (state.type) params.set("type", state.type);

  const data = await apiFetch(`/api/changes?${params}`);
  if (!data) {
    if (timeline) timeline.innerHTML = '<div class="empty-state"><div class="empty-icon">⚠️</div><p>Erreur lors du chargement.</p></div>';
    return;
  }

  state.changes = data.changes || [];

  // Also fetch unfiltered for per-competitor stats used in Concurrents tab
  if (!state.competitor && !state.type) {
    state.allChanges = [...state.changes];
  }

  renderTimeline(state.changes);
}

async function fetchAllChanges() {
  if (!state.domain) return;
  const params = new URLSearchParams({ domain: state.domain, days: state.days, limit: "1000" });
  const data = await apiFetch(`/api/changes?${params}`);
  if (data) state.allChanges = data.changes || [];
}

async function fetchPages() {
  if (!state.domain) return;
  const inventoryList = el("inventory-list");
  if (inventoryList) inventoryList.innerHTML = '<div class="loading-spinner">Chargement de l\'inventaire…</div>';

  const params = new URLSearchParams({ domain: state.domain });
  const data = await apiFetch(`/api/pages?${params}`);
  if (!data) {
    if (inventoryList) inventoryList.innerHTML = '<div class="empty-state"><div class="empty-icon">⚠️</div><p>Erreur de chargement.</p></div>';
    return;
  }
  state.pages = data.pages || [];
  state.inventoryLoaded = true;
  renderInventoryTab(state.pages);
}

async function loadData() {
  if (!state.domain) return;
  state.inventoryLoaded = false;
  await Promise.all([fetchStats(), fetchChanges(), fetchCompetitors()]);
  // Fetch all changes for per-competitor stats (only if needed)
  if (state.competitor || state.type) await fetchAllChanges();
  if (state.activeTab === "inventory") await fetchPages();
}

// --------------- TAB MANAGEMENT ---------------

function switchTab(tabName) {
  state.activeTab = tabName;

  document.querySelectorAll(".tab-btn").forEach(btn => {
    const active = btn.dataset.tab === tabName;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });

  document.querySelectorAll(".tab-content").forEach(pane => {
    pane.classList.toggle("hidden", pane.id !== `tab-${tabName}`);
  });

  if (tabName === "competitors") renderCompetitorsTab();
  if (tabName === "inventory" && !state.inventoryLoaded) fetchPages();

  // Close detail panel when switching away from changes
  if (tabName !== "changes") closeDetail();
}

// --------------- TIMELINE RENDER ---------------

function renderTimeline(changes) {
  const timeline = el("timeline");
  if (!timeline) return;

  if (changes.length === 0) {
    timeline.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📊</div>
        <p>Aucun changement détecté pour la période sélectionnée.</p>
      </div>`;
    return;
  }

  // Group by date
  const groups = {};
  changes.forEach(c => {
    const d = (c.detected_at || "").slice(0, 10) || "inconnu";
    if (!groups[d]) groups[d] = [];
    groups[d].push(c);
  });

  const sortedDates = Object.keys(groups).sort().reverse();

  const html = sortedDates.map(dateStr => {
    const group = groups[dateStr];
    const cardsHtml = group.map((change, idx) => renderChangeCard(change, idx, dateStr)).join("");
    return `
      <div class="date-group">
        <div class="date-group-header">
          <h3>${escHtml(formatDate(dateStr))}</h3>
          <span class="date-group-count">${group.length} changement${group.length > 1 ? "s" : ""}</span>
          <div class="date-group-line"></div>
        </div>
        ${cardsHtml}
      </div>`;
  }).join("");

  timeline.innerHTML = html;

  timeline.querySelectorAll(".change-card").forEach(card => {
    card.addEventListener("click", () => {
      const dateStr = card.dataset.date;
      const idx = parseInt(card.dataset.idx, 10);
      const group = groups[dateStr];
      if (group && group[idx] !== undefined) {
        showDetail(group[idx]);
        timeline.querySelectorAll(".change-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
      }
    });
  });
}

function renderChangeCard(change, idx, dateStr) {
  const type = change.type || "";
  const label = TYPE_LABELS[type] || type;
  const icon  = TYPE_ICONS[type] || "•";
  const comp  = change.competitor || "";
  const url   = change.url || "";
  const severity = change.severity || "";
  const meta  = change.metadata || {};

  const title = meta.title || change.title || "";
  const wc = meta.word_count || change.word_count;
  const schema = meta.schema_types || change.schema_types || [];

  const metaParts = [];
  if (title) metaParts.push(escHtml(title.slice(0, 80) + (title.length > 80 ? "…" : "")));
  if (wc) metaParts.push(`${wc} mots`);
  if (schema.length) metaParts.push(schema.slice(0, 3).map(escHtml).join(", "));
  const metaLine = metaParts.join(" · ");

  const severityDot = severity ? `<span class="severity-dot ${escHtml(severity)}" title="Sévérité ${escHtml(SEVERITY_LABELS[severity] || severity)}"></span>` : "";

  return `
    <div class="change-card" data-type="${escHtml(type)}" data-date="${escHtml(dateStr)}" data-idx="${idx}">
      <div class="card-top">
        <span class="change-badge">${icon} ${escHtml(label)}</span>
        <span class="competitor-tag">${escHtml(comp)}</span>
        ${severityDot}
      </div>
      <div class="change-url">${escHtml(url)}</div>
      ${metaLine ? `<div class="change-meta">${metaLine}</div>` : ""}
      <div class="card-arrow">›</div>
    </div>`;
}

// --------------- COMPETITORS TAB ---------------

function renderCompetitorsTab() {
  const grid = el("competitor-grid");
  if (!grid) return;

  if (!state.competitors.length) {
    grid.innerHTML = `<div class="empty-state">
      <div class="empty-icon">🏢</div>
      <p>Aucun concurrent détecté. Lancez le monitor pour créer un snapshot.</p>
    </div>`;
    return;
  }

  // Build per-competitor change counts from allChanges
  const changeCounts = {};
  state.allChanges.forEach(c => {
    changeCounts[c.competitor] = (changeCounts[c.competitor] || 0) + 1;
  });

  grid.innerHTML = state.competitors.map(comp => {
    const count = changeCounts[comp.domain] || 0;
    const favicon = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(comp.domain)}&sz=32`;
    const changesBadge = count > 0
      ? `<span class="comp-changes-badge">${count} changement${count > 1 ? "s" : ""}</span>`
      : `<span class="comp-changes-badge zero">Aucun changement</span>`;

    return `
      <div class="competitor-card" data-domain="${escHtml(comp.domain)}">
        <div class="comp-card-header">
          <img class="comp-favicon" src="${escHtml(favicon)}" alt="" onerror="this.style.display='none'">
          <div class="comp-domain">${escHtml(comp.domain)}</div>
        </div>
        <div class="comp-stats">
          <div class="comp-stat">
            <span class="comp-stat-value">${comp.page_count}</span>
            <span class="comp-stat-label">pages indexées</span>
          </div>
          <div class="comp-stat">
            <span class="comp-stat-value">${formatDateShort(comp.last_seen)}</span>
            <span class="comp-stat-label">dernier snapshot</span>
          </div>
        </div>
        ${changesBadge}
        <div class="comp-actions">
          <button class="comp-btn-changes" data-domain="${escHtml(comp.domain)}">
            Voir les changements →
          </button>
          <a class="comp-btn-visit" href="https://${escHtml(comp.domain)}" target="_blank" rel="noopener noreferrer">
            Visiter ↗
          </a>
        </div>
      </div>`;
  }).join("");

  grid.querySelectorAll(".comp-btn-changes").forEach(btn => {
    btn.addEventListener("click", () => {
      const domain = btn.dataset.domain;
      // Switch to changes tab and apply competitor filter
      state.competitor = domain;
      el("filter-competitor").value = domain;
      document.querySelectorAll(".stat-card").forEach(c => c.classList.remove("active"));
      state.type = "";
      el("filter-type").value = "";
      switchTab("changes");
      fetchChanges();
    });
  });
}

// --------------- INVENTORY TAB ---------------

function renderInventoryTab(pages) {
  const list = el("inventory-list");
  const countEl = el("inventory-count");
  if (!list) return;

  if (!pages.length) {
    list.innerHTML = `<div class="empty-state">
      <div class="empty-icon">📋</div>
      <p>Aucune page trouvée. Lancez le monitor pour créer un snapshot.</p>
    </div>`;
    if (countEl) countEl.textContent = "";
    return;
  }

  if (countEl) countEl.textContent = `${pages.length} URLs`;

  // Group by competitor
  const grouped = {};
  pages.forEach(p => {
    if (!grouped[p.competitor]) grouped[p.competitor] = [];
    grouped[p.competitor].push(p);
  });

  list.innerHTML = Object.entries(grouped).map(([comp, compPages]) => `
    <div class="inv-group" id="inv-group-${escHtml(comp.replace(/\./g, "-"))}">
      <div class="inv-group-header" data-group="${escHtml(comp)}">
        <span class="inv-group-toggle">▼</span>
        <span class="inv-group-domain">${escHtml(comp)}</span>
        <span class="inv-group-count">${compPages.length} pages</span>
      </div>
      <div class="inv-group-body">
        ${compPages.map(p => renderInventoryRow(p)).join("")}
      </div>
    </div>
  `).join("");

  // Collapse/expand groups
  list.querySelectorAll(".inv-group-header").forEach(hdr => {
    hdr.addEventListener("click", () => {
      const body = hdr.nextElementSibling;
      const toggle = hdr.querySelector(".inv-group-toggle");
      const open = !body.classList.contains("collapsed");
      body.classList.toggle("collapsed", open);
      toggle.textContent = open ? "▶" : "▼";
    });
  });
}

function renderInventoryRow(page) {
  const schemaHtml = (page.schema_types || []).slice(0, 4)
    .map(t => `<span class="inv-schema-pill">${escHtml(t)}</span>`).join("");
  const wc = page.word_count ? `<span class="inv-wc">${page.word_count} mots</span>` : "";
  const title = page.title || "";

  return `
    <div class="inv-row" data-url="${escHtml(page.url)}">
      <div class="inv-row-main">
        <a class="inv-url" href="${escHtml(page.url)}" target="_blank" rel="noopener noreferrer"
           title="${escHtml(page.url)}">${escHtml(page.url)}</a>
        ${title ? `<div class="inv-title">${escHtml(title)}</div>` : ""}
      </div>
      <div class="inv-row-meta">
        ${schemaHtml}
        ${wc}
      </div>
    </div>`;
}

function filterInventory() {
  const search = (el("inventory-search")?.value || "").toLowerCase().trim();
  const compFilter = el("inventory-filter-comp")?.value || "";

  let filtered = state.pages;
  if (compFilter) filtered = filtered.filter(p => p.competitor === compFilter);
  if (search) filtered = filtered.filter(p =>
    (p.url || "").toLowerCase().includes(search) ||
    (p.title || "").toLowerCase().includes(search)
  );

  renderInventoryTab(filtered);
}

// --------------- DETAIL PANEL ---------------

function showDetail(change) {
  state.selectedChange = change;
  const panel = el("detail-panel");
  const overlay = el("overlay");
  const content = el("detail-content");
  if (!panel || !content) return;

  const type = change.type || "";
  const label = TYPE_LABELS[type] || type;
  const icon  = TYPE_ICONS[type]  || "•";
  const url   = change.url || "";
  const comp  = change.competitor || "";
  const severity = change.severity || "";
  const meta  = change.metadata || {};
  const cssVar = TYPE_VAR[type] || "content-updated";

  let html = `
    <div class="detail-badge-row">
      <span class="detail-type-badge" style="background:var(--color-${cssVar}-bg);color:var(--color-${cssVar})">
        ${icon} ${escHtml(label)}
      </span>
      ${severity ? `<span class="detail-severity severity-tag ${escHtml(severity)}">${escHtml(SEVERITY_LABELS[severity] || severity)}</span>` : ""}
    </div>
    <div class="detail-url">
      <a href="${escHtml(url)}" target="_blank" rel="noopener noreferrer">${escHtml(url)}</a>
      <a class="detail-ext-link" href="${escHtml(url)}" target="_blank" rel="noopener noreferrer" title="Ouvrir dans un nouvel onglet">↗</a>
    </div>`;

  html += `<div class="detail-section">
    <div class="detail-section-title">Informations</div>
    <div class="detail-meta-grid">
      <span class="detail-meta-label">Concurrent</span>
      <span class="detail-meta-value">
        <a href="https://${escHtml(comp)}" target="_blank" rel="noopener noreferrer" class="comp-link">${escHtml(comp)}</a>
      </span>
      <span class="detail-meta-label">Détecté le</span>
      <span class="detail-meta-value">${escHtml(formatDate(change.detected_at || ""))}</span>
    </div>
  </div>`;

  if (type === "new_page")     html += renderNewPageDetail(change, meta);
  else if (type === "removed_page") html += renderRemovedPageDetail(change);
  else if (type === "schema_changed") html += renderSchemaDiffDetail(change);
  else if (["meta_changed", "title_changed", "h1_changed"].includes(type)) html += renderTextDiffDetail(change, type);
  else if (type === "content_updated") html += renderContentUpdateDetail(change);

  content.innerHTML = html;
  panel.classList.add("open");
  if (overlay) overlay.classList.add("visible");
  el("timeline")?.classList.add("panel-open");
}

function renderNewPageDetail(change, meta) {
  const title = meta.title || "";
  const h1    = meta.h1 || "";
  const desc  = meta.meta_description || "";
  const wc    = meta.word_count;
  const ctype = meta.content_type || change.content_type || "";
  const schema = meta.schema_types || [];

  let html = "";
  if (title || h1 || desc || wc || ctype) {
    html += `<div class="detail-section">
      <div class="detail-section-title">Métadonnées</div>
      <div class="detail-meta-grid">`;
    if (title) html += `<span class="detail-meta-label">Titre</span><span class="detail-meta-value">${escHtml(title)}</span>`;
    if (h1)    html += `<span class="detail-meta-label">H1</span><span class="detail-meta-value">${escHtml(h1)}</span>`;
    if (desc)  html += `<span class="detail-meta-label">Meta desc.</span><span class="detail-meta-value">${escHtml(desc)}</span>`;
    if (wc)    html += `<span class="detail-meta-label">Mots</span><span class="detail-meta-value">${wc}</span>`;
    if (ctype) html += `<span class="detail-meta-label">Type</span><span class="detail-meta-value"><span class="content-type-badge">${escHtml(ctype)}</span></span>`;
    html += `</div></div>`;
  }

  if (schema.length) {
    html += `<div class="detail-section">
      <div class="detail-section-title">Schémas détectés</div>
      <div class="schema-pills">${schema.map(s => `<span class="schema-pill">${escHtml(s)}</span>`).join("")}</div>
    </div>`;
  }

  const topics = change.topics || [];
  if (topics.length) {
    html += `<div class="detail-section">
      <div class="detail-section-title">Sujets détectés</div>
      <div class="schema-pills">${topics.map(t => `<span class="topic-pill">${escHtml(t)}</span>`).join("")}</div>
    </div>`;
  }

  return html;
}

function renderRemovedPageDetail(change) {
  return `<div class="detail-section">
    <div class="detail-section-title">Page supprimée</div>
    <div class="detail-removed-box">
      <span class="detail-removed-icon">🗑</span>
      <p>Cette page a disparu du sitemap depuis le <strong>${escHtml(formatDate(change.detected_at || ""))}</strong>.</p>
    </div>
  </div>`;
}

function renderSchemaDiffDetail(change) {
  const before = change.before || {};
  const after  = change.after  || {};
  return `<div class="detail-section">
    <div class="detail-section-title">Changement de schéma Schema.org</div>
    ${schemaDiff(before, after)}
    <div class="sdiff-legend">
      <span class="sdiff-pill sdiff-removed">Supprimé</span>
      <span class="sdiff-pill sdiff-added">Ajouté</span>
      <span class="sdiff-pill sdiff-kept">Inchangé</span>
    </div>
  </div>`;
}

function renderTextDiffDetail(change, type) {
  const before = change.before || {};
  const after  = change.after  || {};
  const fieldMap = {
    meta_changed:  { key: "meta_description", label: "Meta description" },
    title_changed: { key: "title",            label: "Titre (balise title)" },
    h1_changed:    { key: "h1",               label: "H1" },
  };
  const { key, label } = fieldMap[type] || { key: "value", label: "Valeur" };
  const bText = before[key] || Object.values(before)[0] || "";
  const aText = after[key]  || Object.values(after)[0]  || "";

  return `<div class="detail-section">
    <div class="detail-section-title">${escHtml(label)}</div>
    <div class="wdiff-block">${wordDiff(bText, aText)}</div>
    <div class="wdiff-meta">
      <span class="wdiff-legend-del">Supprimé</span>
      <span class="wdiff-legend-add">Ajouté</span>
    </div>
  </div>`;
}

function renderContentUpdateDetail(change) {
  const before = change.before || {};
  const after  = change.after  || {};
  const bwc = before.word_count || 0;
  const awc = after.word_count  || 0;
  const diff = awc - bwc;
  const arrow = diff > 0 ? `<span class="wc-up">+${diff} mots</span>` : `<span class="wc-down">${diff} mots</span>`;

  return `<div class="detail-section">
    <div class="detail-section-title">Mise à jour du contenu</div>
    <div class="detail-meta-grid">
      <span class="detail-meta-label">Avant</span>
      <span class="detail-meta-value">${bwc} mots</span>
      <span class="detail-meta-label">Après</span>
      <span class="detail-meta-value">${awc} mots</span>
      <span class="detail-meta-label">Variation</span>
      <span class="detail-meta-value">${arrow}</span>
    </div>
  </div>`;
}

function closeDetail() {
  el("detail-panel")?.classList.remove("open");
  el("overlay")?.classList.remove("visible");
  el("timeline")?.classList.remove("panel-open");
  state.selectedChange = null;
  document.querySelectorAll(".change-card.selected").forEach(c => c.classList.remove("selected"));
}

// --------------- EVENT LISTENERS ---------------

function initEventListeners() {
  // Domain select
  el("domain-select")?.addEventListener("change", e => {
    state.domain = e.target.value;
    state.competitor = "";
    state.type = "";
    state.inventoryLoaded = false;
    el("filter-competitor").value = "";
    el("filter-type").value = "";
    document.querySelectorAll(".stat-card").forEach(c => c.classList.remove("active"));
    closeDetail();
    loadData();
  });

  // Tab buttons
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // Filter: competitor
  el("filter-competitor")?.addEventListener("change", e => {
    state.competitor = e.target.value;
    fetchChanges();
  });

  // Filter: type
  el("filter-type")?.addEventListener("change", e => {
    state.type = e.target.value;
    document.querySelectorAll(".stat-card").forEach(c => {
      c.classList.toggle("active", c.dataset.type === state.type && state.type !== "");
    });
    fetchChanges();
  });

  // Filter: days
  el("filter-days")?.addEventListener("change", e => {
    state.days = e.target.value;
    state.inventoryLoaded = false;
    loadData();
  });

  // Refresh button
  el("btn-refresh")?.addEventListener("click", () => {
    state.inventoryLoaded = false;
    loadData();
  });

  // Stat card click → filter by type
  document.querySelectorAll(".stat-card").forEach(card => {
    card.addEventListener("click", () => {
      const cardType = card.dataset.type;
      const filterTypeEl = el("filter-type");
      const alreadyActive = state.type === cardType;
      state.type = alreadyActive ? "" : cardType;
      if (filterTypeEl) filterTypeEl.value = state.type;
      document.querySelectorAll(".stat-card").forEach(c => {
        c.classList.toggle("active", c.dataset.type === state.type && state.type !== "");
      });
      if (state.activeTab !== "changes") switchTab("changes");
      fetchChanges();
    });
  });

  // Close detail panel
  el("close-detail")?.addEventListener("click", closeDetail);
  el("overlay")?.addEventListener("click", closeDetail);
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeDetail(); });

  // Inventory search
  el("inventory-search")?.addEventListener("input", filterInventory);
  el("inventory-filter-comp")?.addEventListener("change", filterInventory);
}

// --------------- INIT ---------------

async function init() {
  initEventListeners();
  await fetchDomains();
}

document.addEventListener("DOMContentLoaded", init);
