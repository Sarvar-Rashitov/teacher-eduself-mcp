#!/usr/bin/env bash
# ============================================================
# EduSelf Teacher — Container Entrypoint Script
# ============================================================
set -e

echo "=== EduSelf Backend Ishga Tushmoqda ==="

# 1. PostgreSQL mavjudligini kutish
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"

echo "PostgreSQL serveri kutilmoqda ($DB_HOST:$DB_PORT)..."
while ! nc -z "$DB_HOST" "$DB_PORT"; do
  sleep 1
done
echo "PostgreSQL serveri muvaffaqiyatli ulandi."

# 2. Redis mavjudligini kutish
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"

echo "Redis serveri kutilmoqda ($REDIS_HOST:$REDIS_PORT)..."
while ! nc -z "$REDIS_HOST" "$REDIS_PORT"; do
  sleep 1
done
echo "Redis serveri muvaffaqiyatli ulandi."

# 3. Agar buyruq web yoki daphne bo'lsa, migratsiya va collectstatic ni avtomatik bajarish
if [[ "$*" == *"daphne"* ]] || [[ "$1" == "web" ]]; then
  echo "Ma'lumotlar bazasi migratsiyalari tekshirilmoqda..."
  python manage.py migrate --noinput

  echo "Statik fayllar yig'ilmoqda (collectstatic)..."
  python manage.py collectstatic --noinput
fi

echo "Asosiy jarayon ishga tushirilmoqda: $@"
exec "$@"
