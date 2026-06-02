/* ============================================================
   Competitor Monitor — Dashboard JavaScript
   Vanilla JS, no framework, uses fetch() API
   ============================================================ */

// --------------- State ---------------

const state = {
  domain: "",
  competitor: "",
  type: "",
  days: "30",
  changes: [],
  stats: {},
  competitors: [],
  selectedChange: null,
};

// --------------- Type Labels ---------------

const TYPE_LABELS = {
  new_page:       "Nouvelle page",
  removed_page:   "Page supprimée",
  schema_changed: "Schéma modifié",
  meta_changed:   "Meta modifiée",
  title_changed:  "Titre modifié",
  h1_changed:     "H1 modifié",
  content_updated:"Contenu MàJ",
};

const SEVERITY_LABELS = {
  high:   "Haute",
  medium: "Moyenne",
  low:    "Faible",
};

// --------------- DOM helpers ---------------

function el(id) {
  return document.getElementById(id);
}

function setHtml(id, html) {
  const node = el(id);
  if (node) node.innerHTML = html;
}

function setText(id, text) {
  const node = el(id);
  if (node) node.textContent = text;
}

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
  } catch (e) {
    return iso;
  }
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

  // Select first domain and trigger load
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
  setText("stat-new",     bt.new_page       || 0);
  setText("stat-removed", bt.removed_page   || 0);
  setText("stat-schema",  bt.schema_changed || 0);
  setText("stat-meta",    bt.meta_changed   || 0);
  setText("stat-title",   bt.title_changed  || 0);
}

async function fetchCompetitors() {
  if (!state.domain) return;
  const params = new URLSearchParams({ domain: state.domain });
  const data = await apiFetch(`/api/competitors?${params}`);
  if (!data) return;

  state.competitors = data;
  const select = el("filter-competitor");
  if (!select) return;

  const currentVal = select.value;
  select.innerHTML = '<option value="">Tous les concurrents</option>';
  data.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c.domain;
    opt.textContent = `${c.domain} (${c.page_count} pages)`;
    select.appendChild(opt);
  });
  if (currentVal) select.value = currentVal;
}

async function fetchChanges() {
  if (!state.domain) return;

  const timeline = el("timeline");
  if (timeline) timeline.innerHTML = '<div class="loading-spinner">Chargement…</div>';

  const params = new URLSearchParams({
    domain: state.domain,
    days: state.days,
  });
  if (state.competitor) params.set("competitor", state.competitor);
  if (state.type) params.set("type", state.type);

  const data = await apiFetch(`/api/changes?${params}`);
  if (!data) {
    if (timeline) timeline.innerHTML = '<div class="empty-state"><div class="empty-icon">⚠️</div><p>Erreur lors du chargement des données.</p></div>';
    return;
  }

  state.changes = data.changes || [];
  renderTimeline(state.changes);
}

// --------------- Render ---------------

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

  // Sort dates descending
  const sortedDates = Object.keys(groups).sort().reverse();

  const html = sortedDates.map(dateStr => {
    const group = groups[dateStr];
    const cardsHtml = group.map((change, idx) => renderChangeCard(change, idx)).join("");
    return `
      <div class="date-group">
        <div class="date-group-header">
          <h3>${escHtml(formatDate(dateStr))}</h3>
          <span class="date-group-count">${group.length}</span>
          <div class="date-group-line"></div>
        </div>
        ${cardsHtml}
      </div>`;
  }).join("");

  timeline.innerHTML = html;

  // Attach click handlers
  timeline.querySelectorAll(".change-card").forEach(card => {
    card.addEventListener("click", () => {
      const dateStr = card.dataset.date;
      const idx = parseInt(card.dataset.idx, 10);
      const group = groups[dateStr];
      if (group && group[idx] !== undefined) {
        showDetail(group[idx]);
        // Mark selected
        timeline.querySelectorAll(".change-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
      }
    });
  });
}

