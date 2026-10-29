import json
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import User
from .services import (
    check_telegram_hash,
    get_or_create_telegram_user,
    build_google_auth_url,
    get_or_create_google_user,
)
from .security import AccountLockoutManager, LOCKOUT_THRESHOLD


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def telegram_auth_callback(request):
    """
    Telegram Login Widget callback endpointi.
    HMAC-SHA256 tekshiruvi o'tgach, foydalanuvchini tizimga kiritadi.
    """
    data = {}
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return Response(
                {"error": "Yaroqsiz JSON format"},
                status=status.HTTP_400_BAD_REQUEST
            )
    else:
        data = request.POST.dict()

    if not data:
        return Response(
            {"error": "Ma'lumotlar topilmadi"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Hash va vaqt tamg'asini tekshirish
    is_valid = check_telegram_hash(data.copy())
    if not is_valid:
        return Response(
            {"error": "Soxta yoki muddati o‘tgan Telegram ma’lumotlari"},
            status=status.HTTP_403_FORBIDDEN
        )

    user, created = get_or_create_telegram_user(data)
    login(request, user)

    return Response({
        "status": "ok",
        "created": created,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "role": user.role,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "avatar_url": user.avatar_url,
        },
        "redirect_url": "/dashboard/",
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def google_auth_init(request):
    """
    Google OAuth2 avtorizatsiya oynasiga yo'naltirish URL'ini qaytaradi.
    """
    auth_url = build_google_auth_url()
    return Response({"auth_url": auth_url}, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(["POST", "GET"])
@permission_classes([AllowAny])
def google_auth_callback(request):
    """
    Google OAuth2 callback handler.
    Code yoki test payload orqali emailni qabul qilib, sessiya ochadi.
    """
    data = request.data if request.method == "POST" else request.GET.dict()
    email = data.get("email")
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    avatar_url = data.get("avatar_url", "")

    if not email:
        return Response(
            {"error": "Google email topilmadi"},
            status=status.HTTP_400_BAD_REQUEST
        )

    user, created = get_or_create_google_user(
        email=email,
        first_name=first_name,
        last_name=last_name,
        avatar_url=avatar_url
    )
    login(request, user)

    return Response({
        "status": "ok",
        "created": created,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role,
        },
        "redirect_url": "/dashboard/",
    }, status=status.HTTP_200_OK)


def _is_api_request(request) -> bool:
    """So'rov JSON API mijozi (fetch, curl, pytest) tomonidan yuborilganini aniqlash."""
    if request.content_type == "application/json":
        return True
    accept = request.headers.get("Accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return True
    return False


@csrf_exempt
def login_view(request):
    """
    Standart email/username va parol orqali tizimga kirish.
    Brauzer uchun chiroyli EduPlay HTML interfeysini taqdim etadi.
    API mijozlari uchun esa JSON formatida javob qaytaradi.
    """
    # 1. Foydalanuvchi allaqachon tizimga kirgan bo'lsa va sahifani ochsa
    if request.user.is_authenticated and request.method == "GET":
        return redirect("/dashboard/")

    # 2. GET so'rovi: HTML formani to'g'ridan-to'g'ri render qilish
    if request.method == "GET":
        return render(request, "auth/login.html")

    # 3. POST so'rovi: Ma'lumotlarni o'qish (JSON yoki Form-data)
    is_api = _is_api_request(request)
    username = ""
    password = ""

    if request.content_type == "application/json" and request.body:
        try:
            body_data = json.loads(request.body)
            username = body_data.get("username", "").strip()
            password = body_data.get("password", "")
        except json.JSONDecodeError:
            if is_api:
                return JsonResponse({"error": "Yaroqsiz JSON format"}, status=400)
            return render(request, "auth/login.html", {"error": "Yaroqsiz so'rov formati"}, status=400)
    else:
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

    if not username or not password:
        err_msg = "Foydalanuvchi nomi va parol kiritilishi shart."
        if is_api:
            return JsonResponse({"error": err_msg}, status=400)
        return render(request, "auth/login.html", {"error": err_msg, "username": username}, status=400)

    client_ip = (
        request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        or request.META.get("REMOTE_ADDR", "127.0.0.1")
    )

    # 4. Brute-force blokirovkasini tekshirish
    is_locked, remaining = AccountLockoutManager.is_locked(username, client_ip)
    if is_locked:
        err_msg = f"Ko'p marta xato urinishlar tufayli hisob vaqtincha bloklandi. Qolgan vaqt: {remaining} soniya."
        if is_api:
            resp = JsonResponse({"error": err_msg, "retry_after": remaining}, status=429)
        else:
            resp = render(request, "auth/login.html", {"error": err_msg, "username": username}, status=429)
        resp["Retry-After"] = str(remaining)
        return resp

    # 5. Autentifikatsiya
    user = authenticate(request, username=username, password=password)
    if user is None:
        user_by_email = User.objects.filter(email__iexact=username).first()
        if user_by_email:
            user = authenticate(request, username=user_by_email.username, password=password)

    if user is not None:
        if not user.is_active:
            err_msg = "Foydalanuvchi hisobi faol emas."
            if is_api:
                return JsonResponse({"error": err_msg}, status=403)
            return render(request, "auth/login.html", {"error": err_msg, "username": username}, status=403)

        AccountLockoutManager.reset_attempts(username, client_ip)
        login(request, user)

        if is_api:
            return JsonResponse({
                "status": "ok",
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                },
            }, status=200)

        # Brauzer foydalanuvchisini to'g'ridan-to'g'ri Dashboard'ga yo'naltirish
        return redirect("/dashboard/")

    # 6. Muvaffaqiyatsiz urinishni qayd etish
    fails = AccountLockoutManager.record_failed_attempt(username, client_ip)
    if fails >= LOCKOUT_THRESHOLD:
        err_msg = "Ko'p marta xato urinishlar tufayli hisob va IP vaqtincha bloklandi."
        if is_api:
            resp = JsonResponse({"error": err_msg, "retry_after": 900}, status=429)
        else:
            resp = render(request, "auth/login.html", {"error": err_msg, "username": username}, status=429)
        resp["Retry-After"] = "900"
        return resp

    err_msg = "Noto'g'ri foydalanuvchi nomi yoki parol."
    if is_api:
        return JsonResponse({"error": err_msg}, status=401)
    return render(request, "auth/login.html", {"error": err_msg, "username": username}, status=401)


@csrf_exempt
def register_view(request):
    """
    Yangi o'qituvchi / foydalanuvchini ro'yxatdan o'tkazish sahifasi.
    Login va parol yaratadi, avtomatik tizimga kiritadi va Dashboard'ga yo'naltiradi.
    """
    if request.user.is_authenticated and request.method == "GET":
        return redirect("/dashboard/")

    if request.method == "GET":
        return render(request, "auth/register.html")

    is_api = _is_api_request(request)
    data = {}
    if request.content_type == "application/json" and request.body:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            if is_api:
                return JsonResponse({"error": "Yaroqsiz JSON format"}, status=400)
            return render(request, "auth/register.html", {"error": "Yaroqsiz so'rov formati"}, status=400)
    else:
        data = request.POST.dict()

    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    first_name = data.get("first_name", "").strip()
    password = data.get("password", "")
    password_confirm = data.get("password_confirm", "")

    # 1. Maydonlarni tekshirish
    if not username or not password:
        err = "Login va parol kiritilishi shart."
        if is_api:
            return JsonResponse({"error": err}, status=400)
        return render(request, "auth/register.html", {"error": err, "data": data}, status=400)

    if len(username) < 3:
        err = "Login kamida 3 ta belgidan iborat bo'lishi kerak."
        if is_api:
            return JsonResponse({"error": err}, status=400)
        return render(request, "auth/register.html", {"error": err, "data": data}, status=400)

    if len(password) < 6:
        err = "Parol kamida 6 ta belgidan iborat bo'lishi kerak."
        if is_api:
            return JsonResponse({"error": err}, status=400)
        return render(request, "auth/register.html", {"error": err, "data": data}, status=400)

    if password_confirm and password != password_confirm:
        err = "Kiritilgan parollar bir-biriga mos kelmadi."
        if is_api:
            return JsonResponse({"error": err}, status=400)
        return render(request, "auth/register.html", {"error": err, "data": data}, status=400)

    # 2. Mavjudligini tekshirish
    if User.objects.filter(username__iexact=username).exists():
        err = f"'{username}' nomli login band. Iltimos, boshqa login tanlang."
        if is_api:
            return JsonResponse({"error": err}, status=400)
        return render(request, "auth/register.html", {"error": err, "data": data}, status=400)

    if email and User.objects.filter(email__iexact=email).exists():
        err = f"'{email}' elektron pochtasi allaqachon ro'yxatdan o'tgan."
        if is_api:
            return JsonResponse({"error": err}, status=400)
        return render(request, "auth/register.html", {"error": err, "data": data}, status=400)

    # 3. Yangi foydalanuvchi yaratish
    user = User.objects.create_user(
        username=username,
        email=email or f"{username}@eduself.uz",
        first_name=first_name,
        password=password,
        role="teacher",
        is_active=True
    )

    # 4. Tizimga avtomatik kiritish va yo'naltirish
    login(request, user)

    if is_api:
        return JsonResponse({
            "status": "ok",
            "message": "Muvaffaqiyatli ro'yxatdan o'tildi",
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
            "redirect_url": "/dashboard/"
        }, status=201)

    return redirect("/dashboard/")


@csrf_exempt
def logout_view(request):
    """
    Sessiyani yakunlash (Logout).
    Brauzerda login oynasiga yo'naltiradi, API uchun JSON qaytaradi.
    """
    logout(request)
    if _is_api_request(request):
        return JsonResponse({"status": "ok", "message": "Muvaffaqiyatli chiqildi"}, status=200)
    return redirect("/auth/login/")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    """
    Joriy tizimga kirgan foydalanuvchi ma'lumotlarini olish.
    """
    user = request.user
    org_data = None
    if user.organization:
        org_data = {
            "id": str(user.organization.id),
            "name": user.organization.name,
            "subscription_plan": user.organization.subscription_plan,
        }

    return Response({
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "telegram_id": user.telegram_id,
        "preferred_locale": user.preferred_locale,
        "avatar_url": user.avatar_url,
        "organization": org_data,
    }, status=status.HTTP_200_OK)
