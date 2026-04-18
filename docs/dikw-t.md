# DIKW-T Framework

The Cloud Knowledge Platform is organised around the **DIKW-T** pyramid:

> **Data → Information → Knowledge → Wisdom + Time**

Each stage corresponds to a directory in every project vault and to a distinct
lifecycle phase in the pipeline. The time-series dimension is provided by the
per-project Git repo: every stage is versioned, so the system can reason not
only about what is *currently* known but about how that knowledge *evolved*.

## 1. Data — `inbox/`

Raw, unprocessed capture. No structure required.

- Quick mobile notes, clipboard dumps, web clippings, transcripts, pasted logs.
- No frontmatter, no tags, no wikilinks expected.
- Written by: humans (Obsidian sync), external ingestion scripts.
- Classifier rule: file lives under `inbox/` **or** has neither frontmatter
  nor wikilinks nor tags.

## 2. Information — `notes/`

Data that has been categorised: it has a place, tags, and links.

- Markdown files under `notes/…` with YAML frontmatter
  (`status`, `tags`, `project`, …) and/or `[[wikilinks]]` to siblings.
- Written by: humans during desk work, or agents promoting Data.
- Classifier rule: has frontmatter **or** at least one wikilink/hashtag,
  and is not under `inbox/`, `knowledge/`, or `wisdom/`.

## 3. Knowledge — `knowledge/`

Synthesised understanding produced by the **Hermes Agent** from Information.

- Evergreen notes, skill documents, "how X works" summaries.
- Written by: Hermes (subprocess) — never edited in place by humans; if a
  human revises the output, Hermes treats the revision as new Information on
  the next run.
- Classifier rule: file lives under `knowledge/`.

## 4. Wisdom — `wisdom/`  +  Git history

Wisdom is Knowledge *plus* time. It answers **Why did this change?** by
comparing the current `knowledge/` state against its Git history.

- Agent-authored documents that cite commits: "We used to do X (v1, commit
  `a1b2c3`), switched to Y in March after the incident in
  `inbox/2026-03-07-outage.md` (v2, commit `d4e5f6`), current form is Z."
- Written by: Hermes in "wisdom mode" (reads `git log` + knowledge diffs).
- Classifier rule: file lives under `wisdom/`.

The time-series dimension is not a folder — it is a property of *every*
stage. Any stage at any historical commit is retrievable via
`/api/projects/{slug}/history/file`.

## Pipeline

```
 mobile / web clip                 desk work                   Hermes                Hermes (wisdom mode)
 ──────────────── ──► inbox/ ──► ────────── ──► notes/ ──► ─────────── ──► knowledge/ ──► ────────────────── ──► wisdom/
      [Data]                    [Information]                [Knowledge]                  [Wisdom + Time]

 every write ─────────────────────────────────► Git commit (time-series backbone)
```

## API

`GET /api/projects/{slug}/dikw` returns a stage breakdown for the vault:

```json
{
  "project": "proj-a",
  "counts": { "data": 12, "information": 48, "knowledge": 9, "wisdom": 2 },
  "total": 71,
  "commits": 312,
  "first_commit_ts": 1714608000,
  "last_commit_ts": 1744934400
}
```

Use it to drive dashboard widgets, pipeline health checks, or to decide
whether a project has enough Information to be worth running Hermes over.

## Why formalise it

- **Agents orient faster.** Any AI editing this repo can be told "add an
  endpoint for the Knowledge stage" and know exactly which directory and
  which write path is meant.
- **Folder layout survives refactors.** The model is stable even as the
  Hermes implementation changes.
- **Wisdom is a product, not a side effect.** Treating `wisdom/` as a
  first-class stage makes time-series reasoning something the system
  produces on purpose rather than something users have to reconstruct from
  `git log` by hand.
