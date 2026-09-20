#!/usr/bin/env bash
# One-shot developer setup for localcaption.
#
# - creates the model environments under ./runtime (see setup_runtime.sh)
# - installs the dev extras (pytest, ruff) into ./runtime/main
# - downloads all four model checkpoints through the proxy
#
# Re-runnable: skips steps that are already done.
#
# Usage:
#   ./scripts/setup.sh
#   EXTRAS=dev ./scripts/setup.sh
#
# Env vars:
#   EXTRAS            default: dev  (dev | "" )
#   SKIP_MODELS       default: 0    (set 1 to skip the ~7 GB download)
#   LOCALCAPTION_PROXY, LOCALCAPTION_RUNTIME_DIR, LOCALCAPTION_MODELS_DIR

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTRAS="${EXTRAS:-dev}"
SKIP_MODELS="${SKIP_MODELS:-0}"
RUNTIME_DIR="${LOCALCAPTION_RUNTIME_DIR:-${REPO_ROOT}/runtime}"
PY="$RUNTIME_DIR/main/bin/python"

log()  { printf "\033[1;34m[setup]\033[0m %s\n" "$*"; }
die()  { printf "\033[1;31m[err  ]\033[0m %s\n" "$*" >&2; exit 1; }

command -v uv >/dev/null 2>&1 || die "uv is required. Install it:
    curl -LsSf https://astral.sh/uv/install.sh | sh"

# --- 1. Model runtimes ----------------------------------------------------
log "creating model runtimes (this can take several minutes)"
bash "$REPO_ROOT/scripts/setup_runtime.sh"

# --- 2. Dev extras --------------------------------------------------------
if [[ -n "${EXTRAS}" ]]; then
  log "installing localcaption[${EXTRAS}] into runtime/main"
  uv pip install --python "$PY" -e "${REPO_ROOT}[${EXTRAS}]"
fi

# --- 3. Models ------------------------------------------------------------
if [[ "${SKIP_MODELS}" == "1" ]]; then
  log "SKIP_MODELS=1: not downloading model checkpoints"
else
  log "downloading model checkpoints (~7 GB, via the proxy)"
  "$PY" -m localcaption model download --all
fi

log "setup complete."
log "Activate:  source ${RUNTIME_DIR}/main/bin/activate"
log "Run:       localcaption <youtube-url>"
