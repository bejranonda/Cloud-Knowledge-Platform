// Cloud Knowledge Platform — minimal dashboard.
// No framework, no build. Poll-based; can upgrade to SSE later.

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const api = (path, opts) => fetch(`/api${path}`, opts).then(async (r) => {
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  const ct = r.headers.get("content-type") || "";
  return ct.includes("json") ? r.json() : r.text();
});

const state = { project: null, projects: [] };

// ---- tab nav ----
$$("nav button").forEach((b) => b.addEventListener("click", () => {
  $$("nav button").forEach((x) => x.classList.remove("active"));
  $$(".tab").forEach((x) => x.classList.remove("active"));
  b.classList.add("active");
  $(`#${b.dataset.tab}`).classList.add("active");
  refreshActive();
}));

// ---- projects ----
async function loadProjects() {
  state.projects = await api("/projects");
  const tbody = $("#projects-table tbody");
  tbody.innerHTML = state.projects.map((p) => `<tr><td>${p.slug}</td><td>${p.display_name}</td></tr>`).join("");
  const sel = $("#project-select");
  sel.innerHTML = state.projects.map((p) => `<option value="${p.slug}">${p.display_name}</option>`).join("");
  if (state.projects.length && !state.project) state.project = state.projects[0].slug;
  if (state.project) sel.value = state.project;
}

$("#new-project-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  await api("/projects", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ slug: fd.get("slug"), display_name: fd.get("display_name") }),
  });
  e.target.reset();
  await loadProjects();
});

$("#project-select").addEventListener("change", (e) => {
  state.project = e.target.value;
  refreshActive();
});

// ---- sync ----
async function loadSync() {
  const rows = await api("/sync/status");
  $("#sync-table tbody").innerHTML = rows.map((r) => `
    <tr><td>${r.project}</td><td>${r.device}</td><td>${r.last_doc}</td>
    <td>${new Date(r.last_seen * 1000).toLocaleString()}</td></tr>`).join("");
}

// ---- notes ----
async function loadNotes() {
  if (!state.project) return;
  const tree = await api(`/projects/${state.project}/tree`);
  $("#notes-list").innerHTML = tree.map((f) =>
    `<li data-path="${f.path}">${f.path}</li>`).join("");
  $$("#notes-list li").forEach((li) => li.addEventListener("click", async () => {
    $$("#notes-list li").forEach((x) => x.classList.remove("active"));
    li.classList.add("active");
    const p = li.dataset.path;
    $("#note-path").value = p;
    $("#note-editor").value = await api(`/projects/${state.project}/note?path=${encodeURIComponent(p)}`);
  }));
}

$("#save-note").addEventListener("click", async () => {
  const path = $("#note-path").value.trim();
  if (!path) return;
  await api(`/projects/${state.project}/note`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ path, content: $("#note-editor").value }),
  });
  await loadNotes();
});

// ---- graph (canvas force-directed, tiny) ----
async function loadGraph() {
  if (!state.project) return;
  const g = await api(`/projects/${state.project}/graph`);
  drawGraph(g);
}

function drawGraph({ nodes, edges }) {
  const canvas = $("#graph-canvas");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const idx = new Map(nodes.map((n, i) => [n.id, i]));
  const pos = nodes.map(() => [Math.random() * W, Math.random() * H]);
  const vel = nodes.map(() => [0, 0]);
  const N = nodes.length || 1;
  const k = Math.sqrt((W * H) / N);

  for (let iter = 0; iter < 200; iter++) {
    for (let i = 0; i < N; i++) { vel[i][0] = vel[i][1] = 0; }
    for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) {
      let dx = pos[i][0] - pos[j][0], dy = pos[i][1] - pos[j][1];
      const d2 = dx * dx + dy * dy + 0.01;
      const f = (k * k) / d2;
      vel[i][0] += dx * f; vel[i][1] += dy * f;
      vel[j][0] -= dx * f; vel[j][1] -= dy * f;
    }
    for (const e of edges) {
      const a = idx.get(e.source), b = idx.get(e.target);
      if (a === undefined || b === undefined) continue;
      let dx = pos[a][0] - pos[b][0], dy = pos[a][1] - pos[b][1];
      const d = Math.sqrt(dx * dx + dy * dy) + 0.01;
      const f = (d * d) / k;
      vel[a][0] -= (dx / d) * f; vel[a][1] -= (dy / d) * f;
      vel[b][0] += (dx / d) * f; vel[b][1] += (dy / d) * f;
    }
    for (let i = 0; i < N; i++) {
      pos[i][0] = Math.max(20, Math.min(W - 20, pos[i][0] + Math.max(-4, Math.min(4, vel[i][0] * 0.01))));
      pos[i][1] = Math.max(20, Math.min(H - 20, pos[i][1] + Math.max(-4, Math.min(4, vel[i][1] * 0.01))));
    }
  }

  ctx.clearRect(0, 0, W, H);
  ctx.strokeStyle = "#2f3645";
  for (const e of edges) {
    const a = idx.get(e.source), b = idx.get(e.target);
    if (a === undefined || b === undefined) continue;
    ctx.beginPath();
    ctx.moveTo(pos[a][0], pos[a][1]);
    ctx.lineTo(pos[b][0], pos[b][1]);
    ctx.stroke();
  }
  ctx.fillStyle = "#7aa2f7";
  for (let i = 0; i < N; i++) {
    ctx.beginPath();
    ctx.arc(pos[i][0], pos[i][1], 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#e6e8ee";
    ctx.fillText(nodes[i].label, pos[i][0] + 6, pos[i][1] + 3);
    ctx.fillStyle = "#7aa2f7";
  }
}

// ---- history ----
async function loadHistory() {
  if (!state.project) return;
  const rows = await api(`/projects/${state.project}/history`);
  $("#history-table tbody").innerHTML = rows.map((r) => `
    <tr><td>${new Date(r.ts * 1000).toLocaleString()}</td>
    <td>${r.author}</td><td>${r.msg}</td>
    <td><code>${r.hash.slice(0, 8)}</code></td></tr>`).join("");
}

// ---- hermes ----
async function loadHermes() {
  const rows = await api("/hermes/jobs");
  $("#hermes-table tbody").innerHTML = rows.map((r) => `
    <tr><td>${new Date(r.started_ts * 1000).toLocaleString()}</td>
    <td>${r.project}</td><td>${r.source}</td>
    <td class="${r.ok ? 'ok' : 'bad'}">${r.ok ? '✓' : '✗'}</td>
    <td>${r.produced.join(', ')}</td></tr>`).join("");
}

function activeTab() { return $("nav button.active")?.dataset.tab; }
function refreshActive() {
  const t = activeTab();
  ({ projects: loadProjects, sync: loadSync, notes: loadNotes,
     graph: loadGraph, history: loadHistory, hermes: loadHermes }[t])?.();
}

loadProjects().then(refreshActive);
setInterval(() => { if (["sync", "hermes"].includes(activeTab())) refreshActive(); }, 5000);
