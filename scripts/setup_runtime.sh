#!/usr/bin/env bash
# Create the isolated per-model Python environments used by localcaption.
#
# Why more than one environment? The model stacks pin incompatible
# `transformers` versions:
#   * qwen-asr            -> transformers 4.x
#   * nvidia NeMo models  -> transformers >= 5.13
# so each family gets its own venv. Runners are executed through these
# interpreters; the main package never imports torch.
#
# Re-runnable: skips an environment whose imports already succeed.
#
# Env vars:
#   LOCALCAPTION_RUNTIME_DIR   where to put the venvs (default: ./runtime)
#   LOCALCAPTION_PROXY         proxy URL (default: socks5h://127.0.0.1:9050)
#   PYTHON_VERSION             Python for the venvs (default: 3.12)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${LOCALCAPTION_RUNTIME_DIR:-${REPO_ROOT}/runtime}"
export ALL_PROXY="${LOCALCAPTION_PROXY:-socks5h://127.0.0.1:9050}"
export HTTPS_PROXY="$ALL_PROXY"
export HTTP_PROXY="$ALL_PROXY"
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"

log()  { printf "\033[1;34m[runtime]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn   ]\033[0m %s\n" "$*"; }
die()  { printf "\033[1;31m[error  ]\033[0m %s\n" "$*" >&2; exit 1; }

command -v uv >/dev/null 2>&1 || die "uv is required. Install it:
    curl -LsSf https://astral.sh/uv/install.sh | sh"

mkdir -p "$RUNTIME_DIR"

# have <venv> <import-name> -> 0 if the venv exists and can import the module
have() {
  local py="$RUNTIME_DIR/$1/bin/python"
  [ -x "$py" ] && "$py" -c "import $2" >/dev/null 2>&1
}

venv() { uv venv "$RUNTIME_DIR/$1" --python "$PYTHON_VERSION" --seed >/dev/null; }
pip()  { uv pip install --python "$RUNTIME_DIR/$1/bin/python" "${@:2}"; }

# --- main (CLI + yt-dlp) --------------------------------------------------
if have main yt_dlp; then
  log "main: ok"
else
  log "main: creating environment"
  venv main
  pip main -e "$REPO_ROOT"
  pip main "yt-dlp>=2025.10.14"
fi

# --- nvidia (parakeet + nemotron) ----------------------------------------
if have nvidia transformers; then
  log "nvidia: ok"
else
  log "nvidia: installing torch + transformers + librosa"
  [ -x "$RUNTIME_DIR/nvidia/bin/python" ] || venv nvidia
  pip nvidia "torch==2.14.0" --index-url https://download.pytorch.org/whl/cpu
  # librosa: Parakeet's feature extractor (transformers) needs it at import.
  pip nvidia "transformers>=5.13.0" "numpy" "librosa>=0.10"
fi

# --- qwen (Qwen3-ASR) -----------------------------------------------------
if have qwen qwen_asr; then
  log "qwen: ok"
else
  log "qwen: installing torch + qwen-asr"
  [ -x "$RUNTIME_DIR/qwen/bin/python" ] || venv qwen
  pip qwen "torch==2.14.0" --index-url https://download.pytorch.org/whl/cpu
  pip qwen "qwen-asr>=0.0.6"
fi

# --- langid (speechbrain ECAPA-TDNN) -------------------------------------
# speechbrain imports torchaudio at import time, and torchaudio only ships
# CPU wheels up to 2.11, so this env pairs an older torch with matching
# torchaudio. (The runner itself never uses torchaudio; it reads WAV via the
# stdlib, but the import must succeed.)
if have langid speechbrain; then
  log "langid: ok"
else
  log "langid: installing torch + torchaudio + speechbrain"
  [ -x "$RUNTIME_DIR/langid/bin/python" ] || venv langid
  pip langid "torch==2.11.0" "torchaudio==2.11.0" \
    --index-url https://download.pytorch.org/whl/cpu
  pip langid "speechbrain>=1.0"
fi

log "all environments ready in $RUNTIME_DIR"
