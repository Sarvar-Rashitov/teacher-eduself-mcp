import json
from urllib.parse import urlencode
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import User, TeacherProfile
from .services import check_telegram_hash, exchange_google_code_for_user_info


@csrf_exempt
@require_http_methods(["POST"])
def telegram_auth_callback(request):
    """
    Telegram Login Widget orqali kelgan ma'lumotlarni qabul qilish va autentifikatsiya.
    HMAC-SHA256 tekshiruvi xavfsiz o'tgach, foydalanuvchini tizimga kiritadi.
    """
    # JSON yoki form-data formatini qabul qilish
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'error': 'Noto\'g\'ri JSON formati'}, status=400)
    else:
        data = request.POST.dict()

    if not data:
        return JsonResponse({'error': 'Ma\'lumotlar topilmadi'}, status=400)

    # Telegram HMAC-SHA256 tekshiruvi
    if not check_telegram_hash(data.copy()):
        return JsonResponse(
            {'error': 'Soxta yoki muddati o\'tgan Telegram ma\'lumotlari'},
            status=403
        )

    try:
        tg_id = int(data['id'])
    except (KeyError, ValueError, TypeError):
        return JsonResponse({'error': 'Telegram ID noto\'g\'ri'}, status=400)

    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    username = data.get('username') or f"tg_user_{tg_id}"
    photo_url = data.get('photo_url')

    # Foydalanuvchini topish yoki yangi yaratish
    user = User.objects.filter(telegram_id=tg_id).first()
    if not user:
        # Username band bo'lsa, unikal nom hosil qilish
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        user = User.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            telegram_id=tg_id,
            role='teacher',
            avatar_url=photo_url or '',
            preferred_locale='uz-Latn'
        )
        # O'qituvchi profilini yaratish
        TeacherProfile.objects.get_or_create(user=user)
    else:
        # Profilni yangilash
        updated = False
        if photo_url and user.avatar_url != photo_url:
            user.avatar_url = photo_url
            updated = True
        if first_name and not user.first_name:
            user.first_name = first_name
            updated = True
        if updated:
            user.save(update_fields=['avatar_url', 'first_name'])

    # Django sessiyasini ochish
    login(request, user)

    return JsonResponse({
        'status': 'ok',
        'message': 'Muvaffaqiyatli autentifikatsiya',
        'user': {
            'id': str(user.id),
            'username': user.username,
            'role': user.role,
            'first_name': user.first_name,
            'telegram_id': user.telegram_id,
        },
        'redirect_url': '/dashboard/'
    })


@require_http_methods(["GET"])
def google_auth_redirect(request):
    """
    O'qituvchini Google OAuth 2.0 rozilik (consent) sahifasiga yo'naltirish.
    """
    client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')
    if not client_id:
        return JsonResponse({'error': 'Google OAuth sozlanmagan'}, status=503)

    redirect_uri = request.build_absolute_uri('/auth/google/callback/')
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'online',
        'prompt': 'select_account',
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return HttpResponseRedirect(url)


@require_http_methods(["GET"])
def google_auth_callback(request):
    """
    Google dan qaytgan avtorizatsiya kodini tekshirib, foydalanuvchini kiritish.
    """
    code = request.GET.get('code')
    if not code:
        return JsonResponse({'error': 'Avtorizatsiya kodi mavjud emas'}, status=400)

    redirect_uri = request.build_absolute_uri('/auth/google/callback/')
    user_info = exchange_google_code_for_user_info(code, redirect_uri)

    if not user_info or not user_info.get('email'):
        return JsonResponse({'error': 'Google hisob ma\'lumotlarini tasdiqlab bo\'lmadi'}, status=400)

    email = user_info['email']
    first_name = user_info.get('given_name', '')
    last_name = user_info.get('family_name', '')
    avatar_url = user_info.get('picture', '')

    user = User.objects.filter(email=email).first()
    if not user:
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='teacher',
            avatar_url=avatar_url,
            preferred_locale='uz-Latn'
        )
        TeacherProfile.objects.get_or_create(user=user)

    login(request, user)
    return HttpResponseRedirect('/dashboard/')


@csrf_exempt
@require_http_methods(["POST"])
def login_view(request):
    """
    Standart email/username va parol orqali sessiyali kirish.
    """
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'error': 'Noto\'g\'ri JSON formati'}, status=400)
    else:
        data = request.POST.dict()

    identifier = data.get('username') or data.get('email')
    password = data.get('password')

    if not identifier or not password:
        return JsonResponse({'error': 'Foydalanuvchi nomi/email va parol kiritilishi shart'}, status=400)

    # Agar email kiritilgan bo'lsa, unga mos username'ni aniqlaymiz
    user = None
    if '@' in identifier:
        user_by_email = User.objects.filter(email=identifier).first()
        if user_by_email:
            user = authenticate(request, username=user_by_email.username, password=password)
    else:
        user = authenticate(request, username=identifier, password=password)

    if user is None:
        return JsonResponse({'error': 'Foydalanuvchi nomi yoki parol xato'}, status=401)

    if not user.is_active:
        return JsonResponse({'error': 'Foydalanuvchi hisobi faol emas'}, status=403)

    login(request, user)
    return JsonResponse({
        'status': 'ok',
        'message': 'Muvaffaqiyatli kirildi',
        'user': {
            'id': str(user.id),
            'username': user.username,
            'email': user.email,
            'role': user.role,
        }
    })


@require_http_methods(["POST", "GET"])
def logout_view(request):
    """
    Sessiyadan chiqish (Logout).
    """
    logout(request)
    return JsonResponse({'status': 'ok', 'message': 'Muvaffaqiyatli chiqildi'})


@require_http_methods(["GET"])
def me_view(request):
    """
    Joriy tizimga kirgan foydalanuvchi ma'lumotlarini qaytarish.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Autentifikatsiyadan o\'tilmagan'}, status=401)

    user = request.user
    org_data = None
    if user.organization:
        org_data = {
            'id': str(user.organization.id),
            'name': user.organization.name,
            'subscription_plan': user.organization.subscription_plan,
        }

    return JsonResponse({
        'id': str(user.id),
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'telegram_id': user.telegram_id,
        'preferred_locale': user.preferred_locale,
        'avatar_url': user.avatar_url,
        'organization': org_data,
    })
