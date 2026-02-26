# Cursor rules — how this project is set up

## What Cursor reads

| When | What | Purpose |
|------|------|--------|
| **Every session** | `.cursorrules` (repo root) | Points you to the rule file and the plan. |
| **Every session** | `.cursor/rules/project.mdc` | Always-applied rule: constraints, structure, 6-stage pipeline, API contract. Tells you the source of truth. |
| **When implementing or designing** | `BACKEND_PLAN.md` (repo root) | Full architecture, DB design, ingestion phases, retrieval stages, API spec, build order. Read when writing or changing backend code. |

## Single source of truth

- **BACKEND_PLAN.md** (repo root) is the only long-form spec. All backend work must follow it.
- **project.mdc** is a short, always-on constraint list so every session gets the rules without re-reading the whole plan.

## What was removed

- **backend-plan.mdc** — Merged into `project.mdc` (and fixed plan path to repo root).
- **CURSOR_CONTEXT.md** — Redundant with BACKEND_PLAN.md + project.mdc; deleted.
- **.cursorrules** long content — Replaced with a 2-line redirect so we don’t maintain the same rules in two places.
