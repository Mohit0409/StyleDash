#!/usr/bin/env bash
set -Eeuo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "This installer must run as root" >&2
  exit 1
fi

CANDIDATE_DIR="/home/vibeadmin/vibe4you-deployment-backup-candidate"
CANDIDATE_BACKUP="$CANDIDATE_DIR/backup-styledash-data"
CANDIDATE_OPS="$CANDIDATE_DIR/vibe4you-ops"
LIVE_BACKUP="/opt/vibe4you-production/bin/backup-styledash-data"
LIVE_OPS="/usr/local/sbin/vibe4you-ops"
RUN_DIR="/var/lib/vibe4you-production/run"
PRIMARY_MARKER="$RUN_DIR/styledash-last-offdevice-backup"
SECONDARY_MARKER="$RUN_DIR/styledash-last-secondary-backup"
LOCAL_MARKER="$RUN_DIR/styledash-last-local-backup"

EXPECTED_CANDIDATE_BACKUP_SHA256="91ce54bd239615f5b588f81291643376d9681164a2665d7cd878f2d34e2ca6a1"
EXPECTED_CANDIDATE_OPS_SHA256="85b9e1cbc2f206d5548c3c18e91d778f38215554c1814f237fad6ea708bf4a5d"
EXPECTED_LIVE_BACKUP_SHA256="41f64f6144884bc0fe7ba6a72a14d77a6e952bac07bba67eda0457f8b67a809f"
EXPECTED_LIVE_OPS_SHA256="7c5ac28c6821396ce5384fc1f59a8859b091602f53dcfc147ec353257a8aa293"

sha256_of() {
  sha256sum "$1" | awk '{print $1}'
}

require_hash() {
  local path="$1"
  local expected="$2"
  local label="$3"
  local actual
  actual="$(sha256_of "$path")"
  if [ "$actual" != "$expected" ]; then
    echo "$label hash mismatch; refusing installation" >&2
    exit 1
  fi
}

for path in "$CANDIDATE_BACKUP" "$CANDIDATE_OPS" "$LIVE_BACKUP" "$LIVE_OPS"; do
  if [ ! -f "$path" ]; then
    echo "Required file missing: $path" >&2
    exit 1
  fi
done

require_hash "$CANDIDATE_BACKUP" "$EXPECTED_CANDIDATE_BACKUP_SHA256" "Candidate backup script"
require_hash "$CANDIDATE_OPS" "$EXPECTED_CANDIDATE_OPS_SHA256" "Candidate ops wrapper"
require_hash "$LIVE_BACKUP" "$EXPECTED_LIVE_BACKUP_SHA256" "Current production backup script"
require_hash "$LIVE_OPS" "$EXPECTED_LIVE_OPS_SHA256" "Current production ops wrapper"

bash -n "$CANDIDATE_BACKUP"
bash -n "$CANDIDATE_OPS"

for unit in   vibe4you-production-public.service   vibe4you-production-admin.service   vibe4you-cloudflared.service   vibe4you-backup.timer   vibe4you-healthcheck.timer
do
  systemctl is-active --quiet "$unit" || {
    echo "Preflight failed: $unit is not active" >&2
    exit 1
  }
done

if systemctl is-active --quiet vibe4you-backup.service; then
  echo "A full/scheduled backup is currently running; try again after it finishes" >&2
  exit 75
fi

if [ ! -s "$PRIMARY_MARKER" ]; then
  echo "Verified primary cloud backup marker is missing; refusing deployment-mode installation" >&2
  exit 1
fi

before_primary="$(cat "$PRIMARY_MARKER")"
before_secondary="$(cat "$SECONDARY_MARKER" 2>/dev/null || true)"
before_local="$(cat "$LOCAL_MARKER" 2>/dev/null || true)"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
ROLLBACK_DIR="/var/backups/vibe4you-production/pre-deployment-backup-mode-$stamp"
install -d -o root -g root -m 0700 "$ROLLBACK_DIR"
cp -a "$LIVE_BACKUP" "$ROLLBACK_DIR/backup-styledash-data"
cp -a "$LIVE_OPS" "$ROLLBACK_DIR/vibe4you-ops"

mutation_started=0
rollback_files() {
  set +e
  if [ "$mutation_started" -eq 1 ]; then
    install -o root -g vibe4you -m 0750 "$ROLLBACK_DIR/backup-styledash-data" "$LIVE_BACKUP"
    install -o root -g root -m 0755 "$ROLLBACK_DIR/vibe4you-ops" "$LIVE_OPS"
    bash -n "$LIVE_BACKUP"
    bash -n "$LIVE_OPS"
    echo "DEPLOYMENT_BACKUP_MODE_ROLLBACK=PASS" >&2
  fi
}

handle_failure() {
  local status="$1"
  local line="$2"
  trap - ERR INT TERM
  echo "Deployment backup mode installation failed at line $line (status $status)" >&2
  rollback_files
  exit "$status"
}

trap 'handle_failure $? $LINENO' ERR
trap 'handle_failure 130 $LINENO' INT
trap 'handle_failure 143 $LINENO' TERM

mutation_started=1
install -o root -g vibe4you -m 0750 "$CANDIDATE_BACKUP" "$LIVE_BACKUP"
install -o root -g root -m 0755 "$CANDIDATE_OPS" "$LIVE_OPS"

require_hash "$LIVE_BACKUP" "$EXPECTED_CANDIDATE_BACKUP_SHA256" "Installed backup script"
require_hash "$LIVE_OPS" "$EXPECTED_CANDIDATE_OPS_SHA256" "Installed ops wrapper"
bash -n "$LIVE_BACKUP"
bash -n "$LIVE_OPS"

"$LIVE_OPS" backup-deployment

after_primary="$(cat "$PRIMARY_MARKER")"
after_secondary="$(cat "$SECONDARY_MARKER")"
after_local="$(cat "$LOCAL_MARKER")"

if [ "$after_primary" != "$before_primary" ]; then
  echo "Primary cloud marker changed during deployment backup; expected Drive upload to be skipped" >&2
  exit 1
fi
if [ -z "$after_secondary" ] || [ "$after_secondary" = "$before_secondary" ]; then
  echo "Windows secondary marker did not advance during deployment backup" >&2
  exit 1
fi
if [ -z "$after_local" ] || [ "$after_local" = "$before_local" ]; then
  echo "Local backup marker did not advance during deployment backup" >&2
  exit 1
fi
if [ "$after_local" != "$after_secondary" ]; then
  echo "Local and Windows deployment backup markers do not match" >&2
  exit 1
fi

for unit in   vibe4you-production-public.service   vibe4you-production-admin.service   vibe4you-cloudflared.service   vibe4you-backup.timer   vibe4you-healthcheck.timer
do
  systemctl is-active --quiet "$unit" || {
    echo "Post-install check failed: $unit is not active" >&2
    exit 1
  }
done

curl -fsS http://127.0.0.1:8080/api/health >/dev/null

trap - ERR INT TERM
echo "VIBE4YOU_DEPLOYMENT_BACKUP_MODE=PASS"
echo "deployment_backup_stamp=$after_local"
echo "primary_cloud_marker_preserved=$after_primary"
echo "rollback_directory=$ROLLBACK_DIR"
