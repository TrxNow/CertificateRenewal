#!/usr/bin/env bash
# Install Python deps, certbot (in .venv), and a daily system timer on Omarchy.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALL_TIMER=1
# Local time. Override with TIMER_TIME=09:00 ./scripts/install-omarchy.sh
TIMER_TIME="${TIMER_TIME:-12:00}"

usage() {
  cat <<'EOF'
Usage: TIMER_TIME=12:00 scripts/install-omarchy.sh [--no-timer]

Creates .venv, installs certbot with pip, and enables a daily *system*
systemd timer (runs even if you are logged out).

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

chmod +x \
  "$REPO_ROOT/scripts/run-renewal.sh" \
  "$REPO_ROOT/scripts/install-omarchy.sh" \
  "$REPO_ROOT/scripts/timer-status.sh"

if [[ ! -f "$REPO_ROOT/.env" ]]; then
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
  echo "Created $REPO_ROOT/.env — add SMTP settings and set DEV_MODE."
fi

if [[ "$INSTALL_TIMER" -eq 1 ]]; then
  if [[ ! "$TIMER_TIME" =~ ^[0-2][0-9]:[0-5][0-9]$ ]]; then
    echo "TIMER_TIME must be HH:MM (got $TIMER_TIME)" >&2
    exit 1
  fi

  # Avoid a second daily run from the old user timer.
  systemctl --user disable --now certificate-renewal.timer 2>/dev/null || true
  rm -f "$HOME/.config/systemd/user/certificate-renewal.timer" \
        "$HOME/.config/systemd/user/certificate-renewal.service"
  systemctl --user daemon-reload 2>/dev/null || true

  service_path="/etc/systemd/system/certificate-renewal.service"
  timer_path="/etc/systemd/system/certificate-renewal.timer"
  echo "Installing system timer at ${TIMER_TIME} local time (needs sudo)..."
  sudo tee "$service_path" >/dev/null <<EOF
[Unit]
Description=Let's Encrypt certificate renewal
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$USER
Group=$(id -gn)
WorkingDirectory=$REPO_ROOT
Environment=HOME=$HOME
Environment=PATH=$REPO_ROOT/.venv/bin:/usr/bin
ExecStart=$REPO_ROOT/scripts/run-renewal.sh
Nice=10
EOF
  sudo tee "$timer_path" >/dev/null <<EOF
[Unit]
Description=Daily Let's Encrypt certificate renewal

[Timer]
OnCalendar=*-*-* ${TIMER_TIME}:00
AccuracySec=1min
RandomizedDelaySec=0
Persistent=true
WakeSystem=true

[Install]
WantedBy=timers.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable --now certificate-renewal.timer
  echo "Installed system timer: certificate-renewal.timer (${TIMER_TIME} daily, local time)"
  systemctl list-timers certificate-renewal.timer --all --no-pager || true
fi

echo
echo "Done. Next:"
echo "  1. Edit $REPO_ROOT/.env"
echo "  2. Check the schedule: $REPO_ROOT/scripts/timer-status.sh"
echo "  3. Test now: $REPO_ROOT/scripts/run-renewal.sh --dev"
echo "  4. Logs: $REPO_ROOT/logs/"
