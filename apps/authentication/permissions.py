from rest_framework.permissions import BasePermission


class IsTeacher(BasePermission):
    """
    Ruxsat filtri: Faqat tizimga kirgan va roli 'teacher' bo'lgan foydalanuvchilar.
    """
    message = "Ushbu amalni faqat o'qituvchilar bajara oladi."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == "teacher" or request.user.is_superuser)
        )


class IsSchoolAdmin(BasePermission):
    """
    Ruxsat filtri: Faqat maktab ma'muri yoki tizim administratori.
    """
    message = "Ushbu amalni faqat maktab ma'murlari bajara oladi."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role in ("school_admin", "system_admin") or request.user.is_superuser)
        )


class IsSystemAdmin(BasePermission):
    """
    Ruxsat filtri: Faqat tizim bosh ma'muri (superadmin).
    """
    message = "Ushbu amal faqat tizim administratori uchun ruxsat etilgan."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == "system_admin" or request.user.is_superuser)
        )
