// Cloud Knowledge Platform — Obsidian-like dashboard.
// Zero-build ES module. No external deps.

// ---------- tiny utilities ----------
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const token = {
  get: () => localStorage.getItem("ckp_token") || "",
  set: (v) => localStorage.setItem("ckp_token", v || ""),
};

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (opts.body && !headers["content-type"]) headers["content-type"] = "application/json";
  const t = token.get();
  if (t) headers["authorization"] = `Bearer ${t}`;
  const r = await fetch(`/api${path}`, { ...opts, headers });
  if (!r.ok) {
    const txt = await r.text();
    if (r.status === 401 || r.status === 403) {
      toast(`Auth required — paste your admin token`, "bad");
      // Prompt for token only once per event burst to avoid dialog spam.
      if (!api._promptOpen) {
        api._promptOpen = true;
        try {
          const v = prompt("Admin bearer token (stored in this browser only):", t);
          if (v && v !== t) {
            token.set(v);
            toast("Token saved — retrying…");
            api._promptOpen = false;
            return api(path, opts); // retry once with new token
          }
        } finally {
          api._promptOpen = false;
        }
      }
    } else {
      toast(`${r.status} ${txt}`, "bad");
    }
    throw new Error(txt);
  }
  const ct = r.headers.get("content-type") || "";
  return ct.includes("json") ? r.json() : r.text();
}

