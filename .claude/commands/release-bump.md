---
description: Atomic version bump across manifest.json, README.md, info.md, and stage a CHANGE-REGISTER entry.
argument-hint: "<new-version>  (e.g. 2.3.17)"
disable-model-invocation: true
---

# Release Bump

Atomic version-triplet update. The history of CR-260417, CR-260507, CR-260509
shows that releases repeatedly required fix-up commits because manifest.json,
README.md, and info.md drifted out of sync. This command does all three in lockstep.

## Inputs

`$1` — the new version (semver `MAJOR.MINOR.PATCH`, no `v` prefix).
(Claude Code slash commands expose positional arguments as `$1`, `$2`, …; the whole string is `$ARGUMENTS`.)

## Steps

### 1. Validate input

```bash
NEW_VER="$1"
[[ "$NEW_VER" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Bad version: $NEW_VER"; exit 1; }
CURRENT_VER=$(jq -r '.version' custom_components/mikrotik_router/manifest.json)
echo "Bumping: $CURRENT_VER  →  $NEW_VER"
```

If versions are equal, abort with "nothing to bump".

### 2. Update `manifest.json`

Update the `version` field. Preserve formatting (jq output style differs from
the existing file; prefer in-place edit via sed or jq + reformat).

```bash
jq --arg v "$NEW_VER" '.version = $v' custom_components/mikrotik_router/manifest.json \
   > custom_components/mikrotik_router/manifest.json.tmp \
   && mv custom_components/mikrotik_router/manifest.json.tmp custom_components/mikrotik_router/manifest.json
```

### 3. Update `README.md`

Add a new section at the top of the changelog/version-notes area. Look for the
"## What's New" or "## Changelog" anchor; insert a new `### vN.M.P` heading
beneath it. The user (or follow-up edit) writes the release notes content.

### 4. Update `info.md`

Same pattern as `README.md` — insert a new top entry with the new version.
`info.md` is the HACS user-facing notes shown in the HACS UI.

### 5. Stage a CHANGE-REGISTER entry

Insert a templated entry at the top of `docs/CHANGE-REGISTER.md` using the
date-based ID format from the project CLAUDE.md:

```markdown
## CR-{YYMMDD}-{branch-slug} — vN.M.P: <title>

**Date:** YYYY-MM-DD
**Branch:** `<current-branch>`
**Status:** In Progress

### What Changed

| Area | Change |
|------|--------|

### Why

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | pending | ⏳ (CI) |
| Ruff format | pending | ⏳ (CI) |
| Tests | pending | ⏳ (CI) |
```

Leave the table cells blank — the implementer fills them in as work proceeds.

### 6. Stage the changes (do not commit)

```bash
git add custom_components/mikrotik_router/manifest.json README.md info.md docs/CHANGE-REGISTER.md
git status --short
```

### 7. Report

Print:
- The three file paths updated
- The CR-YYMMDD-slug stub created
- A reminder to write release notes in README.md/info.md before committing
- The follow-up command: `/pre-pr-check`

## What this command does NOT do

- Does not edit ADR files (those are immutable once accepted).
- Does not run tests (use `/pre-pr-check`).
- Does not commit or push (user chooses commit message and PR target).
- Does not touch `docs/ISSUES.md` (status updates are per-issue, not per-release).
