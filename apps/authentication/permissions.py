from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from rest_framework.permissions import BasePermission, IsAuthenticated


class IsTeacher(BasePermission):
    """
    Faqat 'teacher' roliga ega bo'lgan foydalanuvchilar uchun ruxsat.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'teacher'
        )


class IsSchoolAdmin(BasePermission):
    """
    Faqat 'school_admin' yoki 'system_admin' uchun ruxsat.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'school_admin' or request.user.role == 'system_admin' or request.user.is_superuser)
        )


class IsSystemAdmin(BasePermission):
    """
    Faqat tizim administratori yoki superuser uchun ruxsat.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'system_admin' or request.user.is_superuser)
        )


def teacher_required(view_func):
    """
    Django standart viewlari uchun o'qituvchi rolini tekshiruvchi dekorator.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not getattr(request.user, 'is_teacher', False) and not request.user.is_superuser:
            raise PermissionDenied("Ushbu amalni bajarish uchun o'qituvchi huquqi talab qilinadi.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def school_admin_required(view_func):
    """
    Django standart viewlari uchun maktab ma'muri rolini tekshiruvchi dekorator.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not getattr(request.user, 'is_school_admin', False) and not request.user.is_superuser:
            raise PermissionDenied("Ushbu amalni bajarish uchun maktab ma'muri huquqi talab qilinadi.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def system_admin_required(view_func):
    """
    Django standart viewlari uchun tizim ma'muri rolini tekshiruvchi dekorator.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not getattr(request.user, 'is_system_admin', False) and not request.user.is_superuser:
            raise PermissionDenied("Ushbu amalni bajarish uchun tizim ma'muri huquqi talab qilinadi.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