function renderChangeCard(change, idx) {
  const type = change.type || "";
  const label = TYPE_LABELS[type] || type;
  const comp = change.competitor || "";
  const url = change.url || "";
  const severity = change.severity || "";
  const meta = change.metadata || {};

  // Build meta line
  const parts = [];
  const title = meta.title || change.title || "";
  if (title) parts.push(escHtml(title.slice(0, 60) + (title.length > 60 ? "…" : "")));
  const wc = meta.word_count || change.word_count;
  if (wc) parts.push(`${wc}w`);
  const schema = meta.schema_types || change.schema_types || [];
  if (schema.length) parts.push(schema.slice(0, 3).join(", "));

  const metaLine = parts.join(" · ");
  const severityLabel = SEVERITY_LABELS[severity] || severity;
  const date = change.detected_at || "";

  return `
    <div class="change-card" data-type="${escHtml(type)}" data-date="${escHtml(date)}" data-idx="${idx}">
      <span class="change-badge">${escHtml(label)}</span>
      <span class="competitor-tag">${escHtml(comp)}</span>
      <span class="severity-tag ${escHtml(severity)}">${escHtml(severityLabel)}</span>
      <div class="change-url">${escHtml(url)}</div>
      ${metaLine ? `<div class="change-meta">${metaLine}</div>` : ""}
    </div>`;
}

// --------------- Detail Panel ---------------

function showDetail(change) {
  state.selectedChange = change;
  const panel = el("detail-panel");
  const overlay = el("overlay");
  const content = el("detail-content");

  if (!panel || !content) return;

  const type = change.type || "";
  const label = TYPE_LABELS[type] || type;
  const url = change.url || "";
  const comp = change.competitor || "";
  const severity = change.severity || "";
  const meta = change.metadata || {};

  let html = `
    <span class="detail-type-badge" style="background:var(--color-${typeToVar(type)}-bg,#f1f5f9);color:var(--color-${typeToVar(type)},#475569)">
      ${escHtml(label)}
    </span>
    <div class="detail-url">
      <a href="${escHtml(url)}" target="_blank" rel="noopener noreferrer">${escHtml(url)}</a>
    </div>`;

  // Meta info
  html += `<div class="detail-section">
    <div class="detail-section-title">Informations</div>
    <div class="detail-meta-grid">
      <span class="detail-meta-label">Concurrent</span>
      <span class="detail-meta-value">${escHtml(comp)}</span>
      <span class="detail-meta-label">Sévérité</span>
      <span class="detail-meta-value severity-tag ${escHtml(severity)}">${escHtml(SEVERITY_LABELS[severity] || severity)}</span>
      <span class="detail-meta-label">Détecté le</span>
      <span class="detail-meta-value">${escHtml(formatDate(change.detected_at || ""))}</span>
    </div>
  </div>`;

  // Type-specific rendering
  if (type === "new_page") {
    html += renderNewPageDetail(change, meta);
  } else if (type === "removed_page") {
    html += renderRemovedPageDetail(change);
  } else if (["schema_changed", "meta_changed", "title_changed", "h1_changed", "content_updated"].includes(type)) {
    html += renderDiffDetail(change);
  }

  content.innerHTML = html;
  panel.classList.add("open");
  if (overlay) overlay.classList.add("visible");

  const timeline = el("timeline");
  if (timeline) timeline.classList.add("panel-open");
}

function typeToVar(type) {
  const map = {
    new_page:        "new-page",
    removed_page:    "removed-page",
    schema_changed:  "schema-changed",
    meta_changed:    "meta-changed",
    title_changed:   "title-changed",
    h1_changed:      "h1-changed",
    content_updated: "content-updated",
  };
  return map[type] || "content-updated";
}

function renderNewPageDetail(change, meta) {
  let html = "";

  const title = meta.title || "";
  const h1 = meta.h1 || "";
  const desc = meta.meta_description || "";
  const wc = meta.word_count;
  const schema = meta.schema_types || [];
  const ctype = meta.content_type || change.content_type || "";

  if (title || h1 || desc || wc || ctype) {
    html += `<div class="detail-section">
      <div class="detail-section-title">Métadonnées de la page</div>
      <div class="detail-meta-grid">`;
    if (title) html += `<span class="detail-meta-label">Titre</span><span class="detail-meta-value">${escHtml(title)}</span>`;
    if (h1) html += `<span class="detail-meta-label">H1</span><span class="detail-meta-value">${escHtml(h1)}</span>`;
    if (desc) html += `<span class="detail-meta-label">Meta desc.</span><span class="detail-meta-value">${escHtml(desc)}</span>`;
    if (wc) html += `<span class="detail-meta-label">Mots</span><span class="detail-meta-value">${wc}</span>`;
    if (ctype) html += `<span class="detail-meta-label">Type</span><span class="detail-meta-value"><span class="content-type-badge">${escHtml(ctype)}</span></span>`;
    html += `</div></div>`;
  }

  if (schema.length > 0) {
    html += `<div class="detail-section">
      <div class="detail-section-title">Schémas détectés</div>
      <div class="schema-pills">
        ${schema.map(s => `<span class="schema-pill">${escHtml(s)}</span>`).join("")}
      </div>
    </div>`;
  }

  return html;
}

