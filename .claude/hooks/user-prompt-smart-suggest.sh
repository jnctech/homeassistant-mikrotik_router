#!/usr/bin/env bash
# UserPromptSubmit hook — soft enforcement of the pre-PR checklist.
#
# Inspects the user prompt. When the user signals PR-creation intent,
# print a one-line reminder of the project's pre-PR sequence unless the
# prompt already references it. Non-blocking; the user still chooses
# what to do.
#
# Reference: Ultimate Claude Code Guide §9.3 — smart-suggest.sh Layer 2.
# Reference: CLAUDE.md "Pre-PR Checklist (overrides global)" section.

set -uo pipefail

# Graceful degrade if jq is missing — non-blocking suggestion hook;
# silent skip is better than blocking every prompt with an error.
command -v jq >/dev/null 2>&1 || exit 0

INPUT="$(cat)"
PROMPT="$(printf '%s' "$INPUT" | jq -r '.prompt // empty' | tr '[:upper:]' '[:lower:]')"

[[ -z "$PROMPT" ]] && exit 0

# Detect PR-creation intent. Word boundary on `pr` prevents matching
# substrings like "project", "presentation", "prequel", "print".
if printf '%s' "$PROMPT" | grep -Eq '(create|make|open|raise|draft).*(\bpr\b|pull[[:space:]]?request)|gh[[:space:]]+pr[[:space:]]+create'; then
    # Suppress reminder if the prompt already references the checks.
    if ! printf '%s' "$PROMPT" | grep -Eq '(pre-pr|change-register|adr|simplify|coverage|sonar)'; then
        cat >&2 <<'EOF'
[pre-PR reminder] Before opening this PR, ensure:
  1. /pre-pr-check has run (ruff + pytest + coverage ≥80%)
  2. docs/CHANGE-REGISTER.md has a CR-YYMMDD entry for the branch
  3. docs/ISSUES.md is updated if this PR resolves an issue
  4. manifest.json / README.md / info.md versions match (if release)
  5. PR target is the jnctech fork (NOT upstream tomaae) unless explicit
EOF
    fi
fi

exit 0
