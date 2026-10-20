#!/usr/bin/env bash
# ============================================================
# EduSelf Teacher — PostgreSQL Zaxiradan Tiklash Skripti
# ============================================================
set -e

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
  echo "Xatolik: Tiklash uchun zaxira fayli ko'rsatilmadi yoki fayl mavjud emas!"
  echo "Foydalanish: $0 /yo'l/fayl.sql.gz"
  exit 1
fi

DB_NAME="${POSTGRES_DB:-eduself}"
DB_USER="${POSTGRES_USER:-eduself}"
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"

echo "=== DIQQAT: PostgreSQL Bazasini Tiklash Boshlanmoqda ==="
echo "Maqsad baza: $DB_NAME ($DB_HOST:$DB_PORT)"
echo "Fayl: $BACKUP_FILE"

if [[ "$BACKUP_FILE" == *.gz ]]; then
  gunzip -c "$BACKUP_FILE" | PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"
else
  PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" < "$BACKUP_FILE"
fi

echo "=== Ma'lumotlar Bazasi Muvaffaqiyatli Tiklandi! ==="