function toast(msg, kind = "ok") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast ${kind}`;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.hidden = true), 2400);
}

// ---------- state ----------
const state = {
  project: null,
  projects: [],
  currentPath: null,
  currentContent: "",
  dirty: false,
  tree: [],
};

// ---------- view routing ----------
function setView(name) {
  $$("nav.views button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  ({
    graph: loadGraph,
    tags: loadTags,
    sync: loadSync,
    history: loadHistory,
    hermes: loadHermes,
    projects: loadProjects,
    editor: loadTree,
    dikw: loadDikw,
  }[name])?.();
}
$$("nav.views button").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));

// ---------- projects ----------
async function loadProjects() {
  state.projects = await api("/projects");
  const sel = $("#project-select");
  sel.innerHTML = state.projects.map((p) => `<option value="${p.slug}">${esc(p.display_name)}</option>`).join("");
  if (!state.project && state.projects.length) state.project = state.projects[0].slug;
  if (state.project) sel.value = state.project;

  $("#projects-table tbody").innerHTML = state.projects
    .map((p) => `<tr><td>${esc(p.slug)}</td><td>${esc(p.display_name)}</td></tr>`).join("");
}
$("#project-select").addEventListener("change", (e) => { state.project = e.target.value; loadTree(); });

$("#new-project-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  await api("/projects", { method: "POST", body: JSON.stringify({
    slug: fd.get("slug"), display_name: fd.get("display_name"),
  })});
  e.target.reset();
  await loadProjects();
  toast("Project created");
});

// ---------- file tree ----------
async function loadTree() {
  if (!state.project) return;
  state.tree = await api(`/projects/${state.project}/tree`);
  renderTree(state.tree);
}

function renderTree(files) {
  // build nested object
  const root = {};
  for (const f of files) {
    const parts = f.path.split("/");
    let cur = root;
    for (let i = 0; i < parts.length - 1; i++) {
      cur = (cur[parts[i]] ||= { __children: {} }).__children;
    }
    cur[parts[parts.length - 1]] = { __file: f };
  }
  $("#tree").innerHTML = renderNode(root, "");

  $$("#tree .file").forEach((el) => el.addEventListener("click", () => openNote(el.dataset.path)));
}

function renderNode(node, prefix) {
  const keys = Object.keys(node).sort((a, b) => {
    const aFile = node[a].__file, bFile = node[b].__file;
    if (!!aFile === !!bFile) return a.localeCompare(b);
    return aFile ? 1 : -1;  // folders first
  });
  return keys.map((k) => {
    const v = node[k];
    const path = prefix ? `${prefix}/${k}` : k;
    if (v.__file) {
      const active = state.currentPath === v.__file.path ? " active" : "";
      const stage = v.__file.stage;
      const pill = stage ? ` <span class="stage stage-${stage}" title="DIKW-T: ${stage}">${stage[0].toUpperCase()}</span>` : "";
      return `<div class="file${active}" data-path="${esc(v.__file.path)}">${esc(k)}${pill}</div>`;
    }
    return `<details open><summary>${esc(k)}</summary>${renderNode(v.__children, path)}</details>`;
  }).join("");
}

$("#refresh-tree").addEventListener("click", loadTree);

// ---------- note open / save / delete ----------
async function openNote(path) {
  if (state.dirty && !confirm("Discard unsaved changes?")) return;
  const body = await api(`/projects/${state.project}/note?path=${encodeURIComponent(path)}`);
  state.currentPath = path;
  state.currentContent = body;
  state.dirty = false;
  $("#note-path").value = path;
  $("#note-editor").value = body;
  renderPreview();
  loadBacklinks();
  loadFileHistory();
  renderNoteTags();
  $$("#tree .file").forEach((el) => el.classList.toggle("active", el.dataset.path === path));
  $("#promote-note").hidden = !path.startsWith("inbox/");
}

$("#note-editor").addEventListener("input", (e) => {
  state.dirty = e.target.value !== state.currentContent;
  renderPreview();
  renderNoteTags();
});

$("#save-note").addEventListener("click", async () => {
  if (!state.project) return toast("Select or create a project first", "bad");
  const path = $("#note-path").value.trim();
  if (!path) return toast("path required", "bad");
  const content = $("#note-editor").value;
  await api(`/projects/${state.project}/note`, {
    method: "PUT", body: JSON.stringify({ path, content }),
  });
  state.currentPath = path;
  state.currentContent = content;
  state.dirty = false;
  toast("Saved");
  await loadTree();
  loadBacklinks();
  loadFileHistory();
});

$("#promote-note").addEventListener("click", async () => {
  if (!state.currentPath || !state.currentPath.startsWith("inbox/")) return;
  const tagsRaw = prompt("Tags for the promoted note (comma-separated, optional):", "");
  if (tagsRaw === null) return;  // user cancelled
  const tags = tagsRaw.split(",").map((t) => t.trim()).filter(Boolean);
  const body = { path: state.currentPath };
  if (tags.length) body.tags = tags;
  const res = await api(`/projects/${state.project}/promote`, {
    method: "POST", body: JSON.stringify(body),
  });
  toast(`Promoted → ${res.to}`);
  await loadTree();
  await openNote(res.to);
});

$("#delete-note").addEventListener("click", async () => {
  if (!state.currentPath) return;
  if (!confirm(`Delete ${state.currentPath}?`)) return;
  await api(`/projects/${state.project}/note?path=${encodeURIComponent(state.currentPath)}`, { method: "DELETE" });
  state.currentPath = null;
  state.currentContent = "";
  state.dirty = false;
  $("#note-editor").value = "";
  $("#note-path").value = "";
  renderPreview();
  await loadTree();
});

$("#new-note-btn").addEventListener("click", () => {
  if (!state.project) return toast("Create a project first", "bad");
  $("#note-path").value = `notes/untitled-${Date.now()}.md`;
  $("#note-editor").value = "# Untitled\n\n";
  state.currentPath = null;
  state.dirty = true;
  renderPreview();
  $("#note-editor").focus();
});

$("#upload-btn").addEventListener("click", () => $("#upload-input").click());
$("#upload-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  const t = token.get();
  const r = await fetch(`/api/projects/${state.project}/attachments`, {
    method: "POST",
    headers: t ? { authorization: `Bearer ${t}` } : {},
    body: fd,
  });
  if (!r.ok) return toast(`upload failed: ${r.status}`, "bad");
  const { path } = await r.json();
  const name = path.replace(/^attachments\//, "");
  const snippet = `![[${name}]]\n`;
  const ed = $("#note-editor");
  const pos = ed.selectionStart;
  ed.value = ed.value.slice(0, pos) + snippet + ed.value.slice(pos);
  ed.dispatchEvent(new Event("input"));
  toast("Uploaded");
  e.target.value = "";
});

$("#preview-toggle").addEventListener("change", (e) => {
  $(".editor-split").classList.toggle("no-preview", !e.target.checked);
});

// ---------- markdown renderer (compact) ----------
function renderMarkdown(src) {
  // escape; then apply block then inline transforms
  let text = esc(src);

  // fenced code
  text = text.replace(/```(\w*)\n([\s\S]*?)```/g,
    (_, lang, code) => `<pre><code class="lang-${esc(lang)}">${code}</code></pre>`);

  // headings
  text = text.replace(/^######\s(.+)$/gm, "<h6>$1</h6>");
  text = text.replace(/^#####\s(.+)$/gm, "<h5>$1</h5>");
  text = text.replace(/^####\s(.+)$/gm, "<h4>$1</h4>");
  text = text.replace(/^###\s(.+)$/gm, "<h3>$1</h3>");
  text = text.replace(/^##\s(.+)$/gm, "<h2>$1</h2>");
  text = text.replace(/^#\s(.+)$/gm, "<h1>$1</h1>");

  // hr
  text = text.replace(/^---+$/gm, "<hr/>");

  // blockquote (single line, sufficient for preview)
  text = text.replace(/^&gt;\s(.+)$/gm, "<blockquote>$1</blockquote>");

  // lists (ordered / unordered) — simple line-wise
  text = text.replace(/(?:^|\n)((?:[-*]\s.+\n?)+)/g, (m) => {
    const items = m.trim().split("\n").map((l) => l.replace(/^[-*]\s/, "")).map((i) => `<li>${i}</li>`).join("");
    return `\n<ul>${items}</ul>`;
  });
  text = text.replace(/(?:^|\n)((?:\d+\.\s.+\n?)+)/g, (m) => {
    const items = m.trim().split("\n").map((l) => l.replace(/^\d+\.\s/, "")).map((i) => `<li>${i}</li>`).join("");
    return `\n<ol>${items}</ol>`;
  });

  // un-escape helper: the whole document was esc()'d up-front, but wikilink /
  // attachment lookups need the raw filename to match state.tree keys.
  const unesc = (s) => s
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'");

  // image embed: ![[file.png]]
  text = text.replace(/!\[\[([^\]]+)\]\]/g, (_, name) => {
    const raw = unesc(name).replace(/^attachments\//, "");
    const src = `/api/projects/${encodeURIComponent(state.project)}/attachments/${encodeURIComponent(raw)}`;
    return `<img src="${esc(src)}" alt="${esc(raw)}" style="max-width:100%"/>`;
  });
  // markdown image: ![alt](path)
  text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, src) => {
    const raw = unesc(src);
    if (!/^https?:/.test(raw)) {
      const rel = raw.replace(/^attachments\//, "");
      src = `/api/projects/${encodeURIComponent(state.project)}/attachments/${encodeURIComponent(rel)}`;
    } else {
      src = raw;
    }
    return `<img src="${esc(src)}" alt="${esc(alt)}" style="max-width:100%"/>`;
  });
  // inline: wikilinks, links, bold/italic, code, tags
  const knownPaths = new Set(state.tree.map((f) => f.path.replace(/\.md$/, "")));
  text = text.replace(/\[\[([^\]|#]+)(?:[|#]([^\]]+))?\]\]/g, (_, tgt, label) => {
    const raw = unesc(tgt.trim());
    const display = esc(label || raw.split("/").pop());
    const match = knownPaths.has(raw) ? raw :
      [...knownPaths].find((p) => p.endsWith(`/${raw}`) || p === raw);
    const cls = match ? "wikilink" : "wikilink dangling";
    const href = match ? `#open:${encodeURIComponent(match + ".md")}` : "#";
    return `<a class="${cls}" href="${esc(href)}">${display}</a>`;
  });
  text = text.replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
  text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  text = text.replace(/(^|\s)#([a-zA-Z][\w\-/]*)/g, '$1<span class="tag">#$2</span>');

  // paragraphs
  text = text.split(/\n{2,}/).map((block) => {
    if (/^<(h\d|ul|ol|pre|blockquote|hr)/.test(block.trim())) return block;
    return `<p>${block.replace(/\n/g, "<br/>")}</p>`;
  }).join("\n");

  return text;
}

