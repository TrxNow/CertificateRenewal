#!/usr/bin/env bash
# Install Python deps, certbot (in .venv), and a daily systemd timer on Omarchy.
# Does not require pacman package DBs (common on a fresh Omarchy install).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALL_TIMER=1

usage() {
  cat <<'EOF'
Usage: scripts/install-omarchy.sh [--no-timer]

Creates .venv, installs PyYAML + certbot with pip, and enables a daily
systemd user timer at 12:00.

  --no-timer   Install the venv only
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-timer|--no-cron) INSTALL_TIMER=0 ;;
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

PYTHON="$(command -v python3 || command -v python || true)"
if [[ -z "$PYTHON" ]]; then
  echo "python3 is not on PATH. Install Python, then rerun." >&2
  exit 1
fi

echo "Using $PYTHON"
echo "Creating Python venv and installing certbot..."
"$PYTHON" -m venv "$REPO_ROOT/.venv"
"$REPO_ROOT/.venv/bin/pip" install --upgrade pip
"$REPO_ROOT/.venv/bin/pip" install -r "$REPO_ROOT/scripts/requirements.txt" certbot

chmod +x "$REPO_ROOT/scripts/run-renewal.sh" "$REPO_ROOT/scripts/install-omarchy.sh"

if [[ ! -f "$REPO_ROOT/.env" ]]; then
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
  echo "Created $REPO_ROOT/.env — add SMTP settings and set DEV_MODE."
fi

if [[ "$INSTALL_TIMER" -eq 1 ]]; then
  unit_dir="$HOME/.config/systemd/user"
  mkdir -p "$unit_dir"
  cat >"$unit_dir/certificate-renewal.service" <<EOF
[Unit]
Description=Let's Encrypt certificate renewal

[Service]
Type=oneshot
WorkingDirectory=$REPO_ROOT
Environment=PATH=$REPO_ROOT/.venv/bin:/usr/bin
ExecStart=$REPO_ROOT/scripts/run-renewal.sh
EOF
  cat >"$unit_dir/certificate-renewal.timer" <<EOF
[Unit]
Description=Daily Let's Encrypt certificate renewal

[Timer]
OnCalendar=*-*-* 12:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now certificate-renewal.timer
  if command -v loginctl >/dev/null 2>&1; then
    loginctl enable-linger "$USER" 2>/dev/null || \
      echo "Could not enable linger; the timer runs while you are logged in."
  fi
  echo "Installed systemd timer: certificate-renewal.timer (12:00 daily)"
  systemctl --user list-timers certificate-renewal.timer --no-pager || true
fi

echo
echo "Done. Next:"
echo "  1. Edit $REPO_ROOT/.env"
echo "  2. Import certbot files into data/letsencrypt/<client-id>/"
echo "  3. Test: $REPO_ROOT/scripts/run-renewal.sh --dev"
echo "  4. Logs: $REPO_ROOT/logs/"
