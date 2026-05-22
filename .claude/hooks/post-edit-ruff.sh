#!/usr/bin/env bash
# PostToolUse hook — tight feedback loop on Python edits.
#
# Triggered after any Edit/Write/MultiEdit tool call. If the touched file
# is Python, run `ruff check --fix` then `ruff format` on just that file
# and print the unified summary. Non-blocking (always exits 0) — this is
# a feedback loop, not a gate. The pre-PR check command + CI are the gates.
#
# Why both: `ruff check --fix` handles lint rules but does NOT reformat
# whitespace/quotes/line-length. Running `ruff format` after closes the
# loop so format drift never accumulates between PRs (ISS-260522).
#
# Reference: Ultimate Claude Code Guide §9.5 "Tight Feedback Loops" —
# PostToolUse hooks for lint after Edit.

set -uo pipefail

# Graceful degrade if jq is missing — this is a non-blocking feedback
# hook, so silently skip rather than spam errors.
command -v jq >/dev/null 2>&1 || exit 0

INPUT="$(cat)"
FILE_PATH="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')"

# Not a file-targeted tool, or file is not Python — nothing to do.
[[ -z "$FILE_PATH" ]] && exit 0
[[ "$FILE_PATH" == *.py ]] || exit 0

# Skip files under the vendored librouteros_custom — out of scope.
case "$FILE_PATH" in
    *librouteros_custom*) exit 0 ;;
esac

# Resolve a usable ruff invocation. Prefer the active venv's ruff, fall
# back to `python -m ruff` so the hook works without venv activation.
if command -v ruff >/dev/null 2>&1; then
    RUFF=(ruff)
elif command -v python >/dev/null 2>&1; then
    RUFF=(python -m ruff)
else
    # No ruff available — silently no-op rather than spamming the user.
    exit 0
fi

CHECK_OUTPUT="$("${RUFF[@]}" check --fix "$FILE_PATH" 2>&1 || true)"
FORMAT_OUTPUT="$("${RUFF[@]}" format "$FILE_PATH" 2>&1 || true)"

# Only surface check output when there's something to say.
if [[ -n "$CHECK_OUTPUT" && "$CHECK_OUTPUT" != *"All checks passed!"* ]]; then
    printf 'ruff check (post-edit): %s\n' "$FILE_PATH" >&2
    printf '%s\n' "$CHECK_OUTPUT" >&2
fi

# Only surface format output when a file was actually reformatted.
# `ruff format` prints "1 file reformatted" on change, "1 file left
# unchanged" otherwise — surface only the former.
if [[ "$FORMAT_OUTPUT" == *"reformatted"* ]]; then
    printf 'ruff format (post-edit): %s\n' "$FILE_PATH" >&2
    printf '%s\n' "$FORMAT_OUTPUT" >&2
fi

exit 0