function renderPreview() {
  $("#note-preview").innerHTML = renderMarkdown($("#note-editor").value);
  $$("#note-preview a.wikilink").forEach((a) => a.addEventListener("click", (e) => {
    const href = a.getAttribute("href");
    if (href.startsWith("#open:")) {
      e.preventDefault();
      openNote(decodeURIComponent(href.slice("#open:".length)));
    }
  }));
}

function renderNoteTags() {
  const text = $("#note-editor").value;
  const tags = new Set();
  text.replace(/(^|\s)#([a-zA-Z][\w\-/]*)/g, (_, __, t) => tags.add(t));
  // frontmatter tags
  const m = text.match(/^---\n([\s\S]*?)\n---/);
  if (m) {
    const fm = m[1];
    fm.split("\n").forEach((line) => {
      const mm = line.match(/^tags?:\s*(.+)$/);
      if (mm) mm[1].replace(/[\[\]"']/g, "").split(",").forEach((t) => t.trim() && tags.add(t.trim()));
    });
  }
  $("#note-tags").innerHTML = [...tags].map((t) => `<span class="chip">#${esc(t)}</span>`).join("");
}

// ---------- backlinks + file history ----------
async function loadBacklinks() {
  if (!state.currentPath) { $("#backlinks").innerHTML = ""; return; }
  const rows = await api(`/projects/${state.project}/backlinks?path=${encodeURIComponent(state.currentPath)}`);
  $("#backlinks").innerHTML = rows.length
    ? rows.map((r) => `<div class="item" data-path="${esc(r.path)}">
        ${esc(r.path)}<span class="ctx">${esc(r.contexts[0] || "")}</span></div>`).join("")
    : `<div class="item" style="color:var(--muted)">No backlinks.</div>`;
  $$("#backlinks .item[data-path]").forEach((el) => el.addEventListener("click", () => openNote(el.dataset.path)));
}

async function loadFileHistory() {
  if (!state.currentPath) { $("#file-history").innerHTML = ""; return; }
  const rows = await api(`/projects/${state.project}/history/file?path=${encodeURIComponent(state.currentPath)}`);
  $("#file-history").innerHTML = rows.length
    ? rows.map((r) => `<div class="item" data-hash="${r.hash}">
        ${esc(r.msg)}<span class="meta">${new Date(r.ts * 1000).toLocaleString()} · ${r.hash.slice(0,7)}</span></div>`).join("")
    : `<div class="item" style="color:var(--muted)">No history.</div>`;
  $$("#file-history .item[data-hash]").forEach((el) => el.addEventListener("click", () => previewRestore(el.dataset.hash)));
}

// Two-step restore: first click shows the old content in the editor (read-only
// preview); a second confirm writes it back.
async function previewRestore(hash) {
  if (!state.currentPath) return;
  const url = `/projects/${state.project}/history/show?commit=${hash}&path=${encodeURIComponent(state.currentPath)}`;
  const old = await api(url);
  const short = hash.slice(0, 8);
  const ok = confirm(
    `Restore ${state.currentPath} to commit ${short}?\n\n` +
    `Preview (first 300 chars):\n\n` +
    String(old).slice(0, 300) +
    (String(old).length > 300 ? "\n…" : "") +
    `\n\nYour current content will be replaced (but remains in Git history).`
  );
  if (!ok) return;
  await api(`/projects/${state.project}/history/restore?commit=${hash}&path=${encodeURIComponent(state.currentPath)}`, { method: "POST" });
  toast("Restored");
  await openNote(state.currentPath);
}

// ---------- search palette ----------
let searchTimer;
$("#search-input").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  if (!q) { $("#search-results").hidden = true; return; }
  searchTimer = setTimeout(() => runSearch(q), 150);
});
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault(); $("#search-input").focus();
  }
  if (e.key === "Escape") $("#search-results").hidden = true;
});

