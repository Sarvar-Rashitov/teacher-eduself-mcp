# apps/authentication/services.py
# Backend.md §3, TECH_STACK.md §4.2 va SECURITY.md §3 asosida
import hashlib
import hmac
import logging
import time
from typing import Optional, Tuple
from django.conf import settings
from django.db import transaction
from .models import User, TeacherProfile

logger = logging.getLogger(__name__)


def check_telegram_hash(data: dict, bot_token: Optional[str] = None) -> bool:
    """
    Telegram Login Widget orqali kelgan ma'lumotlarning haqiqiyligini tekshirish.
    TECH_STACK.md §4.2 va Backend.md §3.1 talabi:
    1. 'hash' maydoni ajratiladi
    2. 'auth_date' 24 soatdan (86400 s) oshmaganligi tekshiriladi
    3. Alfavit bo'yicha saralangan k=v satrlari newline bilan birlashtiriladi
    4. SHA256(bot_token) maxfiy kalit sifatida olinadi
    5. HMAC-SHA256 hesh hisoblanadi va hmac.compare_digest bilan tekshiriladi
    """
    token = bot_token or getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN sozlanmagan!")
        return False

    received_hash = data.get('hash')
    if not received_hash:
        return False

    # auth_date tekshiruvi (24 soatlik muddat)
    try:
        auth_date = int(data.get('auth_date', 0))
    except (TypeError, ValueError):
        return False

    current_time = int(time.time())
    if current_time - auth_date > 86400 or auth_date > current_time + 300:
        logger.warning(f"Telegram auth_date muddati o'tgan yoki noto'g'ri: {auth_date}")
        return False

    # 'hash' dan tashqari barcha ma'lumotlarni alfavit tartibida saralash
    data_check_arr = [
        f"{k}={v}"
        for k, v in sorted(data.items())
        if k != 'hash' and v is not None
    ]
    data_check_string = "\n".join(data_check_arr)

    # SHA256(bot_token) maxfiy kaliti
    secret_key = hashlib.sha256(token.encode('utf-8')).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(calculated_hash, received_hash)


@transaction.atomic
def authenticate_or_create_telegram_user(data: dict) -> Tuple[User, bool]:
    """
    Tasdiqlangan Telegram ma'lumotlari bo'yicha foydalanuvchini topish yoki yaratish.
    """
    tg_id = int(data['id'])
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    username = data.get('username') or f"tg_user_{tg_id}"
    photo_url = data.get('photo_url')

    # 1. Telegram ID bo'yicha qidiramiz
    user = User.objects.filter(telegram_id=tg_id).first()
    created = False

    if not user:
        # Username band bo'lsa unikal username hosil qilamiz
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            telegram_id=tg_id,
            role='teacher',
            avatar_url=photo_url or ''
        )
        created = True
        logger.info(f"Yangi Telegram foydalanuvchi yaratildi: {user.username} (TG: {tg_id})")
    else:
        # Profilni yangilash
        updated_fields = []
        if photo_url and user.avatar_url != photo_url:
            user.avatar_url = photo_url
            updated_fields.append('avatar_url')
        if first_name and not user.first_name:
            user.first_name = first_name
            updated_fields.append('first_name')
        if updated_fields:
            user.save(update_fields=updated_fields)

    # TeacherProfile mavjudligini ta'minlash
    TeacherProfile.objects.get_or_create(user=user)

    return user, created


class GoogleOAuthService:
    """
    Google OAuth 2.0 bilan ishlash servisi.
    Token verifikatsiyasi va foydalanuvchini tizimga ulash.
    """

    @staticmethod
    def process_google_user_info(user_info: dict) -> Tuple[User, bool]:
        """
        Google dan kelgan verified email va profil ma'lumotlari asosida
        User modelini topish yoki yaratish.
        SECURITY.md §3.2: email_verified=True bo'lishi shart!
        """
        email = user_info.get('email')
        email_verified = user_info.get('email_verified', False)

        if not email or not email_verified:
            raise ValueError("Faqat tasdiqlangan (verified) Google email hisoblari qabul qilinadi.")

        first_name = user_info.get('given_name', '')
        last_name = user_info.get('family_name', '')
        picture = user_info.get('picture', '')

        user = User.objects.filter(email__iexact=email).first()
        created = False

        if not user:
            # Yangi foydalanuvchi
            base_username = email.split('@')[0]
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                email=email.lower(),
                first_name=first_name,
                last_name=last_name,
                role='teacher',
                avatar_url=picture
            )
            created = True
            logger.info(f"Yangi Google OAuth foydalanuvchi yaratildi: {user.username} ({email})")
        else:
            # Mavjud foydalanuvchi profilini yangilash
            updated_fields = []
            if picture and not user.avatar_url:
                user.avatar_url = picture
                updated_fields.append('avatar_url')
            if first_name and not user.first_name:
                user.first_name = first_name
                updated_fields.append('first_name')
            if last_name and not user.last_name:
                user.last_name = last_name
                updated_fields.append('last_name')
            if updated_fields:
                user.save(update_fields=updated_fields)

        # TeacherProfile mavjudligini ta'minlash
        TeacherProfile.objects.get_or_create(user=user)

        return user, created
