#!/usr/bin/env bash
# ==============================================================================
# EduSelf Teacher Production Entrypoint Script
# Waits for Database, executes migrations and collectstatic, then launches app.
# ==============================================================================
set -e

echo "=========================================================="
echo " Starting EduSelf Teacher Backend Service..."
echo " Environment: ${ENVIRONMENT:-production}"
echo "=========================================================="

DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-eduself_user}"

# 1. PostgreSQL ma'lumotlar bazasining tayyor bo'lishini kutish
echo "[INFO] Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; do
    echo "[WAIT] Database is unavailable - sleeping 2 seconds..."
    sleep 2
done
echo "[SUCCESS] PostgreSQL is ready!"

# 2. Redis ulanishini tekshirish (agar curl/nc mavjud bo'lsa)
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
echo "[INFO] Checking Redis at ${REDIS_HOST}:${REDIS_PORT}..."

# 3. Avtomatik migratsiyalarni bajarish
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[INFO] Running database migrations..."
    python manage.py migrate --noinput
    echo "[SUCCESS] Migrations applied successfully."
fi

# 4. Statik fayllarni to'plash (collectstatic)
if [ "${COLLECT_STATIC:-true}" = "true" ]; then
    echo "[INFO] Collecting static files..."
    python manage.py collectstatic --noinput --clear || true
    echo "[SUCCESS] Static files collected."
fi

echo "[INFO] Handing over execution to container command: $@"
exec "$@"