async function runSearch(q) {
  if (!state.project) return;
  const hits = await api(`/projects/${state.project}/search?q=${encodeURIComponent(q)}`);
  const box = $("#search-results");
  box.hidden = false;
  box.innerHTML = hits.length
    ? hits.map((h) => `<div class="hit" data-path="${esc(h.path)}">
        <div class="path">${esc(h.path)}</div>
        <div class="snippet">${esc(h.snippet || "")}</div></div>`).join("")
    : `<div class="hit" style="color:var(--muted)">No matches.</div>`;
  $$("#search-results .hit[data-path]").forEach((el) => el.addEventListener("click", () => {
    $("#search-results").hidden = true;
    $("#search-input").value = "";
    setView("editor");
    openNote(el.dataset.path);
  }));
}
document.addEventListener("click", (e) => {
  if (!$("#search-results").contains(e.target) && e.target.id !== "search-input") {
    $("#search-results").hidden = true;
  }
});

// ---------- graph ----------
async function loadGraph() {
  const canvas = $("#graph-canvas");
  const ctx = canvas.getContext("2d");
  canvas.width = canvas.clientWidth || 960;
  canvas.height = canvas.clientHeight || 560;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!state.project) {
    ctx.fillStyle = "#8b93a7";
    ctx.font = "14px sans-serif";
    ctx.fillText("Select or create a project to see its graph.", 20, 30);
    return;
  }
  const g = await api(`/projects/${state.project}/graph`);
  if (!g.nodes.length) {
    ctx.fillStyle = "#8b93a7";
    ctx.font = "14px sans-serif";
    ctx.fillText("No notes yet — add a Markdown file and it'll appear here.", 20, 30);
    return;
  }
  drawGraph(g);
}
function drawGraph({ nodes, edges }) {
  const canvas = $("#graph-canvas");
  const { clientWidth: W, clientHeight: H } = canvas;
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext("2d");
  const N = nodes.length || 1;
  const idx = new Map(nodes.map((n, i) => [n.id, i]));
  const pos = nodes.map(() => [Math.random() * W, Math.random() * H]);
  const vel = nodes.map(() => [0, 0]);
  const k = Math.sqrt((W * H) / N) * 0.8;
  for (let step = 0; step < 180; step++) {
    for (let i = 0; i < N; i++) { vel[i][0] = vel[i][1] = 0; }
    for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) {
      let dx = pos[i][0] - pos[j][0], dy = pos[i][1] - pos[j][1];
      const d2 = dx*dx + dy*dy + 0.01, f = (k*k)/d2;
      vel[i][0] += dx*f; vel[i][1] += dy*f;
      vel[j][0] -= dx*f; vel[j][1] -= dy*f;
    }
    for (const e of edges) {
      const a = idx.get(e.source), b = idx.get(e.target);
      if (a === undefined || b === undefined) continue;
      let dx = pos[a][0] - pos[b][0], dy = pos[a][1] - pos[b][1];
      const d = Math.sqrt(dx*dx + dy*dy) + 0.01, f = (d*d)/k;
      vel[a][0] -= (dx/d)*f; vel[a][1] -= (dy/d)*f;
      vel[b][0] += (dx/d)*f; vel[b][1] += (dy/d)*f;
    }
    for (let i = 0; i < N; i++) {
      pos[i][0] = Math.max(20, Math.min(W-20, pos[i][0] + Math.max(-4, Math.min(4, vel[i][0]*0.01))));
      pos[i][1] = Math.max(20, Math.min(H-20, pos[i][1] + Math.max(-4, Math.min(4, vel[i][1]*0.01))));
    }
  }
  ctx.clearRect(0, 0, W, H);
  ctx.strokeStyle = "#2f3645";
  for (const e of edges) {
    const a = idx.get(e.source), b = idx.get(e.target);
    if (a === undefined || b === undefined) continue;
    ctx.beginPath(); ctx.moveTo(pos[a][0], pos[a][1]); ctx.lineTo(pos[b][0], pos[b][1]); ctx.stroke();
  }
  ctx.font = "11px sans-serif";
  for (let i = 0; i < N; i++) {
    ctx.fillStyle = "#7aa2f7";
    ctx.beginPath(); ctx.arc(pos[i][0], pos[i][1], 4, 0, Math.PI*2); ctx.fill();
    ctx.fillStyle = "#e6e8ee"; ctx.fillText(nodes[i].label, pos[i][0]+6, pos[i][1]+3);
  }
}

