#!/usr/bin/env bash
# PreToolUse hook — block accidental destructive pushes to master/main.
#
# Triggered before any Bash tool invocation. Reads the tool input JSON on
# stdin (Claude Code hook contract). Exits 2 to block; exit 0 lets the
# command through.
#
# Block condition: a `git push` that combines --force/-f/--force-with-lease
# with the master or main remote ref. Dev/feature branches pass through.
#
# Known limitation: a bare `git push --force` with no explicit ref (while
# checked out on master/main) is NOT blocked — the ref must appear in the
# command string. Combined with the project's "no commits directly to
# master" pre-commit guard, the risk surface is narrow but non-zero.
#
# Reference: Ultimate Claude Code Guide §9.3 — check-prod-deploy.sh pattern.

set -euo pipefail

# Graceful degrade if jq is missing — without it we cannot parse the
# tool input. Better to fail open (let the command through) than to
# silently block every Bash call with an opaque "command not found".
command -v jq >/dev/null 2>&1 || exit 0

INPUT="$(cat)"
COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')"

# Not a Bash command we recognize; let it through.
[[ -z "$COMMAND" ]] && exit 0

# Match `git push ... <force-flag> ... master|main`. Conservative:
# only fire when force-flag AND master/main appear in the same push.
if printf '%s' "$COMMAND" | grep -Eq 'git[[:space:]]+push' \
   && printf '%s' "$COMMAND" | grep -Eq -- '--force([[:space:]]|=|$)|--force-with-lease|[[:space:]]-f([[:space:]]|$)' \
   && printf '%s' "$COMMAND" | grep -Eq '(master|main)([[:space:]]|$|:)'; then
    cat >&2 <<'EOF'
BLOCKED: force-push to master/main detected.

This repository's release pipeline (release.yml) triggers on master tags;
a force-push would rewrite release history. If you genuinely need to do
this, run the command directly from your terminal (this hook only guards
agent-initiated pushes).
EOF
    exit 2
fi

exit 0
