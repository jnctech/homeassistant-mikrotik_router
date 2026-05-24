#!/usr/bin/env bash
# SessionStart hook — provision the lint/test toolchain in ephemeral
# Claude Code on the web containers so `ruff` and `pytest` work out of the
# box, pinned to the versions CI uses (environment drift protection).
#
# Why this exists: the web container ships system Python 3.11 with a
# Debian-managed setuptools that cannot build Home Assistant's dependency
# tree — pytest-homeassistant-custom-component pulls PyRIC/paho-mqtt/etc.
# whose wheels fail to build there. We provision an isolated Python 3.13
# venv (matching pyproject.toml target-version = py313 and the CI matrix)
# and install deps into it. Without this, every web session starts unable
# to run the gates documented in docs/quality-gates.md.
#
# Synchronous (no async block): guarantees the toolchain is ready before
# the agent runs any command, preventing a race where pytest/ruff are
# invoked before the venv exists. Trade-off: session start blocks on the
# first provision. Subsequent starts are fast (idempotent reuse).
#
# Web-only: guarded on $CLAUDE_CODE_REMOTE so local dev machines (which
# manage their own venv) are left untouched.
#
# References:
# - docs/quality-gates.md  — ruff==0.9.0 pin, 80% coverage gate
# - ADR-010                — Claude tooling baseline
# - ISS-260522             — ruff-version drift between CI and local

set -euo pipefail

# Local (non-web) sessions manage their own environment — do nothing.
[[ "${CLAUDE_CODE_REMOTE:-}" != "true" ]] && exit 0

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR"

VENV="$PROJECT_DIR/.venv"
RUFF_PIN="ruff==0.9.0"  # keep in lock-step with .github/workflows/ci.yml (ISS-260522)

provision() {
    # Prefer uv (fast, correct build isolation); fall back to stdlib venv + pip.
    if command -v uv >/dev/null 2>&1; then
        uv venv --python 3.13 "$VENV"
        uv pip install --python "$VENV" -r requirements_dev.txt "$RUFF_PIN"
    else
        local py
        py="$(command -v python3.13 || command -v python3)"
        "$py" -m venv "$VENV"
        "$VENV/bin/python" -m pip install --quiet --upgrade pip
        "$VENV/bin/python" -m pip install --quiet -r requirements_dev.txt "$RUFF_PIN"
    fi
}

# Idempotent: only provision when the toolchain is missing from the venv.
if [[ ! -x "$VENV/bin/ruff" || ! -x "$VENV/bin/pytest" ]]; then
    provision
fi

# Persist the venv onto PATH for the rest of the session so `ruff`/`pytest`
# (and the post-edit-ruff hook) resolve to the pinned toolchain.
if [[ -n "${CLAUDE_ENV_FILE:-}" ]]; then
    {
        echo "export VIRTUAL_ENV=\"$VENV\""
        echo "export PATH=\"$VENV/bin:\$PATH\""
    } >> "$CLAUDE_ENV_FILE"
fi

echo "SessionStart: toolchain ready ($("$VENV/bin/ruff" --version), $("$VENV/bin/python" --version 2>&1))"
