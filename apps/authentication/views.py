# apps/authentication/views.py
# Backend.md §3, TECH_STACK.md §4 va SECURITY.md §3 asosida
import json
import logging
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .services import (
    check_telegram_hash,
    authenticate_or_create_telegram_user,
    GoogleOAuthService
)

logger = logging.getLogger(__name__)


def serialize_user(user: User) -> dict:
    """Foydalanuvchi ma'lumotlarini xavfsiz JSON ko'rinishiga keltirish."""
    profile_data = {}
    if hasattr(user, 'teacher_profile'):
        profile = user.teacher_profile
        profile_data = {
            'subject': profile.subject,
            'bio': profile.bio,
            'phone_number': profile.phone_number,
        }

    org_data = None
    if user.organization:
        org_data = {
            'id': str(user.organization.id),
            'name': user.organization.name,
            'plan': user.organization.subscription_plan,
        }

    return {
        'id': str(user.id),
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'preferred_locale': user.preferred_locale,
        'avatar_url': user.avatar_url,
        'organization': org_data,
        'teacher_profile': profile_data,
        'is_staff': user.is_staff,
    }


class LoginView(APIView):
    """
    Standart login endpointi (Email yoki Username + Parol).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        login_identifier = data.get('username') or data.get('email', '')
        password = data.get('password', '')

        if not login_identifier or not password:
            return Response(
                {'error': "Username/Email va parol kiritilishi shart."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Email orqali ham kirish imkoniyati
        username = login_identifier
        if '@' in login_identifier:
            matched_user = User.objects.filter(email__iexact=login_identifier).first()
            if matched_user:
                username = matched_user.username

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {'error': "Login yoki parol noto'g'ri."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {'error': "Ushbu akkaunt faol emas."},
                status=status.HTTP_403_FORBIDDEN
            )

        login(request, user)
        return Response({
            'status': 'ok',
            'message': 'Muvaffaqiyatli tizimga kirildi.',
            'user': serialize_user(user),
            'redirect_url': '/dashboard/'
        })


class LogoutView(APIView):
    """
    Sessiyani yakunlash (Logout).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({
            'status': 'ok',
            'message': 'Tizimdan muvaffaqiyatli chiqildi.'
        })


class TelegramAuthCallbackView(APIView):
    """
    Telegram Login Widget callback endpointi.
    Backend.md §3.1: Server-side HMAC-SHA256 tekshiruvi va avtomatik login.
    """
    permission_classes = [AllowAny]

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        # JSON yoki form data qabul qilish
        data = request.data if hasattr(request, 'data') and request.data else request.POST.dict()
        if not data and request.body:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except Exception:
                data = {}

        if not data or 'hash' not in data or 'id' not in data:
            return Response(
                {'error': "Yetarli Telegram ma'lumotlari taqdim etilmadi."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. HMAC-SHA256 tekshiruvi (xavfsizlik!)
        if not check_telegram_hash(dict(data)):
            logger.warning(f"Soxta yoki muddati o'tgan Telegram hash: TG_ID={data.get('id')}")
            return Response(
                {'error': "Soxta yoki muddati o'tgan Telegram ma'lumotlari."},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Foydalanuvchini topish yoki yaratish
        user, created = authenticate_or_create_telegram_user(dict(data))

        # 3. Django sessiyasiga kiritish
        login(request, user)

        return Response({
            'status': 'ok',
            'created': created,
            'message': 'Telegram orqali muvaffaqiyatli kirildi.',
            'user': serialize_user(user),
            'redirect_url': '/dashboard/'
        })


class GoogleAuthCallbackView(APIView):
    """
    Google OAuth 2.0 callback endpointi.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        user_info = request.data.get('user_info')
        if not user_info or not isinstance(user_info, dict):
            return Response(
                {'error': "Google foydalanuvchi ma'lumotlari kiritilmadi."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user, created = GoogleOAuthService.process_google_user_info(user_info)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        login(request, user)
        return Response({
            'status': 'ok',
            'created': created,
            'message': 'Google orqali muvaffaqiyatli kirildi.',
            'user': serialize_user(user),
            'redirect_url': '/dashboard/'
        })


class CurrentUserView(APIView):
    """
    Joriy tizimga kirgan foydalanuvchi ma'lumotlari.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'user': serialize_user(request.user)
        })
