"""
Render yoki boshqa ishlab chiqarish muhitida avtomatik ravishda
Superadmin foydalanuvchisini yaratuvchi yoki parolini yangilovchi skript.
"""
import os
import sys
from pathlib import Path

# Loyiha asosiy papkasini (root) sys.path ga qo'shish
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

import django

# Django sozlamalarini yuklash
if os.getenv("RENDER"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.production")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.local")

django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def create_or_update_superuser():
    username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin").strip()
    email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@eduself.uz").strip()
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "Admin12345!").strip()

    if not username or not password:
        print("[ERROR] Superuser username yoki password berilmagan.")
        return

    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "role": "system_admin",
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        }
    )

    # Parolni har doim yangilab qo'yamiz (kirishda muammo bo'lmasligi uchun)
    user.set_password(password)
    user.email = email
    user.role = "system_admin"
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.save()

    if created:
        print(f"==> [SUCCESS] Yangi Superadmin '{username}' muvaffaqiyatli yaratildi!")
    else:
        print(f"==> [SUCCESS] Superadmin '{username}' mavjud, uning paroli muvaffaqiyatli yangilandi!")


if __name__ == "__main__":
    create_or_update_superuser()
