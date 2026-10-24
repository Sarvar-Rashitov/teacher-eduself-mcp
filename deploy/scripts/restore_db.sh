#!/usr/bin/env bash
# ==============================================================================
# EduSelf Teacher — PostgreSQL Database Restore Script
# Restores a custom-format pg_dump file to the target database.
# ==============================================================================
set -e

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo "[ERROR] Usage: $0 <path-to-backup-file.dump>"
    echo "[ERROR] Backup file not found: $BACKUP_FILE"
    exit 1
fi

POSTGRES_HOST="${DB_HOST:-postgres}"
POSTGRES_PORT="${DB_PORT:-5432}"
POSTGRES_DB="${DB_NAME:-eduself_db}"
POSTGRES_USER="${DB_USER:-eduself_user}"

export PGPASSWORD="${DB_PASSWORD:-$POSTGRES_PASSWORD}"

echo "=========================================================="
echo " RESTORING DATABASE: ${POSTGRES_DB}"
echo " FROM FILE: ${BACKUP_FILE}"
echo " HOST: ${POSTGRES_HOST}:${POSTGRES_PORT}"
echo "=========================================================="

pg_restore \
    -h "$POSTGRES_HOST" \
    -p "$POSTGRES_PORT" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --clean \
    --if-exists \
    -v \
    "$BACKUP_FILE"

echo "[SUCCESS] Database restoration completed successfully!"
