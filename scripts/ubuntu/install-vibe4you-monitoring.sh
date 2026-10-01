#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "This installer must run as root" >&2
  exit 1
fi

CANDIDATE="/home/vibeadmin/vibe4you-monitoring-candidate"
APP_BIN="/opt/vibe4you-production/bin"
UNIT_DIR="/etc/systemd/system"
OPS_ENV="/etc/vibe4you-production/ops-alert.env"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ROLLBACK="/var/backups/vibe4you-production/pre-monitoring-$STAMP"

for path in \
  "$CANDIDATE/vibe4you_healthcheck.py" \
  "$CANDIDATE/vibe4you_ops_alert.py" \
  "$CANDIDATE/systemd/vibe4you-healthcheck.service" \
  "$CANDIDATE/systemd/vibe4you-healthcheck.timer" \
  "$CANDIDATE/systemd/vibe4you-ops-alert@.service"
do
  if [ ! -f "$path" ]; then
    echo "Missing candidate file: $path" >&2
    exit 1
  fi
done

check_hash() {
  expected="$1"
  path="$2"
  actual="$(sha256sum "$path" | awk '{print $1}')"
  if [ "$actual" != "$expected" ]; then
    echo "Candidate integrity check failed: $path" >&2
    exit 1
  fi
}

check_hash "6d5267ec6bd21db3788a7a748787a8f6de39a28ccb321516c9a064d395c8771f" "$CANDIDATE/vibe4you_healthcheck.py"
check_hash "a2bc55ee2fde610ff2fe729e0223181f07b35753569a2fd3d488e76983bf156c" "$CANDIDATE/vibe4you_ops_alert.py"
check_hash "80115132c427ba5f6caaace39afe7789e5ddb886f2cb579b7c73e7a6e677791a" "$CANDIDATE/systemd/vibe4you-healthcheck.service"
check_hash "1b14dc1daf29cce1e57c1ff87bb6ad38ca0a1b320b2c3293889068d0bcdc5932" "$CANDIDATE/systemd/vibe4you-healthcheck.timer"
check_hash "bb037fcfac15d98c64458202af140d8ea9a3feb3dba4ce68157ad1c8a232e2e1" "$CANDIDATE/systemd/vibe4you-ops-alert@.service"
for unit in \
  vibe4you-production-public.service \
  vibe4you-production-admin.service \
  vibe4you-cloudflared.service \
  vibe4you-backup.timer
do
  systemctl is-active --quiet "$unit" || {
    echo "Preflight failed: $unit is not active" >&2
    exit 1
  }
  systemctl is-enabled --quiet "$unit" || {
    echo "Preflight failed: $unit is not enabled" >&2
    exit 1
  }
done

for path in \
  "$APP_BIN/vibe4you_healthcheck.py" \
  "$APP_BIN/vibe4you_ops_alert.py" \
  "$UNIT_DIR/vibe4you-healthcheck.service" \
  "$UNIT_DIR/vibe4you-healthcheck.timer" \
  "$UNIT_DIR/vibe4you-ops-alert@.service"
do
  if [ -e "$path" ]; then
    echo "Refusing to overwrite existing monitoring file: $path" >&2
    exit 1
  fi
done

if [ -e "$OPS_ENV" ]; then
  echo "Refusing to overwrite existing ops alert environment file" >&2
  exit 1
fi

install -d -o root -g root -m 0700 "$ROLLBACK"
systemctl is-enabled vibe4you-production-public.service vibe4you-production-admin.service vibe4you-cloudflared.service vibe4you-backup.timer > "$ROLLBACK/pre-install-enabled.txt" 2>&1 || true
systemctl is-active vibe4you-production-public.service vibe4you-production-admin.service vibe4you-cloudflared.service vibe4you-backup.timer > "$ROLLBACK/pre-install-active.txt" 2>&1 || true

install -o root -g vibe4you -m 0750 "$CANDIDATE/vibe4you_healthcheck.py" "$APP_BIN/vibe4you_healthcheck.py"
install -o root -g vibe4you -m 0750 "$CANDIDATE/vibe4you_ops_alert.py" "$APP_BIN/vibe4you_ops_alert.py"
install -o root -g root -m 0644 "$CANDIDATE/systemd/vibe4you-healthcheck.service" "$UNIT_DIR/vibe4you-healthcheck.service"
install -o root -g root -m 0644 "$CANDIDATE/systemd/vibe4you-healthcheck.timer" "$UNIT_DIR/vibe4you-healthcheck.timer"
install -o root -g root -m 0644 "$CANDIDATE/systemd/vibe4you-ops-alert@.service" "$UNIT_DIR/vibe4you-ops-alert@.service"

tmp_env="$(mktemp)"
trap 'rm -f "$tmp_env"' EXIT
for source_env in /etc/vibe4you-production/public.env /etc/vibe4you-production/admin.env
do
  if [ -r "$source_env" ]; then
    grep -E '^STYLEDASH_NTFY_(ENABLED|BASE_URL|TOPIC)=' "$source_env" >> "$tmp_env" || true
  fi
done

if [ -s "$tmp_env" ]; then
  awk -F= '!seen[$1]++' "$tmp_env" > "$OPS_ENV"
  chown root:vibe4you "$OPS_ENV"
  chmod 0640 "$OPS_ENV"
  echo "OPS_ALERT_CONFIG=COPIED_WITHOUT_DISPLAY"
else
  install -o root -g vibe4you -m 0640 /dev/null "$OPS_ENV"
  echo "OPS_ALERT_CONFIG=EMPTY"
fi

python3 -m py_compile "$APP_BIN/vibe4you_healthcheck.py" "$APP_BIN/vibe4you_ops_alert.py"

systemd-analyze verify "$UNIT_DIR/vibe4you-healthcheck.service" "$UNIT_DIR/vibe4you-healthcheck.timer" "$UNIT_DIR/vibe4you-ops-alert@.service"

systemctl daemon-reload

if ! systemctl start vibe4you-healthcheck.service; then
  systemctl --no-pager --full status vibe4you-healthcheck.service || true
  echo "Healthcheck failed; timer was not enabled" >&2
  echo "Rollback directory: $ROLLBACK" >&2
  exit 1
fi

systemctl enable --now vibe4you-healthcheck.timer
systemctl is-active --quiet vibe4you-healthcheck.timer
systemctl is-enabled --quiet vibe4you-healthcheck.timer

echo "VIBE4YOU_MONITORING_INSTALL=PASS"
echo "ROLLBACK_DIRECTORY=$ROLLBACK"