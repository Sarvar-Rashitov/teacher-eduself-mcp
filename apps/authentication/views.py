"""
Authentication HTTP views for EduSelf Teacher.
Handles Telegram Login Widget callback, Google OAuth login, standard credentials, and profile retrieval.
"""

import json
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .services import check_telegram_hash, authenticate_telegram_user, authenticate_google_user
from .permissions import login_required_json


@csrf_exempt
@require_http_methods(["POST", "GET"])
def telegram_auth_callback(request: HttpRequest) -> HttpResponse:
    """
    Callback endpoint for Telegram Login Widget.
    Validates HMAC-SHA256 signature and authenticates or registers the teacher.
    """
    if request.method == 'POST':
        # Check both form-encoded and JSON body
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body.decode('utf-8'))
            except Exception:
                return JsonResponse({'error': 'Noto‘g‘ri JSON formati'}, status=400)
        else:
            data = request.POST.dict()
    else:
        data = request.GET.dict()

    if not data or 'hash' not in data:
        return JsonResponse({'error': 'Telegram ma’lumotlari yoki hash topilmadi'}, status=400)

    # Validate HMAC signature
    if not check_telegram_hash(data.copy()):
        return JsonResponse(
            {'error': 'Soxta yoki muddati o‘tgan Telegram ma’lumotlari'},
            status=403
        )

    user, created = authenticate_telegram_user(data)
    login(request, user)

    return JsonResponse({
        'status': 'ok',
        'created': created,
        'user': {
            'id': str(user.id),
            'username': user.username,
            'first_name': user.first_name,
            'role': user.role,
        },
        'redirect_url': '/dashboard/'
    })


@csrf_exempt
@require_http_methods(["POST"])
def google_auth_callback(request: HttpRequest) -> HttpResponse:
    """
    Callback endpoint for Google OAuth token / userinfo exchange.
    Creates or updates the teacher and establishes the session.
    """
    try:
        if request.content_type == 'application/json':
            payload = json.loads(request.body.decode('utf-8'))
        else:
            payload = request.POST.dict()
    except Exception:
        return JsonResponse({'error': 'Noto‘g‘ri JSON formati'}, status=400)

    email = payload.get('email')
    if not email:
        return JsonResponse({'error': 'Email manzili kiritilmadi'}, status=400)

    try:
        user, created = authenticate_google_user(payload)
        login(request, user)
        return JsonResponse({
            'status': 'ok',
            'created': created,
            'user': {
                'id': str(user.id),
                'email': user.email,
                'first_name': user.first_name,
                'role': user.role,
            },
            'redirect_url': '/dashboard/'
        })
    except Exception as exc:
        return JsonResponse({'error': f'Google autentifikatsiyasida xatolik: {str(exc)}'}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    """
    Standard email / username and password login endpoint.
    """
    try:
        if request.content_type == 'application/json':
            body = json.loads(request.body.decode('utf-8'))
        else:
            body = request.POST.dict()
    except Exception:
        return JsonResponse({'error': 'Noto‘g‘ri JSON formati'}, status=400)

    username = body.get('username') or body.get('email')
    password = body.get('password')

    if not username or not password:
        return JsonResponse({'error': 'Login va parol kiritilishi shart'}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({'error': 'Login yoki parol noto‘g‘ri'}, status=401)

    if not user.is_active:
        return JsonResponse({'error': 'Foydalanuvchi hisobi faol emas'}, status=403)

    login(request, user)
    return JsonResponse({
        'status': 'ok',
        'user': {
            'id': str(user.id),
            'username': user.username,
            'role': user.role,
        },
        'redirect_url': '/dashboard/'
    })


@require_http_methods(["POST", "GET"])
def logout_view(request: HttpRequest) -> HttpResponse:
    """
    Terminates the current authenticated session.
    """
    logout(request)
    return JsonResponse({'status': 'ok', 'message': 'Muvaffaqiyatli chiqildi'})


@login_required_json
@require_http_methods(["GET"])
def me_view(request: HttpRequest) -> HttpResponse:
    """
    Returns full details of the currently authenticated teacher / administrator.
    """
    user = request.user
    org = user.organization

    profile_data = None
    if hasattr(user, 'teacher_profile'):
        tp = user.teacher_profile
        profile_data = {
            'subject_specialization': tp.subject_specialization,
            'default_grade': tp.default_grade,
            'school_name': tp.school_name,
            'bio': tp.bio,
        }

    return JsonResponse({
        'status': 'ok',
        'user': {
            'id': str(user.id),
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'preferred_locale': user.preferred_locale,
            'avatar_url': user.avatar_url,
            'telegram_id': user.telegram_id,
            'organization': {
                'id': str(org.id),
                'name': org.name,
                'subscription_plan': org.subscription_plan,
                'ai_monthly_token_budget': org.ai_monthly_token_budget,
            } if org else None,
            'teacher_profile': profile_data,
        }
    })
