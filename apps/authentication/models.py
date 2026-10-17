# apps/authentication/models.py
# Backend.md §2.1 va SECURITY.md §4 asosida
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class Organization(models.Model):
    """
    Maktab yoki ta'lim muassasasi tashkilot modeli.
    AI token limiti va obuna rejasini belgilaydi.
    """
    PLAN_CHOICES = (
        ('free', 'Free'),
        ('pro', 'Pro Teacher'),
        ('school', 'School Enterprise'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Tashkilot nomi")
    subscription_plan = models.CharField(max_length=50, choices=PLAN_CHOICES, default='free')
    ai_monthly_token_budget = models.BigIntegerField(default=1_000_000, verbose_name="Oylik AI Token Byudjeti")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tashkilot"
        verbose_name_plural = "Tashkilotlar"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.subscription_plan})"


class User(AbstractUser):
    """
    EduSelf asosiy foydalanuvchi modeli.
    UUID birlamchi kaliti, rollar (RBAC) va ijtimoiy bog'lanishlar bilan jihozlangan.
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
    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default='teacher',
        db_index=True,
        verbose_name="Foydalanuvchi roli"
    )
    telegram_id = models.BigIntegerField(
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Telegram ID"
    )
    preferred_locale = models.CharField(
        max_length=10,
        default='uz-Latn',
        verbose_name="Tanlangan til"
    )
    avatar_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Avatar URL"
    )

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['telegram_id']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        name = self.get_full_name() or self.username
        return f"{name} ({self.get_role_display()})"

    @property
    def is_teacher(self) -> bool:
        return self.role == 'teacher'

    @property
    def is_school_admin(self) -> bool:
        return self.role == 'school_admin'

    @property
    def is_system_admin(self) -> bool:
        return self.role == 'system_admin' or self.is_superuser


class TeacherProfile(models.Model):
    """
    O'qituvchining qo'shimcha kasbiy profili.
    Fani, bio, telefon va shaxsiy sozlamalarini saqlaydi.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_profile',
        verbose_name="Foydalanuvchi"
    )
    subject = models.CharField(max_length=100, blank=True, default='', verbose_name="Dars beradigan fani")
    bio = models.TextField(blank=True, default='', verbose_name="O'zi haqida qisqacha")
    phone_number = models.CharField(max_length=30, blank=True, default='', verbose_name="Telefon raqami")
    settings_json = models.JSONField(default=dict, blank=True, verbose_name="Shaxsiy sozlamalar")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "O‘qituvchi Profili"
        verbose_name_plural = "O‘qituvchilar Profillari"

    def __str__(self):
        return f"Profil: {self.user.username} - {self.subject or 'Fan belgilanmagan'}"
