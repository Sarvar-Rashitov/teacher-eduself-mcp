# apps/authentication/permissions.py
# SECURITY.md §4 va Backend.md §1.1 asosida RBAC huquqlar filtri
from rest_framework import permissions


class IsTeacher(permissions.BasePermission):
    """
    Faqat 'teacher' roli yoki tizim admini bo'lgan foydalanuvchilarga ruxsat beradi.
    """
    message = "Ushbu amalni bajarish uchun o'qituvchi huquqi talab qilinadi."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'teacher' or request.user.role == 'system_admin' or request.user.is_superuser)
        )


class IsSchoolAdmin(permissions.BasePermission):
    """
    Faqat 'school_admin' yoki tizim admini bo'lgan foydalanuvchilarga ruxsat beradi.
    """
    message = "Ushbu amalni bajarish uchun maktab administratori huquqi talab qilinadi."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'school_admin' or request.user.role == 'system_admin' or request.user.is_superuser)
        )


class IsSystemAdmin(permissions.BasePermission):
    """
    Faqat platforma administratorlariga ruxsat beradi.
    """
    message = "Ushbu amalni bajarish uchun tizim administratori huquqi talab qilinadi."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'system_admin' or request.user.is_superuser)
        )


class HasRole(permissions.BasePermission):
    """
    Ko'p rollarni tekshiruvchi umumiy permission klassi.
    Ishlatilishi: permission_classes = [HasRole.with_roles('teacher', 'school_admin')]
    """
    allowed_roles = ()

    @classmethod
    def with_roles(cls, *roles):
        class RolePermission(cls):
            allowed_roles = roles
        return RolePermission

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_superuser or request.user.role == 'system_admin':
            return True
        return request.user.role in self.allowed_roles


class IsSelfOrAdmin(permissions.BasePermission):
    """
    Foydalanuvchi faqat o'z profilini ko'rish/tahrirlash huquqiga ega (yoki Admin).
    """
    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_superuser or request.user.role == 'system_admin':
            return True
        # obj User yoki TeacherProfile bo'lishi mumkin
        target_user = obj if hasattr(obj, 'username') else getattr(obj, 'user', None)
        return target_user == request.user
