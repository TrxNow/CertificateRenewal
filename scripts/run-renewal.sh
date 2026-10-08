#!/usr/bin/env bash
# Cron entry point for Omarchy/Arch: load .env and run renew_all.py.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

export PATH="$REPO_ROOT/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

load_env() {
  local file="$1" line key val
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "${line// /}" || "$line" == \#* ]] && continue
    key="${line%%=*}"
    val="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    if [[ "$val" == \"*\" && "$val" == *\" ]]; then
      val="${val:1:${#val}-2}"
    elif [[ "$val" == \'*\' && "$val" == *\' ]]; then
      val="${val:1:${#val}-2}"
    fi
    export "$key=$val"
  done <"$file"
}

if [[ -f "$REPO_ROOT/.env" ]]; then
  load_env "$REPO_ROOT/.env"
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
