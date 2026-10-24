import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class Organization(models.Model):
    """
    Tashkilot (maktab, o'quv markazi) modeli.
    Ko'p ijarachilik (multi-tenancy) va oylik AI token byudjetini boshqaradi.
    """
    SUBSCRIPTION_CHOICES = (
        ("free", "Bepul"),
        ("pro", "Pro"),
        ("school", "Maktab"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Tashkilot nomi")
    subscription_plan = models.CharField(
        max_length=50,
        choices=SUBSCRIPTION_CHOICES,
        default="free",
        verbose_name="Obuna tarifi"
    )
    ai_monthly_token_budget = models.BigIntegerField(
        default=1_000_000,
        verbose_name="Oylik AI token limiti"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tashkilot"
        verbose_name_plural = "Tashkilotlar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    """
    Kengaytirilgan foydalanuvchi modeli.
    UUID birlamchi kalit, RBAC rollari va Telegram / Google autentifikatsiyasi.
    """
    ROLE_CHOICES = (
        ("teacher", "O‘qituvchi"),
        ("school_admin", "Maktab Ma’muri"),
        ("system_admin", "Tizim Administratori"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
        verbose_name="Tashkilot"
    )
    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default="teacher",
        verbose_name="Rol"
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
        default="uz-Latn",
        verbose_name="Afzal ko'rilgan til"
    )
    avatar_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Avatar havolasi"
    )

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["telegram_id"]),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_teacher(self):
        return self.role == "teacher"

    @property
    def is_school_admin(self):
        return self.role in ("school_admin", "system_admin") or self.is_superuser

    @property
    def is_system_admin(self):
        return self.role == "system_admin" or self.is_superuser
