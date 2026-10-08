#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "This repair must run as root" >&2
  exit 1
fi

CANDIDATE="/home/vibeadmin/vibe4you-monitoring-candidate/vibe4you_healthcheck.py"
TARGET="/opt/vibe4you-production/bin/vibe4you_healthcheck.py"
EXPECTED="a730a4b395f2c05d26c3cff91562770de65a846bcd88614e0b0319c80cc4c59b"
ROLLBACK="/var/backups/vibe4you-production/pre-monitoring-20261001T050230Z"

for unit in vibe4you-production-public.service vibe4you-production-admin.service vibe4you-cloudflared.service vibe4you-backup.timer
do
  systemctl is-active --quiet "$unit" || {
    echo "Preflight failed: $unit is not active" >&2
    exit 1
  }
done

actual="$(sha256sum "$CANDIDATE" | awk '{print $1}')"
if [ "$actual" != "$EXPECTED" ]; then
  echo "Candidate integrity check failed" >&2
  exit 1
fi

systemctl disable --now vibe4you-healthcheck.timer 2>/dev/null || true
install -d -o root -g root -m 0700 "$ROLLBACK"
if [ -e "$TARGET" ]; then
  cp -a "$TARGET" "$ROLLBACK/vibe4you_healthcheck.py.before-immutable-fix"
fi

install -o root -g vibe4you -m 0750 "$CANDIDATE" "$TARGET"
python3 -m py_compile "$TARGET"
systemctl reset-failed vibe4you-healthcheck.service || true

if ! systemctl start vibe4you-healthcheck.service; then
  systemctl --no-pager --full status vibe4you-healthcheck.service || true
  echo "Healthcheck still failing; timer remains disabled" >&2
  exit 1
fi

systemctl enable --now vibe4you-healthcheck.timer
systemctl is-enabled --quiet vibe4you-healthcheck.timer
systemctl is-active --quiet vibe4you-healthcheck.timer

for unit in vibe4you-production-public.service vibe4you-production-admin.service vibe4you-cloudflared.service vibe4you-backup.timer
do
  systemctl is-active --quiet "$unit" || {
    echo "Post-check failed: $unit is not active" >&2
    exit 1
  }
done

echo "VIBE4YOU_MONITORING_REPAIR=PASS"