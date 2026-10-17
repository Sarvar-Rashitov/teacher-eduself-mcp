"""
Authentication business services for Telegram Login Widget and Google OAuth2.
"""

import hmac
import hashlib
import time
from typing import Optional, Tuple
from django.conf import settings
from .models import User, TeacherProfile


def check_telegram_hash(data: dict, bot_token: Optional[str] = None) -> bool:
    """
    Validates data received from the Telegram Login Widget using HMAC-SHA256.
    Per Telegram specification:
    1. Check that auth_date is within 24 hours (86400 seconds).
    2. Sort all key-value pairs alphabetically (excluding 'hash').
    3. Concatenate as 'key=value\\n'.
    4. Compute SHA256 of bot_token as secret key.
    5. Compare HMAC-SHA256 hex digest against received hash using constant-time comparison.
    """
    token = bot_token or getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        return False

    received_hash = data.get('hash')
    if not received_hash:
        return False

    # Check 24-hour expiration window
    auth_date = data.get('auth_date')
    if not auth_date:
        return False

    try:
        auth_timestamp = int(auth_date)
    except (ValueError, TypeError):
        return False

    if time.time() - auth_timestamp > 86400:
        return False

    # Prepare data-check-string (excluding 'hash')
    check_pairs = [
        f"{k}={v}" for k, v in sorted(data.items()) if k != 'hash' and v is not None
    ]
    data_check_string = "\n".join(check_pairs)

    secret_key = hashlib.sha256(token.encode('utf-8')).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_hash, str(received_hash).lower())


def authenticate_telegram_user(data: dict) -> Tuple[User, bool]:
    """
    Retrieves or registers a teacher using verified Telegram user details.
    Guarantees creation of TeacherProfile for newly registered teachers.
    """
    tg_id = int(data['id'])
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    raw_username = data.get('username')
    photo_url = data.get('photo_url')

    username = raw_username if raw_username else f"tg_{tg_id}"

    user, created = User.objects.get_or_create(
        telegram_id=tg_id,
        defaults={
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'avatar_url': photo_url,
            'role': 'teacher',
        }
    )

    if not created:
        # Update details if changed
        updated = False
        if photo_url and user.avatar_url != photo_url:
            user.avatar_url = photo_url
            updated = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            updated = True
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            updated = True
        if updated:
            user.save(update_fields=['avatar_url', 'first_name', 'last_name'])

    # Ensure teacher profile exists
    if user.is_teacher() and not hasattr(user, 'teacher_profile'):
        TeacherProfile.objects.get_or_create(user=user)

    return user, created


def authenticate_google_user(user_info: dict) -> Tuple[User, bool]:
    """
    Retrieves or creates a teacher account given verified Google userinfo claims.
    """
    email = user_info.get('email')
    if not email:
        raise ValueError("Google userinfo must contain a valid email address.")

    first_name = user_info.get('given_name') or user_info.get('first_name', '')
    last_name = user_info.get('family_name') or user_info.get('last_name', '')
    avatar_url = user_info.get('picture') or user_info.get('avatar_url')

    # Base username from email prefix with collision fallback
    base_username = email.split('@')[0]
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exclude(email=email).exists():
        username = f"{base_username}_{counter}"
        counter += 1

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'avatar_url': avatar_url,
            'role': 'teacher',
        }
    )

    if not created:
        updated = False
        if avatar_url and user.avatar_url != avatar_url:
            user.avatar_url = avatar_url
            updated = True
        if first_name and not user.first_name:
            user.first_name = first_name
            updated = True
        if last_name and not user.last_name:
            user.last_name = last_name
            updated = True
        if updated:
            user.save(update_fields=['avatar_url', 'first_name', 'last_name'])

    if user.is_teacher() and not hasattr(user, 'teacher_profile'):
        TeacherProfile.objects.get_or_create(user=user)

    return user, created