// ---------- tag browser ----------
async function loadTags() {
  if (!state.project) return;
  const tags = await api(`/projects/${state.project}/tags`);
  const entries = Object.entries(tags);
  $("#tag-browser").innerHTML = entries.length
    ? entries.map(([t, files]) => `
        <div class="tag-card"><h3>#${esc(t)}</h3>
          ${files.map((f) => `<div class="file" data-path="${esc(f)}">${esc(f)}</div>`).join("")}
        </div>`).join("")
    : `<p class="warn">No tags yet.</p>`;
  $$("#tag-browser .file").forEach((el) => el.addEventListener("click", () => {
    setView("editor"); openNote(el.dataset.path);
  }));
}

// ---------- sync monitor ----------
async function loadSync() {
  const rows = await api("/sync/status");
  $("#sync-table tbody").innerHTML = rows.length
    ? rows.map((r) => `<tr><td>${esc(r.project)}</td><td>${esc(r.device)}</td>
        <td>${esc(r.last_doc)}</td>
        <td>${new Date(r.last_seen*1000).toLocaleString()}</td></tr>`).join("")
    : `<tr><td colspan="4" style="color:var(--muted)">No devices seen yet.</td></tr>`;
}

// ---------- project history ----------
async function loadHistory() {
  if (!state.project) {
    $("#history-table tbody").innerHTML =
      `<tr><td colspan="5" style="color:var(--muted)">Select or create a project first.</td></tr>`;
    return;
  }
  const rows = await api(`/projects/${state.project}/history`);
  $("#history-table tbody").innerHTML = rows.length ? rows.map((r) => `
    <tr><td>${new Date(r.ts*1000).toLocaleString()}</td>
    <td>${esc(r.author)}</td><td>${esc(r.msg)}</td>
    <td><code>${r.hash.slice(0,8)}</code></td>
    <td><button class="ghost" data-hash="${r.hash}">Diff</button></td></tr>`).join("")
    : `<tr><td colspan="5" style="color:var(--muted)">No commits yet.</td></tr>`;
  $("#diff-view").hidden = true;
  $$("#history-table button[data-hash]").forEach((b) => b.addEventListener("click", async () => {
    const diff = await api(`/projects/${state.project}/history/diff?commit=${b.dataset.hash}`);
    $("#diff-view").hidden = false;
    $("#diff-view").innerHTML = diff.split("\n").map((l) => {
      if (l.startsWith("@@")) return `<div class="hunk">${esc(l)}</div>`;
      if (l.startsWith("+") && !l.startsWith("+++")) return `<div class="add">${esc(l)}</div>`;
      if (l.startsWith("-") && !l.startsWith("---")) return `<div class="del">${esc(l)}</div>`;
      return `<div>${esc(l)}</div>`;
    }).join("");
  }));
}

