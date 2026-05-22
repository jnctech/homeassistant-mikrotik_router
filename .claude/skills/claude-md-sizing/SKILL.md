---
description: Audit CLAUDE.md against the Ultimate Claude Code Guide's sizing and pointer-vs-inline rules. Surfaces drift before it makes CLAUDE.md unreadable.
argument-hint: "[path-to-CLAUDE.md]  (defaults to ./CLAUDE.md)"
disable-model-invocation: true
---

# CLAUDE.md Sizing Audit

Mechanical audit of `CLAUDE.md` against Florian Bruniaux's Ultimate Claude Code Guide rules. The guide's "deep_dive_plan_pipeline_claude_md_limit" entry sets a **120-line hard limit** with a pointer strategy for sub-files. CLAUDE.md bloats subtly — each contributor adds "just one more line" until the file no longer functions as a quick-reference.

## Inputs

`$1` — optional path; defaults to `./CLAUDE.md`.
(Claude Code slash commands expose positional arguments as `$1`, `$2`, …; the whole string is `$ARGUMENTS`.)

## Checks

### 1. Line count

```bash
TARGET="${1:-./CLAUDE.md}"
LINES=$(wc -l < "$TARGET")
echo "Line count: $LINES"
```

| Lines | Verdict | Action |
|-------|---------|--------|
| ≤80 | Healthy | None |
| 81–120 | Watch | Consider extracting sub-pages |
| 121–200 | Drift | Extract at least one section to a pointer |
| >200 | Bloat | Per Ultimate Guide §2.2 ("Multiple Checkpoints") — only relevant if intentional; otherwise compress |

### 2. Pointer-vs-inline balance

Count `[...](docs/...)` style links. The guide's pointer strategy: top-level CLAUDE.md should *summarize and link*, not inline. Long content (>10 lines on one topic) should be in `docs/`.

```bash
POINTERS=$(grep -cE '\[[^]]+\]\(docs/[^)]+\)' "$TARGET" || true)
echo "Pointer links to docs/: $POINTERS"
```

Heuristic: a healthy CLAUDE.md has at least 1 pointer per 30 lines of body.

### 3. Section headings

```bash
grep -nE '^##? ' "$TARGET"
```

Each heading should map to either:
- A short (3–8 line) inline section, or
- A pointer + 1-line summary

Long inline sections (15+ lines under one heading) are extraction candidates.

### 4. Checkpoint markers

If line count >500, the guide recommends "Multiple Checkpoints":
```
# === CHECKPOINT 1 === Project: MyApp ===
```
Verify these exist if relevant. If line count <500, checkpoints are noise; flag if present.

### 5. Required-section presence

The guide's recommended baseline for CLAUDE.md includes:
- Project context (what / why / stack)
- Coding standards reference
- Pre-PR / quality-gate reference
- Git/branching conventions

Verify each is either inline or pointed to. List any missing.

## Output

Produce a markdown report:

```
## CLAUDE.md Audit — <path>

| Metric | Value | Verdict |
|--------|-------|---------|
| Lines | N | Healthy/Watch/Drift/Bloat |
| Pointers | N | N per 30 lines (target ≥1) |
| Sections | N | Avg lines/section |
| Checkpoints | N | Expected? |

### Required sections — coverage
- ✓ / ✗ Project context
- ✓ / ✗ Coding standards
- ✓ / ✗ Quality gates / pre-PR
- ✓ / ✗ Git conventions

### Extraction candidates
- `<section-heading>` (N lines) → suggest move to `docs/<file>.md`

### Recommendations
- (only include if any check failed; otherwise say "No action needed")
```

## What this skill does NOT do

- Does not edit CLAUDE.md (read-only audit; the user decides what to extract).
- Does not validate content correctness — only structural sizing/pointer balance.
- Does not run against global `~/.claude/CLAUDE.md` (that's personal, out of scope).
