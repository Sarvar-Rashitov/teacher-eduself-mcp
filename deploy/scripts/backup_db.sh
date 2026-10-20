#!/usr/bin/env bash
# ============================================================
# EduSelf Teacher — PostgreSQL Avtomatik Zaxira Skripti
# DEPLOYMENT_ARCHITECTURE.md §6 asosida
# ============================================================
set -e

BACKUP_DIR="${BACKUP_DIR:-/data/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/eduself_backup_${TIMESTAMP}.sql.gz"

DB_NAME="${POSTGRES_DB:-eduself}"
DB_USER="${POSTGRES_USER:-eduself}"
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"

mkdir -p "$BACKUP_DIR"

echo "=== PostgreSQL Zaxira Nusxasini Yaratish Boshlandi ==="
echo "Baza: $DB_NAME ($DB_HOST:$DB_PORT)"
echo "Fayl: $BACKUP_FILE"

# pg_dump orqali ma'lumotlarni chiqarib, gzip bilan siqish
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --clean --if-exists | gzip > "$BACKUP_FILE"

echo "Zaxira nusxasi muvaffaqiyatli saqlandi: $(ls -lh "$BACKUP_FILE")"

# 7 kundan eski zaxira fayllarini avtomatik tozalash
echo "7 kundan eski zaxiralar tozalanmoqda..."
find "$BACKUP_DIR" -name "eduself_backup_*.sql.gz" -type f -mtime +7 -delete

echo "=== Zaxira Amaliyoti Yakunlandi ==="