function renderRemovedPageDetail(change) {
  return `
    <div class="detail-section">
      <div class="detail-section-title">Page supprimée</div>
      <p style="font-size:0.85rem;color:var(--color-text-secondary)">
        Cette page a disparu du sitemap du concurrent depuis le ${escHtml(formatDate(change.detected_at || ""))}.
      </p>
    </div>`;
}

function renderDiffDetail(change) {
  const before = change.before || {};
  const after = change.after || {};
  const type = change.type || "";

  let title = "";
  if (type === "schema_changed")  title = "Changement de schéma";
  else if (type === "meta_changed")   title = "Changement de meta description";
  else if (type === "title_changed")  title = "Changement de titre";
  else if (type === "h1_changed")     title = "Changement de H1";
  else if (type === "content_updated") title = "Mise à jour du contenu";

  return `
    <div class="detail-section">
      <div class="detail-section-title">${escHtml(title)}</div>
      <div class="diff-block">
        <div class="diff-before">
          <span class="diff-label">Avant</span>
          <code>${escHtml(JSON.stringify(before, null, 2))}</code>
        </div>
        <div class="diff-after">
          <span class="diff-label">Après</span>
          <code>${escHtml(JSON.stringify(after, null, 2))}</code>
        </div>
      </div>
    </div>`;
}

function closeDetail() {
  const panel = el("detail-panel");
  const overlay = el("overlay");
  const timeline = el("timeline");

  if (panel) panel.classList.remove("open");
  if (overlay) overlay.classList.remove("visible");
  if (timeline) timeline.classList.remove("panel-open");
  state.selectedChange = null;

  // Deselect cards
  document.querySelectorAll(".change-card.selected").forEach(c => c.classList.remove("selected"));
}

// --------------- Orchestration ---------------

async function loadData() {
  if (!state.domain) return;
  await Promise.all([fetchStats(), fetchChanges(), fetchCompetitors()]);
}

// --------------- Event Listeners ---------------

function initEventListeners() {
  const domainSelect = el("domain-select");
  if (domainSelect) {
    domainSelect.addEventListener("change", e => {
      state.domain = e.target.value;
      state.competitor = "";
      state.type = "";
      const compFilter = el("filter-competitor");
      if (compFilter) compFilter.value = "";
      const typeFilter = el("filter-type");
      if (typeFilter) typeFilter.value = "";
      closeDetail();
      loadData();
    });
  }

  const filterComp = el("filter-competitor");
  if (filterComp) {
    filterComp.addEventListener("change", e => {
      state.competitor = e.target.value;
      fetchChanges();
    });
  }

  const filterType = el("filter-type");
  if (filterType) {
    filterType.addEventListener("change", e => {
      state.type = e.target.value;
      // Sync stat cards active state
      document.querySelectorAll(".stat-card").forEach(card => {
        card.classList.toggle("active", card.dataset.type === state.type);
      });
      fetchChanges();
    });
  }

  const filterDays = el("filter-days");
  if (filterDays) {
    filterDays.addEventListener("change", e => {
      state.days = e.target.value;
      loadData();
    });
  }

  const btnRefresh = el("btn-refresh");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => loadData());
  }

  const closeBtn = el("close-detail");
  if (closeBtn) {
    closeBtn.addEventListener("click", closeDetail);
  }

  const overlay = el("overlay");
  if (overlay) {
    overlay.addEventListener("click", closeDetail);
  }

  // Stat card clicks → filter by type
  document.querySelectorAll(".stat-card").forEach(card => {
    card.addEventListener("click", () => {
      const cardType = card.dataset.type;
      const filterTypeEl = el("filter-type");
      if (!filterTypeEl) return;

      const alreadyActive = state.type === cardType;
      state.type = alreadyActive ? "" : cardType;
      filterTypeEl.value = state.type;

      document.querySelectorAll(".stat-card").forEach(c => {
        c.classList.toggle("active", c.dataset.type === state.type && state.type !== "");
      });

      fetchChanges();
    });
  });

  // Keyboard: Escape to close panel
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeDetail();
  });
}

// --------------- Init ---------------

async function init() {
  initEventListeners();
  await fetchDomains();
}

document.addEventListener("DOMContentLoaded", init);
