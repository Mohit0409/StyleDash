#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "This rollback must run as root" >&2
  exit 1
fi

systemctl disable --now vibe4you-healthcheck.timer 2>/dev/null || true
systemctl stop vibe4you-healthcheck.service 2>/dev/null || true

rm -f /etc/systemd/system/vibe4you-healthcheck.service
rm -f /etc/systemd/system/vibe4you-healthcheck.timer
rm -f /etc/systemd/system/vibe4you-ops-alert@.service
rm -f /opt/vibe4you-production/bin/vibe4you_healthcheck.py
rm -f /opt/vibe4you-production/bin/vibe4you_ops_alert.py
rm -f /etc/vibe4you-production/ops-alert.env

systemctl daemon-reload
systemctl reset-failed vibe4you-healthcheck.service 2>/dev/null || true

for unit in vibe4you-production-public.service vibe4you-production-admin.service vibe4you-cloudflared.service vibe4you-backup.timer
do
  systemctl is-active --quiet "$unit" || {
    echo "Rollback warning: $unit is not active" >&2
    exit 1
  }
done

echo "VIBE4YOU_MONITORING_ROLLBACK=PASS"