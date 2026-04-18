# Hermes Agent Contract

Hermes is the DIKW-T **stage-promotion engine**: it consumes Data (`inbox/`)
and Information (`notes/`) and produces Knowledge (`knowledge/`). A future
wisdom-mode pass will read `knowledge/` + Git history and emit Wisdom
(`wisdom/`). See `docs/dikw-t.md`.

The backend invokes Hermes once per new source file. The call is:

```
<CKP_HERMES_BIN> process \
  --input   /abs/path/to/inbox/<source>.md \
  --output-dir /abs/path/to/vault/knowledge \
  --project <slug>
```

## Expectations

| Concern | Requirement |
|---|---|
| Exit code | `0` on success, non-zero on failure (the backend retries up to 3× with exponential backoff). |
| stdout | Optional. Captured by the backend but not parsed. |
| stderr | Human-readable; last 4 KB shown in the dashboard on failure. |
| Output | Zero or more `.md` files written directly to `--output-dir`. The backend diff-picks new files and commits them. |
| Idempotence | Re-processing the same `--input` should either be a no-op or overwrite the same output files. The backend may retry on failure. |
| Timeout | Default 120 s per file. Override via `CKP_HERMES_TIMEOUT` env. |

## Minimal stub (for testing / empty deployments)

If you don't yet have a Hermes build, drop a file named `hermes-agent` on PATH:

```bash
#!/usr/bin/env bash
# Minimal passthrough: copies the input Info to <output>/<name>.md prefixed with "Knowledge: ".
set -euo pipefail
INPUT=""; OUT=""; PROJECT=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --input) INPUT="$2"; shift 2;;
    --output-dir) OUT="$2"; shift 2;;
    --project) PROJECT="$2"; shift 2;;
    process) shift;;
    *) shift;;
  esac
done
name=$(basename "$INPUT" .md)
{ echo "# Knowledge: ${name}"; echo; echo "_auto-generated from inbox on $(date -Iseconds) for ${PROJECT}_"; echo; cat "$INPUT"; } \
  > "$OUT/${name}.md"
```

Make it executable and place it on PATH (e.g. `/usr/local/bin/hermes-agent`).

## Config

- `CKP_HERMES_BIN` — path or command name (default `hermes-agent`).
- `CKP_HERMES_TIMEOUT` — per-file timeout in seconds (default `120`).