// ---------- hermes jobs ----------
async function loadHermes() {
  const rows = await api("/hermes/jobs");
  $("#hermes-table tbody").innerHTML = rows.length
    ? rows.map((r) => `<tr>
        <td>${r.started_ts ? new Date(r.started_ts*1000).toLocaleString() : "—"}</td>
        <td>${esc(r.project)}</td><td>${esc(r.source)}</td>
        <td class="${r.status === 'ok' ? 'ok' : r.status === 'failed' ? 'bad' : 'warn'}">${esc(r.status)}</td>
        <td>${r.attempts}</td>
        <td>${(r.produced || []).join(", ")}</td>
        <td><button class="ghost" data-project="${esc(r.project)}" data-source="${esc(r.source)}">Retry</button></td>
      </tr>`).join("")
    : `<tr><td colspan="7" style="color:var(--muted)">No jobs yet.</td></tr>`;
  $$("#hermes-table button").forEach((b) => b.addEventListener("click", async () => {
    await api(`/projects/${b.dataset.project}/hermes/retrigger?path=${encodeURIComponent(b.dataset.source)}`, { method: "POST" });
    toast("Re-queued");
    loadHermes();
  }));
}

// ---------- admin token ----------
$("#token-btn").addEventListener("click", () => {
  const cur = token.get();
  const v = prompt("Admin bearer token (leave blank to clear):", cur);
  if (v !== null) { token.set(v); toast(v ? "Token saved" : "Token cleared"); }
});

