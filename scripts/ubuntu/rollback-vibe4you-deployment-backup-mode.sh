#!/usr/bin/env bash
set -Eeuo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "This rollback must run as root" >&2
  exit 1
fi

ROOT="/var/backups/vibe4you-production"
if [ "$#" -gt 1 ]; then
  echo "usage: rollback-vibe4you-deployment-backup-mode.sh [ROLLBACK_DIRECTORY]" >&2
  exit 2
fi

if [ "$#" -eq 1 ]; then
  ROLLBACK_DIR="$1"
else
  ROLLBACK_DIR="$(find "$ROOT" -maxdepth 1 -mindepth 1 -type d -name 'pre-deployment-backup-mode-*' -print | LC_ALL=C sort | tail -n 1)"
fi

case "$ROLLBACK_DIR" in
  "$ROOT"/pre-deployment-backup-mode-*) ;;
  *)
    echo "Refusing unsafe rollback directory: $ROLLBACK_DIR" >&2
    exit 1
    ;;
esac

if [ ! -f "$ROLLBACK_DIR/backup-styledash-data" ] || [ ! -f "$ROLLBACK_DIR/vibe4you-ops" ]; then
  echo "Rollback directory is incomplete" >&2
  exit 1
fi

install -o root -g vibe4you -m 0750 "$ROLLBACK_DIR/backup-styledash-data" /opt/vibe4you-production/bin/backup-styledash-data
install -o root -g root -m 0755 "$ROLLBACK_DIR/vibe4you-ops" /usr/local/sbin/vibe4you-ops
bash -n /opt/vibe4you-production/bin/backup-styledash-data
bash -n /usr/local/sbin/vibe4you-ops

for unit in   vibe4you-production-public.service   vibe4you-production-admin.service   vibe4you-cloudflared.service   vibe4you-backup.timer   vibe4you-healthcheck.timer
do
  systemctl is-active --quiet "$unit" || {
    echo "Rollback verification failed: $unit is not active" >&2
    exit 1
  }
done

echo "VIBE4YOU_DEPLOYMENT_BACKUP_MODE_ROLLBACK=PASS"
echo "restored_from=$ROLLBACK_DIR"
