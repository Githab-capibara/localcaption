#!/usr/bin/env bash
#
# localcaption uninstaller
#
# Reverses what scripts/install.sh did. Safe to run multiple times.
#
# Usage:
#   bash scripts/uninstall.sh                 # interactive
#   bash scripts/uninstall.sh --yes           # no prompts (for scripts/CI)
#   bash scripts/uninstall.sh --keep-models   # remove the binary, keep ggml models + whisper.cpp build
#   bash scripts/uninstall.sh --dry-run       # show what WOULD be removed
#
# Exits with status 0 if the system ends up clean, 1 if anything failed.
# Designed to be idempotent — running it on an already-clean system is a no-op.

set -uo pipefail

# ──────────────────────────────────────────────────────────────────────
# Args
# ──────────────────────────────────────────────────────────────────────

ASSUME_YES=0
KEEP_MODELS=0
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    -y|--yes)            ASSUME_YES=1 ;;
    --keep-models)       KEEP_MODELS=1 ;;
    --dry-run)           DRY_RUN=1 ;;
    -h|--help)
      sed -n '3,15p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Run with --help for usage." >&2
      exit 2
      ;;
  esac
done

# ──────────────────────────────────────────────────────────────────────
# Pretty output helpers
# ──────────────────────────────────────────────────────────────────────

if [ -t 1 ]; then
  C_RED=$'\033[0;31m'; C_GRN=$'\033[0;32m'; C_YEL=$'\033[0;33m'
  C_CYN=$'\033[0;36m'; C_DIM=$'\033[2m';    C_RST=$'\033[0m'
else
  C_RED=""; C_GRN=""; C_YEL=""; C_CYN=""; C_DIM=""; C_RST=""
fi

step() { printf "%s▸%s %s\n" "$C_CYN" "$C_RST" "$1"; }
ok()   { printf "  %s✓%s %s\n" "$C_GRN" "$C_RST" "$1"; }
skip() { printf "  %s•%s %s\n" "$C_DIM" "$C_RST" "$C_DIM$1$C_RST"; }
warn() { printf "  %s!%s %s\n" "$C_YEL" "$C_RST" "$1"; }
fail() { printf "  %s✗%s %s\n" "$C_RED" "$C_RST" "$1"; }

confirm() {
  # Returns 0 if the user agrees, 1 otherwise.
  local prompt="$1"
  if [ "$ASSUME_YES" -eq 1 ]; then
    return 0
  fi
  printf "  %s?%s %s [y/N] " "$C_YEL" "$C_RST" "$prompt"
  read -r reply </dev/tty || return 1
  case "$reply" in
    y|Y|yes|YES) return 0 ;;
    *)           return 1 ;;
  esac
}

# Remove a path (file or dir) with optional dry-run + confirmation.
# $1 = path, $2 = human-readable label
remove_path() {
  local path="$1"
  local label="$2"

  if [ ! -e "$path" ] && [ ! -L "$path" ]; then
    skip "$label not present ($path)"
    return 0
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    local size
    size=$(du -sh "$path" 2>/dev/null | cut -f1)
    warn "[dry-run] would remove $label ($size at $path)"
    return 0
  fi

  if ! confirm "Remove $label at $path?"; then
    skip "kept $label"
    return 0
  fi

  if rm -rf -- "$path"; then
    ok "removed $label"
  else
    fail "failed to remove $label"
    return 1
  fi
}

# ──────────────────────────────────────────────────────────────────────
# Plan summary up-front (so users know what's coming)
# ──────────────────────────────────────────────────────────────────────

XDG_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/localcaption"
XDG_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/localcaption"

echo
echo "${C_CYN}localcaption uninstaller${C_RST}"
echo "${C_DIM}────────────────────────${C_RST}"
echo
echo "This will remove:"
echo "  • the 'localcaption' command (via pipx uninstall)"
if [ "$KEEP_MODELS" -eq 1 ]; then
  echo "  • ${C_DIM}(keeping)${C_RST} whisper.cpp build + ggml models in $XDG_DATA"
else
  echo "  • whisper.cpp build + ggml models in $XDG_DATA"
fi
echo "  • cache dir at $XDG_CACHE (if present)"
echo
echo "${C_DIM}Will NOT touch: pipx itself, ffmpeg/cmake/git, or any source repo you cloned.${C_RST}"
echo

if [ "$DRY_RUN" -eq 1 ]; then
  warn "DRY-RUN: nothing will actually be removed."
  echo
fi

errors=0

# ──────────────────────────────────────────────────────────────────────
# Step 1 — pipx uninstall
# ──────────────────────────────────────────────────────────────────────

step "Removing 'localcaption' command (pipx)"

if ! command -v pipx >/dev/null 2>&1; then
  skip "pipx not installed; nothing to uninstall"
elif ! pipx list --short 2>/dev/null | grep -q "^localcaption "; then
  skip "localcaption is not installed via pipx"
else
  if [ "$DRY_RUN" -eq 1 ]; then
    warn "[dry-run] would run: pipx uninstall localcaption"
  elif confirm "Uninstall localcaption from pipx?"; then
    if pipx uninstall localcaption >/dev/null 2>&1; then
      ok "pipx uninstalled localcaption"
    else
      fail "pipx uninstall failed"
      errors=$((errors + 1))
    fi
  else
    skip "kept pipx install"
  fi
fi

# ──────────────────────────────────────────────────────────────────────
# Step 2 — whisper.cpp + models
# ──────────────────────────────────────────────────────────────────────

step "Removing whisper.cpp + models"

if [ "$KEEP_MODELS" -eq 1 ]; then
  warn "skipping (--keep-models): $XDG_DATA preserved"
else
  remove_path "$XDG_DATA" "localcaption data dir" || errors=$((errors + 1))
fi

# ──────────────────────────────────────────────────────────────────────
# Step 3 — cache
# ──────────────────────────────────────────────────────────────────────

step "Removing cache"
remove_path "$XDG_CACHE" "localcaption cache dir" || errors=$((errors + 1))

# ──────────────────────────────────────────────────────────────────────
# Step 4 — verify clean state
# ──────────────────────────────────────────────────────────────────────

step "Verifying clean state"

clean=1
if command -v localcaption >/dev/null 2>&1; then
  warn "'localcaption' is still on PATH at $(command -v localcaption)"
  warn "  (this may be a different install — e.g. an editable dev install)"
  clean=0
fi
if [ -d "$XDG_DATA" ] && [ "$KEEP_MODELS" -eq 0 ]; then
  warn "$XDG_DATA still exists"
  clean=0
fi

if [ "$clean" -eq 1 ]; then
  ok "system is clean"
else
  warn "system has residual installs (see above)"
fi

# ──────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────

echo
if [ "$errors" -eq 0 ]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    printf "%sDry-run complete.%s Re-run without --dry-run to actually remove.\n" "$C_GRN" "$C_RST"
  else
    printf "%s✓%s Uninstall complete.\n" "$C_GRN" "$C_RST"
    printf "  Reinstall any time with: %spipx install localcaption%s\n" "$C_CYN" "$C_RST"
  fi
  exit 0
else
  printf "%s✗%s Uninstall finished with %d error(s) above.\n" "$C_RED" "$C_RST" "$errors"
  exit 1
fi
