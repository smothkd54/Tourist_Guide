#!/usr/bin/env bash
# backup.sh — daily backup for Pushkinskaya Street Explorer
#
# Usage:
#   ./scripts/backup.sh                  # backup to默认目录
#   ./scripts/backup.sh /mnt/backup      # backup to custom directory
#
# Cron example (daily at 3 AM):
#   0 3 * * * /path/to/tourist_app/scripts/backup.sh /mnt/backup >> /var/log/tourist-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${1:-/var/backups/pushkinskaya}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATE=$(date +%Y%m%d_%H%M%S)
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

# Backup models (includes the trained .keras file)
if [ -d "$PROJECT_DIR/models" ]; then
    tar czf "$BACKUP_DIR/models_$DATE.tar.gz" -C "$PROJECT_DIR" models/
    echo "  Models backed up: models_$DATE.tar.gz"
fi

# Backup landmark data
if [ -d "$PROJECT_DIR/data" ]; then
    tar czf "$BACKUP_DIR/data_$DATE.tar.gz" -C "$PROJECT_DIR" \
        --exclude='data/raw' \
        --exclude='data/images' \
        data/
    echo "  Data backed up: data_$DATE.tar.gz"
fi

# Backup logs (last 7 days only)
if [ -d "$PROJECT_DIR/logs" ]; then
    tar czf "$BACKUP_DIR/logs_$DATE.tar.gz" -C "$PROJECT_DIR" logs/
    echo "  Logs backed up: logs_$DATE.tar.gz"
fi

# Clean up old backups
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$KEEP_DAYS -delete 2>/dev/null || true
REMAINING=$(find "$BACKUP_DIR" -name "*.tar.gz" | wc -l)
echo "  Backups retained: $REMAINING (keeping $KEEP_DAYS days)"

echo "[$(date)] Backup complete."
