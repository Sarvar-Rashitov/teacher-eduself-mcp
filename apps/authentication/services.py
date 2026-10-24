import hmac
import hashlib
import time
import urllib.parse
from django.conf import settings
from .models import User


def check_telegram_hash(data: dict, bot_token: str = None) -> bool:
    """
    Telegram Login Widget orqali kelgan ma'lumotlarni HMAC-SHA256 orqali tekshirish.
    24 soatlik (86400 soniya) eskirish vaqtini ham tekshiradi.
    """
    token = bot_token or getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    if not token:
        return False

    received_hash = data.get("hash")
    if not received_hash:
        return False

    # auth_date tekshiruvi (24 soatlik muddat)
    auth_date = data.get("auth_date")
    if not auth_date:
        return False

    try:
        auth_timestamp = int(auth_date)
        if time.time() - auth_timestamp > 86400:
            return False
    except (ValueError, TypeError):
        return False

    # 'hash' kalitini ajratib olib, qolganlarini alifbo tartibida saralash
    check_dict = {k: v for k, v in data.items() if k != "hash"}
    data_check_string = "\n".join([f"{k}={v}" for k, v in sorted(check_dict.items())])

    # Maxfiy kalit = SHA256(bot_token)
    secret_key = hashlib.sha256(token.encode("utf-8")).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_hash, received_hash)


def get_or_create_telegram_user(data: dict) -> tuple[User, bool]:
    """
    Tekshirilgan Telegram ma'lumotlari asosida User obyektini topish yoki yaratish.
    """
    tg_id = int(data["id"])
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    username = data.get("username")
    photo_url = data.get("photo_url", "")

    # Agar username berilmagan bo'lsa yoki band bo'lsa
    base_username = username if username else f"tg_user_{tg_id}"

    user = User.objects.filter(telegram_id=tg_id).first()
    if user:
        # Mavjud foydalanuvchi ma'lumotlarini yangilash
        updated = False
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            updated = True
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            updated = True
        if photo_url and user.avatar_url != photo_url:
            user.avatar_url = photo_url
            updated = True
        if updated:
            user.save()
        return user, False

    # Yangi foydalanuvchi yaratish
    # Username takrorlanmasligini tekshirish
    candidate_username = base_username
    counter = 1
    while User.objects.filter(username=candidate_username).exists():
        candidate_username = f"{base_username}_{counter}"
        counter += 1

    user = User.objects.create(
        username=candidate_username,
        first_name=first_name,
        last_name=last_name,
        telegram_id=tg_id,
        avatar_url=photo_url,
        role="teacher",
    )
    user.set_unusable_password()
    user.save()
    return user, True


def build_google_auth_url(redirect_uri: str = None, state: str = "eduself_oauth") -> str:
    """
    Google OAuth2 avtorizatsiya havolasini shakllantirish.
    """
    client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
    uri = redirect_uri or getattr(settings, "GOOGLE_REDIRECT_URI", "")
    params = {
        "client_id": client_id,
        "redirect_uri": uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "state": state,
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"


def get_or_create_google_user(email: str, first_name: str = "", last_name: str = "", avatar_url: str = "") -> tuple[User, bool]:
    """
    Google OAuth orqali tasdiqlangan email bo'yicha User topish yoki yaratish.
    """
    if not email:
        raise ValueError("Email kiritilishi shart.")

    user = User.objects.filter(email__iexact=email).first()
    if user:
        if avatar_url and not user.avatar_url:
            user.avatar_url = avatar_url
            user.save(update_fields=["avatar_url"])
        return user, False

    # Username generatsiyasi
    base_username = email.split("@")[0]
    candidate_username = base_username
    counter = 1
    while User.objects.filter(username=candidate_username).exists():
        candidate_username = f"{base_username}_{counter}"
        counter += 1

    user = User.objects.create(
        username=candidate_username,
        email=email.lower(),
        first_name=first_name,
        last_name=last_name,
        avatar_url=avatar_url,
        role="teacher",
    )
    user.set_unusable_password()
    user.save()
    return user, True
