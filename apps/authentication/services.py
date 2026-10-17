import hmac
import hashlib
import time
import requests
from typing import Dict, Any, Optional
from django.conf import settings


def check_telegram_hash(data: Dict[str, Any], bot_token: Optional[str] = None) -> bool:
    """
    Telegram Login Widget orqali kelgan ma'lumotlar yaxlitligini
    HMAC-SHA256 algoritmi orqali tekshiradi.

    Talablar (SECURITY.md & Backend.md 3.1):
    1. 'hash' mavjud bo'lishi shart.
    2. 'auth_date' hozirgi vaqtdan 24 soatdan (86400 soniya) eski bo'lmasligi kerak.
    3. Ma'lumotlar alifbo tartibida 'key=value' formatida '\\n' bilan birlashtiriladi.
    4. Xavfsiz hmac.compare_digest orqali taqqoslanadi (Timing Attack'dan himoya).
    """
    token = bot_token or getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        return False

    # Nusxa olamiz, asl ma'lumotni o'zgartirmaslik uchun
    check_data = dict(data)
    received_hash = check_data.pop('hash', None)
    if not received_hash:
        return False

    auth_date = check_data.get('auth_date')
    if not auth_date:
        return False

    try:
        auth_timestamp = int(auth_date)
    except (ValueError, TypeError):
        return False

    # 24 soatlik (86400 soniya) amal qilish muddati
    current_timestamp = int(time.time())
    if current_timestamp - auth_timestamp > 86400 or auth_timestamp > (current_timestamp + 300):
        return False

    # Kalitlarni alifbo bo'yicha saralab, data_check_string tuzish
    data_check_string = "\n".join(
        f"{key}={check_data[key]}"
        for key in sorted(check_data.keys())
    )

    # Secret key: sha256(bot_token)
    secret_key = hashlib.sha256(token.encode('utf-8')).digest()

    # Expected hash: hmac_sha256(secret_key, data_check_string)
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_hash, received_hash)


def exchange_google_code_for_user_info(code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
    """
    Google OAuth 2.0 authorization code'ni access_token'ga almashtiradi
    va foydalanuvchining email hamda profil ma'lumotlarini qabul qiladi.
    """
    client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')
    client_secret = getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', '')

    if not client_id or not client_secret:
        return None

    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }

    try:
        token_resp = requests.post(token_url, data=token_data, timeout=10)
        if token_resp.status_code != 200:
            return None

        tokens = token_resp.json()
        access_token = tokens.get('access_token')
        if not access_token:
            return None

        # Foydalanuvchi ma'lumotlarini olish
        user_info_resp = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={'Authorization': f"Bearer {access_token}"},
            timeout=10
        )
        if user_info_resp.status_code != 200:
            return None

        return user_info_resp.json()
    except requests.RequestException:
        return None
