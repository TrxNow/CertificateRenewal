#!/usr/bin/env bash
# Install certbot, Python deps, cronie, and a daily crontab on Omarchy (Arch).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CRON_MARKER="CertificateRenewal/scripts/run-renewal.sh"
CRON_SCHEDULE="${CRON_SCHEDULE:-0 12 * * *}"
INSTALL_CRON=1

usage() {
  cat <<'EOF'
Usage: scripts/install-omarchy.sh [--no-cron]

Installs certbot, cronie, a local .venv, and a daily crontab that runs
scripts/run-renewal.sh at 12:00 (local time).

  --no-cron   Install packages and the venv only
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-cron) INSTALL_CRON=0 ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if ! command -v pacman >/dev/null 2>&1; then
  echo "This installer is for Omarchy/Arch (pacman not found)." >&2
  exit 1
fi

echo "Installing certbot, python, and cronie..."
sudo pacman -S --needed --noconfirm certbot python python-pip cronie

echo "Enabling cronie..."
sudo systemctl enable --now cronie.service

echo "Creating Python venv..."
python -m venv "$REPO_ROOT/.venv"
"$REPO_ROOT/.venv/bin/pip" install --upgrade pip
"$REPO_ROOT/.venv/bin/pip" install -r "$REPO_ROOT/scripts/requirements.txt"

chmod +x "$REPO_ROOT/scripts/run-renewal.sh" "$REPO_ROOT/scripts/install-omarchy.sh"

if [[ ! -f "$REPO_ROOT/.env" ]]; then
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
  echo "Created $REPO_ROOT/.env — add SMTP settings and set DEV_MODE."
fi

if [[ "$INSTALL_CRON" -eq 1 ]]; then
  cron_line="$CRON_SCHEDULE $REPO_ROOT/scripts/run-renewal.sh"
  existing="$(crontab -l 2>/dev/null || true)"
  filtered="$(printf '%s\n' "$existing" | grep -v "$CRON_MARKER" || true)"
  {
    [[ -n "$filtered" ]] && printf '%s\n' "$filtered"
    printf '%s\n' "$cron_line"
  } | crontab -
  echo "Installed crontab: $cron_line"
  crontab -l
else
  echo "Skipped crontab (--no-cron)."
fi

echo
echo "Done. Next:"
echo "  1. Edit $REPO_ROOT/.env"
echo "  2. Import certbot files into data/letsencrypt/<client-id>/"
echo "  3. Test: $REPO_ROOT/scripts/run-renewal.sh --dev"
echo "  4. Logs: $REPO_ROOT/logs/"
