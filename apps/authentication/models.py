"""
Authentication and User models for EduSelf Teacher.
Defines Organization, User (AbstractUser with UUID and RBAC), and TeacherProfile.
"""

import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class Organization(models.Model):
    """
    Organization (School, Lyceum, Learning Center) entity.
    Tracks membership, subscription tier and AI monthly token quotas.
    """
    PLAN_CHOICES = (
        ('free', 'Bepul'),
        ('pro', 'Professional'),
        ('school', 'Maktab Litsenziyasi'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Tashkilot nomi")
    subscription_plan = models.CharField(max_length=50, choices=PLAN_CHOICES, default='free')
    ai_monthly_token_budget = models.BigIntegerField(default=1_000_000, verbose_name="Oylik AI token byudjeti")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")

    class Meta:
        verbose_name = "Tashkilot"
        verbose_name_plural = "Tashkilotlar"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class User(AbstractUser):
    """
    Primary user model extending Django's AbstractUser.
    Uses UUID primary key, RBAC role choices, and supports Telegram / Google single sign-on.
    """
    ROLE_CHOICES = (
        ('teacher', 'O‘qituvchi'),
        ('school_admin', 'Maktab Ma’muri'),
        ('system_admin', 'Tizim Administratori'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        verbose_name="Tashkilot"
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='teacher', verbose_name="Foydalanuvchi roli")
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True, db_index=True, verbose_name="Telegram ID")
    preferred_locale = models.CharField(max_length=10, default='uz-Latn', verbose_name="Tanlangan til")
    avatar_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Avatar havolasi")

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['telegram_id']),
        ]

    def is_teacher(self) -> bool:
        """Check if user has teacher role."""
        return self.role == 'teacher'

    def is_school_admin(self) -> bool:
        """Check if user has school admin role."""
        return self.role == 'school_admin'

    def is_system_admin(self) -> bool:
        """Check if user has system administrator role or is superuser."""
        return self.role == 'system_admin' or self.is_superuser


class TeacherProfile(models.Model):
    """
    Additional pedagogical profile information for teachers.
    Linked 1-to-1 with User model.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_profile',
        verbose_name="Foydalanuvchi"
    )
    subject_specialization = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Fan mutaxassisligi"
    )
    default_grade = models.IntegerField(default=7, verbose_name="Asosiy sinf darajasi")
    school_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Maktab nomi")
    bio = models.TextField(blank=True, null=True, verbose_name="O'qituvchi haqida")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan sana")

    class Meta:
        verbose_name = "O‘qituvchi Profili"
        verbose_name_plural = "O‘qituvchi Profillari"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} profili"
