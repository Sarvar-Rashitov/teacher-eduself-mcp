#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "==> Upgrading pip..."
python -m pip install --upgrade pip

echo "==> Installing dependencies..."
pip install -r requirements.txt

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Applying database migrations..."
python manage.py migrate --noinput

echo "==> Creating / updating superadmin user..."
python deploy/scripts/create_superuser.py || true

echo "==> Build completed successfully!"
