# Approach & Method

Why this codebase looks the way it does, and the rules we follow when changing it. Shorter than `architecture.md` (which describes the *what*); this is the *how we decide*.

## Guiding principles

1. **One vault = one source of truth.** The on-disk Markdown tree is canonical. CouchDB, the search index, the graph, and the Git repo all derive from it. When two derived views disagree, trust the files.
2. **Every change is a commit.** Users never see the Git repo directly, but every write path — LiveSync, WebDAV, API, Web-App, restore, Hermes — funnels through `versioning.schedule_commit`. Debounced 2 s; never silent.
3. **Per-project isolation is physical, not logical.** A CouchDB DB, a vault dir, a Git repo, a Hermes workdir. No shared tables, no "tenant_id" columns. Cheaper to reason about than to enforce.
4. **Zero-build frontend.** Plain HTML + ES modules + vanilla CSS. Adding a bundler is a last resort, not a default.
5. **Operate with one script.** `scripts/server.sh` is the only lifecycle surface. Subcommands, not new files.
6. **Auth is opt-in for dev, mandatory for prod.** No `CKP_ADMIN_TOKEN` → full open access. Set it and the platform enforces it everywhere (API, WebDAV, per-project tokens).

## Method: how we add a feature

1. **Read the user's request twice.** Is this a new verb, or a new shape on an existing verb? (New endpoints are cheap; new domain modules are not.)
2. **Decide where the side effect lives.** There are only a handful of canonical side-effect sinks: the vault filesystem, the search index, the Git queue, the SSE bus, the Hermes queue, the CouchDB feed. A new feature either triggers these or it doesn't — it almost never needs a new sink.
3. **Write the domain module first** (`backend/app/<thing>.py`). Keep it pure-ish: no FastAPI imports, no route decorators, just functions and types.
4. **Wire a route thinly** in `backend/app/routes/<thing>_routes.py`. Auth dependency at the top; one-liner per handler; return JSON. Anything beyond a handful of lines belongs in the domain module.
5. **Reflect it in the watcher + SSE** if it changes on-disk state, so the dashboard updates live without a reload.
6. **Add a smoke test** in `backend/tests/test_smoke.py` that exercises the full wire through `TestClient`.
7. **Update exactly the docs that describe the thing you changed.** Architecture shifts → `architecture.md`. Operator-visible behaviour → `knowledge.md` and `known-issues.md` as needed. New command surface → the relevant `quickstart-*.md`.

## Method: how we delegate to subagents

Heavy, self-contained coding jobs go to Sonnet. We delegate when:
- The work is **one file** or **one narrow scope** (WebDAV handler, test suite, deploy script).
- The work is **mostly pattern-following** given a strict contract (stable integration hooks, fixed output format).
- It would cost ≥100 lines of main-context code to write inline.

We do *not* delegate:
- Architectural decisions or cross-cutting refactors.
- Anything requiring judgment about the user's intent.
- Tiny edits (< 30 LoC) — the briefing overhead outweighs the savings.

The orchestrator always **reads the result critically**, wires it up, and keeps responsibility for integration correctness. Subagent summaries describe what they meant to do, not what they verifiably did.

## Method: how we refactor

1. **Don't, usually.** The cost of a refactor is paid now; the benefit accrues only if the code keeps changing. Most code doesn't change.
2. **Split when there's a second consumer**, not a second reason. Three similar lines is better than a premature abstraction.
3. **Move code into a new file only after the feature it enables is on disk.** No "scaffolding" commits.
4. **Delete ruthlessly.** Unused = gone. Don't keep fallbacks, feature flags, or compatibility shims for users who don't exist.

## Recent lessons

**Always filter filesystem events explicitly.** The v0.3.1 watcher feedback-loop bug
showed that reacting to every watchdog event type is dangerous: non-mutating events
(`opened`, `closed`) caused `search.update_file()` to read the file, which itself
generated more `opened` events, keeping `last_event_ts` perpetually bumped and
silencing Git commits. The lesson: define an explicit allowlist of mutating event
types (`_MUTATING`) and discard everything else. Never assume "extra" events are
harmless noise.

**Fully relative HTML paths demand a root mount.** When `index.html` loads assets
with bare relative paths (`src="app.js"`, `href="styles.css"`), the static file
server must be mounted at `/`. Mounting at `/ui/` means requests for `/app.js` hit
the API router, not the file server. The lesson: check the mount path against the
HTML asset references before shipping; mismatched paths produce silent 404s that
are hard to diagnose in production.

## What this project deliberately does NOT have

- An ORM. The registry is one JSON file; vault data is the filesystem; Git is Git.
- A task queue service (Celery / RQ). In-process threads are enough; see `hermes.py` queue + `versioning.py` debouncer.
- A build step for the frontend. One HTML, one JS module, one CSS.
- A plugin system for the backend. Changes happen in code and through code review.
- Custom auth server / SSO / SCIM. Bearer tokens, rotated manually. Cross that bridge when a customer asks.