// ---------- SSE live ----------
let _sse = null;
let _sseRetry = null;
function startSSE() {
  if (_sse) { _sse.close(); _sse = null; }
  if (_sseRetry) { clearTimeout(_sseRetry); _sseRetry = null; }
  const es = new EventSource("/api/events");
  _sse = es;
  es.addEventListener("fs", (ev) => {
    const d = JSON.parse(ev.data);
    if (d.project === state.project) {
      loadTree();
      if (d.path === state.currentPath && !state.dirty) {
        openNote(state.currentPath).catch(() => {});
      }
    }
  });
  es.addEventListener("hermes", () => {
    if ($("nav.views button.active").dataset.view === "hermes") loadHermes();
  });
  es.addEventListener("project", loadProjects);
  es.onerror = () => {
    if (es.readyState !== EventSource.CLOSED) es.close();
    if (_sse === es) _sse = null;
    if (!_sseRetry) _sseRetry = setTimeout(startSSE, 3000);
  };
}

// ---------- wisdom synthesis button ----------
$("#wisdom-synth-btn")?.addEventListener("click", async () => {
  if (!state.project) return;
  const btn = $("#wisdom-synth-btn");
  btn.disabled = true;
  $("#wisdom-synth-result").textContent = "Synthesising…";
  try {
    const res = await api(`/projects/${state.project}/wisdom/synthesise`, { method: "POST" });
    const produced = res.produced?.length || 0;
    const skipped = res.skipped?.length || 0;
    $("#wisdom-synth-result").textContent =
      `Produced ${produced} wisdom note(s); skipped ${skipped} (need ≥ 2 commits).`;
    await loadDikw();
    await loadTree();
  } catch (_) {
    $("#wisdom-synth-result").textContent = "Failed — check auth token.";
  } finally {
    btn.disabled = false;
  }
});

// ---------- DIKW-T dashboard ----------
async function loadDikw() {
  if (!state.project) return;
  const cards = $("#dikw-cards");
  const time = $("#dikw-time");
  cards.innerHTML = `<div class="muted">Loading…</div>`;
  time.textContent = "";
  let d;
  try {
    d = await api(`/projects/${state.project}/dikw`);
  } catch {
    return;
  }
  const stages = [
    { key: "data",        label: "Data",        folder: "inbox/",     hint: "Raw capture" },
    { key: "information", label: "Information", folder: "notes/",     hint: "Tagged + linked" },
    { key: "knowledge",   label: "Knowledge",   folder: "knowledge/", hint: "Hermes output" },
    { key: "wisdom",      label: "Wisdom + T",  folder: "wisdom/",    hint: "Why it changed" },
  ];
  const total = d.total || 0;
  cards.innerHTML = stages.map((s) => {
    const n = d.counts?.[s.key] ?? 0;
    const pct = total ? Math.round((n / total) * 100) : 0;
    return `
      <div class="dikw-card stage-${s.key}">
        <div class="dikw-label">${s.label}</div>
        <div class="dikw-count">${n}</div>
        <div class="dikw-meta"><code>${s.folder}</code> · ${pct}%</div>
        <div class="dikw-hint">${s.hint}</div>
      </div>`;
  }).join("");
  const first = d.first_commit_ts ? new Date(d.first_commit_ts * 1000).toISOString().slice(0, 10) : "—";
  const last = d.last_commit_ts ? new Date(d.last_commit_ts * 1000).toISOString().slice(0, 10) : "—";
  time.innerHTML = `<strong>Time axis</strong> — ${d.commits} commits, from ${first} to ${last}.`;
}

// ---------- boot ----------
(async function boot() {
  await loadProjects();
  if (!state.projects.length) {
    setView("projects");
    toast("No projects yet — create your first below.");
  } else {
    await loadTree();
    setView("editor");
  }
  startSSE();
  setInterval(() => {
    const v = $("nav.views button.active").dataset.view;
    if (v === "sync") loadSync();
  }, 5000);
})();
