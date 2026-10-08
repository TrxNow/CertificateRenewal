#!/usr/bin/env bash
# Show whether the daily renewal timer is enabled and when it last/next runs.
set -euo pipefail

echo "=== system timer ==="
if systemctl list-unit-files certificate-renewal.timer --no-legend 2>/dev/null | grep -q certificate-renewal.timer; then
  systemctl status certificate-renewal.timer --no-pager || true
  echo
  systemctl list-timers certificate-renewal.timer --all --no-pager || true
else
  echo "certificate-renewal.timer is not installed as a system timer."
fi

echo
echo "=== user timer (should be off) ==="
systemctl --user list-timers certificate-renewal.timer --all --no-pager 2>/dev/null || true

echo
echo "=== recent log ==="
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ls -1t "$REPO_ROOT/logs"/renewal-*.log 2>/dev/null | head -1 | while read -r f; do
  echo "$f"
  tail -n 20 "$f"
done
