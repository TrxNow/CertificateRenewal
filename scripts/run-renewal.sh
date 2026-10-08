#!/usr/bin/env bash
# Cron entry point for Omarchy/Arch: load .env and run renew_all.py.
set -euo pipefail

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"
  set +a
fi

export LETSENCRYPT_ROOT="${LETSENCRYPT_ROOT:-$REPO_ROOT/data/letsencrypt}"

LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/renewal-$(date -u +%Y-%m-%d).log"

PYTHON="$REPO_ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3 || command -v python)"
fi

{
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) renewal start ====="
  "$PYTHON" "$SCRIPT_DIR/renew_all.py" "$@"
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) renewal done ====="
} 2>&1 | tee -a "$LOG_FILE"
