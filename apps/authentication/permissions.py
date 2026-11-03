"""
Role-Based Access Control (RBAC) permissions and view decorators for EduSelf Teacher.
Enforces role separation between Teachers, School Admins, and System Administrators.
"""

from functools import wraps
from django.http import JsonResponse
from rest_framework.permissions import BasePermission


# -----------------------------------------------------------------------------
# Django View Decorators (JSON Response on 401/403)
# -----------------------------------------------------------------------------

def login_required_json(view_func):
    """Ensure the user is authenticated before calling the view."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Autentifikatsiyadan o‘tish talab qilinadi'}, status=401)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def teacher_required(view_func):
    """Enforce that the caller has teacher privileges or is superuser."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Autentifikatsiyadan o‘tish talab qilinadi'}, status=401)
        if not (request.user.is_teacher() or request.user.is_superuser):
            return JsonResponse({'error': 'Ushbu amal uchun o‘qituvchi huquqi talab qilinadi'}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def school_admin_required(view_func):
    """Enforce that the caller has school admin privileges or higher."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Autentifikatsiyadan o‘tish talab qilinadi'}, status=401)
        if not (request.user.is_school_admin() or request.user.is_system_admin() or request.user.is_superuser):
            return JsonResponse({'error': 'Ushbu amal uchun maktab ma’muri huquqi talab qilinadi'}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def system_admin_required(view_func):
    """Enforce that the caller has system admin privileges."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Autentifikatsiyadan o‘tish talab qilinadi'}, status=401)
        if not (request.user.is_system_admin() or request.user.is_superuser):
            return JsonResponse({'error': 'Ushbu amal uchun tizim ma’muri huquqi talab qilinadi'}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# -----------------------------------------------------------------------------
# Django REST Framework Permission Classes
# -----------------------------------------------------------------------------

class IsTeacher(BasePermission):
    """Allows access only to authenticated teachers or superusers."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_teacher() or request.user.is_superuser)
        )


class IsSchoolAdmin(BasePermission):
    """Allows access to school administrators, system administrators, and superusers."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_school_admin() or request.user.is_system_admin() or request.user.is_superuser)
        )


class IsSystemAdmin(BasePermission):
    """Allows access only to system administrators and superusers."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_system_admin() or request.user.is_superuser)
        )
