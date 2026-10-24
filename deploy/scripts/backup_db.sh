#!/usr/bin/env bash
# ==============================================================================
# EduSelf Teacher — PostgreSQL Database Backup Script (DOC-SEC-01 / DEPLOYMENT)
# Creates compressed custom-format pg_dump and removes backups older than 14 days.
# ==============================================================================
set -e

BACKUP_DIR="${BACKUP_DIR:-/data/backups}"
POSTGRES_HOST="${DB_HOST:-postgres}"
POSTGRES_PORT="${DB_PORT:-5432}"
POSTGRES_DB="${DB_NAME:-eduself_db}"
POSTGRES_USER="${DB_USER:-eduself_user}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/eduself_db_${TIMESTAMP}.dump"

echo "[INFO] Starting PostgreSQL database backup for '${POSTGRES_DB}'..."
echo "[INFO] Destination: ${BACKUP_FILE}"

# 1. pg_dump custom format (-Fc) orqali zaxira nusxa yaratish
export PGPASSWORD="${DB_PASSWORD:-$POSTGRES_PASSWORD}"

pg_dump \
    -h "$POSTGRES_HOST" \
    -p "$POSTGRES_PORT" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -Fc \
    -v \
    -f "$BACKUP_FILE"

# 2. Zaxira nusxa yaxlitligini tekshirish (Integrity check)
echo "[INFO] Verifying backup integrity..."
pg_restore -l "$BACKUP_FILE" > /dev/null 2>&1
echo "[SUCCESS] Backup verification passed!"

# 3. Fayl hajmini va xeshini qayd etish
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[SUCCESS] Backup successfully created: ${BACKUP_FILE} (Size: ${BACKUP_SIZE})"

# 4. Belgilangan kundan (14 kun) eski zaxira nusxalarini tozalash
echo "[INFO] Pruning backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "eduself_db_*.dump" -type f -mtime +"$RETENTION_DAYS" -exec rm -f {} +
echo "[SUCCESS] Backup lifecycle maintenance completed."
