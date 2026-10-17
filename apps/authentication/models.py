import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class Organization(models.Model):
    """
    Organization (maktab, o'quv markazi) modeli.
    O'qituvchilar tashkilot a'zosi bo'lishi va tashkilotning
    oylik umumiy AI token kvotasidan foydalanishi mumkin.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Tashkilot nomi")
    subscription_plan = models.CharField(max_length=50, default='free')  # free, pro, school
    ai_monthly_token_budget = models.BigIntegerField(default=1_000_000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tashkilot"
        verbose_name_plural = "Tashkilotlar"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class User(AbstractUser):
    """
    EduSelf asosiy foydalanuvchi modeli.
    UUID birlamchi kalit, RBAC rollari va Telegram integratsiyasi bilan jihozlangan.
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
        related_name='members'
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='teacher')
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True, db_index=True)
    preferred_locale = models.CharField(max_length=10, default='uz-Latn')
    avatar_url = models.URLField(max_length=500, blank=True, null=True)

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['telegram_id']),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

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
    O'qituvchining qo'shimcha kasbiy profili (fani, bio, aloqa).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_profile'
    )
    subject = models.CharField(max_length=100, blank=True, default='')
    bio = models.TextField(blank=True, default='')
    phone_number = models.CharField(max_length=30, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "O'qituvchi profili"
        verbose_name_plural = "O'qituvchilar profillari"

    def __str__(self):
        return f"{self.user.username} profili ({self.subject or 'Fan kiritilmagan'})"
